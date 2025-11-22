using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using Microsoft.Extensions.Logging;
using RevitPy.WebHost.Models;

namespace RevitPy.WebHost.Services;

/// <summary>
/// WebView2-based host for RevitPy web panels
/// </summary>
public class WebViewHost : IWebViewHost, IDisposable
{
    private readonly ILogger<WebViewHost> _logger;
    private WebView2? _webView;
    private Form? _hostForm;
    private WebViewConfiguration? _configuration;
    private readonly Dictionary<string, Func<string, Task<byte[]>>> _schemeHandlers = new();
    private FileSystemWatcher? _fileWatcher;
    private bool _disposed;

    public event EventHandler<WebViewMessage>? MessageReceived;
    public event EventHandler? WebViewReady;
    public event EventHandler? WebViewClosed;
    public event EventHandler<string>? NavigationCompleted;
    public event EventHandler<ScriptException>? ScriptException;

    public bool IsReady => _webView?.CoreWebView2 != null;
    public string? CurrentUrl => _webView?.Source?.ToString();
    public WebViewConfiguration? Configuration => _configuration;

    public WebViewHost(ILogger<WebViewHost> logger)
    {
        _logger = logger;
    }

    public async Task InitializeAsync(WebViewConfiguration configuration)
    {
        _configuration = configuration ?? throw new ArgumentNullException(nameof(configuration));

        try
        {
            // Create WebView2 control
            _webView = new WebView2
            {
                Dock = DockStyle.Fill
            };

            // Create host form based on panel type
            _hostForm = CreateHostForm();
            _hostForm.Controls.Add(_webView);

            // Initialize WebView2
            var env = await CoreWebView2Environment.CreateAsync(
                browserExecutableFolder: null,
                userDataFolder: _configuration.WebView2.UserDataFolder,
                options: CreateWebViewOptions());

            await _webView.EnsureCoreWebView2Async(env);

            // Configure WebView2 settings
            ConfigureWebViewSettings();

            // Set up event handlers
            SetupEventHandlers();

            // Set up custom scheme handlers
            SetupSchemeHandlers();

            // Set up data binding
            await SetupDataBindingAsync(_configuration.Context);

            // Navigate to initial URL
            if (!string.IsNullOrEmpty(_configuration.Url))
            {
                await NavigateAsync(_configuration.Url);
            }

            // Enable development features if needed
            if (_configuration.DevelopmentMode)
            {
                await SetDevelopmentModeAsync(true);
            }

            if (_configuration.HotReload)
            {
                await SetHotReloadAsync(true);
            }

            _logger.LogInformation("WebView host initialized for panel {PanelId}", _configuration.Id);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to initialize WebView host for panel {PanelId}", _configuration.Id);
            throw;
        }
    }

    public Task ShowAsync()
    {
        if (_hostForm != null && !_hostForm.Visible)
        {
            _hostForm.Show();
            _logger.LogDebug("WebView panel {PanelId} shown", _configuration?.Id);
        }
        return Task.CompletedTask;
    }

    public Task HideAsync()
    {
        if (_hostForm != null && _hostForm.Visible)
        {
            _hostForm.Hide();
            _logger.LogDebug("WebView panel {PanelId} hidden", _configuration?.Id);
        }
        return Task.CompletedTask;
    }

    public Task CloseAsync()
    {
        _hostForm?.Close();
        _logger.LogDebug("WebView panel {PanelId} closed", _configuration?.Id);
        return Task.CompletedTask;
    }

    public async Task SendMessageAsync(WebViewMessage message)
    {
        if (!IsReady) return;

        try
        {
            var json = JsonSerializer.Serialize(message);
            var script = $"window.revitpy?.receiveMessage({json});";
            await _webView!.ExecuteScriptAsync(script);

            _logger.LogDebug("Sent message to WebView: {MessageType} {MessageId}",
                message.Type, message.Id);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send message to WebView");
            throw;
        }
    }

    public async Task<string> ExecuteScriptAsync(string script)
    {
        if (!IsReady) throw new InvalidOperationException("WebView is not ready");

        try
        {
            var result = await _webView!.ExecuteScriptAsync(script);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to execute script in WebView");
            throw;
        }
    }

    public Task ReloadAsync()
    {
        if (!IsReady) return Task.CompletedTask;

        _webView!.Reload();
        return Task.CompletedTask;
    }

    public async Task NavigateAsync(string url)
    {
        if (!IsReady) return;

        try
        {
            _webView!.Source = new Uri(url);
            await Task.CompletedTask;
            _logger.LogDebug("Navigated to {Url}", url);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to navigate to {Url}", url);
            throw;
        }
    }

