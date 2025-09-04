using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using RevitPy.Runtime;

namespace RevitPy.Bridge;

/// <summary>
/// Extension methods for configuring RevitPy Bridge services in dependency injection container
/// </summary>
public static class BridgeServiceCollectionExtensions
{
    /// <summary>
    /// Adds RevitPy Bridge services to the service collection with full integration
    /// </summary>
    public static IServiceCollection AddRevitPyBridge(
        this IServiceCollection services,
        Action<RevitBridgeConfiguration>? configure = null)
    {
        ArgumentNullException.ThrowIfNull(services);

        var configuration = new RevitBridgeConfiguration();
        configure?.Invoke(configuration);

        // Register bridge configuration
        services.AddSingleton(configuration);

        // Register core bridge services
        services.AddSingleton<IRevitTypeConverter, TypeConverterEnhanced>();
        services.AddSingleton<ITransactionManager, TransactionManager>();
        services.AddSingleton<IElementBridge, ElementBridge>();
        services.AddSingleton<IGeometryBridge, GeometryBridge>();
        services.AddSingleton<IParameterBridge, ParameterBridge>();

        // Register Python interpreter pool
        services.AddSingleton<IPythonInterpreterPool, PythonInterpreterPool>();

        // Register main bridge
        services.AddSingleton<IRevitBridge, RevitApiBridge>();

        // Register bridge factory for creating configured instances
        services.AddSingleton<IRevitBridgeFactory, RevitBridgeFactory>();

        // Add logging if not already configured
        services.AddLogging(builder =>
        {
            if (configuration.EnableDebugLogging)
            {
                builder.AddConsole();
                builder.SetMinimumLevel(LogLevel.Debug);
            }
            else
            {
                builder.SetMinimumLevel(LogLevel.Information);
            }
        });

        return services;
    }

    /// <summary>
    /// Adds RevitPy Bridge services with high-performance configuration
    /// </summary>
    public static IServiceCollection AddRevitPyBridgeHighPerformance(this IServiceCollection services)
    {
        return services.AddRevitPyBridge(config =>
        {
            config.EnableCaching = true;
            config.CacheSettings = new CacheSettings
            {
                MaxObjectCacheSize = 50000,
                MaxModuleCacheSize = 500,
                CacheTTL = TimeSpan.FromHours(1)
            };
            config.EnablePerformanceMonitoring = true;
            config.EnableDebugLogging = false;
            config.MaxConcurrentPythonOperations = Environment.ProcessorCount * 2;
            config.EnableMemoryOptimization = true;
        });
    }

    /// <summary>
    /// Adds RevitPy Bridge services with development-friendly configuration
    /// </summary>
    public static IServiceCollection AddRevitPyBridgeDevelopment(this IServiceCollection services)
    {
        return services.AddRevitPyBridge(config =>
        {
            config.EnableCaching = true;
            config.CacheSettings = new CacheSettings
            {
                MaxObjectCacheSize = 1000,
                MaxModuleCacheSize = 50,
                CacheTTL = TimeSpan.FromMinutes(5)
            };
            config.EnablePerformanceMonitoring = true;
            config.EnableDebugLogging = true;
            config.MaxConcurrentPythonOperations = Environment.ProcessorCount;
            config.EnableMemoryOptimization = false;
        });
    }
}

/// <summary>
/// Configuration options for RevitPy Bridge
/// </summary>
public class RevitBridgeConfiguration
{
    /// <summary>
    /// Gets or sets whether caching is enabled
    /// </summary>
    public bool EnableCaching { get; set; } = true;

    /// <summary>
    /// Gets or sets cache configuration settings
    /// </summary>
    public CacheSettings CacheSettings { get; set; } = new();

    /// <summary>
    /// Gets or sets whether performance monitoring is enabled
    /// </summary>
    public bool EnablePerformanceMonitoring { get; set; } = true;

    /// <summary>
    /// Gets or sets whether debug logging is enabled
    /// </summary>
    public bool EnableDebugLogging { get; set; } = false;

    /// <summary>
    /// Gets or sets the maximum number of concurrent Python operations
    /// </summary>
    public int MaxConcurrentPythonOperations { get; set; } = Environment.ProcessorCount;

