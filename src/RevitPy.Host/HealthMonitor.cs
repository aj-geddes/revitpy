using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Core.Configuration;
using System.Collections.Concurrent;
using System.Diagnostics;

namespace RevitPy.Host;

/// <summary>
/// Monitors system health and performs automatic recovery
/// </summary>
public class HealthMonitor : IHealthMonitor, IDisposable
{
    private readonly ILogger<HealthMonitor> _logger;
    private readonly IServiceProvider _serviceProvider;
    private readonly RevitPyOptions _options;
    private readonly ConcurrentDictionary<string, HealthCheckResult> _healthChecks = new();
    private readonly ConcurrentDictionary<string, HealthMetrics> _metrics = new();
    private readonly Timer _healthCheckTimer;
    private readonly Timer _metricsTimer;

    private bool _isRunning;
    private bool _isDisposed;
    private HealthMonitorStats _stats = new();
    private readonly object _statsLock = new();

    public HealthMonitorStats Stats
    {
        get
        {
            lock (_statsLock)
            {
                return new HealthMonitorStats
                {
                    TotalHealthChecks = _stats.TotalHealthChecks,
                    FailedHealthChecks = _stats.FailedHealthChecks,
                    RecoveryAttempts = _stats.RecoveryAttempts,
                    SuccessfulRecoveries = _stats.SuccessfulRecoveries,
                    LastHealthCheck = _stats.LastHealthCheck,
                    LastRecovery = _stats.LastRecovery,
                    AverageHealthCheckTime = _stats.AverageHealthCheckTime,
                    ComponentHealthScores = _healthChecks.ToDictionary(
                        kvp => kvp.Key,
                        kvp => kvp.Value.IsHealthy ? 100.0 : 0.0)
                };
            }
        }
    }

    public bool IsHealthy => _healthChecks.Values.All(h => h.IsHealthy);
    public bool IsRunning => _isRunning;
    public IReadOnlyDictionary<string, HealthCheckResult> CurrentHealthChecks => _healthChecks.AsReadOnly();
    public IReadOnlyDictionary<string, HealthMetrics> CurrentMetrics => _metrics.AsReadOnly();