    public async Task UpdateDataBindingAsync(string propertyPath, object? value)
    {
        if (!IsReady) return;

        var message = new DataBindingMessage
        {
            PropertyPath = propertyPath,
            Value = value,
            Source = "host"
        };

        await SendMessageAsync(message);
    }

    public async Task SetupDataBindingAsync(Dictionary<string, object> bindings)
    {
        if (!IsReady) return;

        foreach (var binding in bindings)
        {
            await UpdateDataBindingAsync(binding.Key, binding.Value);
        }
    }

    public async Task SetDevelopmentModeAsync(bool enable)
    {
        if (!IsReady) return;

        _webView!.CoreWebView2.Settings.AreDevToolsEnabled = enable;
        _webView.CoreWebView2.Settings.AreDefaultScriptDialogsEnabled = enable;

        if (enable)
        {
            // Inject development helpers
            await ExecuteScriptAsync(@"
                window.revitpy = window.revitpy || {};
                window.revitpy.dev = true;
                console.log('RevitPy development mode enabled');
            ");
        }
    }

    public async Task SetHotReloadAsync(bool enable, string? watchPath = null)
    {
        if (enable && !string.IsNullOrEmpty(watchPath) && Directory.Exists(watchPath))
        {
            _fileWatcher?.Dispose();
            _fileWatcher = new FileSystemWatcher(watchPath)
            {
                IncludeSubdirectories = true,
                NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.Size | NotifyFilters.FileName
            };

            _fileWatcher.Changed += OnFileChanged;
            _fileWatcher.Created += OnFileChanged;
            _fileWatcher.Deleted += OnFileChanged;
            _fileWatcher.EnableRaisingEvents = true;

            await ExecuteScriptAsync(@"
                window.revitpy = window.revitpy || {};
                window.revitpy.hotReload = true;
                console.log('RevitPy hot reload enabled');
            ");
        }
        else
        {
            _fileWatcher?.Dispose();
            _fileWatcher = null;
        }
    }

    public async Task<PerformanceMetrics> GetPerformanceMetricsAsync()
    {
        if (!IsReady) throw new InvalidOperationException("WebView is not ready");

        var script = @"
            JSON.stringify({
                memory: performance.memory ? {
                    used: performance.memory.usedJSHeapSize,
                    total: performance.memory.totalJSHeapSize,
                    limit: performance.memory.jsHeapSizeLimit
                } : null,
                navigation: performance.navigation,
                timing: performance.timing
            });
        ";

        var result = await ExecuteScriptAsync(script);
        var data = JsonSerializer.Deserialize<Dictionary<string, object>>(result);

        return new PerformanceMetrics
        {
            MemoryUsage = data.ContainsKey("memory") ?
                ((JsonElement)data["memory"]).GetProperty("used").GetInt64() : 0,
            JsHeapSize = data.ContainsKey("memory") ?
                ((JsonElement)data["memory"]).GetProperty("total").GetInt64() : 0
        };
    }

    public async Task<string> TakeScreenshotAsync(string format = "png", int quality = 90)
    {
        if (!IsReady) throw new InvalidOperationException("WebView is not ready");

        using var stream = await _webView!.CoreWebView2.CapturePreviewAsync(
            format == "png" ? CoreWebView2CapturePreviewImageFormat.Png :
            CoreWebView2CapturePreviewImageFormat.Jpeg);

        using var memoryStream = new MemoryStream();
        stream.CopyTo(memoryStream);
        return Convert.ToBase64String(memoryStream.ToArray());
    }

    public async Task PrintAsync(PrintSettings? settings = null)
    {
        if (!IsReady) throw new InvalidOperationException("WebView is not ready");

        await _webView!.CoreWebView2.PrintAsync();
    }

    public void RegisterSchemeHandler(string scheme, Func<string, Task<byte[]>> handler)
    {
        _schemeHandlers[scheme] = handler;
    }

    public void UnregisterSchemeHandler(string scheme)
    {
        _schemeHandlers.Remove(scheme);
    }

    private Form CreateHostForm()
    {
        var form = new Form
        {
            Text = _configuration!.Title,
            Size = new System.Drawing.Size(_configuration.Size.Width, _configuration.Size.Height),
            StartPosition = FormStartPosition.CenterScreen,
            ShowInTaskbar = _configuration.Type != PanelType.Dockable,
            TopMost = _configuration.Type == PanelType.Modal,
            FormBorderStyle = _configuration.Resizable ?
                FormBorderStyle.Sizable : FormBorderStyle.FixedDialog,
            ControlBox = _configuration.Closable,
            MinimizeBox = _configuration.Type != PanelType.Modal,
            MaximizeBox = _configuration.Resizable && _configuration.Type != PanelType.Modal
        };

        if (_configuration.Size.MinWidth.HasValue)
        {
            form.MinimumSize = new System.Drawing.Size(
                _configuration.Size.MinWidth.Value,
                _configuration.Size.MinHeight ?? form.MinimumSize.Height);
        }

        form.FormClosed += (s, e) => WebViewClosed?.Invoke(this, EventArgs.Empty);

        return form;
    }

    private CoreWebView2EnvironmentOptions CreateWebViewOptions()
    {
        var options = CoreWebView2Environment.CreateCoreWebView2EnvironmentOptions();

        if (!string.IsNullOrEmpty(_configuration!.WebView2.UserAgent))
        {
            options.AdditionalBrowserArguments = $"--user-agent=\"{_configuration.WebView2.UserAgent}\"";
        }

        if (_configuration.WebView2.AdditionalBrowserArguments.Count > 0)
        {
            options.AdditionalBrowserArguments += " " +
                string.Join(" ", _configuration.WebView2.AdditionalBrowserArguments);
        }

        return options;
    }

    private void ConfigureWebViewSettings()
    {
        var settings = _webView!.CoreWebView2.Settings;

        settings.AreDevToolsEnabled = _configuration!.WebView2.DevToolsEnabled;
        settings.IsScriptDebuggingEnabled = _configuration.WebView2.ScriptDebuggingEnabled;
        settings.AreDefaultContextMenusEnabled = _configuration.WebView2.ContextMenuEnabled;
        settings.IsZoomControlEnabled = _configuration.WebView2.ZoomControlEnabled;
        settings.UserAgent = _configuration.WebView2.UserAgent ?? settings.UserAgent;

        // Set default background color
        _webView.CoreWebView2.Profile.DefaultBackgroundColor =
            System.Drawing.ColorTranslator.FromHtml(_configuration.WebView2.BackgroundColor);
    }

    private void SetupEventHandlers()
    {
        _webView!.NavigationCompleted += (s, e) =>
        {
            NavigationCompleted?.Invoke(this, CurrentUrl ?? string.Empty);
            WebViewReady?.Invoke(this, EventArgs.Empty);
        };

        _webView.CoreWebView2.WebMessageReceived += async (s, e) =>
        {
            try
            {
                var messageJson = e.TryGetWebMessageAsString();
                var message = JsonSerializer.Deserialize<WebViewMessage>(messageJson);

                if (message != null)
                {
                    MessageReceived?.Invoke(this, message);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to process WebView message");
            }
        };

        _webView.CoreWebView2.ScriptException += (s, e) =>
        {
            var exception = new ScriptException
            {
                Name = e.Name,
                Message = e.Message,
                Source = e.Source,
                Line = (int)e.LineNumber,
                Column = (int)e.ColumnNumber
            };

            ScriptException?.Invoke(this, exception);
        };
    }

    private void SetupSchemeHandlers()
    {
        foreach (var scheme in _schemeHandlers.Keys)
        {
            _webView!.CoreWebView2.AddWebResourceRequestedFilter($"{scheme}://*",
                CoreWebView2WebResourceContext.All);
        }

        _webView!.CoreWebView2.WebResourceRequested += async (s, e) =>
        {
            var uri = e.Request.Uri;
            var scheme = new Uri(uri).Scheme;

            if (_schemeHandlers.TryGetValue(scheme, out var handler))
            {
                try
                {
                    var content = await handler(uri);
                    var response = _webView.CoreWebView2.Environment.CreateWebResourceResponse(
                        new MemoryStream(content), 200, "OK", "");
                    e.Response = response;
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to handle custom scheme {Scheme}", scheme);
                }
            }
        };
    }

    private async void OnFileChanged(object sender, FileSystemEventArgs e)
    {
        if (_disposed || !IsReady) return;

        try
        {
            await Task.Delay(100); // Debounce file changes

            var message = new HotReloadMessage
            {
                ChangeType = Path.GetExtension(e.Name).ToLowerInvariant(),
                Files = new List<string> { e.FullPath },
                FullReload = Path.GetExtension(e.Name).ToLowerInvariant() == ".html"
            };

            await SendMessageAsync(message);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to handle file change for hot reload");
        }
    }

    public void Dispose()
    {
        if (_disposed) return;

        _fileWatcher?.Dispose();
        _webView?.Dispose();
        _hostForm?.Dispose();

        _disposed = true;
    }
}
