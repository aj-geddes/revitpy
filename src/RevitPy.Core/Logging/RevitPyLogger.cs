using Microsoft.Extensions.Logging;
using System.Text.Json;

namespace RevitPy.Core.Logging;

/// <summary>
/// Implementation of IRevitPyLogger that wraps Microsoft.Extensions.Logging
/// </summary>
public class RevitPyLogger : IRevitPyLogger
{
    private readonly ILogger _logger;
    private readonly string _categoryName;

    public RevitPyLogger(ILogger logger, string categoryName = "RevitPy")
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _categoryName = categoryName;
    }

    public void LogDebug(string message, params object[] args)
    {
        _logger.LogDebug(message, args);
    }

    public void LogInfo(string message, params object[] args)
    {
        _logger.LogInformation(message, args);
    }

    public void LogWarning(string message, params object[] args)
    {
        _logger.LogWarning(message, args);
    }

    public void LogError(string message, params object[] args)
    {
        _logger.LogError(message, args);
    }

    public void LogError(Exception exception, string message, params object[] args)
    {
        _logger.LogError(exception, message, args);
    }

    public void LogCritical(string message, params object[] args)
    {
        _logger.LogCritical(message, args);
    }

    public void LogCritical(Exception exception, string message, params object[] args)
    {
        _logger.LogCritical(exception, message, args);
    }

    public void LogMetric(string metricName, double value, string unit = "count", Dictionary<string, object>? tags = null)
    {
        var metricData = new Dictionary<string, object>
        {
            ["metric"] = metricName,
            ["value"] = value,
            ["unit"] = unit,
            ["timestamp"] = DateTime.UtcNow
        };

        if (tags != null)
        {
            metricData["tags"] = tags;
        }

        var message = "Metric: {MetricName} = {Value} {Unit}";
        var args = new object[] { metricName, value, unit };

        using var scope = BeginScope("Metrics", metricData);
        _logger.LogInformation(message, args);
    }

    public void LogPython(LogLevel level, string pythonMessage, string? stackTrace = null)
    {
        var logLevel = ConvertLogLevel(level);
        var message = "Python: {PythonMessage}";
        var args = new object[] { pythonMessage };

        if (!string.IsNullOrWhiteSpace(stackTrace))
        {
            var pythonData = new Dictionary<string, object>
            {
                ["python_message"] = pythonMessage,
                ["python_stack_trace"] = stackTrace,
                ["source"] = "python"
            };

            using var scope = BeginScope("Python", pythonData);
            _logger.Log(logLevel, message + Environment.NewLine + "Stack trace: {StackTrace}", 
                pythonMessage, stackTrace);
        }
        else
        {
            using var scope = BeginScope("Python", new Dictionary<string, object>
            {
                ["source"] = "python"
            });
            _logger.Log(logLevel, message, args);
        }
    }

    public IDisposable BeginScope(string name, Dictionary<string, object>? properties = null)
    {
        var scopeData = new Dictionary<string, object>
        {
            ["scope_name"] = name,
            ["scope_id"] = Guid.NewGuid().ToString("N")[..8],
            ["started_at"] = DateTime.UtcNow
        };

        if (properties != null)
        {
            foreach (var kvp in properties)
            {
                scopeData[kvp.Key] = kvp.Value;
            }
        }

        return _logger.BeginScope(scopeData);
    }

    private static Microsoft.Extensions.Logging.LogLevel ConvertLogLevel(LogLevel level)
    {
        return level switch
        {
            LogLevel.Debug => Microsoft.Extensions.Logging.LogLevel.Debug,
            LogLevel.Information => Microsoft.Extensions.Logging.LogLevel.Information,
            LogLevel.Warning => Microsoft.Extensions.Logging.LogLevel.Warning,
            LogLevel.Error => Microsoft.Extensions.Logging.LogLevel.Error,
            LogLevel.Critical => Microsoft.Extensions.Logging.LogLevel.Critical,
            _ => Microsoft.Extensions.Logging.LogLevel.Information
        };
    }
}

/// <summary>
/// Factory for creating RevitPy loggers
/// </summary>
public class RevitPyLoggerFactory
{
    private readonly ILoggerFactory _loggerFactory;

