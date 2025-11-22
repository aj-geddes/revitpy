using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Core.Configuration;
using RevitPy.Runtime;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;

namespace RevitPy.Host;

/// <summary>
/// Manages extension loading and lifecycle
/// </summary>
public class PluginManager : IExtensionManager, IDisposable
{
    private readonly ILogger<PluginManager> _logger;
    private readonly RevitPyOptions _options;
    private readonly IPythonInterpreterPool _interpreterPool;
    private readonly ConcurrentDictionary<string, ExtensionInfo> _loadedExtensions = new();
    private readonly ConcurrentDictionary<string, ExtensionLoadContext> _loadContexts = new();
    private readonly FileSystemWatcher[] _watchers;

    private ExtensionManagerStats _stats = new();
    private readonly object _statsLock = new();
    private bool _isInitialized;
    private bool _isDisposed;

    public IReadOnlyList<IExtensionInfo> LoadedExtensions =>
        _loadedExtensions.Values.Cast<IExtensionInfo>().ToList().AsReadOnly();

    public ExtensionManagerStats Stats
    {
        get
        {
            lock (_statsLock)
            {
                return new ExtensionManagerStats
                {
                    TotalDiscovered = _stats.TotalDiscovered,
                    TotalLoaded = _stats.TotalLoaded,
                    LoadFailures = _stats.LoadFailures,
                    AverageLoadTime = _stats.AverageLoadTime,
                    CurrentlyLoaded = _loadedExtensions.Count,
                    LastDiscovery = _stats.LastDiscovery
                };
            }
        }
    }

    public PluginManager(
        ILogger<PluginManager> logger,
        IOptions<RevitPyOptions> options,
        IPythonInterpreterPool interpreterPool)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        _interpreterPool = interpreterPool ?? throw new ArgumentNullException(nameof(interpreterPool));

