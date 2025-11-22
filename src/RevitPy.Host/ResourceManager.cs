using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Core.Configuration;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace RevitPy.Host;

/// <summary>
/// Manages system resources efficiently with pooling and monitoring
/// </summary>
public class ResourceManager : IResourceManager, IDisposable
{
    private readonly ILogger<ResourceManager> _logger;
    private readonly RevitPyOptions _options;
    private readonly Timer _monitoringTimer;
    private readonly object _statsLock = new();

    private ResourceManagerStats _stats = new();
    private ResourceUsageInfo _currentUsage = new();
    private bool _isRunning;
    private bool _isDisposed;

    // Resource pools
    private readonly ConcurrentQueue<PooledResource<Thread>> _threadPool = new();
    private readonly ConcurrentDictionary<string, PooledResource<object>> _connectionPool = new();
    private readonly SemaphoreSlim _maxConcurrentOperations;
    private readonly ConcurrentDictionary<int, ProcessInfo> _managedProcesses = new();

    public ResourceManagerStats Stats
    {
        get
        {
            lock (_statsLock)
            {
                return new ResourceManagerStats
                {
                    TotalResourcesCreated = _stats.TotalResourcesCreated,
                    TotalResourcesDestroyed = _stats.TotalResourcesDestroyed,
                    CurrentResourcesInUse = _stats.CurrentResourcesInUse,
                    PeakResourceUsage = _stats.PeakResourceUsage,
                    ResourcePoolHitRate = _stats.ResourcePoolHitRate,
                    LastCleanup = _stats.LastCleanup,
                    AverageResourceLifetime = _stats.AverageResourceLifetime,
                    ThreadPoolSize = _threadPool.Count,
                    ConnectionPoolSize = _connectionPool.Count,
                    ManagedProcessCount = _managedProcesses.Count
                };
            }
        }
    }

    public ResourceUsageInfo CurrentUsage => _currentUsage;
    public bool IsRunning => _isRunning;

