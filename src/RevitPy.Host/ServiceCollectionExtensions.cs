using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using RevitPy.Bridge;
using RevitPy.Core;
using RevitPy.Core.Configuration;
using RevitPy.Core.Logging;
using RevitPy.Runtime;

namespace RevitPy.Host;

/// <summary>
/// Extension methods for registering RevitPy services
/// </summary>
public static class ServiceCollectionExtensions
{
    /// <summary>
    /// Adds all RevitPy services to the service collection
    /// </summary>
    /// <param name="services">Service collection</param>
    /// <param name="configuration">Configuration</param>
    /// <returns>Service collection for chaining</returns>
    public static IServiceCollection AddRevitPy(this IServiceCollection services, IConfiguration configuration)
    {
        // Configure options
        services.Configure<RevitPyOptions>(configuration.GetSection(RevitPyOptions.SectionName));

        // Add core services
        services.AddRevitPyCore();
        services.AddRevitPyRuntime();
        services.AddRevitPyBridge();
        services.AddRevitPyHost();

        return services;
    }

    /// <summary>
    /// Adds RevitPy core services
    /// </summary>
    /// <param name="services">Service collection</param>
    /// <returns>Service collection for chaining</returns>
    public static IServiceCollection AddRevitPyCore(this IServiceCollection services)
    {
        // Register logging services
        services.AddSingleton<RevitPyLoggerFactory>();
        services.AddTransient<IRevitPyLogger>(provider =>
        {
            var factory = provider.GetRequiredService<RevitPyLoggerFactory>();
            return factory.CreateLogger("RevitPy");
        });

        // Register log sinks
        services.AddTransient<FileLogEventSink>(provider =>
        {
            var logPath = Path.Combine(Path.GetTempPath(), "RevitPy", "Logs", "revitpy.log");
            return new FileLogEventSink(logPath);
        });

        services.AddTransient<WebSocketLogEventSink>();

        return services;
    }

    /// <summary>
    /// Adds RevitPy runtime services
    /// </summary>
    /// <param name="services">Service collection</param>
    /// <returns>Service collection for chaining</returns>
    public static IServiceCollection AddRevitPyRuntime(this IServiceCollection services)
    {
        // Register Python interpreter services
        services.AddTransient<IPythonInterpreter, PythonInterpreter>();
        services.AddSingleton<IPythonInterpreterPool, PythonInterpreterPool>();

        return services;
    }

    /// <summary>
    /// Adds RevitPy bridge services
    /// </summary>
    /// <param name="services">Service collection</param>
    /// <returns>Service collection for chaining</returns>
    public static IServiceCollection AddRevitPyBridge(this IServiceCollection services)
    {
        // These would be implemented in the Bridge project
        // services.AddSingleton<IRevitBridge, RevitBridge>();
        // services.AddSingleton<ITransactionManager, TransactionManager>();
        // services.AddSingleton<IRevitTypeConverter, RevitTypeConverter>();

        return services;
    }

    /// <summary>
    /// Adds RevitPy host services
    /// </summary>
    /// <param name="services">Service collection</param>
    /// <returns>Service collection for chaining</returns>
    public static IServiceCollection AddRevitPyHost(this IServiceCollection services)
    {
        // Register configuration validator
        services.AddSingleton<IConfigurationValidator, ConfigurationValidator>();

        // Register host services
        services.AddSingleton<IMemoryManager, MemoryManager>();
        services.AddSingleton<IWebSocketServer, WebSocketServer>();
        services.AddSingleton<IExtensionManager, PluginManager>();
        services.AddSingleton<IHotReloadManager, HotReloadManager>();
        services.AddSingleton<IHealthMonitor, HealthMonitor>();
        services.AddSingleton<IResourceManager, ResourceManager>();

        // Register main host implementation
        services.AddSingleton<IRevitPyHost, RevitPyHost>();

        return services;
    }

    /// <summary>
    /// Adds RevitPy with custom configuration
    /// </summary>
    /// <param name="services">Service collection</param>
    /// <param name="configureOptions">Configuration action</param>
    /// <returns>Service collection for chaining</returns>
    public static IServiceCollection AddRevitPy(this IServiceCollection services, Action<RevitPyOptions> configureOptions)
    {
        services.Configure(configureOptions);

        services.AddRevitPyCore();
        services.AddRevitPyRuntime();
        services.AddRevitPyBridge();
        services.AddRevitPyHost();

        return services;
    }

    /// <summary>
    /// Adds RevitPy for development with common development settings
    /// </summary>
    /// <param name="services">Service collection</param>
    /// <param name="configuration">Configuration</param>
    /// <returns>Service collection for chaining</returns>
    public static IServiceCollection AddRevitPyForDevelopment(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddRevitPy(configuration);

        // Override options for development
        services.PostConfigure<RevitPyOptions>(options =>
        {
            options.EnableDebugServer = true;
            options.EnableHotReload = true;
            options.EnableMemoryProfiling = true;
            options.EnableSandbox = false; // Disable for easier debugging
        });

        return services;
    }

