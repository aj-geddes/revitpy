using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Bridge;
using RevitPy.Core.Configuration;
using RevitPy.Runtime;
using System.Diagnostics;

namespace RevitPy.Host;

/// <summary>
/// Main implementation of the RevitPy host application
/// </summary>
public class RevitPyHost : IRevitPyHost, IDisposable
{
    private readonly ILogger<RevitPyHost> _logger;
    private readonly RevitPyOptions _options;
    private readonly IConfigurationValidator _configurationValidator;
    private readonly IServiceProvider _serviceProvider;

    // Core services
    private readonly IPythonInterpreterPool _interpreterPool;
    private readonly IMemoryManager _memoryManager;
    private readonly IWebSocketServer? _debugServer;
    private readonly IHotReloadManager? _hotReloadManager;
    private readonly IExtensionManager _extensionManager;
    private readonly IHealthMonitor _healthMonitor;
    private readonly IResourceManager _resourceManager;

    // Host state
    private bool _isInitialized;
    private bool _isRunning;
    private bool _isDisposed;
    private object? _revitApplication;
    private RevitPyHostStats _stats = new();
    private readonly object _statsLock = new();
    private readonly Stopwatch _uptimeStopwatch = new();

    // Service startup order for dependency management
    private readonly List<(string Name, Func<CancellationToken, Task> StartFunc, Func<CancellationToken, Task> StopFunc)> _services;

    public bool IsInitialized => _isInitialized;
    public bool IsRunning => _isRunning;
    public IPythonInterpreterPool InterpreterPool => _interpreterPool;
    public IRevitBridge RevitBridge { get; private set; } = null!;
    public IExtensionManager ExtensionManager => _extensionManager;
    public IWebSocketServer? DebugServer => _debugServer;
    public IHotReloadManager? HotReloadManager => _hotReloadManager;
    public IMemoryManager MemoryManager => _memoryManager;

    public RevitPyHostStats Stats
    {
        get
        {
            lock (_statsLock)
            {
                return new RevitPyHostStats
                {
                    StartTime = _stats.StartTime,
                    Uptime = _uptimeStopwatch.Elapsed,
                    TotalPythonExecutions = _stats.TotalPythonExecutions,
                    SuccessfulExecutions = _stats.SuccessfulExecutions,
                    FailedExecutions = _stats.FailedExecutions,
                    AverageExecutionTime = _stats.AverageExecutionTime,
                    LoadedExtensions = ExtensionManager.LoadedExtensions.Count,
                    MemoryUsage = MemoryManager.GetMemoryUsage(),
                    LastHealthCheck = _stats.LastHealthCheck,
                    LastReset = _stats.LastReset
                };
            }
        }
    }

    public RevitPyHost(
        ILogger<RevitPyHost> logger,
        IOptions<RevitPyOptions> options,
        IConfigurationValidator configurationValidator,
        IPythonInterpreterPool interpreterPool,
        IMemoryManager memoryManager,
        IExtensionManager extensionManager,
        IHealthMonitor healthMonitor,
        IResourceManager resourceManager,
        IServiceProvider serviceProvider,
        IWebSocketServer? debugServer = null,
        IHotReloadManager? hotReloadManager = null)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        _configurationValidator = configurationValidator ?? throw new ArgumentNullException(nameof(configurationValidator));
        _interpreterPool = interpreterPool ?? throw new ArgumentNullException(nameof(interpreterPool));
        _memoryManager = memoryManager ?? throw new ArgumentNullException(nameof(memoryManager));
        _extensionManager = extensionManager ?? throw new ArgumentNullException(nameof(extensionManager));
        _healthMonitor = healthMonitor ?? throw new ArgumentNullException(nameof(healthMonitor));
        _resourceManager = resourceManager ?? throw new ArgumentNullException(nameof(resourceManager));
        _serviceProvider = serviceProvider ?? throw new ArgumentNullException(nameof(serviceProvider));
        _debugServer = debugServer;
        _hotReloadManager = hotReloadManager;

