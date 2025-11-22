namespace RevitPy.Host;

/// <summary>
/// Result of Python code execution
/// </summary>
public class PythonExecutionResult
{
    /// <summary>
    /// Gets or sets whether the execution was successful
    /// </summary>
    public bool IsSuccess { get; set; }

    /// <summary>
    /// Gets or sets the execution result value
    /// </summary>
    public object? Result { get; set; }

    /// <summary>
    /// Gets or sets any error that occurred
    /// </summary>
    public string? Error { get; set; }

    /// <summary>
    /// Gets or sets the execution time
    /// </summary>
    public TimeSpan ExecutionTime { get; set; }

    /// <summary>
    /// Gets or sets any output from the execution
    /// </summary>
    public string? Output { get; set; }

    /// <summary>
    /// Gets or sets any warnings from the execution
    /// </summary>
    public List<string> Warnings { get; set; } = new();

    /// <summary>
    /// Gets or sets execution metadata
    /// </summary>
    public Dictionary<string, object> Metadata { get; set; } = new();
}
