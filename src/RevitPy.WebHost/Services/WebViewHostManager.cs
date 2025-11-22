using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.DependencyInjection;
using RevitPy.WebHost.Models;

namespace RevitPy.WebHost.Services;

/// <summary>
/// Manages multiple WebView hosts and their lifecycle
/// </summary>
public class WebViewHostManager : IDisposable
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<WebViewHostManager> _logger;
    private readonly ConcurrentDictionary<string, IWebViewHost> _hosts = new();
    private bool _disposed;

    public event EventHandler<WebViewHostEventArgs>? HostCreated;
    public event EventHandler<WebViewHostEventArgs>? HostClosed;
    public event EventHandler<WebViewMessageEventArgs>? MessageReceived;

    public WebViewHostManager(IServiceProvider serviceProvider, ILogger<WebViewHostManager> logger)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
    }

    /// <summary>
    /// Create a new WebView host with the specified configuration
    /// </summary>
    public async Task<IWebViewHost> CreateHostAsync(WebViewConfiguration configuration)
    {
        if (_disposed) throw new ObjectDisposedException(nameof(WebViewHostManager));

        if (_hosts.ContainsKey(configuration.Id))
        {
            throw new InvalidOperationException($"Host with ID '{configuration.Id}' already exists");
        }

        try
        {
            var host = _serviceProvider.GetRequiredService<IWebViewHost>();

            // Set up event handlers
            host.MessageReceived += (s, message) =>
                MessageReceived?.Invoke(this, new WebViewMessageEventArgs(configuration.Id, message));

            host.WebViewClosed += (s, e) =>
            {
                _hosts.TryRemove(configuration.Id, out _);
                HostClosed?.Invoke(this, new WebViewHostEventArgs(configuration.Id, host));
            };

            await host.InitializeAsync(configuration);

            if (_hosts.TryAdd(configuration.Id, host))
            {
                HostCreated?.Invoke(this, new WebViewHostEventArgs(configuration.Id, host));
                _logger.LogInformation("Created WebView host {HostId}", configuration.Id);
                return host;
            }
            else
            {
                await host.CloseAsync();
                throw new InvalidOperationException($"Failed to register host with ID '{configuration.Id}'");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create WebView host {HostId}", configuration.Id);
            throw;
        }
    }

    /// <summary>
    /// Get an existing WebView host by ID
    /// </summary>
    public IWebViewHost? GetHost(string hostId)
    {
        return _hosts.TryGetValue(hostId, out var host) ? host : null;
    }

    /// <summary>
    /// Get all active WebView hosts
    /// </summary>
    public IReadOnlyCollection<IWebViewHost> GetAllHosts()
    {
        return _hosts.Values.ToList().AsReadOnly();
    }

    /// <summary>
    /// Close a specific WebView host
    /// </summary>
    public async Task CloseHostAsync(string hostId)
    {
        if (_hosts.TryRemove(hostId, out var host))
        {
            await host.CloseAsync();
            _logger.LogInformation("Closed WebView host {HostId}", hostId);
        }
    }

    /// <summary>
    /// Close all WebView hosts
    /// </summary>
    public async Task CloseAllHostsAsync()
    {
        var hosts = _hosts.Values.ToList();
        _hosts.Clear();

        var closeTasks = hosts.Select(async host =>
        {
            try
            {
                await host.CloseAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to close WebView host");
            }
        });

        await Task.WhenAll(closeTasks);
        _logger.LogInformation("Closed all WebView hosts ({Count})", hosts.Count);
    }

    /// <summary>
    /// Show a specific WebView host
    /// </summary>
    public async Task ShowHostAsync(string hostId)
    {
        if (_hosts.TryGetValue(hostId, out var host))
        {
            await host.ShowAsync();
        }
    }

    /// <summary>
    /// Hide a specific WebView host
    /// </summary>
    public async Task HideHostAsync(string hostId)
    {
        if (_hosts.TryGetValue(hostId, out var host))
        {
            await host.HideAsync();
        }
    }

    /// <summary>
    /// Send a message to a specific WebView host
    /// </summary>
    public async Task SendMessageAsync(string hostId, WebViewMessage message)
    {
        if (_hosts.TryGetValue(hostId, out var host))
        {
            await host.SendMessageAsync(message);
        }
    }

    /// <summary>
    /// Send a message to all WebView hosts
    /// </summary>
    public async Task BroadcastMessageAsync(WebViewMessage message)
    {
        var sendTasks = _hosts.Values.Select(async host =>
        {
            try
            {
                await host.SendMessageAsync(message);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to send broadcast message to WebView host");
            }
        });

        await Task.WhenAll(sendTasks);
    }

    /// <summary>
    /// Update data binding for a specific host
    /// </summary>
    public async Task UpdateDataBindingAsync(string hostId, string propertyPath, object? value)
    {
        if (_hosts.TryGetValue(hostId, out var host))
        {
            await host.UpdateDataBindingAsync(propertyPath, value);
        }
    }

    /// <summary>
    /// Update data binding for all hosts
    /// </summary>
    public async Task BroadcastDataBindingAsync(string propertyPath, object? value)
    {
        var updateTasks = _hosts.Values.Select(async host =>
        {
            try
            {
                await host.UpdateDataBindingAsync(propertyPath, value);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to update data binding for WebView host");
            }
        });

        await Task.WhenAll(updateTasks);
    }

    /// <summary>
    /// Enable development mode for a specific host
    /// </summary>
    public async Task SetDevelopmentModeAsync(string hostId, bool enable)
    {
        if (_hosts.TryGetValue(hostId, out var host))
        {
            await host.SetDevelopmentModeAsync(enable);
        }
    }

    /// <summary>
    /// Enable development mode for all hosts
    /// </summary>
    public async Task SetDevelopmentModeAllAsync(bool enable)
    {
        var tasks = _hosts.Values.Select(async host =>
        {
            try
            {
                await host.SetDevelopmentModeAsync(enable);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to set development mode for WebView host");
            }
        });

        await Task.WhenAll(tasks);
    }

    /// <summary>
    /// Get performance metrics from all hosts
    /// </summary>
    public async Task<Dictionary<string, PerformanceMetrics>> GetAllPerformanceMetricsAsync()
    {
        var results = new Dictionary<string, PerformanceMetrics>();

        var tasks = _hosts.Select(async kvp =>
        {
            try
            {
                var metrics = await kvp.Value.GetPerformanceMetricsAsync();
                return (kvp.Key, metrics);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to get performance metrics for host {HostId}", kvp.Key);
                return (kvp.Key, (PerformanceMetrics?)null);
            }
        });

        var metrics = await Task.WhenAll(tasks);

        foreach (var (hostId, metric) in metrics)
        {
            if (metric != null)
            {
                results[hostId] = metric;
            }
        }

        return results;
    }

    /// <summary>
    /// Create a panel group for related panels
    /// </summary>
    public async Task<PanelGroup> CreatePanelGroupAsync(string groupId, IEnumerable<WebViewConfiguration> configurations)
    {
        var hosts = new List<IWebViewHost>();

        foreach (var config in configurations)
        {
            try
            {
                var host = await CreateHostAsync(config);
                hosts.Add(host);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to create host {HostId} for panel group {GroupId}",
                    config.Id, groupId);

                // Clean up already created hosts on failure
                foreach (var createdHost in hosts)
                {
                    try
                    {
                        await createdHost.CloseAsync();
                    }
                    catch { }
                }
                throw;
            }
        }

        return new PanelGroup(groupId, hosts);
    }

    /// <summary>
    /// Check if a host exists
    /// </summary>
    public bool HostExists(string hostId)
    {
        return _hosts.ContainsKey(hostId);
    }

    /// <summary>
    /// Get the count of active hosts
    /// </summary>
    public int ActiveHostCount => _hosts.Count;

    /// <summary>
    /// Get host IDs
    /// </summary>
    public IEnumerable<string> GetHostIds()
    {
        return _hosts.Keys.ToList();
    }

    public void Dispose()
    {
        if (_disposed) return;

        try
        {
            CloseAllHostsAsync().Wait(TimeSpan.FromSeconds(5));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to close all hosts during disposal");
        }

        _disposed = true;
    }
}