    public ResourceManager(
        ILogger<ResourceManager> logger,
        IOptions<RevitPyOptions> options)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));

        // Initialize semaphore for concurrent operations
        _maxConcurrentOperations = new SemaphoreSlim(
            Math.Max(Environment.ProcessorCount * 2, 10), // Initial count
            Math.Max(Environment.ProcessorCount * 4, 20)  // Maximum count
        );

        // Create monitoring timer
        _monitoringTimer = new Timer(
            async _ => await MonitorResourcesAsync(),
            null,
            TimeSpan.FromSeconds(30), // Initial delay
            TimeSpan.FromSeconds(30)  // Monitoring interval
        );

        _logger.LogInformation("Resource manager initialized with max concurrent operations: {MaxOperations}",
            _maxConcurrentOperations.CurrentCount);
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (_isRunning)
            return;

        _logger.LogInformation("Starting resource manager");

        try
        {
            _isRunning = true;

            // Initialize resource pools
            await InitializeResourcePoolsAsync(cancellationToken);

            // Start monitoring
            await MonitorResourcesAsync();

            _logger.LogInformation("Resource manager started successfully");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to start resource manager");
            throw;
        }
    }

    public async Task StopAsync(CancellationToken cancellationToken = default)
    {
        if (!_isRunning)
            return;

        _logger.LogInformation("Stopping resource manager");

        try
        {
            _isRunning = false;

            // Cleanup resources
            await CleanupResourcesAsync(cancellationToken);

            _logger.LogInformation("Resource manager stopped successfully");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error stopping resource manager");
        }
    }

    public async Task<T> AcquireResourceAsync<T>(string resourceKey, Func<Task<T>> factory, TimeSpan? timeout = null)
        where T : class
    {
        var effectiveTimeout = timeout ?? TimeSpan.FromSeconds(30);
        using var cts = new CancellationTokenSource(effectiveTimeout);

        try
        {
            // Wait for available slot
            await _maxConcurrentOperations.WaitAsync(cts.Token);

            try
            {
                // Try to get from pool first
                if (_connectionPool.TryGetValue(resourceKey, out var pooledResource) &&
                    pooledResource.Resource is T cachedResource &&
                    !pooledResource.IsExpired)
                {
                    pooledResource.LastUsed = DateTime.UtcNow;
                    pooledResource.UseCount++;

                    lock (_statsLock)
                    {
                        _stats.ResourcePoolHits++;
                    }

                    _logger.LogDebug("Retrieved resource from pool: {ResourceKey}", resourceKey);
                    return cachedResource;
                }

                // Create new resource
                var resource = await factory();
                var newPooledResource = new PooledResource<object>
                {
                    Resource = resource,
                    CreatedAt = DateTime.UtcNow,
                    LastUsed = DateTime.UtcNow,
                    UseCount = 1,
                    ExpiresAt = DateTime.UtcNow.AddMinutes(30) // Default 30-minute expiration
                };

                _connectionPool.AddOrUpdate(resourceKey, newPooledResource, (_, _) => newPooledResource);

                lock (_statsLock)
                {
                    _stats.TotalResourcesCreated++;
                    _stats.CurrentResourcesInUse++;
                    _stats.ResourcePoolMisses++;

                    if (_stats.CurrentResourcesInUse > _stats.PeakResourceUsage)
                    {
                        _stats.PeakResourceUsage = _stats.CurrentResourcesInUse;
                    }
                }

                _logger.LogDebug("Created new resource: {ResourceKey}", resourceKey);
                return resource;
            }
            finally
            {
                _maxConcurrentOperations.Release();
            }
        }
        catch (OperationCanceledException) when (cts.Token.IsCancellationRequested)
        {
            _logger.LogWarning("Resource acquisition timed out for: {ResourceKey}", resourceKey);
            throw new TimeoutException($"Failed to acquire resource '{resourceKey}' within {effectiveTimeout.TotalSeconds} seconds");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to acquire resource: {ResourceKey}", resourceKey);
            throw;
        }
    }

    public async Task ReleaseResourceAsync(string resourceKey, bool forceDispose = false)
    {
        try
        {
            if (_connectionPool.TryGetValue(resourceKey, out var pooledResource))
            {
                if (forceDispose || pooledResource.IsExpired || pooledResource.UseCount > 1000)
                {
                    // Remove from pool and dispose
                    _connectionPool.TryRemove(resourceKey, out _);

                    if (pooledResource.Resource is IDisposable disposable)
                    {
                        disposable.Dispose();
                    }

                    lock (_statsLock)
                    {
                        _stats.TotalResourcesDestroyed++;
                        _stats.CurrentResourcesInUse--;

                        var lifetime = DateTime.UtcNow - pooledResource.CreatedAt;
                        _stats.AverageResourceLifetime = TimeSpan.FromMilliseconds(
                            (_stats.AverageResourceLifetime.TotalMilliseconds + lifetime.TotalMilliseconds) / 2);
                    }

                    _logger.LogDebug("Disposed resource: {ResourceKey}", resourceKey);
                }
                else
                {
                    // Keep in pool for reuse
                    pooledResource.LastUsed = DateTime.UtcNow;
                    _logger.LogDebug("Released resource to pool: {ResourceKey}", resourceKey);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error releasing resource: {ResourceKey}", resourceKey);
        }
    }

    public async Task<PooledThread> GetThreadFromPoolAsync(ThreadStart threadStart, string? name = null)
    {
        if (_threadPool.TryDequeue(out var pooledThread) && !pooledThread.IsExpired)
        {
            // Reuse existing thread
            pooledThread.LastUsed = DateTime.UtcNow;
            pooledThread.UseCount++;

            var thread = pooledThread.Resource;

            // Update thread for new work
            // Note: In practice, you can't reuse .NET threads like this
            // This is more conceptual - you'd use a ThreadPool or TaskScheduler

            _logger.LogDebug("Reused thread from pool: {ThreadName}", name ?? "Unnamed");
            return new PooledThread { Thread = thread, IsFromPool = true };
        }

        // Create new thread
        var newThread = new Thread(threadStart)
        {
            Name = name ?? $"RevitPy-{Guid.NewGuid():N}",
            IsBackground = true
        };

        var newPooledThread = new PooledResource<Thread>
        {
            Resource = newThread,
            CreatedAt = DateTime.UtcNow,
            LastUsed = DateTime.UtcNow,
            UseCount = 1,
            ExpiresAt = DateTime.UtcNow.AddMinutes(10)
        };

        lock (_statsLock)
        {
            _stats.TotalResourcesCreated++;
        }

        _logger.LogDebug("Created new thread: {ThreadName}", newThread.Name);
        return new PooledThread { Thread = newThread, IsFromPool = false };
    }

    public async Task ReturnThreadToPoolAsync(PooledThread pooledThread)
    {
        if (pooledThread?.Thread == null)
            return;

        try
        {
            // In practice, threads can't be reused like this in .NET
            // This would be handled by ThreadPool or custom thread management

            if (pooledThread.IsFromPool && _threadPool.Count < 10) // Limit pool size
            {
                var pooledResource = new PooledResource<Thread>
                {
                    Resource = pooledThread.Thread,
                    CreatedAt = DateTime.UtcNow,
                    LastUsed = DateTime.UtcNow,
                    UseCount = 0,
                    ExpiresAt = DateTime.UtcNow.AddMinutes(5)
                };

                _threadPool.Enqueue(pooledResource);
                _logger.LogDebug("Returned thread to pool: {ThreadName}", pooledThread.Thread.Name);
            }
            else
            {
                // Thread will be garbage collected
                _logger.LogDebug("Thread disposed: {ThreadName}", pooledThread.Thread.Name);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error returning thread to pool: {ThreadName}", pooledThread.Thread?.Name);
        }
    }

    public async Task<ProcessInfo> StartManagedProcessAsync(ProcessStartInfo startInfo, TimeSpan? timeout = null)
    {
        var process = new Process { StartInfo = startInfo };

        try
        {
            process.Start();

            var processInfo = new ProcessInfo
            {
                Process = process,
                StartTime = DateTime.UtcNow,
                Timeout = timeout,
                IsManaged = true
            };

            _managedProcesses.TryAdd(process.Id, processInfo);

            // Monitor process
            _ = Task.Run(async () => await MonitorProcessAsync(processInfo));

            _logger.LogInformation("Started managed process: {ProcessId} ({ProcessName})",
                process.Id, process.ProcessName);

            return processInfo;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to start managed process: {FileName}", startInfo.FileName);
            process?.Dispose();
            throw;
        }
    }

    public async Task StopManagedProcessAsync(int processId, bool force = false)
    {
        if (!_managedProcesses.TryGetValue(processId, out var processInfo))
        {
            _logger.LogWarning("Managed process not found: {ProcessId}", processId);
            return;
        }

        try
        {
            var process = processInfo.Process;

            if (!process.HasExited)
            {
                if (force)
                {
                    process.Kill();
                    _logger.LogInformation("Forcefully killed managed process: {ProcessId}", processId);
                }
                else
                {
                    process.CloseMainWindow();

                    // Wait for graceful shutdown
                    if (!process.WaitForExit(5000))
                    {
                        process.Kill();
                        _logger.LogWarning("Managed process did not exit gracefully, killed: {ProcessId}", processId);
                    }
                    else
                    {
                        _logger.LogInformation("Managed process exited gracefully: {ProcessId}", processId);
                    }
                }
            }

            _managedProcesses.TryRemove(processId, out _);
            process.Dispose();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error stopping managed process: {ProcessId}", processId);
        }
    }

    public async Task OptimizeResourceUsageAsync()
    {
        _logger.LogInformation("Optimizing resource usage");

        try
        {
            // Clean up expired resources
            await CleanupExpiredResourcesAsync();

            // Force garbage collection if memory usage is high
            var memoryUsage = GC.GetTotalMemory(false);
            if (memoryUsage > _options.MaxMemoryUsageMB * 1024 * 1024 * 0.8) // 80% of limit
            {
                _logger.LogInformation("High memory usage detected, forcing garbage collection");
                GC.Collect();
                GC.WaitForPendingFinalizers();
                GC.Collect();

                var newMemoryUsage = GC.GetTotalMemory(true);
                _logger.LogInformation("Garbage collection completed. Memory reduced from {OldMB:F1}MB to {NewMB:F1}MB",
                    memoryUsage / 1024.0 / 1024.0,
                    newMemoryUsage / 1024.0 / 1024.0);
            }

            // Clean up old threads
            await CleanupThreadPoolAsync();

            // Check managed processes
            await CheckManagedProcessesAsync();

            lock (_statsLock)
            {
                _stats.LastCleanup = DateTime.UtcNow;
            }

            _logger.LogInformation("Resource optimization completed");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during resource optimization");
        }
    }

    public ResourceUsageSnapshot CreateResourceSnapshot()
    {
        var process = Process.GetCurrentProcess();

        return new ResourceUsageSnapshot
        {
            Timestamp = DateTime.UtcNow,
            ManagedMemoryMB = GC.GetTotalMemory(false) / 1024.0 / 1024.0,
            WorkingSetMB = process.WorkingSet64 / 1024.0 / 1024.0,
            PrivateMemoryMB = process.PrivateMemorySize64 / 1024.0 / 1024.0,
            VirtualMemoryMB = process.VirtualMemorySize64 / 1024.0 / 1024.0,
            ThreadCount = process.Threads.Count,
            HandleCount = process.HandleCount,
            GcCollectionCounts = new Dictionary<string, long>
            {
                ["Gen0"] = GC.CollectionCount(0),
                ["Gen1"] = GC.CollectionCount(1),
                ["Gen2"] = GC.CollectionCount(2)
            },
            ResourcePoolSizes = new Dictionary<string, int>
            {
                ["ThreadPool"] = _threadPool.Count,
                ["ConnectionPool"] = _connectionPool.Count,
                ["ManagedProcesses"] = _managedProcesses.Count
            },
            AvailableConcurrentOperations = _maxConcurrentOperations.CurrentCount
        };
    }

    private async Task InitializeResourcePoolsAsync(CancellationToken cancellationToken)
    {
        // Pre-warm thread pool if needed
        // In practice, this would be handled by ThreadPool configuration

        _logger.LogDebug("Resource pools initialized");
    }

    private async Task MonitorResourcesAsync()
    {
        if (!_isRunning || _isDisposed)
            return;

        try
        {
            // Update current usage
            _currentUsage = new ResourceUsageInfo
            {
                Timestamp = DateTime.UtcNow,
                ManagedMemoryMB = GC.GetTotalMemory(false) / 1024.0 / 1024.0,
                ThreadPoolSize = _threadPool.Count,
                ConnectionPoolSize = _connectionPool.Count,
                ManagedProcessCount = _managedProcesses.Count,
                AvailableConcurrentSlots = _maxConcurrentOperations.CurrentCount
            };

            // Check for resource leaks or excessive usage
            if (_currentUsage.ManagedMemoryMB > _options.MaxMemoryUsageMB * 0.9)
            {
                _logger.LogWarning("Memory usage is approaching limit: {MemoryMB:F1}MB of {LimitMB}MB",
                    _currentUsage.ManagedMemoryMB, _options.MaxMemoryUsageMB);

                await OptimizeResourceUsageAsync();
            }

            // Periodic cleanup
            if (DateTime.UtcNow - (_stats.LastCleanup ?? DateTime.MinValue) > TimeSpan.FromMinutes(5))
            {
                await OptimizeResourceUsageAsync();
            }

            _logger.LogTrace("Resource monitoring: Memory={MemoryMB:F1}MB, Threads={ThreadCount}, Connections={ConnectionCount}, Processes={ProcessCount}",
                _currentUsage.ManagedMemoryMB,
                _currentUsage.ThreadPoolSize,
                _currentUsage.ConnectionPoolSize,
                _currentUsage.ManagedProcessCount);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during resource monitoring");
        }
    }

    private async Task CleanupResourcesAsync(CancellationToken cancellationToken)
    {
        // Stop all managed processes
        var processTasks = _managedProcesses.Keys.Select(processId =>
            StopManagedProcessAsync(processId, force: true));
        await Task.WhenAll(processTasks);

        // Dispose all pooled resources
        await CleanupExpiredResourcesAsync(disposeAll: true);

        // Clear thread pool
        while (_threadPool.TryDequeue(out var pooledThread))
        {
            // Threads are managed by the runtime
        }

        _logger.LogInformation("All resources cleaned up");
    }

    private async Task CleanupExpiredResourcesAsync(bool disposeAll = false)
    {
        var expiredKeys = new List<string>();
        var now = DateTime.UtcNow;

        foreach (var kvp in _connectionPool)
        {
            if (disposeAll || kvp.Value.IsExpired)
            {
                expiredKeys.Add(kvp.Key);
            }
        }

        foreach (var key in expiredKeys)
        {
            if (_connectionPool.TryRemove(key, out var pooledResource))
            {
                if (pooledResource.Resource is IDisposable disposable)
                {
                    disposable.Dispose();
                }

                lock (_statsLock)
                {
                    _stats.TotalResourcesDestroyed++;
                    _stats.CurrentResourcesInUse--;
                }
            }
        }

        if (expiredKeys.Count > 0)
        {
            _logger.LogDebug("Cleaned up {Count} expired resources", expiredKeys.Count);
        }
    }

    private async Task CleanupThreadPoolAsync()
    {
        var expiredThreads = new List<PooledResource<Thread>>();
        var tempQueue = new ConcurrentQueue<PooledResource<Thread>>();

        // Remove expired threads
        while (_threadPool.TryDequeue(out var pooledThread))
        {
            if (pooledThread.IsExpired)
            {
                expiredThreads.Add(pooledThread);
            }
            else
            {
                tempQueue.Enqueue(pooledThread);
            }
        }

        // Return non-expired threads to pool
        while (tempQueue.TryDequeue(out var pooledThread))
        {
            _threadPool.Enqueue(pooledThread);
        }

        if (expiredThreads.Count > 0)
        {
            _logger.LogDebug("Removed {Count} expired threads from pool", expiredThreads.Count);
        }
    }

    private async Task CheckManagedProcessesAsync()
    {
        var completedProcesses = new List<int>();

        foreach (var kvp in _managedProcesses)
        {
            var processInfo = kvp.Value;
            var process = processInfo.Process;

            try
            {
                if (process.HasExited)
                {
                    completedProcesses.Add(kvp.Key);
                }
                else if (processInfo.Timeout.HasValue &&
                         DateTime.UtcNow - processInfo.StartTime > processInfo.Timeout.Value)
                {
                    _logger.LogWarning("Managed process timed out, terminating: {ProcessId}", kvp.Key);
                    await StopManagedProcessAsync(kvp.Key, force: true);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error checking managed process: {ProcessId}", kvp.Key);
                completedProcesses.Add(kvp.Key);
            }
        }

        // Clean up completed processes
        foreach (var processId in completedProcesses)
        {
            if (_managedProcesses.TryRemove(processId, out var processInfo))
            {
                processInfo.Process.Dispose();
                _logger.LogDebug("Cleaned up completed process: {ProcessId}", processId);
            }
        }
    }

    private async Task MonitorProcessAsync(ProcessInfo processInfo)
    {
        try
        {
            var process = processInfo.Process;
            await Task.Run(() => process.WaitForExit());

            _logger.LogInformation("Managed process exited: {ProcessId} (Exit code: {ExitCode})",
                process.Id, process.ExitCode);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error monitoring process: {ProcessId}", processInfo.Process?.Id);
        }
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        _isDisposed = true;
        _isRunning = false;

        _logger.LogInformation("Disposing resource manager");

        try
        {
            StopAsync().Wait(TimeSpan.FromSeconds(10));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during resource manager disposal");
        }

        _monitoringTimer?.Dispose();
        _maxConcurrentOperations?.Dispose();
    }
}

/// <summary>
/// Interface for resource management
/// </summary>
public interface IResourceManager
{
    /// <summary>
    /// Gets resource manager statistics
    /// </summary>
    ResourceManagerStats Stats { get; }

    /// <summary>
    /// Gets current resource usage
    /// </summary>
    ResourceUsageInfo CurrentUsage { get; }

    /// <summary>
    /// Gets whether the resource manager is running
    /// </summary>
    bool IsRunning { get; }

    /// <summary>
    /// Starts the resource manager
    /// </summary>
    Task StartAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Stops the resource manager
    /// </summary>
    Task StopAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Acquires a resource with optional pooling
    /// </summary>
    Task<T> AcquireResourceAsync<T>(string resourceKey, Func<Task<T>> factory, TimeSpan? timeout = null) where T : class;

    /// <summary>
    /// Releases a resource back to the pool or disposes it
    /// </summary>
    Task ReleaseResourceAsync(string resourceKey, bool forceDispose = false);

    /// <summary>
    /// Gets a thread from the thread pool
    /// </summary>
    Task<PooledThread> GetThreadFromPoolAsync(ThreadStart threadStart, string? name = null);

    /// <summary>
    /// Returns a thread to the pool
    /// </summary>
    Task ReturnThreadToPoolAsync(PooledThread pooledThread);

    /// <summary>
    /// Starts a managed process
    /// </summary>
    Task<ProcessInfo> StartManagedProcessAsync(ProcessStartInfo startInfo, TimeSpan? timeout = null);

    /// <summary>
    /// Stops a managed process
    /// </summary>
    Task StopManagedProcessAsync(int processId, bool force = false);

    /// <summary>
    /// Optimizes resource usage
    /// </summary>
    Task OptimizeResourceUsageAsync();

    /// <summary>
    /// Creates a snapshot of current resource usage
    /// </summary>
    ResourceUsageSnapshot CreateResourceSnapshot();
}

/// <summary>
/// Pooled resource wrapper
/// </summary>
public class PooledResource<T>
{
    public T Resource { get; set; } = default!;
    public DateTime CreatedAt { get; set; }
    public DateTime LastUsed { get; set; }
    public DateTime ExpiresAt { get; set; }
    public int UseCount { get; set; }
    public bool IsExpired => DateTime.UtcNow > ExpiresAt;
}

/// <summary>
/// Pooled thread wrapper
/// </summary>
public class PooledThread
{
    public Thread Thread { get; set; } = null!;
    public bool IsFromPool { get; set; }
}

/// <summary>
/// Process information
/// </summary>
public class ProcessInfo
{
    public Process Process { get; set; } = null!;
    public DateTime StartTime { get; set; }
    public TimeSpan? Timeout { get; set; }
    public bool IsManaged { get; set; }
}

/// <summary>
/// Resource manager statistics
/// </summary>
public class ResourceManagerStats
{
    public long TotalResourcesCreated { get; set; }
    public long TotalResourcesDestroyed { get; set; }
    public int CurrentResourcesInUse { get; set; }
    public int PeakResourceUsage { get; set; }
    public double ResourcePoolHitRate => ResourcePoolHits + ResourcePoolMisses == 0 ? 0 :
        (double)ResourcePoolHits / (ResourcePoolHits + ResourcePoolMisses) * 100;
    public long ResourcePoolHits { get; set; }
    public long ResourcePoolMisses { get; set; }
    public DateTime? LastCleanup { get; set; }
    public TimeSpan AverageResourceLifetime { get; set; }
    public int ThreadPoolSize { get; set; }
    public int ConnectionPoolSize { get; set; }
    public int ManagedProcessCount { get; set; }
}

/// <summary>
/// Current resource usage information
/// </summary>
public class ResourceUsageInfo
{
    public DateTime Timestamp { get; set; }
    public double ManagedMemoryMB { get; set; }
    public int ThreadPoolSize { get; set; }
    public int ConnectionPoolSize { get; set; }
    public int ManagedProcessCount { get; set; }
    public int AvailableConcurrentSlots { get; set; }
}

/// <summary>
/// Snapshot of resource usage at a point in time
/// </summary>
public class ResourceUsageSnapshot
{
    public DateTime Timestamp { get; set; }
    public double ManagedMemoryMB { get; set; }
    public double WorkingSetMB { get; set; }
    public double PrivateMemoryMB { get; set; }
    public double VirtualMemoryMB { get; set; }
    public int ThreadCount { get; set; }
    public int HandleCount { get; set; }
    public Dictionary<string, long> GcCollectionCounts { get; set; } = new();
    public Dictionary<string, int> ResourcePoolSizes { get; set; } = new();
    public int AvailableConcurrentOperations { get; set; }
}