    public RevitPyLoggerFactory(ILoggerFactory loggerFactory)
    {
        _loggerFactory = loggerFactory ?? throw new ArgumentNullException(nameof(loggerFactory));
    }

    /// <summary>
    /// Creates a logger for the specified category
    /// </summary>
    /// <param name="categoryName">Category name</param>
    /// <returns>RevitPy logger instance</returns>
    public IRevitPyLogger CreateLogger(string categoryName)
    {
        var logger = _loggerFactory.CreateLogger(categoryName);
        return new RevitPyLogger(logger, categoryName);
    }

    /// <summary>
    /// Creates a logger for the specified type
    /// </summary>
    /// <typeparam name="T">Type to create logger for</typeparam>
    /// <returns>RevitPy logger instance</returns>
    public IRevitPyLogger CreateLogger<T>()
    {
        return CreateLogger(typeof(T).FullName ?? typeof(T).Name);
    }
}

/// <summary>
/// Structured log event that can be serialized
/// </summary>
public class StructuredLogEvent
{
    /// <summary>
    /// Gets or sets the timestamp
    /// </summary>
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;

    /// <summary>
    /// Gets or sets the log level
    /// </summary>
    public string Level { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the category
    /// </summary>
    public string Category { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the message
    /// </summary>
    public string Message { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the exception information
    /// </summary>
    public string? Exception { get; set; }

    /// <summary>
    /// Gets or sets the scope information
    /// </summary>
    public Dictionary<string, object>? Scope { get; set; }

    /// <summary>
    /// Gets or sets additional properties
    /// </summary>
    public Dictionary<string, object>? Properties { get; set; }

    /// <summary>
    /// Gets or sets the thread ID
    /// </summary>
    public int ThreadId { get; set; } = Thread.CurrentThread.ManagedThreadId;

    /// <summary>
    /// Serializes the log event to JSON
    /// </summary>
    /// <returns>JSON representation</returns>
    public string ToJson()
    {
        var options = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            WriteIndented = false
        };
        
        return JsonSerializer.Serialize(this, options);
    }
}

/// <summary>
/// Log event sink that can be used to capture and forward log events
/// </summary>
public interface ILogEventSink
{
    /// <summary>
    /// Processes a log event
    /// </summary>
    /// <param name="logEvent">Log event to process</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the processing</returns>
    Task ProcessLogEventAsync(StructuredLogEvent logEvent, CancellationToken cancellationToken = default);
}

/// <summary>
/// File-based log event sink
/// </summary>
public class FileLogEventSink : ILogEventSink, IDisposable
{
    private readonly string _filePath;
    private readonly SemaphoreSlim _semaphore = new(1, 1);
    private bool _isDisposed;

    public FileLogEventSink(string filePath)
    {
        _filePath = filePath ?? throw new ArgumentNullException(nameof(filePath));
        
        // Ensure directory exists
        var directory = Path.GetDirectoryName(_filePath);
        if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
        {
            Directory.CreateDirectory(directory);
        }
    }

    public async Task ProcessLogEventAsync(StructuredLogEvent logEvent, CancellationToken cancellationToken = default)
    {
        if (_isDisposed)
            return;

        await _semaphore.WaitAsync(cancellationToken);

        try
        {
            var json = logEvent.ToJson();
            await File.AppendAllTextAsync(_filePath, json + Environment.NewLine, cancellationToken);
        }
        finally
        {
            _semaphore.Release();
        }
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        _isDisposed = true;
        _semaphore.Dispose();
    }
}

/// <summary>
/// WebSocket log event sink for real-time log streaming
/// </summary>
public class WebSocketLogEventSink : ILogEventSink
{
    private readonly IWebSocketServer? _webSocketServer;

    public WebSocketLogEventSink(IWebSocketServer? webSocketServer)
    {
        _webSocketServer = webSocketServer;
    }

    public async Task ProcessLogEventAsync(StructuredLogEvent logEvent, CancellationToken cancellationToken = default)
    {
        if (_webSocketServer?.IsRunning != true)
            return;

        try
        {
            var message = JsonSerializer.Serialize(new
            {
                type = "log_event",
                data = logEvent
            });

            await _webSocketServer.BroadcastAsync(message, cancellationToken);
        }
        catch (Exception)
        {
            // Ignore errors - logging should not fail the application
        }
    }
}