    /// <summary>
    /// Gets or sets whether automatic memory optimization is enabled
    /// </summary>
    public bool EnableMemoryOptimization { get; set; } = true;

    /// <summary>
    /// Gets or sets the interval for automatic memory cleanup
    /// </summary>
    public TimeSpan MemoryCleanupInterval { get; set; } = TimeSpan.FromMinutes(5);

    /// <summary>
    /// Gets or sets whether transaction management is enabled
    /// </summary>
    public bool EnableTransactionManagement { get; set; } = true;

    /// <summary>
    /// Gets or sets the default transaction timeout
    /// </summary>
    public TimeSpan DefaultTransactionTimeout { get; set; } = TimeSpan.FromMinutes(5);

    /// <summary>
    /// Gets or sets custom Python paths to include
    /// </summary>
    public List<string> PythonPaths { get; set; } = new();

    /// <summary>
    /// Gets or sets custom Python modules to preload
    /// </summary>
    public List<string> PreloadModules { get; set; } = new();
}

/// <summary>
/// Factory for creating configured RevitPy Bridge instances
/// </summary>
public interface IRevitBridgeFactory
{
    /// <summary>
    /// Creates a new bridge instance with the specified configuration
    /// </summary>
    IRevitBridge CreateBridge(RevitBridgeConfiguration? configuration = null);

    /// <summary>
    /// Creates a high-performance bridge instance
    /// </summary>
    IRevitBridge CreateHighPerformanceBridge();

    /// <summary>
    /// Creates a development-friendly bridge instance
    /// </summary>
    IRevitBridge CreateDevelopmentBridge();
}

/// <summary>
/// Default implementation of RevitPy Bridge factory
/// </summary>
public class RevitBridgeFactory : IRevitBridgeFactory
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<RevitBridgeFactory> _logger;

    public RevitBridgeFactory(IServiceProvider serviceProvider, ILogger<RevitBridgeFactory> logger)
    {
        _serviceProvider = serviceProvider ?? throw new ArgumentNullException(nameof(serviceProvider));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc/>
    public IRevitBridge CreateBridge(RevitBridgeConfiguration? configuration = null)
    {
        try
        {
            var bridge = _serviceProvider.GetRequiredService<IRevitBridge>();
            
            if (configuration?.PreloadModules.Count > 0)
            {
                _ = Task.Run(async () =>
                {
                    foreach (var module in configuration.PreloadModules)
                    {
                        try
                        {
                            await bridge.ImportPythonModuleAsync(module);
                            _logger.LogInformation("Preloaded Python module: {ModuleName}", module);
                        }
                        catch (Exception ex)
                        {
                            _logger.LogWarning(ex, "Failed to preload Python module: {ModuleName}", module);
                        }
                    }
                });
            }

            return bridge;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create RevitPy Bridge instance");
            throw new InvalidOperationException("Failed to create bridge instance", ex);
        }
    }

    /// <inheritdoc/>
    public IRevitBridge CreateHighPerformanceBridge()
    {
        var config = new RevitBridgeConfiguration
        {
            EnableCaching = true,
            CacheSettings = new CacheSettings
            {
                MaxObjectCacheSize = 50000,
                MaxModuleCacheSize = 500,
                CacheTTL = TimeSpan.FromHours(1)
            },
            EnablePerformanceMonitoring = true,
            EnableDebugLogging = false,
            MaxConcurrentPythonOperations = Environment.ProcessorCount * 2,
            EnableMemoryOptimization = true,
            PreloadModules = new List<string> { "math", "json", "datetime" }
        };

        return CreateBridge(config);
    }

    /// <inheritdoc/>
    public IRevitBridge CreateDevelopmentBridge()
    {
        var config = new RevitBridgeConfiguration
        {
            EnableCaching = true,
            CacheSettings = new CacheSettings
            {
                MaxObjectCacheSize = 1000,
                MaxModuleCacheSize = 50,
                CacheTTL = TimeSpan.FromMinutes(5)
            },
            EnablePerformanceMonitoring = true,
            EnableDebugLogging = true,
            MaxConcurrentPythonOperations = Environment.ProcessorCount,
            EnableMemoryOptimization = false
        };

        return CreateBridge(config);
    }
}

