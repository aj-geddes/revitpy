using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Core.Configuration;
using RevitPy.Runtime;
using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;

namespace RevitPy.Host;

/// <summary>
/// Manages hot-reload functionality for development
/// </summary>
public class HotReloadManager : IHotReloadManager, IDisposable
{
    private readonly ILogger<HotReloadManager> _logger;
    private readonly RevitPyOptions _options;
    private readonly IPythonInterpreterPool _interpreterPool;
    private readonly IWebSocketServer? _webSocketServer;
    private readonly ConcurrentDictionary<string, FileWatcher> _watchers = new();
    private readonly ConcurrentDictionary<string, FileInfo> _watchedFiles = new();
    private readonly Timer _debounceTimer;
    private readonly ConcurrentQueue<FileChangeEvent> _pendingChanges = new();
    
    private bool _isActive;
    private bool _isDisposed;
    private HotReloadStats _stats = new();
    private readonly object _statsLock = new();

    public bool IsEnabled => _options.EnableHotReload;
    public bool IsActive => _isActive;
    public IReadOnlyList<string> WatchedPaths => _watchers.Keys.ToList().AsReadOnly();

    public HotReloadStats Stats
    {
        get
        {
            lock (_statsLock)
            {
                return new HotReloadStats
                {
                    TotalReloads = _stats.TotalReloads,
                    SuccessfulReloads = _stats.SuccessfulReloads,
                    FailedReloads = _stats.FailedReloads,
                    AverageReloadTime = _stats.AverageReloadTime,
                    LastReload = _stats.LastReload,
                    WatchedFileCount = _watchedFiles.Count,
                    WatchedDirectoryCount = _watchers.Count
                };
            }
        }
    }

    public HotReloadManager(
        ILogger<HotReloadManager> logger,
        IOptions<RevitPyOptions> options,
        IPythonInterpreterPool interpreterPool,
        IWebSocketServer? webSocketServer = null)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        _interpreterPool = interpreterPool ?? throw new ArgumentNullException(nameof(interpreterPool));
        _webSocketServer = webSocketServer;

        // Initialize debounce timer for batching file changes
        _debounceTimer = new Timer(
            async _ => await ProcessPendingChangesAsync(),
            null,
            Timeout.Infinite,
            Timeout.Infinite);
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (!IsEnabled || IsActive)
            return;

        _logger.LogInformation("Starting hot-reload manager");

        try
        {
            _isActive = true;

            // Add default watch paths
            foreach (var searchPath in _options.Extensions.SearchPaths)
            {
                if (Directory.Exists(searchPath))
                {
                    AddWatchPath(searchPath, recursive: true);
                }
            }

            // Also watch the temp directory for user scripts
            var userScriptsPath = Path.Combine(_options.TempDirectory, "UserScripts");
            if (!Directory.Exists(userScriptsPath))
            {
                Directory.CreateDirectory(userScriptsPath);
            }
            AddWatchPath(userScriptsPath, recursive: true);

            _logger.LogInformation("Hot-reload manager started successfully. Watching {PathCount} paths with {FileCount} files",
                _watchers.Count, _watchedFiles.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to start hot-reload manager");
            _isActive = false;
            throw;
        }
    }

    public async Task StopAsync(CancellationToken cancellationToken = default)
    {
        if (!IsActive)
            return;

        _logger.LogInformation("Stopping hot-reload manager");

        try
        {
            _isActive = false;

            // Stop all watchers
            foreach (var watcher in _watchers.Values)
            {
                watcher.FileSystemWatcher.EnableRaisingEvents = false;
                watcher.FileSystemWatcher.Dispose();
            }

            _watchers.Clear();
            _watchedFiles.Clear();

            // Stop debounce timer
            _debounceTimer.Change(Timeout.Infinite, Timeout.Infinite);

            _logger.LogInformation("Hot-reload manager stopped successfully");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error stopping hot-reload manager");
        }
    }

    public void AddWatchPath(string path, bool recursive = true)
    {
        if (!IsEnabled || string.IsNullOrWhiteSpace(path))
            return;

        try
        {
            var fullPath = Path.GetFullPath(path);

            if (_watchers.ContainsKey(fullPath))
            {
                _logger.LogDebug("Path already being watched: {Path}", fullPath);
                return;
            }

            if (!Directory.Exists(fullPath))
            {
                _logger.LogWarning("Cannot watch non-existent directory: {Path}", fullPath);
                return;
            }

            var watcher = new FileSystemWatcher(fullPath)
            {
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite | NotifyFilters.CreationTime | NotifyFilters.Size,
                IncludeSubdirectories = recursive,
                Filter = "*.py", // Primary focus on Python files
                EnableRaisingEvents = IsActive
            };

            watcher.Created += OnFileChanged;
            watcher.Changed += OnFileChanged;
            watcher.Deleted += OnFileDeleted;
            watcher.Renamed += OnFileRenamed;

            var fileWatcher = new FileWatcher
            {
                FileSystemWatcher = watcher,
                Path = fullPath,
                Recursive = recursive,
                AddedAt = DateTime.UtcNow
            };

            _watchers.TryAdd(fullPath, fileWatcher);

            // Index existing files
            if (IsActive)
            {
                await IndexExistingFilesAsync(fullPath, recursive);
            }

            _logger.LogInformation("Added watch path: {Path} (Recursive: {Recursive})", fullPath, recursive);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to add watch path: {Path}", path);
        }
    }

