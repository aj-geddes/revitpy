using RevitPy.Bridge;
using RevitPy.Runtime;

namespace RevitPy.Host;

/// <summary>
/// Main interface for the RevitPy host application
/// </summary>
public interface IRevitPyHost : IDisposable
{
    /// <summary>
    /// Gets a value indicating whether the host is initialized
    /// </summary>
    bool IsInitialized { get; }

    /// <summary>
    /// Gets a value indicating whether the host is running
    /// </summary>
    bool IsRunning { get; }

    /// <summary>
    /// Gets the Python interpreter pool
    /// </summary>
    IPythonInterpreterPool InterpreterPool { get; }

    /// <summary>
    /// Gets the Revit bridge
    /// </summary>
    IRevitBridge RevitBridge { get; }

    /// <summary>
    /// Gets the extension manager
    /// </summary>
    IExtensionManager ExtensionManager { get; }

    /// <summary>
    /// Gets the WebSocket server for development tools
    /// </summary>
    IWebSocketServer? DebugServer { get; }

    /// <summary>
    /// Gets the hot-reload manager
    /// </summary>
    IHotReloadManager? HotReloadManager { get; }

    /// <summary>
    /// Gets the memory manager
    /// </summary>
    IMemoryManager MemoryManager { get; }

    /// <summary>
    /// Gets host statistics
    /// </summary>
    RevitPyHostStats Stats { get; }

    /// <summary>
    /// Initializes the host with the Revit application
    /// </summary>
    /// <param name="revitApplication">Revit application instance</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the initialization</returns>
    Task InitializeAsync(object revitApplication, CancellationToken cancellationToken = default);

