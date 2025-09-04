using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Core.Configuration;
using RevitPy.Core.Exceptions;
using System.Collections.Concurrent;
using System.Diagnostics;

namespace RevitPy.Runtime;

/// <summary>
/// Implementation of IPythonInterpreterPool that manages a pool of Python interpreters
/// </summary>
public class PythonInterpreterPool : IPythonInterpreterPool
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<PythonInterpreterPool> _logger;
    private readonly RevitPyOptions _options;
    private readonly ConcurrentQueue<IPythonInterpreter> _availableInterpreters = new();
    private readonly ConcurrentDictionary<string, IPythonInterpreter> _allInterpreters = new();
    private readonly ConcurrentDictionary<string, RentedInterpreter> _rentedInterpreters = new();
    private readonly SemaphoreSlim _semaphore;
    private readonly Timer _healthCheckTimer;
    private readonly Timer _cleanupTimer;

    private bool _isInitialized;
    private bool _isDisposed;
    private DateTime _createdAt;
    private DateTime? _lastResetAt;
    private PythonInterpreterPoolStats _stats = new();

    public int AvailableCount => _availableInterpreters.Count;
    public int BusyCount => _rentedInterpreters.Count;
    public int TotalCount => _allInterpreters.Count;

    public PythonInterpreterPool(
        IServiceProvider serviceProvider,
        ILogger<PythonInterpreterPool> logger,
        IOptions<RevitPyOptions> options)
    {
        _serviceProvider = serviceProvider ?? throw new ArgumentNullException(nameof(serviceProvider));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        
        _semaphore = new SemaphoreSlim(_options.MaxInterpreters, _options.MaxInterpreters);
        _createdAt = DateTime.UtcNow;

        // Set up periodic health checks
        _healthCheckTimer = new Timer(async _ => await PerformHealthCheckAsync(), 
            null, TimeSpan.FromMinutes(5), TimeSpan.FromMinutes(5));

        // Set up periodic cleanup
        _cleanupTimer = new Timer(async _ => await PerformCleanupAsync(),
            null, TimeSpan.FromMinutes(10), TimeSpan.FromMinutes(10));
    }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        if (_isInitialized)
            return;

        _logger.LogInformation("Initializing Python interpreter pool with max size {MaxInterpreters}", 
            _options.MaxInterpreters);

        try
        {
            // Pre-create initial interpreters (start with 2)
            var initialCount = Math.Min(2, _options.MaxInterpreters);
            var tasks = new List<Task>();

            for (int i = 0; i < initialCount; i++)
            {
                tasks.Add(CreateInterpreterAsync(cancellationToken));
            }

            await Task.WhenAll(tasks);

            _isInitialized = true;
            _stats.CurrentPoolSize = _allInterpreters.Count;
            
            _logger.LogInformation("Python interpreter pool initialized with {Count} interpreters", 
                _allInterpreters.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to initialize Python interpreter pool");
            throw new PythonInitializationException("Failed to initialize interpreter pool", ex);
        }
    }

    public async Task<IRentedInterpreter> RentAsync(TimeSpan? timeout = null, CancellationToken cancellationToken = default)
    {
        if (!_isInitialized)
            throw new InvalidOperationException("Pool is not initialized");

        if (_isDisposed)
            throw new ObjectDisposedException(nameof(PythonInterpreterPool));

        var effectiveTimeout = timeout ?? TimeSpan.FromMilliseconds(_options.PythonTimeout);
        var stopwatch = Stopwatch.StartNew();

        try
        {
            // Wait for an available slot
            if (!await _semaphore.WaitAsync(effectiveTimeout, cancellationToken))
            {
                _stats.FailedRentals++;
                throw new TimeoutException($"Timeout waiting for available Python interpreter after {effectiveTimeout}");
            }

            IPythonInterpreter? interpreter = null;

            // Try to get an available interpreter
            if (!_availableInterpreters.TryDequeue(out interpreter))
            {
                // Create a new one if we haven't reached the limit
                if (_allInterpreters.Count < _options.MaxInterpreters)
                {
                    interpreter = await CreateInterpreterAsync(cancellationToken);
                }
                else
                {
                    // Wait for one to become available
                    var waitStopwatch = Stopwatch.StartNew();
                    while (!_availableInterpreters.TryDequeue(out interpreter) && 
                           waitStopwatch.Elapsed < effectiveTimeout)
                    {
                        await Task.Delay(100, cancellationToken);
                    }

                    if (interpreter == null)
                    {
                        _semaphore.Release();
                        _stats.FailedRentals++;
                        throw new TimeoutException("No interpreter became available within timeout");
                    }
                }
            }

            // Create the rental wrapper
            var rental = new RentedInterpreter(interpreter, this);
            _rentedInterpreters[interpreter.Id] = rental;

            // Update stats
            _stats.TotalRentals++;
            _stats.PeakConcurrentRentals = Math.Max(_stats.PeakConcurrentRentals, _rentedInterpreters.Count);

            _logger.LogDebug("Rented interpreter {InterpreterId} (rental time: {RentalTime}ms)", 
                interpreter.Id, stopwatch.ElapsedMilliseconds);

            return rental;
        }
        catch (OperationCanceledException)
        {
            _semaphore.Release();
            _stats.FailedRentals++;
            throw;
        }
        catch (Exception ex)
        {
            _semaphore.Release();
            _stats.FailedRentals++;
            _logger.LogError(ex, "Failed to rent Python interpreter");
            throw;
        }
    }

    public PythonInterpreterPoolStats GetStats()
    {
        var uptime = _lastResetAt?.Subtract(_createdAt) ?? DateTime.UtcNow.Subtract(_createdAt);
        
        return new PythonInterpreterPoolStats
        {
            TotalCreated = _stats.TotalCreated,
            TotalDestroyed = _stats.TotalDestroyed,
            TotalRentals = _stats.TotalRentals,
            FailedRentals = _stats.FailedRentals,
            AverageRentalDuration = _stats.AverageRentalDuration,
            PeakConcurrentRentals = _stats.PeakConcurrentRentals,
            CurrentPoolSize = _allInterpreters.Count,
            HealthyInterpreters = _availableInterpreters.Count + _rentedInterpreters.Count,
            TotalMemoryUsage = CalculateTotalMemoryUsage(),
            LastResetAt = _lastResetAt,
            Uptime = uptime
        };
    }

    public async Task<PythonInterpreterPoolHealth> HealthCheckAsync(CancellationToken cancellationToken = default)
    {
        var health = new PythonInterpreterPoolHealth
        {
            CheckedAt = DateTime.UtcNow
        };

        var healthTasks = _allInterpreters.Values.Select(async interpreter =>
        {
            var result = new InterpreterHealthResult
            {
                InterpreteId = interpreter.Id,
                LastSuccessfulExecution = interpreter.LastActivity
            };

            try
            {
                var stopwatch = Stopwatch.StartNew();
                
                // Simple health check - evaluate 1+1
                var healthResult = await interpreter.EvaluateAsync<int>("1+1", 
                    cancellationToken: cancellationToken);
                
                stopwatch.Stop();
                
                result.IsHealthy = healthResult == 2;
                result.ResponseTime = stopwatch.Elapsed;
                result.MemoryInfo = interpreter.GetMemoryInfo();

                if (!result.IsHealthy)
                {
                    result.ErrorMessage = $"Health check returned unexpected result: {healthResult}";
                }
            }
            catch (Exception ex)
            {
                result.IsHealthy = false;
                result.ErrorMessage = ex.Message;
                result.ResponseTime = TimeSpan.MaxValue;
            }

            return result;
        });

        health.InterpreterResults = (await Task.WhenAll(healthTasks)).ToList();
        health.IsHealthy = health.InterpreterResults.All(r => r.IsHealthy);

        // Analyze health issues
        var unhealthyCount = health.InterpreterResults.Count(r => !r.IsHealthy);
        if (unhealthyCount > 0)
        {
            health.Issues.Add($"{unhealthyCount} interpreters are unhealthy");
            
            if (unhealthyCount > _allInterpreters.Count / 2)
            {
                health.RecommendedActions.Add("Consider resetting the interpreter pool");
            }
        }

        var highMemoryCount = health.InterpreterResults.Count(r => 
            r.MemoryInfo.AllocatedBytes > _options.MaxMemoryUsageMB * 1024 * 1024);
        
        if (highMemoryCount > 0)
        {
            health.Issues.Add($"{highMemoryCount} interpreters have high memory usage");
            health.RecommendedActions.Add("Consider performing garbage collection or resetting high-memory interpreters");
        }

        return health;
    }

    public async Task ResetPoolAsync(CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("Resetting Python interpreter pool");

        try
        {
            // Wait for all current rentals to complete or timeout
            var timeout = TimeSpan.FromSeconds(30);
            var stopwatch = Stopwatch.StartNew();
            
            while (_rentedInterpreters.Count > 0 && stopwatch.Elapsed < timeout)
            {
                await Task.Delay(1000, cancellationToken);
            }

            // Force return any remaining rentals
            foreach (var rental in _rentedInterpreters.Values.ToList())
            {
                rental.ForceReturn();
            }

            // Dispose all interpreters
            var disposeTasks = _allInterpreters.Values.Select(async interpreter =>
            {
                try
                {
                    interpreter.Dispose();
                }
                catch (Exception ex)
                {
                    _logger.LogWarning("Error disposing interpreter {InterpreterId}: {Error}", 
                        interpreter.Id, ex.Message);
                }
            });

            await Task.WhenAll(disposeTasks);

            // Clear collections
            while (_availableInterpreters.TryDequeue(out _)) { }
            _allInterpreters.Clear();
            _rentedInterpreters.Clear();

            // Reset stats
            _stats.TotalDestroyed += _stats.CurrentPoolSize;
            _stats.CurrentPoolSize = 0;
            _lastResetAt = DateTime.UtcNow;

            // Reinitialize with fresh interpreters
            await InitializeAsync(cancellationToken);

            _logger.LogInformation("Python interpreter pool reset completed");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during interpreter pool reset");
            throw;
        }
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        _isDisposed = true;

        _logger.LogInformation("Disposing Python interpreter pool");

        _healthCheckTimer?.Dispose();
        _cleanupTimer?.Dispose();

        // Dispose all interpreters
        foreach (var interpreter in _allInterpreters.Values)
        {
            try
            {
                interpreter.Dispose();
            }
            catch (Exception ex)
            {
                _logger.LogWarning("Error disposing interpreter: {Error}", ex.Message);
            }
        }

        _semaphore?.Dispose();
    }

    internal void ReturnInterpreter(IPythonInterpreter interpreter)
    {
        if (_isDisposed || !_allInterpreters.ContainsKey(interpreter.Id))
            return;

        try
        {
            _rentedInterpreters.TryRemove(interpreter.Id, out _);

            // Check if interpreter is still healthy
            if (!interpreter.IsInitialized || interpreter.IsBusy)
            {
                // Replace unhealthy interpreter
                _ = Task.Run(async () =>
                {
                    try
                    {
                        interpreter.Dispose();
                        _allInterpreters.TryRemove(interpreter.Id, out _);
                        _stats.TotalDestroyed++;

                        // Create replacement if needed
                        if (_allInterpreters.Count < _options.MaxInterpreters)
                        {
                            await CreateInterpreterAsync();
                        }
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning("Error replacing unhealthy interpreter: {Error}", ex.Message);
                    }
                });
            }
            else
            {
                _availableInterpreters.Enqueue(interpreter);
            }
        }
        finally
        {
            _semaphore.Release();
        }
    }

    private async Task<IPythonInterpreter> CreateInterpreterAsync(CancellationToken cancellationToken = default)
    {
        var interpreter = _serviceProvider.GetRequiredService<IPythonInterpreter>();
        await interpreter.InitializeAsync(cancellationToken);
        
        _allInterpreters[interpreter.Id] = interpreter;
        _availableInterpreters.Enqueue(interpreter);
        
        _stats.TotalCreated++;
        _stats.CurrentPoolSize = _allInterpreters.Count;

        _logger.LogDebug("Created new Python interpreter {InterpreterId}", interpreter.Id);

        return interpreter;
    }

    private long CalculateTotalMemoryUsage()
    {
        return _allInterpreters.Values.Sum(i => 
        {
            try
            {
                return i.GetMemoryInfo().AllocatedBytes;
            }
            catch
            {
                return 0L;
            }
        });
    }

    private async Task PerformHealthCheckAsync()
    {
        if (_isDisposed || !_isInitialized)
            return;

        try
        {
            var health = await HealthCheckAsync();
            
            if (!health.IsHealthy)
            {
                _logger.LogWarning("Interpreter pool health check failed: {Issues}", 
                    string.Join(", ", health.Issues));
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during periodic health check");
        }
    }

    private async Task PerformCleanupAsync()
    {
        if (_isDisposed || !_isInitialized)
            return;

        try
        {
            var threshold = DateTime.UtcNow.AddMinutes(-30);
            var staleRentals = _rentedInterpreters.Values
                .Where(r => r.RentedAt < threshold)
                .ToList();

            foreach (var rental in staleRentals)
            {
                _logger.LogWarning("Force returning stale interpreter rental {InterpreterId}", 
                    rental.Interpreter.Id);
                rental.ForceReturn();
            }

            // Trigger garbage collection on idle interpreters
            var idleInterpreters = _availableInterpreters.ToArray()
                .Where(i => i.LastActivity < threshold);

            foreach (var interpreter in idleInterpreters)
            {
                try
                {
                    await interpreter.ExecuteAsync("import gc; gc.collect()");
                }
                catch (Exception ex)
                {
                    _logger.LogDebug("Error during GC on interpreter {InterpreterId}: {Error}", 
                        interpreter.Id, ex.Message);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during periodic cleanup");
        }
    }
}

/// <summary>
/// Implementation of IRentedInterpreter
/// </summary>
internal class RentedInterpreter : IRentedInterpreter
{
    private readonly PythonInterpreterPool _pool;
    private bool _isDisposed;

    public IPythonInterpreter Interpreter { get; }
    public DateTime RentedAt { get; }
    public bool IsValid => !_isDisposed && Interpreter.IsInitialized;

    public RentedInterpreter(IPythonInterpreter interpreter, PythonInterpreterPool pool)
    {
        Interpreter = interpreter ?? throw new ArgumentNullException(nameof(interpreter));
        _pool = pool ?? throw new ArgumentNullException(nameof(pool));
        RentedAt = DateTime.UtcNow;
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        _isDisposed = true;
        _pool.ReturnInterpreter(Interpreter);
    }

    internal void ForceReturn()
    {
        if (!_isDisposed)
        {
            _isDisposed = true;
        }
    }
}