        // Initialize file system watchers for auto-discovery
        _watchers = CreateFileSystemWatchers();
    }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        if (_isInitialized)
            return;

        _logger.LogInformation("Initializing plugin manager");

        try
        {
            // Validate extension directories
            await ValidateExtensionDirectoriesAsync();

            // Discover initial extensions if auto-discovery is enabled
            if (_options.Extensions.EnableAutoDiscovery)
            {
                await DiscoverExtensionsAsync(cancellationToken);

                // Auto-load discovered extensions
                var discoveredExtensions = await DiscoverExtensionsAsync(cancellationToken);
                foreach (var extensionPath in discoveredExtensions)
                {
                    try
                    {
                        await LoadExtensionAsync(extensionPath, cancellationToken);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, "Failed to auto-load extension: {ExtensionPath}", extensionPath);
                    }
                }
            }

            _isInitialized = true;
            _logger.LogInformation("Plugin manager initialized successfully. Loaded {ExtensionCount} extensions",
                _loadedExtensions.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to initialize plugin manager");
            throw;
        }
    }

    public async Task<IEnumerable<string>> DiscoverExtensionsAsync(CancellationToken cancellationToken = default)
    {
        var discoveredExtensions = new List<string>();
        var stopwatch = Stopwatch.StartNew();

        _logger.LogInformation("Discovering extensions in search paths");

        try
        {
            foreach (var searchPath in _options.Extensions.SearchPaths)
            {
                if (!Directory.Exists(searchPath))
                {
                    _logger.LogWarning("Extension search path does not exist: {SearchPath}", searchPath);
                    continue;
                }

                var extensions = await DiscoverExtensionsInPathAsync(searchPath, cancellationToken);
                discoveredExtensions.AddRange(extensions);
            }

            lock (_statsLock)
            {
                _stats.TotalDiscovered += discoveredExtensions.Count;
                _stats.LastDiscovery = DateTime.UtcNow;
            }

            stopwatch.Stop();
            _logger.LogInformation("Discovered {ExtensionCount} extensions in {Duration}ms",
                discoveredExtensions.Count, stopwatch.ElapsedMilliseconds);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during extension discovery");
        }

        return discoveredExtensions;
    }

    public async Task<IExtensionInfo> LoadExtensionAsync(string extensionPath, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(extensionPath))
            throw new ArgumentException("Extension path cannot be empty", nameof(extensionPath));

        if (!File.Exists(extensionPath))
            throw new FileNotFoundException($"Extension file not found: {extensionPath}");

        var stopwatch = Stopwatch.StartNew();
        var extensionId = GenerateExtensionId(extensionPath);

        _logger.LogInformation("Loading extension: {ExtensionPath} (ID: {ExtensionId})", extensionPath, extensionId);

        try
        {
            // Check if already loaded
            if (_loadedExtensions.ContainsKey(extensionId))
            {
                _logger.LogWarning("Extension already loaded: {ExtensionId}", extensionId);
                return _loadedExtensions[extensionId];
            }

            // Validate extension
            var validationResult = await ValidateExtensionAsync(extensionPath, cancellationToken);
            if (!validationResult.IsValid)
            {
                var errorMessage = string.Join("; ", validationResult.Errors);
                throw new InvalidOperationException($"Extension validation failed: {errorMessage}");
            }

            // Create extension info
            var extensionInfo = await CreateExtensionInfoAsync(extensionPath, extensionId);

            // Load extension based on type
            var loadContext = await LoadExtensionByTypeAsync(extensionInfo, cancellationToken);
            _loadContexts.TryAdd(extensionId, loadContext);

            // Update extension status
            extensionInfo.Status = ExtensionStatus.Loaded;
            extensionInfo.LoadTime = DateTime.UtcNow;

            // Add to loaded extensions
            _loadedExtensions.TryAdd(extensionId, extensionInfo);

            // Update statistics
            lock (_statsLock)
            {
                _stats.TotalLoaded++;
                var totalTime = _stats.AverageLoadTime.TotalMilliseconds * (_stats.TotalLoaded - 1);
                totalTime += stopwatch.ElapsedMilliseconds;
                _stats.AverageLoadTime = TimeSpan.FromMilliseconds(totalTime / _stats.TotalLoaded);
            }

            stopwatch.Stop();
            _logger.LogInformation("Successfully loaded extension {ExtensionId} ({Name} v{Version}) in {Duration}ms",
                extensionId, extensionInfo.Name, extensionInfo.Version, stopwatch.ElapsedMilliseconds);

            return extensionInfo;
        }
        catch (Exception ex)
        {
            lock (_statsLock)
            {
                _stats.LoadFailures++;
            }

            var errorMessage = $"Failed to load extension {extensionPath}: {ex.Message}";
            _logger.LogError(ex, errorMessage);

            // Create failed extension info
            var failedExtension = new ExtensionInfo
            {
                Id = extensionId,
                Name = Path.GetFileNameWithoutExtension(extensionPath),
                Path = extensionPath,
                Status = ExtensionStatus.Failed,
                LoadErrors = { errorMessage }
            };

            _loadedExtensions.TryAdd(extensionId, failedExtension);
            throw;
        }
    }

    public async Task UnloadExtensionAsync(string extensionId, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(extensionId))
            throw new ArgumentException("Extension ID cannot be empty", nameof(extensionId));

        if (!_loadedExtensions.TryGetValue(extensionId, out var extensionInfo))
        {
            _logger.LogWarning("Extension not found for unloading: {ExtensionId}", extensionId);
            return;
        }

        _logger.LogInformation("Unloading extension: {ExtensionId} ({Name})", extensionId, extensionInfo.Name);

        try
        {
            extensionInfo.Status = ExtensionStatus.Unloading;

            // Unload based on extension type
            if (_loadContexts.TryRemove(extensionId, out var loadContext))
            {
                await UnloadExtensionContextAsync(loadContext, cancellationToken);
            }

            // Remove from loaded extensions
            _loadedExtensions.TryRemove(extensionId, out _);

            _logger.LogInformation("Successfully unloaded extension: {ExtensionId}", extensionId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to unload extension: {ExtensionId}", extensionId);
            extensionInfo.Status = ExtensionStatus.Failed;
            throw;
        }
    }

    public async Task ReloadExtensionAsync(string extensionId, CancellationToken cancellationToken = default)
    {
        if (!_loadedExtensions.TryGetValue(extensionId, out var extensionInfo))
        {
            throw new ArgumentException($"Extension not found: {extensionId}", nameof(extensionId));
        }

        _logger.LogInformation("Reloading extension: {ExtensionId} ({Name})", extensionId, extensionInfo.Name);

        var extensionPath = extensionInfo.Path;

        // Unload the extension
        await UnloadExtensionAsync(extensionId, cancellationToken);

        // Reload the extension
        await LoadExtensionAsync(extensionPath, cancellationToken);

        _logger.LogInformation("Successfully reloaded extension: {ExtensionId}", extensionId);
    }

    public async Task<ExtensionValidationResult> ValidateExtensionAsync(string extensionPath, CancellationToken cancellationToken = default)
    {
        var result = new ExtensionValidationResult();
        var stopwatch = Stopwatch.StartNew();

        try
        {
            _logger.LogDebug("Validating extension: {ExtensionPath}", extensionPath);

            // Basic file checks
            if (!File.Exists(extensionPath))
            {
                result.Errors.Add("Extension file does not exist");
                return result;
            }

            var fileInfo = new FileInfo(extensionPath);
            if (fileInfo.Length == 0)
            {
                result.Errors.Add("Extension file is empty");
                return result;
            }

            // Check file extension
            var extension = Path.GetExtension(extensionPath).ToLowerInvariant();
            var supportedExtensions = _options.Extensions.FilePatterns
                .Select(pattern => pattern.Replace("*", "").ToLowerInvariant())
                .ToArray();

            if (!supportedExtensions.Contains(extension))
            {
                result.Errors.Add($"Unsupported extension type: {extension}");
                return result;
            }

            // Validate based on extension type
            await ValidateExtensionByTypeAsync(extensionPath, extension, result, cancellationToken);

            // Security validation
            await ValidateExtensionSecurityAsync(extensionPath, result, cancellationToken);

            // Signature validation if required
            if (_options.Extensions.RequireSigned)
            {
                await ValidateExtensionSignatureAsync(extensionPath, result, cancellationToken);
            }

            result.IsValid = !result.Errors.Any();

            stopwatch.Stop();
            _logger.LogDebug("Extension validation completed in {Duration}ms. Valid: {IsValid}, Errors: {ErrorCount}",
                stopwatch.ElapsedMilliseconds, result.IsValid, result.Errors.Count);
        }
        catch (Exception ex)
        {
            result.Errors.Add($"Validation failed with exception: {ex.Message}");
            result.IsValid = false;
            _logger.LogError(ex, "Extension validation failed: {ExtensionPath}", extensionPath);
        }

        return result;
    }

    private async Task<IEnumerable<string>> DiscoverExtensionsInPathAsync(string searchPath, CancellationToken cancellationToken)
    {
        var extensions = new List<string>();

        foreach (var pattern in _options.Extensions.FilePatterns)
        {
            var files = Directory.GetFiles(searchPath, pattern, SearchOption.AllDirectories);
            extensions.AddRange(files);
        }

        return extensions.Distinct();
    }

    private async Task ValidateExtensionDirectoriesAsync()
    {
        foreach (var searchPath in _options.Extensions.SearchPaths)
        {
            if (!Directory.Exists(searchPath))
            {
                try
                {
                    Directory.CreateDirectory(searchPath);
                    _logger.LogInformation("Created extension search directory: {SearchPath}", searchPath);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Could not create extension search directory: {SearchPath}", searchPath);
                }
            }
        }
    }

    private async Task<ExtensionInfo> CreateExtensionInfoAsync(string extensionPath, string extensionId)
    {
        var extensionInfo = new ExtensionInfo
        {
            Id = extensionId,
            Path = extensionPath,
            Status = ExtensionStatus.Loading
        };

        var extension = Path.GetExtension(extensionPath).ToLowerInvariant();

        if (extension == ".py")
        {
            extensionInfo.Type = ExtensionType.PythonScript;
            await PopulatePythonExtensionInfoAsync(extensionInfo);
        }
        else if (extension == ".rpx")
        {
            extensionInfo.Type = ExtensionType.CompiledPackage;
            await PopulateCompiledExtensionInfoAsync(extensionInfo);
        }
        else if (extension == ".dll")
        {
            extensionInfo.Type = ExtensionType.NativeLibrary;
            await PopulateNativeExtensionInfoAsync(extensionInfo);
        }

        return extensionInfo;
    }

    private async Task PopulatePythonExtensionInfoAsync(ExtensionInfo extensionInfo)
    {
        try
        {
            var content = await File.ReadAllTextAsync(extensionInfo.Path);

            // Extract metadata from Python comments or docstrings
            var lines = content.Split('\n');
            foreach (var line in lines.Take(20)) // Check first 20 lines
            {
                var trimmed = line.Trim();
                if (trimmed.StartsWith("# Name:"))
                {
                    extensionInfo.Name = trimmed.Substring(7).Trim();
                }
                else if (trimmed.StartsWith("# Version:"))
                {
                    extensionInfo.Version = trimmed.Substring(10).Trim();
                }
                else if (trimmed.StartsWith("# Author:"))
                {
                    extensionInfo.Author = trimmed.Substring(9).Trim();
                }
                else if (trimmed.StartsWith("# Description:"))
                {
                    extensionInfo.Description = trimmed.Substring(14).Trim();
                }
            }

            // Defaults if metadata not found
            if (string.IsNullOrEmpty(extensionInfo.Name))
                extensionInfo.Name = Path.GetFileNameWithoutExtension(extensionInfo.Path);
            if (string.IsNullOrEmpty(extensionInfo.Version))
                extensionInfo.Version = "1.0.0";
            if (string.IsNullOrEmpty(extensionInfo.Author))
                extensionInfo.Author = "Unknown";
            if (string.IsNullOrEmpty(extensionInfo.Description))
                extensionInfo.Description = "Python extension";
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Could not read Python extension metadata: {ExtensionPath}", extensionInfo.Path);
            extensionInfo.Name = Path.GetFileNameWithoutExtension(extensionInfo.Path);
            extensionInfo.Version = "1.0.0";
            extensionInfo.Author = "Unknown";
            extensionInfo.Description = "Python extension";
        }
    }

    private async Task PopulateCompiledExtensionInfoAsync(ExtensionInfo extensionInfo)
    {
        try
        {
            // .rpx files could be ZIP archives with manifest
            // For now, use filename-based metadata
            extensionInfo.Name = Path.GetFileNameWithoutExtension(extensionInfo.Path);
            extensionInfo.Version = "1.0.0";
            extensionInfo.Author = "Unknown";
            extensionInfo.Description = "Compiled RevitPy package";
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Could not read compiled extension metadata: {ExtensionPath}", extensionInfo.Path);
        }
    }

    private async Task PopulateNativeExtensionInfoAsync(ExtensionInfo extensionInfo)
    {
        try
        {
            var versionInfo = FileVersionInfo.GetVersionInfo(extensionInfo.Path);
            extensionInfo.Name = versionInfo.ProductName ?? Path.GetFileNameWithoutExtension(extensionInfo.Path);
            extensionInfo.Version = versionInfo.ProductVersion ?? "1.0.0";
            extensionInfo.Author = versionInfo.CompanyName ?? "Unknown";
            extensionInfo.Description = versionInfo.FileDescription ?? "Native library";
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Could not read native extension metadata: {ExtensionPath}", extensionInfo.Path);
            extensionInfo.Name = Path.GetFileNameWithoutExtension(extensionInfo.Path);
            extensionInfo.Version = "1.0.0";
            extensionInfo.Author = "Unknown";
            extensionInfo.Description = "Native library";
        }
    }

    private async Task<ExtensionLoadContext> LoadExtensionByTypeAsync(ExtensionInfo extensionInfo, CancellationToken cancellationToken)
    {
        var timeout = TimeSpan.FromMilliseconds(_options.Extensions.LoadTimeout);
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        cts.CancelAfter(timeout);

        return extensionInfo.Type switch
        {
            ExtensionType.PythonScript => await LoadPythonExtensionAsync(extensionInfo, cts.Token),
            ExtensionType.CompiledPackage => await LoadCompiledExtensionAsync(extensionInfo, cts.Token),
            ExtensionType.NativeLibrary => await LoadNativeExtensionAsync(extensionInfo, cts.Token),
            _ => throw new NotSupportedException($"Extension type {extensionInfo.Type} is not supported")
        };
    }

    private async Task<ExtensionLoadContext> LoadPythonExtensionAsync(ExtensionInfo extensionInfo, CancellationToken cancellationToken)
    {
        using var interpreter = await _interpreterPool.GetInterpreterAsync(TimeSpan.FromSeconds(5));

        var script = await File.ReadAllTextAsync(extensionInfo.Path, cancellationToken);
        var result = await interpreter.ExecuteAsync(script, cancellationToken: cancellationToken);

        if (!result.IsSuccess)
        {
            throw new InvalidOperationException($"Failed to load Python extension: {result.Error}");
        }

        return new ExtensionLoadContext
        {
            ExtensionId = extensionInfo.Id,
            LoadType = ExtensionType.PythonScript,
            Context = result
        };
    }

    private async Task<ExtensionLoadContext> LoadCompiledExtensionAsync(ExtensionInfo extensionInfo, CancellationToken cancellationToken)
    {
        // Implementation for compiled packages (.rpx files)
        // This would involve extracting and loading the package
        return new ExtensionLoadContext
        {
            ExtensionId = extensionInfo.Id,
            LoadType = ExtensionType.CompiledPackage,
            Context = extensionInfo.Path
        };
    }

    private async Task<ExtensionLoadContext> LoadNativeExtensionAsync(ExtensionInfo extensionInfo, CancellationToken cancellationToken)
    {
        // Implementation for native libraries (.dll files)
        var assembly = Assembly.LoadFrom(extensionInfo.Path);

        return new ExtensionLoadContext
        {
            ExtensionId = extensionInfo.Id,
            LoadType = ExtensionType.NativeLibrary,
            Context = assembly
        };
    }

    private async Task ValidateExtensionByTypeAsync(string extensionPath, string extension, ExtensionValidationResult result, CancellationToken cancellationToken)
    {
        switch (extension)
        {
            case ".py":
                await ValidatePythonExtensionAsync(extensionPath, result, cancellationToken);
                break;
            case ".rpx":
                await ValidateCompiledExtensionAsync(extensionPath, result, cancellationToken);
                break;
            case ".dll":
                await ValidateNativeExtensionAsync(extensionPath, result, cancellationToken);
                break;
        }
    }

    private async Task ValidatePythonExtensionAsync(string extensionPath, ExtensionValidationResult result, CancellationToken cancellationToken)
    {
        try
        {
            var content = await File.ReadAllTextAsync(extensionPath, cancellationToken);

            // Basic syntax validation using Python interpreter
            using var interpreter = await _interpreterPool.GetInterpreterAsync(TimeSpan.FromSeconds(5));
            var compileResult = await interpreter.ExecuteAsync($"compile({JsonSerializer.Serialize(content)}, {JsonSerializer.Serialize(extensionPath)}, 'exec')", cancellationToken: cancellationToken);

            if (!compileResult.IsSuccess)
            {
                result.Errors.Add($"Python syntax error: {compileResult.Error}");
            }
        }
        catch (Exception ex)
        {
            result.Errors.Add($"Python validation failed: {ex.Message}");
        }
    }

    private async Task ValidateCompiledExtensionAsync(string extensionPath, ExtensionValidationResult result, CancellationToken cancellationToken)
    {
        try
        {
            // Validate compiled package structure
            // This would involve checking the package format
        }
        catch (Exception ex)
        {
            result.Errors.Add($"Compiled package validation failed: {ex.Message}");
        }
    }

    private async Task ValidateNativeExtensionAsync(string extensionPath, ExtensionValidationResult result, CancellationToken cancellationToken)
    {
        try
        {
            // Validate that it's a valid .NET assembly
            var assembly = Assembly.ReflectionOnlyLoadFrom(extensionPath);

            // Check for required interfaces or attributes
            // This would be specific to RevitPy extension requirements
        }
        catch (Exception ex)
        {
            result.Errors.Add($"Native library validation failed: {ex.Message}");
        }
    }

    private async Task ValidateExtensionSecurityAsync(string extensionPath, ExtensionValidationResult result, CancellationToken cancellationToken)
    {
        try
        {
            // File size check
            var fileInfo = new FileInfo(extensionPath);
            const long maxFileSizeMB = 50;
            if (fileInfo.Length > maxFileSizeMB * 1024 * 1024)
            {
                result.SecurityIssues.Add($"File size ({fileInfo.Length / 1024 / 1024}MB) exceeds maximum allowed size ({maxFileSizeMB}MB)");
            }

            // Content scanning for suspicious patterns
            if (Path.GetExtension(extensionPath).ToLowerInvariant() == ".py")
            {
                var content = await File.ReadAllTextAsync(extensionPath, cancellationToken);
                var suspiciousPatterns = new[]
                {
                    "import os", "import subprocess", "import socket",
                    "exec(", "eval(", "__import__",
                    "open(", "file(", "input("
                };

                foreach (var pattern in suspiciousPatterns)
                {
                    if (content.Contains(pattern, StringComparison.OrdinalIgnoreCase))
                    {
                        result.SecurityIssues.Add($"Potentially dangerous pattern detected: {pattern}");
                    }
                }
            }
        }
        catch (Exception ex)
        {
            result.SecurityIssues.Add($"Security validation failed: {ex.Message}");
        }
    }

    private async Task ValidateExtensionSignatureAsync(string extensionPath, ExtensionValidationResult result, CancellationToken cancellationToken)
    {
        try
        {
            // Implementation would verify digital signatures
            // For now, just check if publisher is trusted
            var fileInfo = new FileInfo(extensionPath);
            // This would involve checking digital certificates
            result.Warnings.Add("Digital signature validation not implemented");
        }
        catch (Exception ex)
        {
            result.Errors.Add($"Signature validation failed: {ex.Message}");
        }
    }

    private async Task UnloadExtensionContextAsync(ExtensionLoadContext loadContext, CancellationToken cancellationToken)
    {
        try
        {
            switch (loadContext.LoadType)
            {
                case ExtensionType.PythonScript:
                    // Python scripts are unloaded automatically when interpreter is disposed
                    break;
                case ExtensionType.CompiledPackage:
                    // Cleanup compiled package resources
                    break;
                case ExtensionType.NativeLibrary:
                    // Unload native assemblies (limited support in .NET)
                    break;
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error unloading extension context for {ExtensionId}", loadContext.ExtensionId);
        }
    }

    private FileSystemWatcher[] CreateFileSystemWatchers()
    {
        var watchers = new List<FileSystemWatcher>();

        if (!_options.Extensions.EnableAutoDiscovery)
            return watchers.ToArray();

        foreach (var searchPath in _options.Extensions.SearchPaths)
        {
            try
            {
                if (!Directory.Exists(searchPath))
                    continue;

                var watcher = new FileSystemWatcher(searchPath)
                {
                    NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite | NotifyFilters.CreationTime,
                    IncludeSubdirectories = true,
                    EnableRaisingEvents = true
                };

                foreach (var pattern in _options.Extensions.FilePatterns)
                {
                    watcher.Filter = pattern;
                    watcher.Created += OnExtensionFileChanged;
                    watcher.Changed += OnExtensionFileChanged;
                    watcher.Deleted += OnExtensionFileDeleted;
                    watcher.Renamed += OnExtensionFileRenamed;
                }

                watchers.Add(watcher);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Could not create file system watcher for path: {SearchPath}", searchPath);
            }
        }

        return watchers.ToArray();
    }

    private void OnExtensionFileChanged(object sender, FileSystemEventArgs e)
    {
        _ = Task.Run(async () =>
        {
            try
            {
                await Task.Delay(1000); // Debounce file changes

                var extensionId = GenerateExtensionId(e.FullPath);
                if (_loadedExtensions.ContainsKey(extensionId))
                {
                    _logger.LogInformation("Extension file changed, reloading: {FilePath}", e.FullPath);
                    await ReloadExtensionAsync(extensionId);
                }
                else
                {
                    _logger.LogInformation("New extension file detected, loading: {FilePath}", e.FullPath);
                    await LoadExtensionAsync(e.FullPath);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error handling extension file change: {FilePath}", e.FullPath);
            }
        });
    }

    private void OnExtensionFileDeleted(object sender, FileSystemEventArgs e)
    {
        _ = Task.Run(async () =>
        {
            try
            {
                var extensionId = GenerateExtensionId(e.FullPath);
                if (_loadedExtensions.ContainsKey(extensionId))
                {
                    _logger.LogInformation("Extension file deleted, unloading: {FilePath}", e.FullPath);
                    await UnloadExtensionAsync(extensionId);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error handling extension file deletion: {FilePath}", e.FullPath);
            }
        });
    }

    private void OnExtensionFileRenamed(object sender, RenamedEventArgs e)
    {
        _ = Task.Run(async () =>
        {
            try
            {
                var oldExtensionId = GenerateExtensionId(e.OldFullPath);
                if (_loadedExtensions.ContainsKey(oldExtensionId))
                {
                    _logger.LogInformation("Extension file renamed, reloading: {OldPath} -> {NewPath}", e.OldFullPath, e.FullPath);
                    await UnloadExtensionAsync(oldExtensionId);
                }

                await LoadExtensionAsync(e.FullPath);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error handling extension file rename: {OldPath} -> {NewPath}", e.OldFullPath, e.FullPath);
            }
        });
    }

    private static string GenerateExtensionId(string extensionPath)
    {
        using var sha256 = SHA256.Create();
        var hash = sha256.ComputeHash(System.Text.Encoding.UTF8.GetBytes(extensionPath));
        return Convert.ToHexString(hash)[..16]; // Use first 16 characters of hash
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        _isDisposed = true;

        _logger.LogInformation("Disposing plugin manager");

        // Dispose file system watchers
        foreach (var watcher in _watchers)
        {
            watcher?.Dispose();
        }

        // Unload all extensions
        var unloadTasks = _loadedExtensions.Keys.Select(extensionId =>
            UnloadExtensionAsync(extensionId).ContinueWith(t =>
            {
                if (t.IsFaulted)
                    _logger.LogError(t.Exception, "Error unloading extension during disposal: {ExtensionId}", extensionId);
            }));

        try
        {
            Task.WhenAll(unloadTasks).Wait(TimeSpan.FromSeconds(10));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during extension unloading");
        }
    }
}

/// <summary>
/// Extension information implementation
/// </summary>
internal class ExtensionInfo : IExtensionInfo
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string Version { get; set; } = string.Empty;
    public string Author { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string Path { get; set; } = string.Empty;
    public ExtensionType Type { get; set; }
    public ExtensionStatus Status { get; set; }
    public DateTime LoadTime { get; set; }
    public DateTime LastActivity { get; set; } = DateTime.UtcNow;
    public Dictionary<string, object> Metadata { get; set; } = new();
    public IReadOnlyList<string> LoadErrors => _loadErrors.AsReadOnly();

    internal List<string> _loadErrors = new();
    List<string> IExtensionInfo.LoadErrors => _loadErrors;
}

/// <summary>
/// Extension load context
/// </summary>
internal class ExtensionLoadContext
{
    public string ExtensionId { get; set; } = string.Empty;
    public ExtensionType LoadType { get; set; }
    public object? Context { get; set; }
    public DateTime LoadTime { get; set; } = DateTime.UtcNow;
}