        // Define service startup order (dependencies first)
        _services = new List<(string, Func<CancellationToken, Task>, Func<CancellationToken, Task>)>
        {
            ("ResourceManager", _resourceManager.StartAsync, _resourceManager.StopAsync),
            ("MemoryManager", _memoryManager.StartAsync, _memoryManager.StopAsync),
            ("PythonInterpreterPool", StartPythonInterpreterPoolAsync, StopPythonInterpreterPoolAsync),
            ("ExtensionManager", _extensionManager.InitializeAsync, StopExtensionManagerAsync),
            ("HealthMonitor", _healthMonitor.StartAsync, _healthMonitor.StopAsync)
        };

        // Add optional services
        if (_debugServer != null)
        {
            _services.Add(("WebSocketServer", _debugServer.StartAsync, _debugServer.StopAsync));
        }

        if (_hotReloadManager != null)
        {
            _services.Add(("HotReloadManager", _hotReloadManager.StartAsync, _hotReloadManager.StopAsync));
        }
    }

    public async Task InitializeAsync(object revitApplication, CancellationToken cancellationToken = default)
    {
        if (_isInitialized)
        {
            _logger.LogWarning("RevitPy host is already initialized");
            return;
        }

        var initStopwatch = Stopwatch.StartNew();
        _logger.LogInformation("Initializing RevitPy host...");

        try
        {
            // Store Revit application reference
            _revitApplication = revitApplication ?? throw new ArgumentNullException(nameof(revitApplication));

            // Validate configuration
            _logger.LogInformation("Validating configuration...");
            var configValidation = await _configurationValidator.ValidateAsync(
                _serviceProvider.GetService(typeof(Microsoft.Extensions.Configuration.IConfiguration))
                as Microsoft.Extensions.Configuration.IConfiguration ?? throw new InvalidOperationException("Configuration not found"));

            if (!configValidation.IsValid)
            {
                var errors = string.Join("; ", configValidation.Errors);
                throw new InvalidOperationException($"Configuration validation failed: {errors}");
            }

            if (configValidation.Warnings.Any())
            {
                foreach (var warning in configValidation.Warnings)
                {
                    _logger.LogWarning("Configuration warning: {Warning}", warning);
                }
            }

            // Initialize Revit bridge
            _logger.LogInformation("Initializing Revit bridge...");
            RevitBridge = _serviceProvider.GetService<IRevitBridge>() ??
                         throw new InvalidOperationException("Revit bridge service not available");

            if (RevitBridge is IInitializable initializableBridge)
            {
                await initializableBridge.InitializeAsync(revitApplication, cancellationToken);
            }

            // Ensure required directories exist
            await EnsureDirectoriesAsync();

            _isInitialized = true;
            initStopwatch.Stop();

            lock (_statsLock)
            {
                _stats.StartTime = DateTime.UtcNow;
            }

            _logger.LogInformation("RevitPy host initialized successfully in {Duration}ms", initStopwatch.ElapsedMilliseconds);
        }
        catch (Exception ex)
        {
            initStopwatch.Stop();
            _logger.LogError(ex, "Failed to initialize RevitPy host after {Duration}ms", initStopwatch.ElapsedMilliseconds);
            throw;
        }
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (!_isInitialized)
        {
            throw new InvalidOperationException("Host must be initialized before starting");
        }

        if (_isRunning)
        {
            _logger.LogWarning("RevitPy host is already running");
            return;
        }

        var startStopwatch = Stopwatch.StartNew();
        _logger.LogInformation("Starting RevitPy host services...");

        try
        {
            // Start services in dependency order
            foreach (var (serviceName, startFunc, _) in _services)
            {
                _logger.LogInformation("Starting service: {ServiceName}", serviceName);
                var serviceStopwatch = Stopwatch.StartNew();

                try
                {
                    await startFunc(cancellationToken);
                    serviceStopwatch.Stop();
                    _logger.LogInformation("Service {ServiceName} started in {Duration}ms",
                        serviceName, serviceStopwatch.ElapsedMilliseconds);
                }
                catch (Exception ex)
                {
                    serviceStopwatch.Stop();
                    _logger.LogError(ex, "Failed to start service {ServiceName} after {Duration}ms",
                        serviceName, serviceStopwatch.ElapsedMilliseconds);

                    // Stop already started services
                    await StopStartedServicesAsync(serviceName, cancellationToken);
                    throw;
                }
            }

            _isRunning = true;
            _uptimeStopwatch.Start();
            startStopwatch.Stop();

            // Verify startup meets performance requirement (<2 seconds)
            if (startStopwatch.ElapsedMilliseconds > 2000)
            {
                _logger.LogWarning("Host startup took {Duration}ms, exceeding the 2-second requirement",
                    startStopwatch.ElapsedMilliseconds);
            }

            _logger.LogInformation("RevitPy host started successfully in {Duration}ms. All {ServiceCount} services are running.",
                startStopwatch.ElapsedMilliseconds, _services.Count);

            // Perform initial health check
            _ = Task.Run(async () =>
            {
                await Task.Delay(5000, cancellationToken); // Wait 5 seconds before first health check
                var health = await HealthCheckAsync(cancellationToken);

                if (!health.IsHealthy)
                {
                    _logger.LogWarning("Initial health check failed: {IssueCount} issues detected", health.Issues.Count);
                    foreach (var issue in health.Issues)
                    {
                        _logger.LogWarning("Health issue: {Issue}", issue);
                    }
                }
                else
                {
                    _logger.LogInformation("Initial health check passed - all systems healthy");
                }
            }, cancellationToken);
        }
        catch (Exception ex)
        {
            startStopwatch.Stop();
            _logger.LogError(ex, "Failed to start RevitPy host after {Duration}ms", startStopwatch.ElapsedMilliseconds);
            _isRunning = false;
            throw;
        }
    }

    public async Task StopAsync(CancellationToken cancellationToken = default)
    {
        if (!_isRunning)
        {
            _logger.LogInformation("RevitPy host is not running");
            return;
        }

        var stopStopwatch = Stopwatch.StartNew();
        _logger.LogInformation("Stopping RevitPy host services...");

        try
        {
            _isRunning = false;
            _uptimeStopwatch.Stop();

            // Stop services in reverse order
            var servicesReversed = _services.AsEnumerable().Reverse().ToList();

            foreach (var (serviceName, _, stopFunc) in servicesReversed)
            {
                _logger.LogInformation("Stopping service: {ServiceName}", serviceName);
                var serviceStopwatch = Stopwatch.StartNew();

                try
                {
                    await stopFunc(cancellationToken);
                    serviceStopwatch.Stop();
                    _logger.LogInformation("Service {ServiceName} stopped in {Duration}ms",
                        serviceName, serviceStopwatch.ElapsedMilliseconds);
                }
                catch (Exception ex)
                {
                    serviceStopwatch.Stop();
                    _logger.LogError(ex, "Error stopping service {ServiceName} after {Duration}ms",
                        serviceName, serviceStopwatch.ElapsedMilliseconds);
                    // Continue stopping other services
                }
            }

            stopStopwatch.Stop();

            // Verify shutdown meets performance requirement (<5 seconds)
            if (stopStopwatch.ElapsedMilliseconds > 5000)
            {
                _logger.LogWarning("Host shutdown took {Duration}ms, exceeding the 5-second requirement",
                    stopStopwatch.ElapsedMilliseconds);
            }

            _logger.LogInformation("RevitPy host stopped successfully in {Duration}ms", stopStopwatch.ElapsedMilliseconds);
        }
        catch (Exception ex)
        {
            stopStopwatch.Stop();
            _logger.LogError(ex, "Error stopping RevitPy host after {Duration}ms", stopStopwatch.ElapsedMilliseconds);
        }
    }

    public async Task<PythonExecutionResult> ExecutePythonAsync(
        string code,
        Dictionary<string, object>? globals = null,
        Dictionary<string, object>? locals = null,
        CancellationToken cancellationToken = default)
    {
        if (!_isRunning)
        {
            throw new InvalidOperationException("Host is not running");
        }

        if (string.IsNullOrWhiteSpace(code))
        {
            throw new ArgumentException("Code cannot be empty", nameof(code));
        }

        var executionStopwatch = Stopwatch.StartNew();

        lock (_statsLock)
        {
            _stats.TotalPythonExecutions++;
        }

        try
        {
            _logger.LogDebug("Executing Python code ({CodeLength} characters)", code.Length);

            using var interpreter = await _interpreterPool.GetInterpreterAsync(
                TimeSpan.FromMilliseconds(_options.PythonTimeout), cancellationToken);

            // Add Revit bridge to globals if not provided
            var effectiveGlobals = globals ?? new Dictionary<string, object>();
            if (!effectiveGlobals.ContainsKey("revit"))
            {
                effectiveGlobals["revit"] = RevitBridge;
            }

            var result = await interpreter.ExecuteAsync(code, effectiveGlobals, locals, cancellationToken);

            executionStopwatch.Stop();

            lock (_statsLock)
            {
                if (result.IsSuccess)
                {
                    _stats.SuccessfulExecutions++;
                }
                else
                {
                    _stats.FailedExecutions++;
                }

                // Update average execution time
                var totalTime = _stats.AverageExecutionTime.TotalMilliseconds * (_stats.TotalPythonExecutions - 1);
                totalTime += executionStopwatch.ElapsedMilliseconds;
                _stats.AverageExecutionTime = TimeSpan.FromMilliseconds(totalTime / _stats.TotalPythonExecutions);
            }

            var level = result.IsSuccess ? LogLevel.Debug : LogLevel.Warning;
            _logger.Log(level, "Python execution {Result} in {Duration}ms",
                result.IsSuccess ? "succeeded" : "failed",
                executionStopwatch.ElapsedMilliseconds);

            return result;
        }
        catch (Exception ex)
        {
            executionStopwatch.Stop();

            lock (_statsLock)
            {
                _stats.FailedExecutions++;
            }

            _logger.LogError(ex, "Python execution failed after {Duration}ms", executionStopwatch.ElapsedMilliseconds);

            return new PythonExecutionResult
            {
                IsSuccess = false,
                Error = ex.Message,
                ExecutionTime = executionStopwatch.Elapsed
            };
        }
    }

    public async Task<IExtensionInfo> LoadExtensionAsync(string extensionPath, CancellationToken cancellationToken = default)
    {
        if (!_isRunning)
        {
            throw new InvalidOperationException("Host is not running");
        }

        _logger.LogInformation("Loading extension: {ExtensionPath}", extensionPath);

        try
        {
            var extensionInfo = await _extensionManager.LoadExtensionAsync(extensionPath, cancellationToken);

            _logger.LogInformation("Extension loaded successfully: {ExtensionId} ({Name} v{Version})",
                extensionInfo.Id, extensionInfo.Name, extensionInfo.Version);

            return extensionInfo;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to load extension: {ExtensionPath}", extensionPath);
            throw;
        }
    }

    public async Task UnloadExtensionAsync(string extensionId, CancellationToken cancellationToken = default)
    {
        if (!_isRunning)
        {
            throw new InvalidOperationException("Host is not running");
        }

        _logger.LogInformation("Unloading extension: {ExtensionId}", extensionId);

        try
        {
            await _extensionManager.UnloadExtensionAsync(extensionId, cancellationToken);

            _logger.LogInformation("Extension unloaded successfully: {ExtensionId}", extensionId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to unload extension: {ExtensionId}", extensionId);
            throw;
        }
    }

    public async Task<RevitPyHostHealth> HealthCheckAsync(CancellationToken cancellationToken = default)
    {
        _logger.LogDebug("Performing host health check");

        try
        {
            var health = await _healthMonitor.PerformHealthCheckAsync(cancellationToken);

            lock (_statsLock)
            {
                _stats.LastHealthCheck = DateTime.UtcNow;
            }

            var level = health.IsHealthy ? LogLevel.Debug : LogLevel.Warning;
            _logger.Log(level, "Host health check completed. Healthy: {IsHealthy}, Components: {ComponentCount}, Issues: {IssueCount}",
                health.IsHealthy, health.Components.Count, health.Issues.Count);

            return health;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Health check failed");
            throw;
        }
    }

    public async Task ResetAsync(CancellationToken cancellationToken = default)
    {
        if (!_isRunning)
        {
            throw new InvalidOperationException("Host is not running");
        }

        _logger.LogInformation("Resetting RevitPy host");

        var resetStopwatch = Stopwatch.StartNew();

        try
        {
            // Reset Python interpreter pool
            if (_interpreterPool is IResettable resettablePool)
            {
                await resettablePool.ResetAsync(cancellationToken);
            }

            // Force memory cleanup
            await _memoryManager.ForceGarbageCollectionAsync(cancellationToken: cancellationToken);

            // Reset resource manager
            await _resourceManager.OptimizeResourceUsageAsync();

            // Reset statistics
            lock (_statsLock)
            {
                _stats.LastReset = DateTime.UtcNow;
                _stats.TotalPythonExecutions = 0;
                _stats.SuccessfulExecutions = 0;
                _stats.FailedExecutions = 0;
                _stats.AverageExecutionTime = TimeSpan.Zero;
            }

            resetStopwatch.Stop();

            _logger.LogInformation("RevitPy host reset completed in {Duration}ms", resetStopwatch.ElapsedMilliseconds);
        }
        catch (Exception ex)
        {
            resetStopwatch.Stop();
            _logger.LogError(ex, "Host reset failed after {Duration}ms", resetStopwatch.ElapsedMilliseconds);
            throw;
        }
    }

    private async Task EnsureDirectoriesAsync()
    {
        var directories = new[]
        {
            _options.TempDirectory,
            _options.LogDirectory,
            Path.Combine(_options.TempDirectory, "UserScripts"),
            Path.Combine(_options.TempDirectory, "Cache")
        };

        foreach (var directory in directories)
        {
            if (!Directory.Exists(directory))
            {
                try
                {
                    Directory.CreateDirectory(directory);
                    _logger.LogDebug("Created directory: {Directory}", directory);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to create directory: {Directory}", directory);
                    throw;
                }
            }
        }
    }

    private async Task StartPythonInterpreterPoolAsync(CancellationToken cancellationToken)
    {
        // The interpreter pool doesn't have a specific Start method in the interface
        // This is a placeholder for initialization if needed
        _logger.LogDebug("Python interpreter pool ready");
        await Task.CompletedTask;
    }

    private async Task StopPythonInterpreterPoolAsync(CancellationToken cancellationToken)
    {
        if (_interpreterPool is IDisposable disposablePool)
        {
            disposablePool.Dispose();
        }
        await Task.CompletedTask;
    }

    private async Task StopExtensionManagerAsync(CancellationToken cancellationToken)
    {
        // Unload all extensions
        var extensionIds = _extensionManager.LoadedExtensions.Select(e => e.Id).ToList();
        foreach (var extensionId in extensionIds)
        {
            try
            {
                await _extensionManager.UnloadExtensionAsync(extensionId, cancellationToken);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error unloading extension during shutdown: {ExtensionId}", extensionId);
            }
        }
    }

    private async Task StopStartedServicesAsync(string failedService, CancellationToken cancellationToken)
    {
        _logger.LogInformation("Stopping already started services due to {FailedService} failure", failedService);

        var startedServices = _services
            .TakeWhile(s => s.Name != failedService)
            .Reverse()
            .ToList();

        foreach (var (serviceName, _, stopFunc) in startedServices)
        {
            try
            {
                await stopFunc(cancellationToken);
                _logger.LogDebug("Stopped service during cleanup: {ServiceName}", serviceName);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error stopping service during cleanup: {ServiceName}", serviceName);
            }
        }
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        _isDisposed = true;

        _logger.LogInformation("Disposing RevitPy host");

        try
        {
            if (_isRunning)
            {
                StopAsync().Wait(TimeSpan.FromSeconds(10));
            }

            // Dispose disposable services
            if (_resourceManager is IDisposable disposableResourceManager)
                disposableResourceManager.Dispose();

            if (_memoryManager is IDisposable disposableMemoryManager)
                disposableMemoryManager.Dispose();

            if (_extensionManager is IDisposable disposableExtensionManager)
                disposableExtensionManager.Dispose();

            if (_healthMonitor is IDisposable disposableHealthMonitor)
                disposableHealthMonitor.Dispose();

            if (_debugServer is IDisposable disposableDebugServer)
                disposableDebugServer.Dispose();

            if (_hotReloadManager is IDisposable disposableHotReloadManager)
                disposableHotReloadManager.Dispose();

            _uptimeStopwatch.Stop();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during RevitPy host disposal");
        }
    }
}

/// <summary>
/// Interface for resettable services
/// </summary>
public interface IResettable
{
    /// <summary>
    /// Resets the service to a clean state
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the reset operation</returns>
    Task ResetAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Interface for initializable services
/// </summary>
public interface IInitializable
{
    /// <summary>
    /// Initializes the service
    /// </summary>
    /// <param name="context">Initialization context</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the initialization</returns>
    Task InitializeAsync(object context, CancellationToken cancellationToken = default);
}