/// <summary>
/// Health check service for RevitPy Bridge
/// </summary>
public interface IRevitBridgeHealthCheck
{
    /// <summary>
    /// Performs a comprehensive health check of all bridge components
    /// </summary>
    Task<BridgeHealthStatus> CheckHealthAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Performs a quick health check for monitoring
    /// </summary>
    Task<bool> IsHealthyAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Health check implementation for RevitPy Bridge
/// </summary>
public class RevitBridgeHealthCheck : IRevitBridgeHealthCheck
{
    private readonly IRevitBridge _bridge;
    private readonly ILogger<RevitBridgeHealthCheck> _logger;

    public RevitBridgeHealthCheck(IRevitBridge bridge, ILogger<RevitBridgeHealthCheck> logger)
    {
        _bridge = bridge ?? throw new ArgumentNullException(nameof(bridge));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc/>
    public async Task<BridgeHealthStatus> CheckHealthAsync(CancellationToken cancellationToken = default)
    {
        var status = new BridgeHealthStatus
        {
            CheckTime = DateTime.UtcNow,
            IsHealthy = true
        };

        try
        {
            // Test Python execution
            var pythonResult = await _bridge.ExecutePythonCodeAsync("import sys; sys.version", cancellationToken: cancellationToken);
            status.PythonEngineHealthy = pythonResult != null;
            status.Details.Add("PythonEngine", pythonResult?.ToString() ?? "Failed");

            // Test module import
            var mathModule = await _bridge.ImportPythonModuleAsync("math", cancellationToken: cancellationToken);
            status.ModuleImportHealthy = mathModule != null;
            status.Details.Add("ModuleImport", "Success");

            // Test function call
            var sqrtResult = await _bridge.CallPythonFunctionAsync<double>("math", "sqrt", new object[] { 16.0 }, cancellationToken);
            status.FunctionCallHealthy = Math.Abs(sqrtResult - 4.0) < 0.001;
            status.Details.Add("FunctionCall", sqrtResult.ToString());

            // Get performance stats
            var stats = _bridge.GetStats();
            status.PerformanceStats = stats;
            status.Details.Add("TotalOperations", stats.TotalOperations.ToString());
            status.Details.Add("SuccessRatio", $"{stats.SuccessRatio:P2}");
            status.Details.Add("MemoryUsage", $"{stats.MemoryUsageMB}MB");

            status.IsHealthy = status.PythonEngineHealthy && status.ModuleImportHealthy && status.FunctionCallHealthy;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Health check failed");
            status.IsHealthy = false;
            status.Error = ex.Message;
            status.Details.Add("Error", ex.ToString());
        }

        return status;
    }

    /// <inheritdoc/>
    public async Task<bool> IsHealthyAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            // Quick health check - just verify Python engine is responsive
            var result = await _bridge.ExecutePythonCodeAsync("1 + 1", cancellationToken: cancellationToken);
            return result?.ToString() == "2";
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Quick health check failed");
            return false;
        }
    }
}

/// <summary>
/// Represents the health status of the RevitPy Bridge
/// </summary>
public class BridgeHealthStatus
{
    /// <summary>
    /// Gets or sets when the health check was performed
    /// </summary>
    public DateTime CheckTime { get; set; }

    /// <summary>
    /// Gets or sets whether the bridge is healthy
    /// </summary>
    public bool IsHealthy { get; set; }

    /// <summary>
    /// Gets or sets whether the Python engine is healthy
    /// </summary>
    public bool PythonEngineHealthy { get; set; }

    /// <summary>
    /// Gets or sets whether module import is working
    /// </summary>
    public bool ModuleImportHealthy { get; set; }

    /// <summary>
    /// Gets or sets whether function calls are working
    /// </summary>
    public bool FunctionCallHealthy { get; set; }

    /// <summary>
    /// Gets or sets any error that occurred during health check
    /// </summary>
    public string? Error { get; set; }

    /// <summary>
    /// Gets detailed health check information
    /// </summary>
    public Dictionary<string, string> Details { get; } = new();

    /// <summary>
    /// Gets or sets performance statistics
    /// </summary>
    public RevitBridgeStats? PerformanceStats { get; set; }
}