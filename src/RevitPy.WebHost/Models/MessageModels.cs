using System;
using System.Collections.Generic;
using System.Text.Json;

namespace RevitPy.WebHost.Models;

/// <summary>
/// Base message for communication between WebView and host
/// </summary>
public abstract class WebViewMessage
{
    /// <summary>
    /// Unique message identifier
    /// </summary>
    public string Id { get; set; } = Guid.NewGuid().ToString();

    /// <summary>
    /// Message type
    /// </summary>
    public string Type { get; set; } = string.Empty;

    /// <summary>
    /// Timestamp when the message was created
    /// </summary>
    public long Timestamp { get; set; } = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
}

/// <summary>
/// Request message from WebView to host
/// </summary>
public class WebViewRequest : WebViewMessage
{
    /// <summary>
    /// Method name to invoke
    /// </summary>
    public string Method { get; set; } = string.Empty;

    /// <summary>
    /// Parameters for the method call
    /// </summary>
    public Dictionary<string, object>? Parameters { get; set; }

    /// <summary>
    /// Callback identifier for response handling
    /// </summary>
    public string? CallbackId { get; set; }

    public WebViewRequest()
    {
        Type = "request";
    }
}

/// <summary>
/// Response message from host to WebView
/// </summary>
public class WebViewResponse : WebViewMessage
{
    /// <summary>
    /// Whether the operation was successful
    /// </summary>
    public bool Success { get; set; }

    /// <summary>
    /// Result data
    /// </summary>
    public object? Data { get; set; }

    /// <summary>
    /// Error information if operation failed
    /// </summary>
    public WebViewError? Error { get; set; }

    /// <summary>
    /// Original request ID this response corresponds to
    /// </summary>
    public string? RequestId { get; set; }

    /// <summary>
    /// Execution time in milliseconds
    /// </summary>
    public long ExecutionTime { get; set; }

    public WebViewResponse()
    {
        Type = "response";
    }
}

/// <summary>
/// Notification message from host to WebView
/// </summary>
public class WebViewNotification : WebViewMessage
{
    /// <summary>
    /// Event name
    /// </summary>
    public string Event { get; set; } = string.Empty;

    /// <summary>
    /// Event data
    /// </summary>
    public object? Data { get; set; }

    /// <summary>
    /// Event source
    /// </summary>
    public string Source { get; set; } = string.Empty;

    public WebViewNotification()
    {
        Type = "notification";
    }
}

/// <summary>
/// Error information
/// </summary>
public class WebViewError
{
    /// <summary>
    /// Error code
    /// </summary>
    public string Code { get; set; } = string.Empty;

    /// <summary>
    /// Error message
    /// </summary>
    public string Message { get; set; } = string.Empty;

    /// <summary>
    /// Detailed error information
    /// </summary>
    public string? Details { get; set; }

    /// <summary>
    /// Stack trace if available
    /// </summary>
    public string? StackTrace { get; set; }

    /// <summary>
    /// Additional context data
    /// </summary>
    public Dictionary<string, object>? Context { get; set; }
}

/// <summary>
/// Data binding message for real-time updates
/// </summary>
public class DataBindingMessage : WebViewMessage
{
    /// <summary>
    /// Property path that changed
    /// </summary>
    public string PropertyPath { get; set; } = string.Empty;

    /// <summary>
    /// New value
    /// </summary>
    public object? Value { get; set; }

    /// <summary>
    /// Previous value
    /// </summary>
    public object? OldValue { get; set; }

    /// <summary>
    /// Source of the change (host or webview)
    /// </summary>
    public string Source { get; set; } = string.Empty;

    public DataBindingMessage()
    {
        Type = "databinding";
    }
}

/// <summary>
/// Hot reload message for development
/// </summary>
public class HotReloadMessage : WebViewMessage
{
    /// <summary>
    /// Type of change (file, css, js, etc.)
    /// </summary>
    public string ChangeType { get; set; } = string.Empty;

    /// <summary>
    /// Files that changed
    /// </summary>
    public List<string> Files { get; set; } = new();

    /// <summary>
    /// Whether a full reload is required
    /// </summary>
    public bool FullReload { get; set; } = false;

    public HotReloadMessage()
    {
        Type = "hotreload";
    }
}

/// <summary>
/// Performance metrics message
/// </summary>
public class PerformanceMetrics : WebViewMessage
{
    /// <summary>
    /// Memory usage in bytes
    /// </summary>
    public long MemoryUsage { get; set; }

    /// <summary>
    /// CPU usage percentage
    /// </summary>
    public double CpuUsage { get; set; }

    /// <summary>
    /// Number of DOM nodes
    /// </summary>
    public int DomNodes { get; set; }

    /// <summary>
    /// JavaScript heap size
    /// </summary>
    public long JsHeapSize { get; set; }

    /// <summary>
    /// Frame rate
    /// </summary>
    public double FrameRate { get; set; }

    /// <summary>
    /// Network requests count
    /// </summary>
    public int NetworkRequests { get; set; }

    public PerformanceMetrics()
    {
        Type = "performance";
    }
}

/// <summary>
/// Console message from WebView
/// </summary>
public class ConsoleMessage : WebViewMessage
{
    /// <summary>
    /// Log level (log, info, warn, error, debug)
    /// </summary>
    public string Level { get; set; } = string.Empty;

    /// <summary>
    /// Console message
    /// </summary>
    public string Message { get; set; } = string.Empty;

    /// <summary>
    /// Source file
    /// </summary>
    public string? Source { get; set; }

    /// <summary>
    /// Line number
    /// </summary>
    public int? Line { get; set; }

    /// <summary>
    /// Arguments passed to console method
    /// </summary>
    public List<object>? Arguments { get; set; }

    public ConsoleMessage()
    {
        Type = "console";
    }
}

/// <summary>
/// JavaScript exception message
/// </summary>
public class ScriptException : WebViewMessage
{
    /// <summary>
    /// Exception name
    /// </summary>
    public string Name { get; set; } = string.Empty;

    /// <summary>
    /// Exception message
    /// </summary>
    public string Message { get; set; } = string.Empty;

    /// <summary>
    /// Stack trace
    /// </summary>
    public string? Stack { get; set; }

    /// <summary>
    /// Source file
    /// </summary>
    public string? Source { get; set; }

    /// <summary>
    /// Line number
    /// </summary>
    public int? Line { get; set; }

    /// <summary>
    /// Column number
    /// </summary>
    public int? Column { get; set; }

    public ScriptException()
    {
        Type = "exception";
    }
}
