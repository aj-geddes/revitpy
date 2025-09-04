using System;
using System.Threading.Tasks;
using RevitPy.WebHost.Models;

namespace RevitPy.WebHost.Services;

/// <summary>
/// Interface for WebView host service
/// </summary>
public interface IWebViewHost
{
    /// <summary>
    /// Event raised when a message is received from the WebView
    /// </summary>
    event EventHandler<WebViewMessage>? MessageReceived;

    /// <summary>
    /// Event raised when the WebView is ready
    /// </summary>
    event EventHandler? WebViewReady;

    /// <summary>
    /// Event raised when the WebView is closed
    /// </summary>
    event EventHandler? WebViewClosed;

    /// <summary>
    /// Event raised when navigation completes
    /// </summary>
    event EventHandler<string>? NavigationCompleted;

    /// <summary>
    /// Event raised when a script exception occurs
    /// </summary>
    event EventHandler<ScriptException>? ScriptException;

    /// <summary>
    /// Initialize the WebView host
    /// </summary>
    /// <param name="configuration">WebView configuration</param>
    /// <returns>Task representing the async operation</returns>
    Task InitializeAsync(WebViewConfiguration configuration);

    /// <summary>
    /// Show the WebView panel
    /// </summary>
    /// <returns>Task representing the async operation</returns>
    Task ShowAsync();

    /// <summary>
    /// Hide the WebView panel
    /// </summary>
    /// <returns>Task representing the async operation</returns>
    Task HideAsync();

    /// <summary>
    /// Close the WebView panel
    /// </summary>
    /// <returns>Task representing the async operation</returns>
    Task CloseAsync();

    /// <summary>
    /// Send a message to the WebView
    /// </summary>
    /// <param name="message">Message to send</param>
    /// <returns>Task representing the async operation</returns>
    Task SendMessageAsync(WebViewMessage message);

    /// <summary>
    /// Execute JavaScript in the WebView
    /// </summary>
    /// <param name="script">JavaScript code to execute</param>
    /// <returns>Result of the script execution</returns>
    Task<string> ExecuteScriptAsync(string script);

    /// <summary>
    /// Reload the WebView content
    /// </summary>
    /// <returns>Task representing the async operation</returns>
    Task ReloadAsync();

    /// <summary>
    /// Navigate to a new URL
    /// </summary>
    /// <param name="url">URL to navigate to</param>
    /// <returns>Task representing the async operation</returns>
    Task NavigateAsync(string url);

    /// <summary>
    /// Check if the WebView is initialized and ready
    /// </summary>
    bool IsReady { get; }

    /// <summary>
    /// Get the current URL
    /// </summary>
    string? CurrentUrl { get; }

    /// <summary>
    /// Get the WebView configuration
    /// </summary>
    WebViewConfiguration? Configuration { get; }

    /// <summary>
    /// Update data binding
    /// </summary>
    /// <param name="propertyPath">Property path</param>
    /// <param name="value">New value</param>
    /// <returns>Task representing the async operation</returns>
    Task UpdateDataBindingAsync(string propertyPath, object? value);

    /// <summary>
    /// Set up bi-directional data binding
    /// </summary>
    /// <param name="bindings">Property bindings</param>
    /// <returns>Task representing the async operation</returns>
    Task SetupDataBindingAsync(Dictionary<string, object> bindings);

    /// <summary>
    /// Enable development mode features
    /// </summary>
    /// <param name="enable">Whether to enable development mode</param>
    /// <returns>Task representing the async operation</returns>
    Task SetDevelopmentModeAsync(bool enable);

    /// <summary>
    /// Enable hot reload for development
    /// </summary>
    /// <param name="enable">Whether to enable hot reload</param>
    /// <param name="watchPath">Path to watch for changes</param>
    /// <returns>Task representing the async operation</returns>
    Task SetHotReloadAsync(bool enable, string? watchPath = null);

    /// <summary>
    /// Get performance metrics from the WebView
    /// </summary>
    /// <returns>Performance metrics</returns>
    Task<PerformanceMetrics> GetPerformanceMetricsAsync();

    /// <summary>
    /// Take a screenshot of the WebView
    /// </summary>
    /// <param name="format">Image format (png, jpeg)</param>
    /// <param name="quality">Image quality (0-100)</param>
    /// <returns>Screenshot as base64 string</returns>
    Task<string> TakeScreenshotAsync(string format = "png", int quality = 90);

    /// <summary>
    /// Print the WebView content
    /// </summary>
    /// <param name="settings">Print settings</param>
    /// <returns>Task representing the async operation</returns>
    Task PrintAsync(PrintSettings? settings = null);

    /// <summary>
    /// Register a custom scheme handler
    /// </summary>
    /// <param name="scheme">Scheme name</param>
    /// <param name="handler">Handler function</param>
    void RegisterSchemeHandler(string scheme, Func<string, Task<byte[]>> handler);

    /// <summary>
    /// Unregister a custom scheme handler
    /// </summary>
    /// <param name="scheme">Scheme name</param>
    void UnregisterSchemeHandler(string scheme);
}

/// <summary>
/// Print settings for WebView content
/// </summary>
public class PrintSettings
{
    /// <summary>
    /// Page size (A4, Letter, etc.)
    /// </summary>
    public string PageSize { get; set; } = "A4";

    /// <summary>
    /// Page orientation (portrait, landscape)
    /// </summary>
    public string Orientation { get; set; } = "portrait";

    /// <summary>
    /// Margins in inches
    /// </summary>
    public PrintMargins Margins { get; set; } = new();

    /// <summary>
    /// Whether to print background graphics
    /// </summary>
    public bool PrintBackgrounds { get; set; } = false;

    /// <summary>
    /// Scale factor (0.1 - 2.0)
    /// </summary>
    public double Scale { get; set; } = 1.0;

    /// <summary>
    /// Page ranges to print (e.g., "1-3,5")
    /// </summary>
    public string? PageRanges { get; set; }
}

/// <summary>
/// Print margins
/// </summary>
public class PrintMargins
{
    public double Top { get; set; } = 0.4;
    public double Bottom { get; set; } = 0.4;
    public double Left { get; set; } = 0.4;
    public double Right { get; set; } = 0.4;
}