    /// <summary>
    /// Starts the host and all its services
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the startup</returns>
    Task StartAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Stops the host and all its services
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the shutdown</returns>
    Task StopAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Executes Python code using the host
    /// </summary>
    /// <param name="code">Python code to execute</param>
    /// <param name="globals">Global variables</param>
    /// <param name="locals">Local variables</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Execution result</returns>
    Task<PythonExecutionResult> ExecutePythonAsync(
        string code,
        Dictionary<string, object>? globals = null,
        Dictionary<string, object>? locals = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Loads an extension from the specified path
    /// </summary>
    /// <param name="extensionPath">Path to the extension</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Extension information</returns>
    Task<IExtensionInfo> LoadExtensionAsync(string extensionPath, CancellationToken cancellationToken = default);

    /// <summary>
    /// Unloads an extension
    /// </summary>
    /// <param name="extensionId">Extension ID</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the operation</returns>
    Task UnloadExtensionAsync(string extensionId, CancellationToken cancellationToken = default);

    /// <summary>
    /// Performs a health check on all host components
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Health check results</returns>
    Task<RevitPyHostHealth> HealthCheckAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Resets the host to a clean state
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the reset</returns>
    Task ResetAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Manages extensions for the RevitPy host
/// </summary>
public interface IExtensionManager
{
    /// <summary>
    /// Gets all loaded extensions
    /// </summary>
    IReadOnlyList<IExtensionInfo> LoadedExtensions { get; }

    /// <summary>
    /// Gets extension manager statistics
    /// </summary>
    ExtensionManagerStats Stats { get; }

    /// <summary>
    /// Initializes the extension manager
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the initialization</returns>
    Task InitializeAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Discovers extensions in configured search paths
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Discovered extension paths</returns>
    Task<IEnumerable<string>> DiscoverExtensionsAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Loads an extension from the specified path
    /// </summary>
    /// <param name="extensionPath">Extension path</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Extension information</returns>
    Task<IExtensionInfo> LoadExtensionAsync(string extensionPath, CancellationToken cancellationToken = default);

    /// <summary>
    /// Unloads an extension
    /// </summary>
    /// <param name="extensionId">Extension ID</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the operation</returns>
    Task UnloadExtensionAsync(string extensionId, CancellationToken cancellationToken = default);

    /// <summary>
    /// Reloads an extension
    /// </summary>
    /// <param name="extensionId">Extension ID</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the operation</returns>
    Task ReloadExtensionAsync(string extensionId, CancellationToken cancellationToken = default);

    /// <summary>
    /// Validates an extension
    /// </summary>
    /// <param name="extensionPath">Extension path</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Validation result</returns>
    Task<ExtensionValidationResult> ValidateExtensionAsync(string extensionPath, CancellationToken cancellationToken = default);
}

/// <summary>
/// Information about a loaded extension
/// </summary>
public interface IExtensionInfo
{
    /// <summary>
    /// Gets the extension ID
    /// </summary>
    string Id { get; }

    /// <summary>
    /// Gets the extension name
    /// </summary>
    string Name { get; }

    /// <summary>
    /// Gets the extension version
    /// </summary>
    string Version { get; }

    /// <summary>
    /// Gets the extension author
    /// </summary>
    string Author { get; }

    /// <summary>
    /// Gets the extension description
    /// </summary>
    string Description { get; }

    /// <summary>
    /// Gets the extension path
    /// </summary>
    string Path { get; }

    /// <summary>
    /// Gets the extension type
    /// </summary>
    ExtensionType Type { get; }

    /// <summary>
    /// Gets the extension status
    /// </summary>
    ExtensionStatus Status { get; }

    /// <summary>
    /// Gets the load time
    /// </summary>
    DateTime LoadTime { get; }

    /// <summary>
    /// Gets the last activity time
    /// </summary>
    DateTime LastActivity { get; }

    /// <summary>
    /// Gets extension metadata
    /// </summary>
    Dictionary<string, object> Metadata { get; }

    /// <summary>
    /// Gets any load errors
    /// </summary>
    IReadOnlyList<string> LoadErrors { get; }
}

/// <summary>
/// WebSocket server for development tools communication
/// </summary>
public interface IWebSocketServer
{
    /// <summary>
    /// Gets a value indicating whether the server is running
    /// </summary>
    bool IsRunning { get; }

    /// <summary>
    /// Gets the server port
    /// </summary>
    int Port { get; }

    /// <summary>
    /// Gets the number of connected clients
    /// </summary>
    int ConnectedClients { get; }

    /// <summary>
    /// Starts the WebSocket server
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the startup</returns>
    Task StartAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Stops the WebSocket server
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the shutdown</returns>
    Task StopAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Broadcasts a message to all connected clients
    /// </summary>
    /// <param name="message">Message to broadcast</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the broadcast</returns>
    Task BroadcastAsync(string message, CancellationToken cancellationToken = default);

    /// <summary>
    /// Sends a message to a specific client
    /// </summary>
    /// <param name="clientId">Client ID</param>
    /// <param name="message">Message to send</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the send</returns>
    Task SendToClientAsync(string clientId, string message, CancellationToken cancellationToken = default);
}

/// <summary>
/// Manages hot-reload functionality
/// </summary>
public interface IHotReloadManager
{
    /// <summary>
    /// Gets a value indicating whether hot-reload is enabled
    /// </summary>
    bool IsEnabled { get; }

    /// <summary>
    /// Gets a value indicating whether hot-reload is active
    /// </summary>
    bool IsActive { get; }

    /// <summary>
    /// Gets the watched paths
    /// </summary>
    IReadOnlyList<string> WatchedPaths { get; }

    /// <summary>
    /// Starts hot-reload monitoring
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the startup</returns>
    Task StartAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Stops hot-reload monitoring
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the shutdown</returns>
    Task StopAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Adds a path to watch for changes
    /// </summary>
    /// <param name="path">Path to watch</param>
    /// <param name="recursive">Whether to watch recursively</param>
    void AddWatchPath(string path, bool recursive = true);

    /// <summary>
    /// Removes a watched path
    /// </summary>
    /// <param name="path">Path to stop watching</param>
    void RemoveWatchPath(string path);

    /// <summary>
    /// Forces a reload of all watched files
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the reload</returns>
    Task ForceReloadAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Manages memory usage and garbage collection
/// </summary>
public interface IMemoryManager
{
    /// <summary>
    /// Gets current memory usage information
    /// </summary>
    MemoryUsageInfo GetMemoryUsage();

    /// <summary>
    /// Gets memory manager statistics
    /// </summary>
    MemoryManagerStats Stats { get; }

    /// <summary>
    /// Starts memory monitoring
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the startup</returns>
    Task StartAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Stops memory monitoring
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the shutdown</returns>
    Task StopAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Forces garbage collection
    /// </summary>
    /// <param name="generation">GC generation to collect</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the GC</returns>
    Task ForceGarbageCollectionAsync(int? generation = null, CancellationToken cancellationToken = default);

    /// <summary>
    /// Sets the memory usage threshold for automatic cleanup
    /// </summary>
    /// <param name="thresholdMB">Threshold in MB</param>
    void SetMemoryThreshold(int thresholdMB);
}

/// <summary>
/// Extension types
/// </summary>
public enum ExtensionType
{
    PythonScript,
    CompiledPackage,
    NativeLibrary
}

/// <summary>
/// Extension status
/// </summary>
public enum ExtensionStatus
{
    Loading,
    Loaded,
    Failed,
    Unloading,
    Unloaded
}

/// <summary>
/// Result of extension validation
/// </summary>
public class ExtensionValidationResult
{
    /// <summary>
    /// Gets or sets a value indicating whether validation passed
    /// </summary>
    public bool IsValid { get; set; }

    /// <summary>
    /// Gets or sets validation errors
    /// </summary>
    public List<string> Errors { get; set; } = new();

    /// <summary>
    /// Gets or sets validation warnings
    /// </summary>
    public List<string> Warnings { get; set; } = new();

    /// <summary>
    /// Gets or sets security issues
    /// </summary>
    public List<string> SecurityIssues { get; set; } = new();

    /// <summary>
    /// Gets or sets extension metadata discovered during validation
    /// </summary>
    public Dictionary<string, object> Metadata { get; set; } = new();
}

/// <summary>
/// Statistics for the RevitPy host
/// </summary>
public class RevitPyHostStats
{
    /// <summary>
    /// Gets or sets the startup time
    /// </summary>
    public DateTime StartTime { get; set; }

    /// <summary>
    /// Gets or sets the uptime
    /// </summary>
    public TimeSpan Uptime { get; set; }

    /// <summary>
    /// Gets or sets the total number of Python executions
    /// </summary>
    public long TotalPythonExecutions { get; set; }

    /// <summary>
    /// Gets or sets the number of successful executions
    /// </summary>
    public long SuccessfulExecutions { get; set; }

    /// <summary>
    /// Gets or sets the number of failed executions
    /// </summary>
    public long FailedExecutions { get; set; }

    /// <summary>
    /// Gets or sets the average execution time
    /// </summary>
    public TimeSpan AverageExecutionTime { get; set; }

    /// <summary>
    /// Gets or sets the number of loaded extensions
    /// </summary>
    public int LoadedExtensions { get; set; }

    /// <summary>
    /// Gets or sets the memory usage
    /// </summary>
    public MemoryUsageInfo MemoryUsage { get; set; } = new();

    /// <summary>
    /// Gets or sets the last health check time
    /// </summary>
    public DateTime? LastHealthCheck { get; set; }

    /// <summary>
    /// Gets or sets the last reset time
    /// </summary>
    public DateTime? LastReset { get; set; }
}

/// <summary>
/// Extension manager statistics
/// </summary>
public class ExtensionManagerStats
{
    /// <summary>
    /// Gets or sets the total number of extensions discovered
    /// </summary>
    public long TotalDiscovered { get; set; }

    /// <summary>
    /// Gets or sets the total number of extensions loaded
    /// </summary>
    public long TotalLoaded { get; set; }

    /// <summary>
    /// Gets or sets the total number of load failures
    /// </summary>
    public long LoadFailures { get; set; }

    /// <summary>
    /// Gets or sets the average load time
    /// </summary>
    public TimeSpan AverageLoadTime { get; set; }

    /// <summary>
    /// Gets or sets the currently loaded extensions count
    /// </summary>
    public int CurrentlyLoaded { get; set; }

    /// <summary>
    /// Gets or sets the last discovery time
    /// </summary>
    public DateTime? LastDiscovery { get; set; }
}

/// <summary>
/// Memory usage information
/// </summary>
public class MemoryUsageInfo
{
    /// <summary>
    /// Gets or sets the total managed memory in bytes
    /// </summary>
    public long TotalManagedMemory { get; set; }

    /// <summary>
    /// Gets or sets the working set in bytes
    /// </summary>
    public long WorkingSet { get; set; }

    /// <summary>
    /// Gets or sets the private memory in bytes
    /// </summary>
    public long PrivateMemory { get; set; }

    /// <summary>
    /// Gets or sets the virtual memory in bytes
    /// </summary>
    public long VirtualMemory { get; set; }

    /// <summary>
    /// Gets or sets the Python memory usage
    /// </summary>
    public Dictionary<string, long> PythonMemory { get; set; } = new();

    /// <summary>
    /// Gets or sets the timestamp of this measurement
    /// </summary>
    public DateTime Timestamp { get; set; }
}

/// <summary>
/// Memory manager statistics
/// </summary>
public class MemoryManagerStats
{
    /// <summary>
    /// Gets or sets the number of automatic GC triggers
    /// </summary>
    public long AutomaticGcTriggers { get; set; }

    /// <summary>
    /// Gets or sets the number of manual GC calls
    /// </summary>
    public long ManualGcCalls { get; set; }

    /// <summary>
    /// Gets or sets the peak memory usage
    /// </summary>
    public long PeakMemoryUsage { get; set; }

    /// <summary>
    /// Gets or sets the current memory threshold
    /// </summary>
    public long CurrentThreshold { get; set; }

    /// <summary>
    /// Gets or sets the last cleanup time
    /// </summary>
    public DateTime? LastCleanup { get; set; }

    /// <summary>
    /// Gets or sets the average memory after cleanup
    /// </summary>
    public long AverageMemoryAfterCleanup { get; set; }
}

/// <summary>
/// Health information for the RevitPy host
/// </summary>
public class RevitPyHostHealth
{
    /// <summary>
    /// Gets or sets a value indicating whether the host is healthy
    /// </summary>
    public bool IsHealthy { get; set; }

    /// <summary>
    /// Gets or sets the health check timestamp
    /// </summary>
    public DateTime CheckedAt { get; set; }

    /// <summary>
    /// Gets or sets the component health results
    /// </summary>
    public Dictionary<string, ComponentHealth> Components { get; set; } = new();

    /// <summary>
    /// Gets or sets overall health issues
    /// </summary>
    public List<string> Issues { get; set; } = new();

    /// <summary>
    /// Gets or sets recommended actions
    /// </summary>
    public List<string> RecommendedActions { get; set; } = new();
}

/// <summary>
/// Health information for a component
/// </summary>
public class ComponentHealth
{
    /// <summary>
    /// Gets or sets the component name
    /// </summary>
    public string Name { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets a value indicating whether the component is healthy
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
    /// Gets or sets component-specific metrics
    /// </summary>
    public Dictionary<string, object> Metrics { get; set; } = new();
}