    public void RemoveWatchPath(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
            return;

        try
        {
            var fullPath = Path.GetFullPath(path);

            if (_watchers.TryRemove(fullPath, out var watcher))
            {
                watcher.FileSystemWatcher.EnableRaisingEvents = false;
                watcher.FileSystemWatcher.Dispose();

                // Remove watched files in this path
                var filesToRemove = _watchedFiles.Keys
                    .Where(f => f.StartsWith(fullPath, StringComparison.OrdinalIgnoreCase))
                    .ToList();

                foreach (var file in filesToRemove)
                {
                    _watchedFiles.TryRemove(file, out _);
                }

                _logger.LogInformation("Removed watch path: {Path} (Removed {FileCount} files)", fullPath, filesToRemove.Count);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to remove watch path: {Path}", path);
        }
    }

    public async Task ForceReloadAsync(CancellationToken cancellationToken = default)
    {
        if (!IsEnabled)
            return;

        _logger.LogInformation("Force reloading all watched files");

        var reloadTasks = _watchedFiles.Keys.Select(filePath => ReloadFileAsync(filePath, cancellationToken));
        var results = await Task.WhenAll(reloadTasks);

        var successCount = results.Count(r => r);
        var totalCount = results.Length;

        _logger.LogInformation("Force reload completed: {SuccessCount}/{TotalCount} files reloaded successfully",
            successCount, totalCount);

        // Notify clients
        await NotifyClientsAsync(new HotReloadEvent
        {
            Type = HotReloadEventType.BatchReload,
            Message = $"Force reloaded {successCount}/{totalCount} files",
            Timestamp = DateTime.UtcNow,
            Details = new Dictionary<string, object>
            {
                ["TotalFiles"] = totalCount,
                ["SuccessfulReloads"] = successCount,
                ["FailedReloads"] = totalCount - successCount
            }
        });
    }

    public async Task<bool> ReloadFileAsync(string filePath, CancellationToken cancellationToken = default)
    {
        var stopwatch = System.Diagnostics.Stopwatch.StartNew();
        var normalizedPath = Path.GetFullPath(filePath);

        try
        {
            _logger.LogDebug("Reloading file: {FilePath}", normalizedPath);

            if (!File.Exists(normalizedPath))
            {
                _logger.LogWarning("File not found for reload: {FilePath}", normalizedPath);
                return false;
            }

            var fileExtension = Path.GetExtension(normalizedPath).ToLowerInvariant();

            // Handle different file types
            var reloadResult = fileExtension switch
            {
                ".py" => await ReloadPythonFileAsync(normalizedPath, cancellationToken),
                ".json" => await ReloadConfigFileAsync(normalizedPath, cancellationToken),
                _ => await ReloadGenericFileAsync(normalizedPath, cancellationToken)
            };

            stopwatch.Stop();

            lock (_statsLock)
            {
                _stats.TotalReloads++;
                if (reloadResult)
                {
                    _stats.SuccessfulReloads++;
                }
                else
                {
                    _stats.FailedReloads++;
                }

                _stats.LastReload = DateTime.UtcNow;

                // Update average reload time
                var totalTime = _stats.AverageReloadTime.TotalMilliseconds * (_stats.TotalReloads - 1);
                totalTime += stopwatch.ElapsedMilliseconds;
                _stats.AverageReloadTime = TimeSpan.FromMilliseconds(totalTime / _stats.TotalReloads);
            }

            // Update file info
            _watchedFiles.AddOrUpdate(normalizedPath, new FileInfo(normalizedPath), (_, _) => new FileInfo(normalizedPath));

            var level = reloadResult ? LogLevel.Information : LogLevel.Warning;
            _logger.Log(level, "File reload {Result} in {Duration}ms: {FilePath}",
                reloadResult ? "succeeded" : "failed",
                stopwatch.ElapsedMilliseconds,
                normalizedPath);

            // Notify clients
            await NotifyClientsAsync(new HotReloadEvent
            {
                Type = HotReloadEventType.FileReloaded,
                FilePath = normalizedPath,
                Success = reloadResult,
                Duration = stopwatch.Elapsed,
                Message = reloadResult ? "File reloaded successfully" : "File reload failed",
                Timestamp = DateTime.UtcNow
            });

            return reloadResult;
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            
            lock (_statsLock)
            {
                _stats.TotalReloads++;
                _stats.FailedReloads++;
                _stats.LastReload = DateTime.UtcNow;
            }

            _logger.LogError(ex, "Error reloading file: {FilePath}", normalizedPath);

            await NotifyClientsAsync(new HotReloadEvent
            {
                Type = HotReloadEventType.ReloadError,
                FilePath = normalizedPath,
                Success = false,
                Duration = stopwatch.Elapsed,
                Message = $"Reload error: {ex.Message}",
                Timestamp = DateTime.UtcNow,
                Details = new Dictionary<string, object> { ["Exception"] = ex.ToString() }
            });

            return false;
        }
    }

    private async Task<bool> ReloadPythonFileAsync(string filePath, CancellationToken cancellationToken)
    {
        try
        {
            var content = await File.ReadAllTextAsync(filePath, cancellationToken);
            
            // Validate Python syntax first
            using var interpreter = await _interpreterPool.GetInterpreterAsync(TimeSpan.FromSeconds(5));
            
            var compileResult = await interpreter.ExecuteAsync(
                $"compile({System.Text.Json.JsonSerializer.Serialize(content)}, {System.Text.Json.JsonSerializer.Serialize(filePath)}, 'exec')",
                cancellationToken: cancellationToken);

            if (!compileResult.IsSuccess)
            {
                _logger.LogError("Python syntax error in {FilePath}: {Error}", filePath, compileResult.Error);
                return false;
            }

            // Execute the reloaded script in a clean environment
            var executeResult = await interpreter.ExecuteAsync(content, cancellationToken: cancellationToken);

            if (!executeResult.IsSuccess)
            {
                _logger.LogError("Python execution error in {FilePath}: {Error}", filePath, executeResult.Error);
                return false;
            }

            _logger.LogDebug("Python file reloaded successfully: {FilePath}", filePath);
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to reload Python file: {FilePath}", filePath);
            return false;
        }
    }

    private async Task<bool> ReloadConfigFileAsync(string filePath, CancellationToken cancellationToken)
    {
        try
        {
            // For configuration files, we might trigger a configuration reload
            var content = await File.ReadAllTextAsync(filePath, cancellationToken);
            
            // Basic JSON validation
            System.Text.Json.JsonDocument.Parse(content);
            
            _logger.LogDebug("Configuration file validated: {FilePath}", filePath);
            
            // In a real implementation, this might trigger a configuration refresh
            // For now, we just validate the JSON structure
            
            return true;
        }
        catch (System.Text.Json.JsonException ex)
        {
            _logger.LogError("JSON validation error in {FilePath}: {Error}", filePath, ex.Message);
            return false;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to reload config file: {FilePath}", filePath);
            return false;
        }
    }

    private async Task<bool> ReloadGenericFileAsync(string filePath, CancellationToken cancellationToken)
    {
        try
        {
            // For generic files, just verify they can be read
            await File.ReadAllBytesAsync(filePath, cancellationToken);
            _logger.LogDebug("Generic file validated: {FilePath}", filePath);
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to reload generic file: {FilePath}", filePath);
            return false;
        }
    }

    private async Task IndexExistingFilesAsync(string directoryPath, bool recursive)
    {
        try
        {
            var searchOption = recursive ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly;
            var files = Directory.GetFiles(directoryPath, "*.py", searchOption);

            foreach (var file in files)
            {
                var fileInfo = new FileInfo(file);
                _watchedFiles.TryAdd(file, fileInfo);
            }

            _logger.LogDebug("Indexed {FileCount} files in {DirectoryPath}", files.Length, directoryPath);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to index files in directory: {DirectoryPath}", directoryPath);
        }
    }

    private void OnFileChanged(object sender, FileSystemEventArgs e)
    {
        if (!IsActive)
            return;

        // Add to pending changes for debounced processing
        _pendingChanges.Enqueue(new FileChangeEvent
        {
            Type = FileChangeType.Modified,
            FilePath = e.FullPath,
            Timestamp = DateTime.UtcNow
        });

        // Start or reset the debounce timer
        _debounceTimer.Change(500, Timeout.Infinite); // 500ms debounce
    }

    private void OnFileDeleted(object sender, FileSystemEventArgs e)
    {
        if (!IsActive)
            return;

        _pendingChanges.Enqueue(new FileChangeEvent
        {
            Type = FileChangeType.Deleted,
            FilePath = e.FullPath,
            Timestamp = DateTime.UtcNow
        });

        _debounceTimer.Change(500, Timeout.Infinite);
    }

    private void OnFileRenamed(object sender, RenamedEventArgs e)
    {
        if (!IsActive)
            return;

        _pendingChanges.Enqueue(new FileChangeEvent
        {
            Type = FileChangeType.Renamed,
            FilePath = e.FullPath,
            OldPath = e.OldFullPath,
            Timestamp = DateTime.UtcNow
        });

        _debounceTimer.Change(500, Timeout.Infinite);
    }

    private async Task ProcessPendingChangesAsync()
    {
        if (!IsActive)
            return;

        var changes = new List<FileChangeEvent>();
        
        // Collect all pending changes
        while (_pendingChanges.TryDequeue(out var change))
        {
            changes.Add(change);
        }

        if (changes.Count == 0)
            return;

        _logger.LogDebug("Processing {ChangeCount} file changes", changes.Count);

        // Group changes by file path and process the latest change for each file
        var latestChanges = changes
            .GroupBy(c => c.FilePath)
            .Select(g => g.OrderByDescending(c => c.Timestamp).First())
            .ToList();

        var reloadTasks = latestChanges
            .Where(c => c.Type != FileChangeType.Deleted)
            .Select(async change =>
            {
                try
                {
                    await ReloadFileAsync(change.FilePath);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error processing file change: {FilePath}", change.FilePath);
                }
            });

        await Task.WhenAll(reloadTasks);

        // Handle deleted files
        foreach (var deletedChange in latestChanges.Where(c => c.Type == FileChangeType.Deleted))
        {
            _watchedFiles.TryRemove(deletedChange.FilePath, out _);
            
            await NotifyClientsAsync(new HotReloadEvent
            {
                Type = HotReloadEventType.FileDeleted,
                FilePath = deletedChange.FilePath,
                Message = "File deleted",
                Timestamp = DateTime.UtcNow
            });
        }

        _logger.LogDebug("Completed processing {ChangeCount} file changes", latestChanges.Count);
    }

    private async Task NotifyClientsAsync(HotReloadEvent hotReloadEvent)
    {
        try
        {
            if (_webSocketServer?.IsRunning == true)
            {
                var message = System.Text.Json.JsonSerializer.Serialize(new
                {
                    type = "hotReload",
                    data = hotReloadEvent
                });

                await _webSocketServer.BroadcastAsync(message);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to notify clients of hot-reload event");
        }
    }

    private static string ComputeFileHash(string filePath)
    {
        try
        {
            using var sha256 = SHA256.Create();
            using var stream = File.OpenRead(filePath);
            var hash = sha256.ComputeHash(stream);
            return Convert.ToHexString(hash);
        }
        catch
        {
            return string.Empty;
        }
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        _isDisposed = true;

        _logger.LogInformation("Disposing hot-reload manager");

        try
        {
            StopAsync().Wait(TimeSpan.FromSeconds(5));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during hot-reload manager disposal");
        }

        _debounceTimer?.Dispose();
    }
}

/// <summary>
/// File watcher information
/// </summary>
internal class FileWatcher
{
    public FileSystemWatcher FileSystemWatcher { get; set; } = null!;
    public string Path { get; set; } = string.Empty;
    public bool Recursive { get; set; }
    public DateTime AddedAt { get; set; }
}

/// <summary>
/// File change event
/// </summary>
internal class FileChangeEvent
{
    public FileChangeType Type { get; set; }
    public string FilePath { get; set; } = string.Empty;
    public string? OldPath { get; set; }
    public DateTime Timestamp { get; set; }
}

/// <summary>
/// File change type
/// </summary>
internal enum FileChangeType
{
    Modified,
    Deleted,
    Renamed,
    Created
}

/// <summary>
/// Hot-reload event for clients
/// </summary>
public class HotReloadEvent
{
    public HotReloadEventType Type { get; set; }
    public string? FilePath { get; set; }
    public bool Success { get; set; }
    public TimeSpan Duration { get; set; }
    public string Message { get; set; } = string.Empty;
    public DateTime Timestamp { get; set; }
    public Dictionary<string, object> Details { get; set; } = new();
}

/// <summary>
/// Hot-reload event types
/// </summary>
public enum HotReloadEventType
{
    FileReloaded,
    FileDeleted,
    ReloadError,
    BatchReload
}

/// <summary>
/// Hot-reload statistics
/// </summary>
public class HotReloadStats
{
    public long TotalReloads { get; set; }
    public long SuccessfulReloads { get; set; }
    public long FailedReloads { get; set; }
    public TimeSpan AverageReloadTime { get; set; }
    public DateTime? LastReload { get; set; }
    public int WatchedFileCount { get; set; }
    public int WatchedDirectoryCount { get; set; }
}