    /// <summary>
    /// Adds RevitPy for production with secure defaults
    /// </summary>
    /// <param name="services">Service collection</param>
    /// <param name="configuration">Configuration</param>
    /// <returns>Service collection for chaining</returns>
    public static IServiceCollection AddRevitPyForProduction(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddRevitPy(configuration);

        // Override options for production
        services.PostConfigure<RevitPyOptions>(options =>
        {
            options.EnableDebugServer = false;
            options.EnableSandbox = true;
            options.Extensions.RequireSigned = true;
            options.Extensions.EnableValidation = true;
        });

        return services;
    }
}

/// <summary>
/// Extension methods for building RevitPy hosts
/// </summary>
public static class RevitPyHostBuilderExtensions
{
    /// <summary>
    /// Creates a RevitPy host with default configuration
    /// </summary>
    /// <param name="revitApplication">Revit application instance</param>
    /// <returns>Configured service provider</returns>
    public static async Task<IServiceProvider> CreateRevitPyHostAsync(object revitApplication)
    {
        var services = new ServiceCollection();
        
        // Add basic logging
        services.AddLogging(builder =>
        {
            builder.AddConsole();
            builder.SetMinimumLevel(LogLevel.Information);
        });

        // Add configuration
        var configBuilder = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile($"appsettings.{Environment.GetEnvironmentVariable("ASPNETCORE_ENVIRONMENT") ?? "Production"}.json", optional: true)
            .AddEnvironmentVariables("REVITPY_");

        var configuration = configBuilder.Build();
        services.AddSingleton<IConfiguration>(configuration);

        // Add RevitPy services
        services.AddRevitPy(configuration);

        // Build service provider
        var serviceProvider = services.BuildServiceProvider();

        // Initialize the host
        // var host = serviceProvider.GetRequiredService<IRevitPyHost>();
        // await host.InitializeAsync(revitApplication);

        return serviceProvider;
    }

    /// <summary>
    /// Creates a RevitPy host for development
    /// </summary>
    /// <param name="revitApplication">Revit application instance</param>
    /// <returns>Configured service provider</returns>
    public static async Task<IServiceProvider> CreateRevitPyDevelopmentHostAsync(object revitApplication)
    {
        var services = new ServiceCollection();
        
        // Add debug logging
        services.AddLogging(builder =>
        {
            builder.AddConsole();
            builder.AddDebug();
            builder.SetMinimumLevel(LogLevel.Debug);
        });

        // Add configuration
        var configBuilder = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: true)
            .AddJsonFile("appsettings.Development.json", optional: true)
            .AddEnvironmentVariables("REVITPY_");

        var configuration = configBuilder.Build();
        services.AddSingleton<IConfiguration>(configuration);

        // Add RevitPy services with development settings
        services.AddRevitPyForDevelopment(configuration);

        // Build service provider
        var serviceProvider = services.BuildServiceProvider();

        // Initialize the host
        // var host = serviceProvider.GetRequiredService<IRevitPyHost>();
        // await host.InitializeAsync(revitApplication);
        // await host.StartAsync();

        return serviceProvider;
    }

    /// <summary>
    /// Validates RevitPy configuration
    /// </summary>
    /// <param name="services">Service collection</param>
    /// <returns>Validation results</returns>
    public static List<string> ValidateRevitPyConfiguration(this IServiceCollection services)
    {
        var errors = new List<string>();

        // Build temporary service provider for validation
        using var serviceProvider = services.BuildServiceProvider();

        try
        {
            // Validate configuration
            var options = serviceProvider.GetService<Microsoft.Extensions.Options.IOptions<RevitPyOptions>>();
            if (options?.Value == null)
            {
                errors.Add("RevitPy configuration is missing");
                return errors;
            }

            var config = options.Value;

            // Validate Python configuration
            if (string.IsNullOrWhiteSpace(config.PythonVersion))
            {
                errors.Add("PythonVersion is required");
            }

            if (config.MaxInterpreters <= 0)
            {
                errors.Add("MaxInterpreters must be greater than 0");
            }

            if (config.PythonTimeout <= 0)
            {
                errors.Add("PythonTimeout must be greater than 0");
            }

            // Validate debug server configuration
            if (config.EnableDebugServer && (config.DebugServerPort <= 0 || config.DebugServerPort > 65535))
            {
                errors.Add("DebugServerPort must be between 1 and 65535 when debug server is enabled");
            }

            // Validate memory configuration
            if (config.EnableMemoryProfiling)
            {
                if (config.MemoryCheckInterval <= 0)
                {
                    errors.Add("MemoryCheckInterval must be greater than 0 when memory profiling is enabled");
                }

                if (config.MaxMemoryUsageMB <= 0)
                {
                    errors.Add("MaxMemoryUsageMB must be greater than 0 when memory profiling is enabled");
                }
            }

            // Validate extension configuration
            if (config.Extensions.LoadTimeout <= 0)
            {
                errors.Add("Extension LoadTimeout must be greater than 0");
            }

            // Check for required services
            var requiredServices = new[]
            {
                typeof(IPythonInterpreterPool),
                typeof(IMemoryManager),
                typeof(IWebSocketServer)
            };

            foreach (var serviceType in requiredServices)
            {
                if (serviceProvider.GetService(serviceType) == null)
                {
                    errors.Add($"Required service {serviceType.Name} is not registered");
                }
            }
        }
        catch (Exception ex)
        {
            errors.Add($"Configuration validation failed: {ex.Message}");
        }

        return errors;
    }
}