/// <summary>
/// Event args for WebView host events
/// </summary>
public class WebViewHostEventArgs : EventArgs
{
    public string HostId { get; }
    public IWebViewHost Host { get; }

    public WebViewHostEventArgs(string hostId, IWebViewHost host)
    {
        HostId = hostId;
        Host = host;
    }
}

/// <summary>
/// Event args for WebView message events
/// </summary>
public class WebViewMessageEventArgs : EventArgs
{
    public string HostId { get; }
    public WebViewMessage Message { get; }

    public WebViewMessageEventArgs(string hostId, WebViewMessage message)
    {
        HostId = hostId;
        Message = message;
    }
}

/// <summary>
/// Represents a group of related panels
/// </summary>
public class PanelGroup
{
    public string Id { get; }
    public IReadOnlyList<IWebViewHost> Hosts { get; }

    public PanelGroup(string id, IEnumerable<IWebViewHost> hosts)
    {
        Id = id;
        Hosts = hosts.ToList().AsReadOnly();
    }

    /// <summary>
    /// Show all panels in the group
    /// </summary>
    public async Task ShowAllAsync()
    {
        var tasks = Hosts.Select(host => host.ShowAsync());
        await Task.WhenAll(tasks);
    }

    /// <summary>
    /// Hide all panels in the group
    /// </summary>
    public async Task HideAllAsync()
    {
        var tasks = Hosts.Select(host => host.HideAsync());
        await Task.WhenAll(tasks);
    }

    /// <summary>
    /// Close all panels in the group
    /// </summary>
    public async Task CloseAllAsync()
    {
        var tasks = Hosts.Select(host => host.CloseAsync());
        await Task.WhenAll(tasks);
    }

    /// <summary>
    /// Send a message to all panels in the group
    /// </summary>
    public async Task BroadcastMessageAsync(WebViewMessage message)
    {
        var tasks = Hosts.Select(host => host.SendMessageAsync(message));
        await Task.WhenAll(tasks);
    }
}
