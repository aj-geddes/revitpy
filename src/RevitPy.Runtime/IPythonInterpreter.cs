using RevitPy.Core.Exceptions;

namespace RevitPy.Runtime;

/// <summary>
/// Represents a Python interpreter instance
/// </summary>
public interface IPythonInterpreter : IDisposable
{
    /// <summary>
    /// Gets the interpreter ID
    /// </summary>
    string Id { get; }

    /// <summary>
    /// Gets a value indicating whether the interpreter is initialized
    /// </summary>
    bool IsInitialized { get; }

    /// <summary>
    /// Gets a value indicating whether the interpreter is busy
    /// </summary>
    bool IsBusy { get; }

    /// <summary>
    /// Gets the last activity timestamp
    /// </summary>
    DateTime LastActivity { get; }

    /// <summary>
    /// Initializes the Python interpreter
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the initialization</returns>
    Task InitializeAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Executes Python code
    /// </summary>
    /// <param name="code">Python code to execute</param>
    /// <param name="globals">Global variables</param>
    /// <param name="locals">Local variables</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Execution result</returns>
    Task<PythonExecutionResult> ExecuteAsync(
        string code, 
        Dictionary<string, object>? globals = null,
        Dictionary<string, object>? locals = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Evaluates Python expression
    /// </summary>
    /// <typeparam name="T">Expected return type</typeparam>
    /// <param name="expression">Python expression</param>
    /// <param name="globals">Global variables</param>
    /// <param name="locals">Local variables</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Evaluation result</returns>
    Task<T?> EvaluateAsync<T>(
        string expression,
        Dictionary<string, object>? globals = null,
        Dictionary<string, object>? locals = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Imports a Python module
    /// </summary>
    /// <param name="moduleName">Module name to import</param>
    /// <param name="alias">Optional alias for the module</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the import</returns>
    Task ImportModuleAsync(string moduleName, string? alias = null, CancellationToken cancellationToken = default);

    /// <summary>
    /// Adds a path to sys.path
    /// </summary>
    /// <param name="path">Path to add</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the operation</returns>
    Task AddPathAsync(string path, CancellationToken cancellationToken = default);

    /// <summary>
    /// Sets a variable in the global namespace
    /// </summary>
    /// <param name="name">Variable name</param>
    /// <param name="value">Variable value</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the operation</returns>
    Task SetVariableAsync(string name, object? value, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets a variable from the global namespace
    /// </summary>
    /// <typeparam name="T">Expected variable type</typeparam>
    /// <param name="name">Variable name</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Variable value</returns>
    Task<T?> GetVariableAsync<T>(string name, CancellationToken cancellationToken = default);

    /// <summary>
    /// Resets the interpreter state
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the reset</returns>
    Task ResetAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets memory usage information
    /// </summary>
    /// <returns>Memory usage information</returns>
    PythonMemoryInfo GetMemoryInfo();
}

/// <summary>
/// Result of Python code execution
/// </summary>
public class PythonExecutionResult
{
    /// <summary>
    /// Gets or sets a value indicating whether execution was successful
    /// </summary>
    public bool Success { get; set; }

    /// <summary>
    /// Gets or sets the return value
    /// </summary>
    public object? ReturnValue { get; set; }

    /// <summary>
    /// Gets or sets the standard output
    /// </summary>
    public string? StandardOutput { get; set; }

    /// <summary>
    /// Gets or sets the standard error
    /// </summary>
    public string? StandardError { get; set; }

    /// <summary>
    /// Gets or sets the execution time
    /// </summary>
    public TimeSpan ExecutionTime { get; set; }

    /// <summary>
    /// Gets or sets the exception if execution failed
    /// </summary>
    public Exception? Exception { get; set; }

    /// <summary>
    /// Gets or sets the Python stack trace
    /// </summary>
    public string? PythonStackTrace { get; set; }

    /// <summary>
    /// Gets or sets additional execution metadata
    /// </summary>
    public Dictionary<string, object>? Metadata { get; set; }
}

/// <summary>
/// Python interpreter memory information
/// </summary>
public class PythonMemoryInfo
{
    /// <summary>
    /// Gets or sets the allocated memory in bytes
    /// </summary>
    public long AllocatedBytes { get; set; }

    /// <summary>
    /// Gets or sets the peak allocated memory in bytes
    /// </summary>
    public long PeakAllocatedBytes { get; set; }

    /// <summary>
    /// Gets or sets the number of objects
    /// </summary>
    public long ObjectCount { get; set; }

    /// <summary>
    /// Gets or sets the number of active references
    /// </summary>
    public long ActiveReferences { get; set; }

    /// <summary>
    /// Gets or sets the garbage collection counts by generation
    /// </summary>
    public Dictionary<int, long> GcCounts { get; set; } = new();
}