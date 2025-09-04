using Microsoft.Extensions.DependencyInjection;

namespace RevitPy.Core;

/// <summary>
/// Represents a RevitPy module that can be loaded and initialized
/// </summary>
public interface IRevitPyModule
{
    /// <summary>
    /// Gets the module name
    /// </summary>
    string Name { get; }

    /// <summary>
    /// Gets the module version
    /// </summary>
    string Version { get; }

    /// <summary>
    /// Gets the module description
    /// </summary>
    string Description { get; }

    /// <summary>
    /// Configures services for this module
    /// </summary>
    /// <param name="services">The service collection to configure</param>
    void ConfigureServices(IServiceCollection services);

    /// <summary>
    /// Initializes the module
    /// </summary>
    /// <param name="serviceProvider">The service provider</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the initialization</returns>
    Task InitializeAsync(IServiceProvider serviceProvider, CancellationToken cancellationToken = default);

    /// <summary>
    /// Shuts down the module
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the shutdown</returns>
    Task ShutdownAsync(CancellationToken cancellationToken = default);
}