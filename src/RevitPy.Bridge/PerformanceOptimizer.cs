using System.Collections.Concurrent;
using System.Diagnostics;
using System.Runtime.CompilerServices;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.ObjectPool;

namespace RevitPy.Bridge;

/// <summary>
/// High-performance optimization utilities for RevitPy Bridge operations
/// </summary>
public interface IPerformanceOptimizer
{
    /// <summary>
    /// Gets or creates an object from the pool
    /// </summary>
    T GetPooledObject<T>() where T : class, new();

    /// <summary>
    /// Returns an object to the pool
    /// </summary>
    void ReturnPooledObject<T>(T obj) where T : class;

    /// <summary>
    /// Executes an operation with pooled objects
    /// </summary>
    Task<TResult> ExecuteWithPooledObjects<TResult>(Func<IObjectPoolProvider, Task<TResult>> operation, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets cached computation result or computes and caches it
    /// </summary>
    Task<TResult> GetOrComputeAsync<TResult>(string cacheKey, Func<Task<TResult>> computeFunc, TimeSpan? expiration = null, CancellationToken cancellationToken = default);

    /// <summary>
    /// Performs batch operations with optimized concurrency
    /// </summary>
    Task<IEnumerable<TResult>> ExecuteBatchAsync<TInput, TResult>(
        IEnumerable<TInput> inputs,
        Func<TInput, Task<TResult>> operation,
        int? maxConcurrency = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Monitors and reports performance metrics
    /// </summary>
    PerformanceMetrics GetMetrics();

    /// <summary>
    /// Optimizes memory usage by clearing expired cache entries
    /// </summary>
    Task OptimizeMemoryAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Preloads frequently used objects into pools
    /// </summary>
    Task PreloadPoolsAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// High-performance implementation with advanced object pooling and caching
/// </summary>
public class PerformanceOptimizer : IPerformanceOptimizer, IDisposable
{
    private readonly ILogger<PerformanceOptimizer> _logger;
    private readonly ConcurrentDictionary<Type, IObjectPool<object>> _objectPools;
    private readonly ConcurrentDictionary<string, CacheEntry> _computationCache;
    private readonly ConcurrentDictionary<string, SemaphoreSlim> _computationSemaphores;
    private readonly DefaultObjectPoolProvider _objectPoolProvider;
    private readonly PerformanceMetrics _metrics;
    private readonly object _metricsLock = new();
    private readonly Timer _cleanupTimer;
    private readonly SemaphoreSlim _batchSemaphore;

    // Performance tuning parameters
    private readonly int _maxObjectsPerPool;
    private readonly TimeSpan _defaultCacheExpiration;
    private readonly int _maxConcurrentComputations;
    private readonly TimeSpan _cleanupInterval;

    public PerformanceOptimizer(ILogger<PerformanceOptimizer> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));

        _objectPools = new ConcurrentDictionary<Type, IObjectPool<object>>();
        _computationCache = new ConcurrentDictionary<string, CacheEntry>();
        _computationSemaphores = new ConcurrentDictionary<string, SemaphoreSlim>();
        _objectPoolProvider = new DefaultObjectPoolProvider();
        _metrics = new PerformanceMetrics { StartTime = DateTime.UtcNow };

        // Performance configuration
        _maxObjectsPerPool = Environment.ProcessorCount * 4;
        _defaultCacheExpiration = TimeSpan.FromMinutes(10);
        _maxConcurrentComputations = Environment.ProcessorCount * 2;
        _cleanupInterval = TimeSpan.FromMinutes(5);

        _batchSemaphore = new SemaphoreSlim(_maxConcurrentComputations, _maxConcurrentComputations);

        // Start cleanup timer
        _cleanupTimer = new Timer(async _ => await OptimizeMemoryAsync(), null, _cleanupInterval, _cleanupInterval);

        InitializeCommonPools();
    }

    /// <inheritdoc/>
    public T GetPooledObject<T>() where T : class, new()
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            var pool = GetOrCreatePool<T>();
            var obj = (T)pool.Get();

            RecordPoolOperation("Get", typeof(T), stopwatch.Elapsed);
            return obj;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to get pooled object of type {Type}", typeof(T).Name);
            RecordPoolFailure("Get", typeof(T), stopwatch.Elapsed);

            // Fallback to creating new instance
            return new T();
        }
    }

    /// <inheritdoc/>
    public void ReturnPooledObject<T>(T obj) where T : class
    {
        ArgumentNullException.ThrowIfNull(obj);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var pool = GetOrCreatePool<T>();
            pool.Return(obj);

            RecordPoolOperation("Return", typeof(T), stopwatch.Elapsed);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to return pooled object of type {Type}", typeof(T).Name);
            RecordPoolFailure("Return", typeof(T), stopwatch.Elapsed);
        }
    }

    /// <inheritdoc/>
    public async Task<TResult> ExecuteWithPooledObjects<TResult>(
        Func<IObjectPoolProvider, Task<TResult>> operation,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(operation);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var result = await operation(_objectPoolProvider);

            RecordPooledOperation("ExecuteWithPooled", stopwatch.Elapsed, true);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to execute operation with pooled objects");
            RecordPooledOperation("ExecuteWithPooled", stopwatch.Elapsed, false);
            throw;
        }
    }

    /// <inheritdoc/>
    public async Task<TResult> GetOrComputeAsync<TResult>(
        string cacheKey,
        Func<Task<TResult>> computeFunc,
        TimeSpan? expiration = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(cacheKey);
        ArgumentNullException.ThrowIfNull(computeFunc);

        var stopwatch = Stopwatch.StartNew();

        // Check cache first
        if (_computationCache.TryGetValue(cacheKey, out var cacheEntry) &&
            !cacheEntry.IsExpired)
        {
            RecordCacheOperation("Hit", cacheKey, stopwatch.Elapsed);
            return (TResult)cacheEntry.Value;
        }

        // Get or create semaphore for this computation
        var semaphore = _computationSemaphores.GetOrAdd(cacheKey, _ => new SemaphoreSlim(1, 1));

        await semaphore.WaitAsync(cancellationToken);
        try
        {
            // Double-check cache after acquiring lock
            if (_computationCache.TryGetValue(cacheKey, out cacheEntry) &&
                !cacheEntry.IsExpired)
            {
                RecordCacheOperation("Hit", cacheKey, stopwatch.Elapsed);
                return (TResult)cacheEntry.Value;
            }

            // Compute the value
            var computationStopwatch = Stopwatch.StartNew();
            var result = await computeFunc();

            // Cache the result
            var cacheExpiration = expiration ?? _defaultCacheExpiration;
            _computationCache[cacheKey] = new CacheEntry
            {
                Value = result!,
                ExpirationTime = DateTime.UtcNow.Add(cacheExpiration),
                ComputationTime = computationStopwatch.Elapsed,
                AccessCount = 1
            };

            RecordCacheOperation("Miss", cacheKey, stopwatch.Elapsed);
            RecordComputation(cacheKey, computationStopwatch.Elapsed);

            return result;
        }
        finally
        {
            semaphore.Release();
        }
    }

    /// <inheritdoc/>
    public async Task<IEnumerable<TResult>> ExecuteBatchAsync<TInput, TResult>(
        IEnumerable<TInput> inputs,
        Func<TInput, Task<TResult>> operation,
        int? maxConcurrency = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(inputs);
        ArgumentNullException.ThrowIfNull(operation);

        var inputList = inputs.ToList();
        if (inputList.Count == 0)
            return Array.Empty<TResult>();

        var stopwatch = Stopwatch.StartNew();
        var concurrency = maxConcurrency ?? Math.Min(_maxConcurrentComputations, inputList.Count);

        try
        {
            await _batchSemaphore.WaitAsync(cancellationToken);

            var results = new ConcurrentBag<TResult>();
            var semaphore = new SemaphoreSlim(concurrency, concurrency);
            var tasks = new List<Task>();

            foreach (var input in inputList)
            {
                tasks.Add(ProcessBatchItem(input, operation, results, semaphore, cancellationToken));
            }

            await Task.WhenAll(tasks);

            var resultList = results.ToList();
            RecordBatchOperation(inputList.Count, resultList.Count, concurrency, stopwatch.Elapsed);

            return resultList;
        }
        finally
        {
            _batchSemaphore.Release();
        }
    }

    /// <inheritdoc/>
    public PerformanceMetrics GetMetrics()
    {
        lock (_metricsLock)
        {
            var currentTime = DateTime.UtcNow;
            return new PerformanceMetrics
            {
                StartTime = _metrics.StartTime,
                TotalOperations = _metrics.TotalOperations,
                PoolOperations = _metrics.PoolOperations,
                CacheOperations = _metrics.CacheOperations,
                ComputationOperations = _metrics.ComputationOperations,
                BatchOperations = _metrics.BatchOperations,
                FailedOperations = _metrics.FailedOperations,
                AverageOperationTime = _metrics.AverageOperationTime,
                CacheHitRatio = _metrics.CacheOperations > 0 ?
                    (double)_metrics.CacheHits / _metrics.CacheOperations : 0.0,
                PoolUtilization = CalculatePoolUtilization(),
                CacheSize = _computationCache.Count,
                ActivePoolTypes = _objectPools.Count,
                MemoryPressure = GC.GetTotalMemory(false),
                UpTime = currentTime - _metrics.StartTime
            };
        }
    }

    /// <inheritdoc/>
    public async Task OptimizeMemoryAsync(CancellationToken cancellationToken = default)
    {
        var stopwatch = Stopwatch.StartNew();
        var cleanedEntries = 0;
        var cleanedSemaphores = 0;

        try
        {
            // Clean expired cache entries
            var expiredKeys = _computationCache
                .Where(kvp => kvp.Value.IsExpired)
                .Select(kvp => kvp.Key)
                .ToList();

            foreach (var key in expiredKeys)
            {
                if (_computationCache.TryRemove(key, out _))
                {
                    cleanedEntries++;
                }
            }

            // Clean unused semaphores
            var unusedSemaphores = _computationSemaphores
                .Where(kvp => !_computationCache.ContainsKey(kvp.Key))
                .Select(kvp => kvp.Key)
                .ToList();

            foreach (var key in unusedSemaphores)
            {
                if (_computationSemaphores.TryRemove(key, out var semaphore))
                {
                    semaphore.Dispose();
                    cleanedSemaphores++;
                }
            }

            // Force garbage collection if significant cleanup occurred
            if (cleanedEntries > 100 || cleanedSemaphores > 50)
            {
                GC.Collect(2, GCCollectionMode.Optimized, blocking: false);
            }

            RecordCleanupOperation(cleanedEntries, cleanedSemaphores, stopwatch.Elapsed);

            _logger.LogDebug("Memory optimization completed: {CleanedEntries} cache entries, {CleanedSemaphores} semaphores in {Duration}ms",
                cleanedEntries, cleanedSemaphores, stopwatch.ElapsedMilliseconds);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error during memory optimization");
        }
    }

    /// <inheritdoc/>
    public async Task PreloadPoolsAsync(CancellationToken cancellationToken = default)
    {
        var stopwatch = Stopwatch.StartNew();
        var preloadedCount = 0;

        try
        {
            // Preload common types
            var commonTypes = new[]
            {
                typeof(Dictionary<string, object>),
                typeof(List<object>),
                typeof(StringBuilder),
                typeof(MemoryStream)
            };

            foreach (var type in commonTypes)
            {
                try
                {
                    var pool = GetOrCreatePoolForType(type);

                    // Pre-populate pool with half of max capacity
                    var preloadCount = _maxObjectsPerPool / 2;
                    for (int i = 0; i < preloadCount && !cancellationToken.IsCancellationRequested; i++)
                    {
                        var obj = Activator.CreateInstance(type);
                        if (obj != null)
                        {
                            pool.Return(obj);
                            preloadedCount++;
                        }
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Failed to preload pool for type {Type}", type.Name);
                }
            }

            RecordPreloadOperation(preloadedCount, stopwatch.Elapsed);

            _logger.LogInformation("Pool preloading completed: {PreloadedCount} objects in {Duration}ms",
                preloadedCount, stopwatch.ElapsedMilliseconds);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during pool preloading");
        }
    }

    private void InitializeCommonPools()
    {
        // Pre-create pools for common types to avoid runtime overhead
        var commonTypes = new[]
        {
            typeof(Dictionary<string, object>),
            typeof(List<object>),
            typeof(StringBuilder),
            typeof(MemoryStream)
        };

        foreach (var type in commonTypes)
        {
            GetOrCreatePoolForType(type);
        }
    }

    private IObjectPool<object> GetOrCreatePool<T>() where T : class
    {
        return GetOrCreatePoolForType(typeof(T));
    }

    private IObjectPool<object> GetOrCreatePoolForType(Type type)
    {
        return _objectPools.GetOrAdd(type, t =>
        {
            var policy = new DefaultPooledObjectPolicy<object>(
                () => Activator.CreateInstance(t) ?? throw new InvalidOperationException($"Cannot create instance of {t.Name}"),
                obj => ResetObject(obj));

            return new DefaultObjectPool<object>(policy, _maxObjectsPerPool);
        });
    }

    private bool ResetObject(object obj)
    {
        try
        {
            // Reset object to initial state for reuse
            switch (obj)
            {
                case Dictionary<string, object> dict:
                    dict.Clear();
                    break;
                case List<object> list:
                    list.Clear();
                    break;
                case StringBuilder sb:
                    sb.Clear();
                    break;
                case MemoryStream ms:
                    ms.SetLength(0);
                    ms.Position = 0;
                    break;
                case IDisposable disposable:
                    // Don't reuse disposable objects that have been disposed
                    return false;
            }

            return true;
        }
        catch
        {
            return false; // Don't reuse if reset failed
        }
    }

    private async Task ProcessBatchItem<TInput, TResult>(
        TInput input,
        Func<TInput, Task<TResult>> operation,
        ConcurrentBag<TResult> results,
        SemaphoreSlim semaphore,
        CancellationToken cancellationToken)
    {
        await semaphore.WaitAsync(cancellationToken);
        try
        {
            var result = await operation(input);
            results.Add(result);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Batch operation failed for input item");
        }
        finally
        {
            semaphore.Release();
        }
    }

    private double CalculatePoolUtilization()
    {
        if (_objectPools.Count == 0)
            return 0.0;

        // This is a simplified utilization calculation
        // In a real implementation, you'd track pool usage more precisely
        return Math.Min(1.0, (double)_objectPools.Count / 10.0);
    }

    // Statistics recording methods

    private void RecordPoolOperation(string operation, Type type, TimeSpan duration)
    {
        lock (_metricsLock)
        {
            _metrics.TotalOperations++;
            _metrics.PoolOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordPoolFailure(string operation, Type type, TimeSpan duration)
    {
        lock (_metricsLock)
        {
            _metrics.TotalOperations++;
            _metrics.FailedOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordPooledOperation(string operation, TimeSpan duration, bool success)
    {
        lock (_metricsLock)
        {
            _metrics.TotalOperations++;
            if (!success)
                _metrics.FailedOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordCacheOperation(string operation, string cacheKey, TimeSpan duration)
    {
        lock (_metricsLock)
        {
            _metrics.TotalOperations++;
            _metrics.CacheOperations++;

            if (operation == "Hit")
                _metrics.CacheHits++;

            UpdateAverageTime(duration);
        }
    }

    private void RecordComputation(string cacheKey, TimeSpan duration)
    {
        lock (_metricsLock)
        {
            _metrics.ComputationOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordBatchOperation(int inputCount, int resultCount, int concurrency, TimeSpan duration)
    {
        lock (_metricsLock)
        {
            _metrics.TotalOperations++;
            _metrics.BatchOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordCleanupOperation(int cleanedEntries, int cleanedSemaphores, TimeSpan duration)
    {
        lock (_metricsLock)
        {
            _metrics.CleanupOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordPreloadOperation(int preloadedCount, TimeSpan duration)
    {
        lock (_metricsLock)
        {
            _metrics.PreloadOperations++;
            UpdateAverageTime(duration);
        }
    }

    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    private void UpdateAverageTime(TimeSpan duration)
    {
        var totalTicks = _metrics.AverageOperationTime.Ticks * (_metrics.TotalOperations - 1) + duration.Ticks;
        _metrics.AverageOperationTime = new TimeSpan(totalTicks / _metrics.TotalOperations);
    }

    public void Dispose()
    {
        _cleanupTimer?.Dispose();
        _batchSemaphore?.Dispose();

        // Dispose all semaphores
        foreach (var semaphore in _computationSemaphores.Values)
        {
            try
            {
                semaphore.Dispose();
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error disposing semaphore");
            }
        }

        _computationSemaphores.Clear();
        _computationCache.Clear();
        _objectPools.Clear();
    }
}

/// <summary>
/// Cache entry with expiration and metadata
/// </summary>
internal class CacheEntry
{
    public object Value { get; set; } = null!;
    public DateTime ExpirationTime { get; set; }
    public TimeSpan ComputationTime { get; set; }
    public long AccessCount { get; set; }

    public bool IsExpired => DateTime.UtcNow > ExpirationTime;
}

/// <summary>
/// Performance metrics for optimization tracking
/// </summary>
public class PerformanceMetrics
{
    /// <summary>
    /// Gets or sets the start time of metrics collection
    /// </summary>
    public DateTime StartTime { get; set; }

    /// <summary>
    /// Gets or sets the total number of operations
    /// </summary>
    public long TotalOperations { get; set; }

    /// <summary>
    /// Gets or sets the number of pool operations
    /// </summary>
    public long PoolOperations { get; set; }

    /// <summary>
    /// Gets or sets the number of cache operations
    /// </summary>
    public long CacheOperations { get; set; }

    /// <summary>
    /// Gets or sets the number of cache hits
    /// </summary>
    public long CacheHits { get; set; }

    /// <summary>
    /// Gets or sets the number of computation operations
    /// </summary>
    public long ComputationOperations { get; set; }

    /// <summary>
    /// Gets or sets the number of batch operations
    /// </summary>
    public long BatchOperations { get; set; }

    /// <summary>
    /// Gets or sets the number of failed operations
    /// </summary>
    public long FailedOperations { get; set; }

    /// <summary>
    /// Gets or sets the number of cleanup operations
    /// </summary>
    public long CleanupOperations { get; set; }

    /// <summary>
    /// Gets or sets the number of preload operations
    /// </summary>
    public long PreloadOperations { get; set; }

    /// <summary>
    /// Gets or sets the average operation time
    /// </summary>
    public TimeSpan AverageOperationTime { get; set; }

    /// <summary>
    /// Gets or sets the cache hit ratio
    /// </summary>
    public double CacheHitRatio { get; set; }

    /// <summary>
    /// Gets or sets the pool utilization ratio
    /// </summary>
    public double PoolUtilization { get; set; }

    /// <summary>
    /// Gets or sets the current cache size
    /// </summary>
    public int CacheSize { get; set; }

    /// <summary>
    /// Gets or sets the number of active pool types
    /// </summary>
    public int ActivePoolTypes { get; set; }

    /// <summary>
    /// Gets or sets the current memory pressure
    /// </summary>
    public long MemoryPressure { get; set; }

    /// <summary>
    /// Gets or sets the uptime
    /// </summary>
    public TimeSpan UpTime { get; set; }

    /// <summary>
    /// Gets or sets the success ratio
    /// </summary>
    public double SuccessRatio => TotalOperations > 0 ?
        (double)(TotalOperations - FailedOperations) / TotalOperations : 1.0;

    /// <summary>
    /// Gets or sets the operations per second
    /// </summary>
    public double OperationsPerSecond => UpTime.TotalSeconds > 0 ?
        TotalOperations / UpTime.TotalSeconds : 0.0;
}

/// <summary>
/// Custom pooled object policy for better control
/// </summary>
public class DefaultPooledObjectPolicy<T> : IPooledObjectPolicy<T> where T : class
{
    private readonly Func<T> _createFunc;
    private readonly Func<T, bool> _resetFunc;

    public DefaultPooledObjectPolicy(Func<T> createFunc, Func<T, bool> resetFunc)
    {
        _createFunc = createFunc ?? throw new ArgumentNullException(nameof(createFunc));
        _resetFunc = resetFunc ?? throw new ArgumentNullException(nameof(resetFunc));
    }

    public T Create()
    {
        return _createFunc();
    }

    public bool Return(T obj)
    {
        if (obj == null)
            return false;

        try
        {
            return _resetFunc(obj);
        }
        catch
        {
            return false;
        }
    }
}
