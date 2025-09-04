namespace RevitPy.Core.Logging;

/// <summary>
/// Structured logger interface for RevitPy components
/// </summary>
public interface IRevitPyLogger
{
    /// <summary>
    /// Logs a debug message
    /// </summary>
    /// <param name="message">The message to log</param>
    /// <param name="args">Message arguments</param>
    void LogDebug(string message, params object[] args);

    /// <summary>
    /// Logs an information message
    /// </summary>
    /// <param name="message">The message to log</param>
    /// <param name="args">Message arguments</param>
    void LogInfo(string message, params object[] args);

    /// <summary>
    /// Logs a warning message
    /// </summary>
    /// <param name="message">The message to log</param>
    /// <param name="args">Message arguments</param>
    void LogWarning(string message, params object[] args);

    /// <summary>
    /// Logs an error message
    /// </summary>
    /// <param name="message">The message to log</param>
    /// <param name="args">Message arguments</param>
    void LogError(string message, params object[] args);

    /// <summary>
    /// Logs an error with exception
    /// </summary>
    /// <param name="exception">The exception to log</param>
    /// <param name="message">The message to log</param>
    /// <param name="args">Message arguments</param>
    void LogError(Exception exception, string message, params object[] args);

    /// <summary>
    /// Logs a critical error message
    /// </summary>
    /// <param name="message">The message to log</param>
    /// <param name="args">Message arguments</param>
    void LogCritical(string message, params object[] args);

    /// <summary>
    /// Logs a critical error with exception
    /// </summary>
    /// <param name="exception">The exception to log</param>
    /// <param name="message">The message to log</param>
    /// <param name="args">Message arguments</param>
    void LogCritical(Exception exception, string message, params object[] args);

    /// <summary>
    /// Logs a performance metric
    /// </summary>
    /// <param name="metricName">Name of the metric</param>
    /// <param name="value">Metric value</param>
    /// <param name="unit">Metric unit</param>
    /// <param name="tags">Additional tags</param>
    void LogMetric(string metricName, double value, string unit = "count", Dictionary<string, object>? tags = null);

    /// <summary>
    /// Logs a Python-specific message
    /// </summary>
    /// <param name="level">Log level</param>
    /// <param name="pythonMessage">Message from Python</param>
    /// <param name="stackTrace">Python stack trace</param>
    void LogPython(LogLevel level, string pythonMessage, string? stackTrace = null);

    /// <summary>
    /// Begins a structured logging scope
    /// </summary>
    /// <param name="name">Scope name</param>
    /// <param name="properties">Scope properties</param>
    /// <returns>Disposable scope</returns>
    IDisposable BeginScope(string name, Dictionary<string, object>? properties = null);
}

/// <summary>
/// Log levels
/// </summary>
public enum LogLevel
{
    Debug,
    Information,
    Warning,
    Error,
    Critical
}