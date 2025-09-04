namespace RevitPy.Bridge;

/// <summary>
/// Main interface for the Revit API bridge
/// </summary>
public interface IRevitBridge
{
    /// <summary>
    /// Gets the current Revit application
    /// </summary>
    object? Application { get; }

    /// <summary>
    /// Gets the active document
    /// </summary>
    object? ActiveDocument { get; }

    /// <summary>
    /// Gets the transaction manager
    /// </summary>
    ITransactionManager TransactionManager { get; }

    /// <summary>
    /// Gets the type converter for Python/Revit type marshaling
    /// </summary>
    IRevitTypeConverter TypeConverter { get; }

    /// <summary>
    /// Gets a value indicating whether Revit is available
    /// </summary>
    bool IsRevitAvailable { get; }

    /// <summary>
    /// Initializes the bridge with Revit application
    /// </summary>
    /// <param name="application">Revit application instance</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the initialization</returns>
    Task InitializeAsync(object application, CancellationToken cancellationToken = default);

    /// <summary>
    /// Invokes a method on a Revit object safely
    /// </summary>
    /// <typeparam name="T">Expected return type</typeparam>
    /// <param name="target">Target object</param>
    /// <param name="methodName">Method name</param>
    /// <param name="parameters">Method parameters</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Method result</returns>
    Task<T?> InvokeMethodAsync<T>(
        object target, 
        string methodName, 
        object[]? parameters = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets a property value from a Revit object
    /// </summary>
    /// <typeparam name="T">Expected property type</typeparam>
    /// <param name="target">Target object</param>
    /// <param name="propertyName">Property name</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Property value</returns>
    Task<T?> GetPropertyAsync<T>(
        object target, 
        string propertyName,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Sets a property value on a Revit object
    /// </summary>
    /// <param name="target">Target object</param>
    /// <param name="propertyName">Property name</param>
    /// <param name="value">Property value</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the operation</returns>
    Task SetPropertyAsync(
        object target, 
        string propertyName, 
        object? value,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Creates a new instance of a Revit type
    /// </summary>
    /// <typeparam name="T">Expected instance type</typeparam>
    /// <param name="typeName">Type name</param>
    /// <param name="parameters">Constructor parameters</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>New instance</returns>
    Task<T?> CreateInstanceAsync<T>(
        string typeName, 
        object[]? parameters = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Registers an event handler for Revit events
    /// </summary>
    /// <param name="eventName">Event name</param>
    /// <param name="handler">Event handler</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Event subscription</returns>
    Task<IEventSubscription> RegisterEventHandlerAsync(
        string eventName, 
        Func<object, object[], Task> handler,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets the Revit version information
    /// </summary>
    /// <returns>Version information</returns>
    RevitVersionInfo GetVersionInfo();

    /// <summary>
    /// Validates that an object is a valid Revit API object
    /// </summary>
    /// <param name="obj">Object to validate</param>
    /// <returns>True if valid</returns>
    bool IsValidRevitObject(object? obj);

    /// <summary>
    /// Disposes of bridge resources
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing disposal</returns>
    Task DisposeAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Represents an event subscription
/// </summary>
public interface IEventSubscription : IDisposable
{
    /// <summary>
    /// Gets the event name
    /// </summary>
    string EventName { get; }

    /// <summary>
    /// Gets the subscription ID
    /// </summary>
    string SubscriptionId { get; }

    /// <summary>
    /// Gets a value indicating whether the subscription is active
    /// </summary>
    bool IsActive { get; }

    /// <summary>
    /// Unsubscribes from the event
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the unsubscription</returns>
    Task UnsubscribeAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Information about the Revit version
/// </summary>
public class RevitVersionInfo
{
    /// <summary>
    /// Gets or sets the Revit version number (e.g., "2024")
    /// </summary>
    public string Version { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the build number
    /// </summary>
    public string BuildNumber { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the product name
    /// </summary>
    public string ProductName { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the language
    /// </summary>
    public string Language { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets additional version details
    /// </summary>
    public Dictionary<string, string> AdditionalInfo { get; set; } = new();
}