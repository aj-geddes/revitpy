using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Core.Configuration;
using System.Collections.Concurrent;
using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

namespace RevitPy.Host;

/// <summary>
/// WebSocket server implementation for development tools communication
/// </summary>
public class WebSocketServer : IWebSocketServer, IDisposable
{
    private readonly ILogger<WebSocketServer> _logger;
    private readonly RevitPyOptions _options;
    private readonly ConcurrentDictionary<string, WebSocketConnection> _connections = new();
    
    private HttpListener? _httpListener;
    private CancellationTokenSource? _cancellationTokenSource;
    private Task? _serverTask;
    private bool _isDisposed;

    public bool IsRunning { get; private set; }
    public int Port => _options.DebugServerPort;
    public int ConnectedClients => _connections.Count;

    public WebSocketServer(ILogger<WebSocketServer> logger, IOptions<RevitPyOptions> options)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (IsRunning || !_options.EnableDebugServer)
            return;

        _logger.LogInformation("Starting WebSocket server on port {Port}", Port);

        try
        {
            _httpListener = new HttpListener();
            _httpListener.Prefixes.Add($"http://localhost:{Port}/");
            _httpListener.Start();

            _cancellationTokenSource = new CancellationTokenSource();
            _serverTask = AcceptConnectionsAsync(_cancellationTokenSource.Token);

            IsRunning = true;
            _logger.LogInformation("WebSocket server started successfully on port {Port}", Port);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to start WebSocket server on port {Port}", Port);
            throw;
        }
    }

    public async Task StopAsync(CancellationToken cancellationToken = default)
    {
        if (!IsRunning)
            return;

        _logger.LogInformation("Stopping WebSocket server");

        try
        {
            _cancellationTokenSource?.Cancel();
            _httpListener?.Stop();

            // Wait for server task to complete
            if (_serverTask != null)
            {
                await _serverTask.ConfigureAwait(false);
            }

            // Close all connections
            var closeTasks = _connections.Values.Select(conn => conn.CloseAsync());
            await Task.WhenAll(closeTasks);
            _connections.Clear();

            IsRunning = false;
            _logger.LogInformation("WebSocket server stopped");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error stopping WebSocket server");
        }
    }

    public async Task BroadcastAsync(string message, CancellationToken cancellationToken = default)
    {
        if (!IsRunning || string.IsNullOrWhiteSpace(message))
            return;

        var tasks = _connections.Values.Select(conn => 
            conn.SendAsync(message, cancellationToken));

        try
        {
            await Task.WhenAll(tasks);
        }
        catch (Exception ex)
        {
            _logger.LogWarning("Error broadcasting message: {Error}", ex.Message);
        }
    }

    public async Task SendToClientAsync(string clientId, string message, CancellationToken cancellationToken = default)
    {
        if (!IsRunning || string.IsNullOrWhiteSpace(clientId) || string.IsNullOrWhiteSpace(message))
            return;

        if (_connections.TryGetValue(clientId, out var connection))
        {
            try
            {
                await connection.SendAsync(message, cancellationToken);
            }
            catch (Exception ex)
            {
                _logger.LogWarning("Error sending message to client {ClientId}: {Error}", clientId, ex.Message);
            }
        }
        else
        {
            _logger.LogWarning("Client {ClientId} not found", clientId);
        }
    }

    private async Task AcceptConnectionsAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested && _httpListener != null)
        {
            try
            {
                var context = await _httpListener.GetContextAsync();
                _ = Task.Run(async () => await HandleConnectionAsync(context, cancellationToken), cancellationToken);
            }
            catch (HttpListenerException) when (cancellationToken.IsCancellationRequested)
            {
                // Expected when cancellation is requested
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error accepting WebSocket connection");
            }
        }
    }

    private async Task HandleConnectionAsync(HttpListenerContext context, CancellationToken cancellationToken)
    {
        if (!context.Request.IsWebSocketRequest)
        {
            context.Response.StatusCode = 400;
            context.Response.Close();
            return;
        }

        WebSocketConnection? connection = null;

        try
        {
            var webSocketContext = await context.AcceptWebSocketAsync(null);
            var clientId = Guid.NewGuid().ToString("N")[..8];
            
            connection = new WebSocketConnection(clientId, webSocketContext.WebSocket, _logger);
            _connections.TryAdd(clientId, connection);

            _logger.LogInformation("WebSocket client {ClientId} connected from {RemoteEndpoint}", 
                clientId, context.Request.RemoteEndPoint);

            // Send welcome message
            var welcomeMessage = JsonSerializer.Serialize(new
            {
                type = "welcome",
                clientId = clientId,
                serverVersion = "0.1.0",
                timestamp = DateTime.UtcNow
            });

            await connection.SendAsync(welcomeMessage, cancellationToken);

            // Handle messages from this connection
            await HandleClientMessagesAsync(connection, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error handling WebSocket connection");
        }
        finally
        {
            if (connection != null)
            {
                _connections.TryRemove(connection.Id, out _);
                await connection.CloseAsync();
                _logger.LogInformation("WebSocket client {ClientId} disconnected", connection.Id);
            }
        }
    }

    private async Task HandleClientMessagesAsync(WebSocketConnection connection, CancellationToken cancellationToken)
    {
        var buffer = new byte[4096];

        while (connection.State == WebSocketState.Open && !cancellationToken.IsCancellationRequested)
        {
            try
            {
                var result = await connection.WebSocket.ReceiveAsync(new ArraySegment<byte>(buffer), cancellationToken);

                if (result.MessageType == WebSocketMessageType.Close)
                {
                    break;
                }

                if (result.MessageType == WebSocketMessageType.Text)
                {
                    var message = Encoding.UTF8.GetString(buffer, 0, result.Count);
                    await ProcessClientMessage(connection, message, cancellationToken);
                }
            }
            catch (WebSocketException ex) when (ex.WebSocketErrorCode == WebSocketError.ConnectionClosedPrematurely)
            {
                // Client disconnected unexpectedly
                break;
            }
            catch (OperationCanceledException)
            {
                // Cancellation requested
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error receiving message from client {ClientId}", connection.Id);
                break;
            }
        }
    }

    private async Task ProcessClientMessage(WebSocketConnection connection, string message, CancellationToken cancellationToken)
    {
        try
        {
            var messageObj = JsonSerializer.Deserialize<JsonElement>(message);
            
            if (messageObj.TryGetProperty("type", out var typeElement))
            {
                var messageType = typeElement.GetString();
                
                switch (messageType)
                {
                    case "ping":
                        await connection.SendAsync(JsonSerializer.Serialize(new
                        {
                            type = "pong",
                            timestamp = DateTime.UtcNow
                        }), cancellationToken);
                        break;
                        
                    case "subscribe":
                        // Handle subscription to events
                        if (messageObj.TryGetProperty("events", out var eventsElement))
                        {
                            // Implementation for event subscriptions
                        }
                        break;
                        
                    case "execute":
                        // Handle Python code execution request
                        if (messageObj.TryGetProperty("code", out var codeElement))
                        {
                            var code = codeElement.GetString();
                            // This would integrate with the Python interpreter
                            // For now, just echo back
                            await connection.SendAsync(JsonSerializer.Serialize(new
                            {
                                type = "execution_result",
                                success = true,
                                result = "Code execution not implemented yet"
                            }), cancellationToken);
                        }
                        break;
                        
                    default:
                        _logger.LogWarning("Unknown message type from client {ClientId}: {MessageType}", 
                            connection.Id, messageType);
                        break;
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing message from client {ClientId}", connection.Id);
        }
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        _isDisposed = true;

        try
        {
            StopAsync().Wait(TimeSpan.FromSeconds(5));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error disposing WebSocket server");
        }

        _cancellationTokenSource?.Dispose();
        _httpListener?.Close();
    }
}

/// <summary>
/// Represents a WebSocket connection to a client
/// </summary>
internal class WebSocketConnection
{
    private readonly ILogger _logger;

    public string Id { get; }
    public WebSocket WebSocket { get; }
    public DateTime ConnectedAt { get; }
    public WebSocketState State => WebSocket.State;

    public WebSocketConnection(string id, WebSocket webSocket, ILogger logger)
    {
        Id = id;
        WebSocket = webSocket;
        _logger = logger;
        ConnectedAt = DateTime.UtcNow;
    }

    public async Task SendAsync(string message, CancellationToken cancellationToken = default)
    {
        if (WebSocket.State != WebSocketState.Open)
            return;

        try
        {
            var buffer = Encoding.UTF8.GetBytes(message);
            await WebSocket.SendAsync(
                new ArraySegment<byte>(buffer), 
                WebSocketMessageType.Text, 
                true, 
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error sending message to client {ClientId}", Id);
        }
    }

    public async Task CloseAsync()
    {
        try
        {
            if (WebSocket.State == WebSocketState.Open)
            {
                await WebSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Server shutdown", CancellationToken.None);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error closing WebSocket connection for client {ClientId}", Id);
        }
        finally
        {
            WebSocket?.Dispose();
        }
    }
}