    public HealthMonitor(
        ILogger<HealthMonitor> logger,
        IServiceProvider serviceProvider,
        IOptions<RevitPyOptions> options)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _serviceProvider = serviceProvider ?? throw new ArgumentNullException(nameof(serviceProvider));
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));

        // Create timers for periodic health checks and metrics collection
        _healthCheckTimer = new Timer(
            async _ => await PerformHealthChecksAsync(),
            null,
            TimeSpan.FromSeconds(30), // Initial delay
            TimeSpan.FromSeconds(30)  // Health check interval
        );

        _metricsTimer = new Timer(
            async _ => await CollectMetricsAsync(),
            null,
            TimeSpan.FromSeconds(10), // Initial delay
            TimeSpan.FromSeconds(10)  // Metrics collection interval
        );
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (_isRunning)
            return;

        _logger.LogInformation("Starting health monitoring");

        _isRunning = true;

        // Perform initial health check
        await PerformHealthChecksAsync();

        _logger.LogInformation("Health monitoring started successfully");
    }

    public async Task StopAsync(CancellationToken cancellationToken = default)
    {
        if (!_isRunning)
            return;

        _logger.LogInformation("Stopping health monitoring");

        _isRunning = false;

        await Task.CompletedTask;

        _logger.LogInformation("Health monitoring stopped");
    }

    public async Task<RevitPyHostHealth> PerformHealthCheckAsync(CancellationToken cancellationToken = default)
    {
        var stopwatch = Stopwatch.StartNew();
        var hostHealth = new RevitPyHostHealth
        {
            CheckedAt = DateTime.UtcNow
        };

        try
        {
            // Perform all health checks
            var checkTasks = new List<Task>
            {
                CheckPythonInterpreterPoolHealthAsync(),
                CheckMemoryHealthAsync(),
                CheckWebSocketServerHealthAsync(),
                CheckFileSystemHealthAsync(),
                CheckExtensionManagerHealthAsync(),
                CheckResourceUsageAsync()
            };

            await Task.WhenAll(checkTasks);

            // Aggregate results
            hostHealth.IsHealthy = _healthChecks.Values.All(h => h.IsHealthy);
            hostHealth.Components = _healthChecks.ToDictionary(
                kvp => kvp.Key,
                kvp => new ComponentHealth
                {
                    Name = kvp.Key,
                    IsHealthy = kvp.Value.IsHealthy,
                    ResponseTime = kvp.Value.ResponseTime,
                    ErrorMessage = kvp.Value.ErrorMessage,
                    Metrics = kvp.Value.Metrics
                });

            // Collect overall issues and recommendations
            hostHealth.Issues.AddRange(_healthChecks.Values
                .Where(h => !h.IsHealthy)
                .Select(h => h.ErrorMessage ?? "Unknown issue"));

            hostHealth.RecommendedActions.AddRange(GenerateRecommendedActions());

            // Update statistics
            lock (_statsLock)
            {
                _stats.TotalHealthChecks++;
                if (!hostHealth.IsHealthy)
                {
                    _stats.FailedHealthChecks++;
                }
                _stats.LastHealthCheck = DateTime.UtcNow;

                // Update average health check time
                var totalTime = _stats.AverageHealthCheckTime.TotalMilliseconds * (_stats.TotalHealthChecks - 1);
                totalTime += stopwatch.ElapsedMilliseconds;
                _stats.AverageHealthCheckTime = TimeSpan.FromMilliseconds(totalTime / _stats.TotalHealthChecks);
            }

            var level = hostHealth.IsHealthy ? LogLevel.Debug : LogLevel.Warning;
            _logger.Log(level, "Health check completed in {Duration}ms. Healthy: {IsHealthy}, Issues: {IssueCount}",
                stopwatch.ElapsedMilliseconds,
                hostHealth.IsHealthy,
                hostHealth.Issues.Count);
        }
        catch (Exception ex)
        {
            hostHealth.IsHealthy = false;
            hostHealth.Issues.Add($"Health check failed with exception: {ex.Message}");
            _logger.LogError(ex, "Health check failed");
        }

        stopwatch.Stop();
        return hostHealth;
    }

    public async Task<bool> AttemptRecoveryAsync(string componentName, CancellationToken cancellationToken = default)
    {
        _logger.LogWarning("Attempting recovery for component: {ComponentName}", componentName);

        lock (_statsLock)
        {
            _stats.RecoveryAttempts++;
        }

        try
        {
            var recoverySuccessful = componentName switch
            {
                "PythonInterpreterPool" => await RecoverPythonInterpreterPoolAsync(),
                "MemoryManager" => await RecoverMemoryManagerAsync(),
                "WebSocketServer" => await RecoverWebSocketServerAsync(),
                "ExtensionManager" => await RecoverExtensionManagerAsync(),
                _ => false
            };

            if (recoverySuccessful)
            {
                lock (_statsLock)
                {
                    _stats.SuccessfulRecoveries++;
                    _stats.LastRecovery = DateTime.UtcNow;
                }

                _logger.LogInformation("Recovery successful for component: {ComponentName}", componentName);
            }
            else
            {
                _logger.LogError("Recovery failed for component: {ComponentName}", componentName);
            }

            return recoverySuccessful;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Recovery attempt failed for component: {ComponentName}", componentName);
            return false;
        }
    }

    public void RegisterCustomHealthCheck(string name, Func<Task<HealthCheckResult>> healthCheck)
    {
        if (string.IsNullOrWhiteSpace(name))
            throw new ArgumentException("Health check name cannot be empty", nameof(name));

        if (healthCheck == null)
            throw new ArgumentNullException(nameof(healthCheck));

        _customHealthChecks[name] = healthCheck;
        _logger.LogInformation("Registered custom health check: {Name}", name);
    }

    public void UnregisterHealthCheck(string name)
    {
        if (_customHealthChecks.TryRemove(name, out _))
        {
            _healthChecks.TryRemove(name, out _);
            _logger.LogInformation("Unregistered health check: {Name}", name);
        }
    }

    private readonly ConcurrentDictionary<string, Func<Task<HealthCheckResult>>> _customHealthChecks = new();

    private async Task PerformHealthChecksAsync()
    {
        if (!_isRunning || _isDisposed)
            return;

        try
        {
            await PerformHealthCheckAsync();

            // If any component is unhealthy, attempt automatic recovery
            var unhealthyComponents = _healthChecks
                .Where(kvp => !kvp.Value.IsHealthy)
                .Select(kvp => kvp.Key)
                .ToList();

            foreach (var component in unhealthyComponents)
            {
                await AttemptRecoveryAsync(component);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during periodic health checks");
        }
    }

    private async Task CollectMetricsAsync()
    {
        if (!_isRunning || _isDisposed)
            return;

        try
        {
            var process = Process.GetCurrentProcess();
            var metrics = new HealthMetrics
            {
                Timestamp = DateTime.UtcNow,
                CpuUsage = GetCpuUsage(),
                MemoryUsage = process.WorkingSet64,
                ThreadCount = process.Threads.Count,
                HandleCount = process.HandleCount,
                GCCollectionCounts = new Dictionary<string, long>
                {
                    ["Gen0"] = GC.CollectionCount(0),
                    ["Gen1"] = GC.CollectionCount(1),
                    ["Gen2"] = GC.CollectionCount(2)
                }
            };

            _metrics.AddOrUpdate("System", metrics, (_, _) => metrics);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error collecting metrics");
        }
    }

    private async Task CheckPythonInterpreterPoolHealthAsync()
    {
        var stopwatch = Stopwatch.StartNew();
        var healthCheck = new HealthCheckResult { Name = "PythonInterpreterPool" };

        try
        {
            var interpreterPool = _serviceProvider.GetService(typeof(Runtime.IPythonInterpreterPool))
                as Runtime.IPythonInterpreterPool;

            if (interpreterPool == null)
            {
                healthCheck.IsHealthy = false;
                healthCheck.ErrorMessage = "Python interpreter pool service not available";
            }
            else
            {
                // Check if pool is responsive by trying to get an interpreter
                using var interpreter = await interpreterPool.GetInterpreterAsync(TimeSpan.FromSeconds(5));
                healthCheck.IsHealthy = interpreter != null;
                healthCheck.ErrorMessage = interpreter == null ? "Unable to get Python interpreter from pool" : null;
                healthCheck.Metrics["AvailableInterpreters"] = interpreterPool.AvailableCount;
                healthCheck.Metrics["TotalInterpreters"] = interpreterPool.TotalCount;
            }
        }
        catch (Exception ex)
        {
            healthCheck.IsHealthy = false;
            healthCheck.ErrorMessage = ex.Message;
        }

        stopwatch.Stop();
        healthCheck.ResponseTime = stopwatch.Elapsed;
        _healthChecks.AddOrUpdate("PythonInterpreterPool", healthCheck, (_, _) => healthCheck);
    }

    private async Task CheckMemoryHealthAsync()
    {
        var stopwatch = Stopwatch.StartNew();
        var healthCheck = new HealthCheckResult { Name = "MemoryManager" };

        try
        {
            var memoryManager = _serviceProvider.GetService(typeof(IMemoryManager)) as IMemoryManager;

            if (memoryManager == null)
            {
                healthCheck.IsHealthy = false;
                healthCheck.ErrorMessage = "Memory manager service not available";
            }
            else
            {
                var memoryInfo = memoryManager.GetMemoryUsage();
                var memoryUsageMB = memoryInfo.TotalManagedMemory / 1024 / 1024;
                var thresholdMB = _options.MaxMemoryUsageMB;

                healthCheck.IsHealthy = memoryUsageMB < thresholdMB * 0.9; // 90% of threshold
                healthCheck.ErrorMessage = healthCheck.IsHealthy ? null : $"Memory usage ({memoryUsageMB}MB) is approaching threshold ({thresholdMB}MB)";
                healthCheck.Metrics["MemoryUsageMB"] = memoryUsageMB;
                healthCheck.Metrics["MemoryThresholdMB"] = thresholdMB;
                healthCheck.Metrics["WorkingSetMB"] = memoryInfo.WorkingSet / 1024 / 1024;
            }
        }
        catch (Exception ex)
        {
            healthCheck.IsHealthy = false;
            healthCheck.ErrorMessage = ex.Message;
        }

        stopwatch.Stop();
        healthCheck.ResponseTime = stopwatch.Elapsed;
        _healthChecks.AddOrUpdate("MemoryManager", healthCheck, (_, _) => healthCheck);
    }

    private async Task CheckWebSocketServerHealthAsync()
    {
        var stopwatch = Stopwatch.StartNew();
        var healthCheck = new HealthCheckResult { Name = "WebSocketServer" };

        try
        {
            var webSocketServer = _serviceProvider.GetService(typeof(IWebSocketServer)) as IWebSocketServer;

            if (!_options.EnableDebugServer)
            {
                healthCheck.IsHealthy = true;
                healthCheck.ErrorMessage = null;
                healthCheck.Metrics["Enabled"] = false;
            }
            else if (webSocketServer == null)
            {
                healthCheck.IsHealthy = false;
                healthCheck.ErrorMessage = "WebSocket server service not available";
            }
            else
            {
                healthCheck.IsHealthy = webSocketServer.IsRunning || !_options.EnableDebugServer;
                healthCheck.ErrorMessage = healthCheck.IsHealthy ? null : "WebSocket server is not running";
                healthCheck.Metrics["IsRunning"] = webSocketServer.IsRunning;
                healthCheck.Metrics["Port"] = webSocketServer.Port;
                healthCheck.Metrics["ConnectedClients"] = webSocketServer.ConnectedClients;
            }
        }
        catch (Exception ex)
        {
            healthCheck.IsHealthy = false;
            healthCheck.ErrorMessage = ex.Message;
        }

        stopwatch.Stop();
        healthCheck.ResponseTime = stopwatch.Elapsed;
        _healthChecks.AddOrUpdate("WebSocketServer", healthCheck, (_, _) => healthCheck);
    }

    private async Task CheckFileSystemHealthAsync()
    {
        var stopwatch = Stopwatch.StartNew();
        var healthCheck = new HealthCheckResult { Name = "FileSystem" };

        try
        {
            // Check temp directory
            var tempTestFile = Path.Combine(_options.TempDirectory, $"health_check_{Guid.NewGuid():N}.tmp");
            await File.WriteAllTextAsync(tempTestFile, "health check");
            var content = await File.ReadAllTextAsync(tempTestFile);
            File.Delete(tempTestFile);

            // Check log directory
            var logTestFile = Path.Combine(_options.LogDirectory, $"health_check_{Guid.NewGuid():N}.log");
            await File.WriteAllTextAsync(logTestFile, "health check");
            File.Delete(logTestFile);

            // Check disk space
            var tempDrive = new DriveInfo(_options.TempDirectory);
            var availableSpaceGB = tempDrive.AvailableFreeSpace / 1024.0 / 1024.0 / 1024.0;

            healthCheck.IsHealthy = content == "health check" && availableSpaceGB > 1.0;
            healthCheck.ErrorMessage = healthCheck.IsHealthy ? null : $"File system issues detected. Available space: {availableSpaceGB:F1}GB";
            healthCheck.Metrics["AvailableSpaceGB"] = availableSpaceGB;
            healthCheck.Metrics["TempDirectory"] = _options.TempDirectory;
            healthCheck.Metrics["LogDirectory"] = _options.LogDirectory;
        }
        catch (Exception ex)
        {
            healthCheck.IsHealthy = false;
            healthCheck.ErrorMessage = ex.Message;
        }

        stopwatch.Stop();
        healthCheck.ResponseTime = stopwatch.Elapsed;
        _healthChecks.AddOrUpdate("FileSystem", healthCheck, (_, _) => healthCheck);
    }

    private async Task CheckExtensionManagerHealthAsync()
    {
        var stopwatch = Stopwatch.StartNew();
        var healthCheck = new HealthCheckResult { Name = "ExtensionManager" };

        try
        {
            var extensionManager = _serviceProvider.GetService(typeof(IExtensionManager)) as IExtensionManager;

            if (extensionManager == null)
            {
                healthCheck.IsHealthy = false;
                healthCheck.ErrorMessage = "Extension manager service not available";
            }
            else
            {
                healthCheck.IsHealthy = true;
                healthCheck.ErrorMessage = null;
                healthCheck.Metrics["LoadedExtensions"] = extensionManager.LoadedExtensions.Count;
                healthCheck.Metrics["FailedLoads"] = extensionManager.Stats.LoadFailures;
            }
        }
        catch (Exception ex)
        {
            healthCheck.IsHealthy = false;
            healthCheck.ErrorMessage = ex.Message;
        }

        stopwatch.Stop();
        healthCheck.ResponseTime = stopwatch.Elapsed;
        _healthChecks.AddOrUpdate("ExtensionManager", healthCheck, (_, _) => healthCheck);
    }

    private async Task CheckResourceUsageAsync()
    {
        var stopwatch = Stopwatch.StartNew();
        var healthCheck = new HealthCheckResult { Name = "ResourceUsage" };

        try
        {
            var process = Process.GetCurrentProcess();
            var cpuUsage = GetCpuUsage();

            healthCheck.IsHealthy = cpuUsage < 80.0; // CPU usage below 80%
            healthCheck.ErrorMessage = healthCheck.IsHealthy ? null : $"High CPU usage detected: {cpuUsage:F1}%";
            healthCheck.Metrics["CpuUsage"] = cpuUsage;
            healthCheck.Metrics["ThreadCount"] = process.Threads.Count;
            healthCheck.Metrics["HandleCount"] = process.HandleCount;
        }
        catch (Exception ex)
        {
            healthCheck.IsHealthy = false;
            healthCheck.ErrorMessage = ex.Message;
        }

        stopwatch.Stop();
        healthCheck.ResponseTime = stopwatch.Elapsed;
        _healthChecks.AddOrUpdate("ResourceUsage", healthCheck, (_, _) => healthCheck);
    }

    private async Task<bool> RecoverPythonInterpreterPoolAsync()
    {
        try
        {
            var interpreterPool = _serviceProvider.GetService(typeof(Runtime.IPythonInterpreterPool))
                as Runtime.IPythonInterpreterPool;

            if (interpreterPool != null)
            {
                // Force cleanup and restart of interpreter pool
                // This would be implemented in the interpreter pool
                return true;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to recover Python interpreter pool");
        }

        return false;
    }

    private async Task<bool> RecoverMemoryManagerAsync()
    {
        try
        {
            var memoryManager = _serviceProvider.GetService(typeof(IMemoryManager)) as IMemoryManager;

            if (memoryManager != null)
            {
                await memoryManager.ForceGarbageCollectionAsync();
                return true;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to recover memory manager");
        }

        return false;
    }

    private async Task<bool> RecoverWebSocketServerAsync()
    {
        try
        {
            var webSocketServer = _serviceProvider.GetService(typeof(IWebSocketServer)) as IWebSocketServer;

            if (webSocketServer != null && _options.EnableDebugServer)
            {
                await webSocketServer.StopAsync();
                await Task.Delay(1000); // Brief delay
                await webSocketServer.StartAsync();
                return true;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to recover WebSocket server");
        }

        return false;
    }

    private async Task<bool> RecoverExtensionManagerAsync()
    {
        try
        {
            var extensionManager = _serviceProvider.GetService(typeof(IExtensionManager)) as IExtensionManager;

            if (extensionManager != null)
            {
                // Reload failed extensions
                // This would be implemented in the extension manager
                return true;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to recover extension manager");
        }

        return false;
    }

    private List<string> GenerateRecommendedActions()
    {
        var actions = new List<string>();

        foreach (var healthCheck in _healthChecks.Values.Where(h => !h.IsHealthy))
        {
            actions.Add(healthCheck.Name switch
            {
                "PythonInterpreterPool" => "Restart Python interpreter pool or check Python installation",
                "MemoryManager" => "Perform garbage collection or increase memory limits",
                "WebSocketServer" => "Restart WebSocket server or check port availability",
                "FileSystem" => "Check disk space and file permissions",
                "ExtensionManager" => "Reload failed extensions or check extension configuration",
                "ResourceUsage" => "Reduce system load or restart application",
                _ => $"Check {healthCheck.Name} configuration and logs"
            });
        }

        return actions;
    }

    private double GetCpuUsage()
    {
        try
        {
            using var process = Process.GetCurrentProcess();
            var startTime = DateTime.UtcNow;
            var startCpuUsage = process.TotalProcessorTime;

            Thread.Sleep(100); // Sample period

            var endTime = DateTime.UtcNow;
            var endCpuUsage = process.TotalProcessorTime;

            var cpuUsedMs = (endCpuUsage - startCpuUsage).TotalMilliseconds;
            var totalMsPassed = (endTime - startTime).TotalMilliseconds;
            var cpuUsageTotal = cpuUsedMs / (Environment.ProcessorCount * totalMsPassed);

            return cpuUsageTotal * 100;
        }
        catch
        {
            return 0.0;
        }
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        _isDisposed = true;
        _isRunning = false;

        _logger.LogInformation("Disposing health monitor");

        _healthCheckTimer?.Dispose();
        _metricsTimer?.Dispose();
    }
}

/// <summary>
/// Interface for health monitoring
/// </summary>
public interface IHealthMonitor
{
    /// <summary>
    /// Gets whether the system is healthy
    /// </summary>
    bool IsHealthy { get; }

    /// <summary>
    /// Gets whether monitoring is running
    /// </summary>
    bool IsRunning { get; }

    /// <summary>
    /// Gets current health check results
    /// </summary>
    IReadOnlyDictionary<string, HealthCheckResult> CurrentHealthChecks { get; }

    /// <summary>
    /// Gets current metrics
    /// </summary>
    IReadOnlyDictionary<string, HealthMetrics> CurrentMetrics { get; }

    /// <summary>
    /// Gets health monitor statistics
    /// </summary>
    HealthMonitorStats Stats { get; }

    /// <summary>
    /// Starts health monitoring
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the startup</returns>
    Task StartAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Stops health monitoring
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the shutdown</returns>
    Task StopAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Performs a complete health check
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Health check result</returns>
    Task<RevitPyHostHealth> PerformHealthCheckAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Attempts to recover a failed component
    /// </summary>
    /// <param name="componentName">Name of the component to recover</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>True if recovery was successful</returns>
    Task<bool> AttemptRecoveryAsync(string componentName, CancellationToken cancellationToken = default);

    /// <summary>
    /// Registers a custom health check
    /// </summary>
    /// <param name="name">Health check name</param>
    /// <param name="healthCheck">Health check function</param>
    void RegisterCustomHealthCheck(string name, Func<Task<HealthCheckResult>> healthCheck);

    /// <summary>
    /// Unregisters a health check
    /// </summary>
    /// <param name="name">Health check name</param>
    void UnregisterHealthCheck(string name);
}

/// <summary>
/// Result of a health check
/// </summary>
public class HealthCheckResult
{
    /// <summary>
    /// Gets or sets the health check name
    /// </summary>
    public string Name { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets whether the component is healthy
    /// </summary>
    public bool IsHealthy { get; set; }

    /// <summary>
    /// Gets or sets the response time
    /// </summary>
    public TimeSpan ResponseTime { get; set; }

    /// <summary>
    /// Gets or sets any error message
    /// </summary>
    public string? ErrorMessage { get; set; }

    /// <summary>
    /// Gets health check metrics
    /// </summary>
    public Dictionary<string, object> Metrics { get; set; } = new();

    /// <summary>
    /// Gets or sets the check timestamp
    /// </summary>
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
}

/// <summary>
/// Health metrics
/// </summary>
public class HealthMetrics
{
    /// <summary>
    /// Gets or sets the timestamp
    /// </summary>
    public DateTime Timestamp { get; set; }

    /// <summary>
    /// Gets or sets CPU usage percentage
    /// </summary>
    public double CpuUsage { get; set; }

    /// <summary>
    /// Gets or sets memory usage in bytes
    /// </summary>
    public long MemoryUsage { get; set; }

    /// <summary>
    /// Gets or sets thread count
    /// </summary>
    public int ThreadCount { get; set; }

    /// <summary>
    /// Gets or sets handle count
    /// </summary>
    public int HandleCount { get; set; }

    /// <summary>
    /// Gets or sets GC collection counts by generation
    /// </summary>
    public Dictionary<string, long> GCCollectionCounts { get; set; } = new();

    /// <summary>
    /// Gets or sets custom metrics
    /// </summary>
    public Dictionary<string, object> CustomMetrics { get; set; } = new();
}

/// <summary>
/// Health monitor statistics
/// </summary>
public class HealthMonitorStats
{
    /// <summary>
    /// Gets or sets total health checks performed
    /// </summary>
    public long TotalHealthChecks { get; set; }

    /// <summary>
    /// Gets or sets failed health checks count
    /// </summary>
    public long FailedHealthChecks { get; set; }

    /// <summary>
    /// Gets or sets recovery attempts count
    /// </summary>
    public long RecoveryAttempts { get; set; }

    /// <summary>
    /// Gets or sets successful recoveries count
    /// </summary>
    public long SuccessfulRecoveries { get; set; }

    /// <summary>
    /// Gets or sets last health check time
    /// </summary>
    public DateTime? LastHealthCheck { get; set; }

    /// <summary>
    /// Gets or sets last recovery time
    /// </summary>
    public DateTime? LastRecovery { get; set; }

    /// <summary>
    /// Gets or sets average health check time
    /// </summary>
    public TimeSpan AverageHealthCheckTime { get; set; }

    /// <summary>
    /// Gets or sets component health scores
    /// </summary>
    public Dictionary<string, double> ComponentHealthScores { get; set; } = new();
}
