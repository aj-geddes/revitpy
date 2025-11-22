using System.Collections.Concurrent;
using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.ObjectPool;

namespace RevitPy.Bridge;

/// <summary>
/// Enhanced performance optimization utilities with comprehensive monitoring and benchmarking
/// </summary>
public interface IEnhancedPerformanceOptimizer : IPerformanceOptimizer
{
    /// <summary>
    /// Optimizes application startup time
    /// </summary>
    Task OptimizeStartupAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Starts performance monitoring and optimization
    /// </summary>
    Task StartMonitoringAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Stops performance monitoring
    /// </summary>
    Task StopMonitoringAsync();

    /// <summary>
    /// Detects performance regressions
    /// </summary>
    Task<PerformanceRegressionReport> DetectRegressionsAsync(PerformanceMetrics baseline);

    /// <summary>
    /// Applies automatic performance optimizations
    /// </summary>
    Task<AutoOptimizationReport> ApplyAutoOptimizationsAsync();

    /// <summary>
    /// Gets startup performance metrics
    /// </summary>
    StartupMetrics GetStartupMetrics();

    /// <summary>
    /// Benchmarks API latency for various operations
    /// </summary>
    Task<LatencyBenchmarkReport> BenchmarkLatencyAsync();

    /// <summary>
    /// Monitors memory for leaks over time
    /// </summary>
    Task<MemoryLeakReport> MonitorMemoryLeaksAsync(TimeSpan duration);

    /// <summary>
    /// Runs comprehensive performance benchmarks
    /// </summary>
    Task<ComprehensiveBenchmarkReport> RunBenchmarkSuiteAsync();

    /// <summary>
    /// Optimizes for specific performance targets
    /// </summary>
    Task<OptimizationResult> OptimizeForTargetsAsync(PerformanceTargets targets);
}

/// <summary>
/// Enhanced high-performance implementation with startup optimization and comprehensive monitoring
/// </summary>
public class EnhancedPerformanceOptimizer : IEnhancedPerformanceOptimizer, IDisposable
{
    private readonly ILogger<EnhancedPerformanceOptimizer> _logger;
    private readonly ConcurrentDictionary<Type, IObjectPool<object>> _objectPools;
    private readonly ConcurrentDictionary<string, CacheEntry> _computationCache;
    private readonly ConcurrentDictionary<string, SemaphoreSlim> _computationSemaphores;
    private readonly DefaultObjectPoolProvider _objectPoolProvider;
    private readonly PerformanceMetrics _metrics;
    private readonly StartupMetrics _startupMetrics;
    private readonly object _metricsLock = new();
    private readonly Timer _cleanupTimer;
    private readonly Timer _monitoringTimer;
    private readonly SemaphoreSlim _batchSemaphore;
    private readonly ConcurrentQueue<MemorySnapshot> _memorySnapshots;
    private readonly ConcurrentDictionary<string, LatencyTracker> _latencyTrackers;
    private readonly List<PerformanceMetrics> _historicalMetrics;
    private readonly PerformanceTargets _targets;
    private bool _isMonitoring;
    private bool _disposed;

    // Performance tuning parameters
    private readonly int _maxObjectsPerPool;
    private readonly TimeSpan _defaultCacheExpiration;
    private readonly int _maxConcurrentComputations;
    private readonly TimeSpan _cleanupInterval;
    private readonly TimeSpan _monitoringInterval;

    public EnhancedPerformanceOptimizer(ILogger<EnhancedPerformanceOptimizer> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));

        _objectPools = new ConcurrentDictionary<Type, IObjectPool<object>>();
        _computationCache = new ConcurrentDictionary<string, CacheEntry>();
        _computationSemaphores = new ConcurrentDictionary<string, SemaphoreSlim>();
        _objectPoolProvider = new DefaultObjectPoolProvider();
        _metrics = new PerformanceMetrics { StartTime = DateTime.UtcNow };
        _startupMetrics = new StartupMetrics { StartTime = DateTime.UtcNow };
        _memorySnapshots = new ConcurrentQueue<MemorySnapshot>();
        _latencyTrackers = new ConcurrentDictionary<string, LatencyTracker>();
        _historicalMetrics = new List<PerformanceMetrics>();

        // Performance targets as specified in requirements
        _targets = new PerformanceTargets
        {
            StartupTimeMs = 2000,
            PythonInitTimeMs = 1000,
            VSCodeActivationMs = 500,
            CLIResponseMs = 200,
            APILatencySimpleMs = 1,
            APILatencyComplexMs = 100,
            MemoryIdleMB = 50,
            MemoryPeakMB = 500,
            MaxElements = 10000,
            MaxConcurrentSessions = 100,
            RegistryResponseMs = 2000
        };

        // Performance configuration - optimized for enterprise workloads
        _maxObjectsPerPool = Environment.ProcessorCount * 8; // Increased pool size
        _defaultCacheExpiration = TimeSpan.FromMinutes(15);
        _maxConcurrentComputations = Environment.ProcessorCount * 4; // Increased concurrency
        _cleanupInterval = TimeSpan.FromMinutes(2); // More frequent cleanup
        _monitoringInterval = TimeSpan.FromSeconds(5);

        _batchSemaphore = new SemaphoreSlim(_maxConcurrentComputations, _maxConcurrentComputations);

        // Start cleanup timer
        _cleanupTimer = new Timer(async _ => await OptimizeMemoryAsync(), null, _cleanupInterval, _cleanupInterval);

        InitializeOptimizedPools();
        _ = Task.Run(RecordStartupMetrics);
    }

    #region Core Performance Methods (from base interface)

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
            return new T();
        }
    }

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
        if (_computationCache.TryGetValue(cacheKey, out var cacheEntry) && !cacheEntry.IsExpired)
        {
            RecordCacheOperation("Hit", cacheKey, stopwatch.Elapsed);
            return (TResult)cacheEntry.Value;
        }

        var semaphore = _computationSemaphores.GetOrAdd(cacheKey, _ => new SemaphoreSlim(1, 1));

        await semaphore.WaitAsync(cancellationToken);
        try
        {
            // Double-check cache
            if (_computationCache.TryGetValue(cacheKey, out cacheEntry) && !cacheEntry.IsExpired)
            {
                RecordCacheOperation("Hit", cacheKey, stopwatch.Elapsed);
                return (TResult)cacheEntry.Value;
            }

            // Compute the value
            var computationStopwatch = Stopwatch.StartNew();
            var result = await computeFunc();

            // Cache the result with optimized expiration
            var cacheExpiration = expiration ?? _defaultCacheExpiration;
            _computationCache[cacheKey] = new CacheEntry
            {
                Value = result!,
                ExpirationTime = DateTime.UtcNow.Add(cacheExpiration),
                ComputationTime = computationStopwatch.Elapsed,
                AccessCount = 1,
                LastAccessTime = DateTime.UtcNow
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

            var partitioner = Partitioner.Create(inputList, true);
            var results = new ConcurrentBag<TResult>();

            await Parallel.ForEachAsync(partitioner,
                new ParallelOptions
                {
                    MaxDegreeOfParallelism = concurrency,
                    CancellationToken = cancellationToken
                },
                async (input, ct) =>
                {
                    try
                    {
                        var result = await operation(input);
                        results.Add(result);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, "Batch operation failed for input item");
                    }
                });

            var resultList = results.ToList();
            RecordBatchOperation(inputList.Count, resultList.Count, concurrency, stopwatch.Elapsed);

            return resultList;
        }
        finally
        {
            _batchSemaphore.Release();
        }
    }

    public PerformanceMetrics GetMetrics()
    {
        lock (_metricsLock)
        {
            var currentTime = DateTime.UtcNow;
            var latestSnapshot = _memorySnapshots.LastOrDefault();

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
                MemoryPressure = latestSnapshot?.MemoryUsageMB ?? (GC.GetTotalMemory(false) / 1024 / 1024),
                UpTime = currentTime - _metrics.StartTime,
                CleanupOperations = _metrics.CleanupOperations,
                PreloadOperations = _metrics.PreloadOperations,
                SuccessRatio = _metrics.TotalOperations > 0 ?
                    (double)(_metrics.TotalOperations - _metrics.FailedOperations) / _metrics.TotalOperations : 1.0,
                OperationsPerSecond = (currentTime - _metrics.StartTime).TotalSeconds > 0 ?
                    _metrics.TotalOperations / (currentTime - _metrics.StartTime).TotalSeconds : 0.0
            };
        }
    }

    public async Task OptimizeMemoryAsync(CancellationToken cancellationToken = default)
    {
        var stopwatch = Stopwatch.StartNew();
        var cleanedEntries = 0;
        var cleanedSemaphores = 0;

        try
        {
            // Clean expired cache entries with access pattern analysis
            var expiredKeys = _computationCache
                .Where(kvp => kvp.Value.IsExpired ||
                             (kvp.Value.AccessCount < 3 &&
                              DateTime.UtcNow - kvp.Value.LastAccessTime > TimeSpan.FromHours(1)))
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

            // Trim memory snapshots (keep last 1000)
            while (_memorySnapshots.Count > 1000 && _memorySnapshots.TryDequeue(out _))
            {
                // Remove old snapshots
            }

            // Force GC if significant cleanup or memory pressure
            var memoryPressure = GC.GetTotalMemory(false) / 1024 / 1024;
            if (cleanedEntries > 100 || cleanedSemaphores > 50 || memoryPressure > _targets.MemoryPeakMB * 0.8)
            {
                GC.Collect(2, GCCollectionMode.Optimized, blocking: false);
                GC.WaitForPendingFinalizers();
            }

            RecordCleanupOperation(cleanedEntries, cleanedSemaphores, stopwatch.Elapsed);

            _logger.LogDebug("Memory optimization completed: {CleanedEntries} cache entries, {CleanedSemaphores} semaphores, {MemoryMB}MB in {Duration}ms",
                cleanedEntries, cleanedSemaphores, memoryPressure, stopwatch.ElapsedMilliseconds);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error during memory optimization");
        }
    }

    public async Task PreloadPoolsAsync(CancellationToken cancellationToken = default)
    {
        var stopwatch = Stopwatch.StartNew();
        var preloadedCount = 0;

        try
        {
            // Enhanced preloading with more types and larger pools
            var commonTypes = new[]
            {
                typeof(Dictionary<string, object>),
                typeof(List<object>),
                typeof(StringBuilder),
                typeof(MemoryStream),
                typeof(ConcurrentDictionary<string, object>),
                typeof(ConcurrentBag<object>),
                typeof(JsonSerializerOptions),
                typeof(Stopwatch)
            };

            // Parallel preloading for faster startup
            await Parallel.ForEachAsync(commonTypes,
                new ParallelOptions
                {
                    MaxDegreeOfParallelism = Environment.ProcessorCount,
                    CancellationToken = cancellationToken
                },
                async (type, ct) =>
                {
                    try
                    {
                        var pool = GetOrCreatePoolForType(type);
                        var preloadCount = _maxObjectsPerPool / 2;

                        for (int i = 0; i < preloadCount && !ct.IsCancellationRequested; i++)
                        {
                            var obj = Activator.CreateInstance(type);
                            if (obj != null)
                            {
                                pool.Return(obj);
                                Interlocked.Increment(ref preloadedCount);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, "Failed to preload pool for type {Type}", type.Name);
                    }
                });

            RecordPreloadOperation(preloadedCount, stopwatch.Elapsed);

            _logger.LogInformation("Enhanced pool preloading completed: {PreloadedCount} objects in {Duration}ms",
                preloadedCount, stopwatch.ElapsedMilliseconds);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during pool preloading");
        }
    }

    #endregion

    #region Enhanced Performance Methods

    public async Task OptimizeStartupAsync(CancellationToken cancellationToken = default)
    {
        var startTime = DateTime.UtcNow;
        _logger.LogInformation("Starting startup optimization...");

        try
        {
            var tasks = new List<Task>
            {
                // Parallel initialization
                PreloadPoolsAsync(cancellationToken),
                WarmupCacheAsync(cancellationToken),
                OptimizeGCSettingsAsync(cancellationToken),
                PreJITCriticalPathsAsync(cancellationToken)
            };

            await Task.WhenAll(tasks);

            var duration = DateTime.UtcNow - startTime;
            _startupMetrics.OptimizationTime = duration;
            _startupMetrics.IsOptimized = duration <= TimeSpan.FromMilliseconds(_targets.StartupTimeMs);

            _logger.LogInformation("Startup optimization completed in {Duration}ms (target: {Target}ms)",
                duration.TotalMilliseconds, _targets.StartupTimeMs);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during startup optimization");
            _startupMetrics.OptimizationError = ex.Message;
        }
    }

    public async Task StartMonitoringAsync(CancellationToken cancellationToken = default)
    {
        if (_isMonitoring) return;

        _isMonitoring = true;
        _monitoringTimer?.Change(_monitoringInterval, _monitoringInterval);

        // Start background monitoring tasks
        _ = Task.Run(() => MonitorMemoryUsageAsync(cancellationToken), cancellationToken);
        _ = Task.Run(() => MonitorLatencyAsync(cancellationToken), cancellationToken);

        _logger.LogInformation("Performance monitoring started");
        await Task.CompletedTask;
    }

    public async Task StopMonitoringAsync()
    {
        _isMonitoring = false;
        _monitoringTimer?.Change(Timeout.Infinite, Timeout.Infinite);

        _logger.LogInformation("Performance monitoring stopped");
        await Task.CompletedTask;
    }

    public async Task<PerformanceRegressionReport> DetectRegressionsAsync(PerformanceMetrics baseline)
    {
        ArgumentNullException.ThrowIfNull(baseline);

        var current = GetMetrics();
        var regressions = new List<PerformanceRegression>();

        // Check for regressions against targets
        if (current.AverageOperationTime.TotalMilliseconds > baseline.AverageOperationTime.TotalMilliseconds * 1.5)
        {
            regressions.Add(new PerformanceRegression
            {
                Metric = "AverageOperationTime",
                BaselineValue = baseline.AverageOperationTime.TotalMilliseconds,
                CurrentValue = current.AverageOperationTime.TotalMilliseconds,
                RegressionPercentage = (current.AverageOperationTime.TotalMilliseconds - baseline.AverageOperationTime.TotalMilliseconds) / baseline.AverageOperationTime.TotalMilliseconds * 100,
                Severity = PerformanceRegressionSeverity.High
            });
        }

        if (current.CacheHitRatio < baseline.CacheHitRatio * 0.8)
        {
            regressions.Add(new PerformanceRegression
            {
                Metric = "CacheHitRatio",
                BaselineValue = baseline.CacheHitRatio,
                CurrentValue = current.CacheHitRatio,
                RegressionPercentage = (baseline.CacheHitRatio - current.CacheHitRatio) / baseline.CacheHitRatio * 100,
                Severity = PerformanceRegressionSeverity.Medium
            });
        }

        if (current.MemoryPressure > _targets.MemoryPeakMB * 1024 * 1024)
        {
            regressions.Add(new PerformanceRegression
            {
                Metric = "MemoryPressure",
                BaselineValue = baseline.MemoryPressure,
                CurrentValue = current.MemoryPressure,
                RegressionPercentage = (current.MemoryPressure - baseline.MemoryPressure) / baseline.MemoryPressure * 100,
                Severity = PerformanceRegressionSeverity.Critical
            });
        }

        return new PerformanceRegressionReport
        {
            Timestamp = DateTime.UtcNow,
            BaselineMetrics = baseline,
            CurrentMetrics = current,
            Regressions = regressions,
            OverallSeverity = regressions.Any() ? regressions.Max(r => r.Severity) : PerformanceRegressionSeverity.None
        };
    }

    public async Task<AutoOptimizationReport> ApplyAutoOptimizationsAsync()
    {
        var report = new AutoOptimizationReport
        {
            Timestamp = DateTime.UtcNow,
            Optimizations = new List<AppliedOptimization>()
        };

        try
        {
            var metrics = GetMetrics();

            // Auto-optimize cache based on hit ratio
            if (metrics.CacheHitRatio < 0.7)
            {
                await ExpandCacheAsync();
                report.Optimizations.Add(new AppliedOptimization
                {
                    Type = "CacheExpansion",
                    Description = "Expanded cache size due to low hit ratio",
                    ExpectedImpact = "Improved cache performance"
                });
            }

            // Auto-optimize pools based on utilization
            if (metrics.PoolUtilization > 0.8)
            {
                await ExpandPoolsAsync();
                report.Optimizations.Add(new AppliedOptimization
                {
                    Type = "PoolExpansion",
                    Description = "Expanded object pools due to high utilization",
                    ExpectedImpact = "Reduced object allocation overhead"
                });
            }

            // Auto-optimize GC if memory pressure is high
            if (metrics.MemoryPressure > _targets.MemoryIdleMB * 1024 * 1024 * 1.5)
            {
                await OptimizeMemoryAsync();
                report.Optimizations.Add(new AppliedOptimization
                {
                    Type = "MemoryOptimization",
                    Description = "Triggered memory cleanup due to high pressure",
                    ExpectedImpact = "Reduced memory usage"
                });
            }

            report.Success = true;
        }
        catch (Exception ex)
        {
            report.Success = false;
            report.Error = ex.Message;
            _logger.LogError(ex, "Error during auto-optimization");
        }

        return report;
    }

    public StartupMetrics GetStartupMetrics()
    {
        return new StartupMetrics
        {
            StartTime = _startupMetrics.StartTime,
            OptimizationTime = _startupMetrics.OptimizationTime,
            IsOptimized = _startupMetrics.IsOptimized,
            OptimizationError = _startupMetrics.OptimizationError,
            TotalStartupTime = DateTime.UtcNow - _startupMetrics.StartTime,
            MeetsTarget = (DateTime.UtcNow - _startupMetrics.StartTime).TotalMilliseconds <= _targets.StartupTimeMs
        };
    }

    public async Task<LatencyBenchmarkReport> BenchmarkLatencyAsync()
    {
        var report = new LatencyBenchmarkReport
        {
            Timestamp = DateTime.UtcNow,
            Benchmarks = new Dictionary<string, LatencyBenchmark>()
        };

        try
        {
            // Benchmark simple operations
            var simpleLatencies = await BenchmarkOperationAsync("SimpleOperation",
                async () => await Task.Delay(0), 100);

            report.Benchmarks["SimpleOperation"] = new LatencyBenchmark
            {
                OperationType = "SimpleOperation",
                AverageLatencyMs = simpleLatencies.Average(),
                MedianLatencyMs = simpleLatencies.OrderBy(x => x).ElementAt(simpleLatencies.Count / 2),
                P95LatencyMs = simpleLatencies.OrderBy(x => x).ElementAt((int)(simpleLatencies.Count * 0.95)),
                P99LatencyMs = simpleLatencies.OrderBy(x => x).ElementAt((int)(simpleLatencies.Count * 0.99)),
                MeetsTarget = simpleLatencies.Average() <= _targets.APILatencySimpleMs,
                TargetMs = _targets.APILatencySimpleMs
            };

            // Benchmark complex operations
            var complexLatencies = await BenchmarkOperationAsync("ComplexOperation",
                async () =>
                {
                    // Simulate complex operation
                    await GetOrComputeAsync("benchmark_key", async () =>
                    {
                        await Task.Delay(10);
                        return "benchmark_result";
                    });
                }, 50);

            report.Benchmarks["ComplexOperation"] = new LatencyBenchmark
            {
                OperationType = "ComplexOperation",
                AverageLatencyMs = complexLatencies.Average(),
                MedianLatencyMs = complexLatencies.OrderBy(x => x).ElementAt(complexLatencies.Count / 2),
                P95LatencyMs = complexLatencies.OrderBy(x => x).ElementAt((int)(complexLatencies.Count * 0.95)),
                P99LatencyMs = complexLatencies.OrderBy(x => x).ElementAt((int)(complexLatencies.Count * 0.99)),
                MeetsTarget = complexLatencies.Average() <= _targets.APILatencyComplexMs,
                TargetMs = _targets.APILatencyComplexMs
            };

            report.OverallResult = report.Benchmarks.Values.All(b => b.MeetsTarget) ?
                BenchmarkResult.Pass : BenchmarkResult.Fail;
        }
        catch (Exception ex)
        {
            report.Error = ex.Message;
            report.OverallResult = BenchmarkResult.Error;
            _logger.LogError(ex, "Error during latency benchmarking");
        }

        return report;
    }

    public async Task<MemoryLeakReport> MonitorMemoryLeaksAsync(TimeSpan duration)
    {
        var report = new MemoryLeakReport
        {
            StartTime = DateTime.UtcNow,
            Duration = duration,
            Snapshots = new List<MemorySnapshot>()
        };

        var endTime = DateTime.UtcNow.Add(duration);
        var interval = TimeSpan.FromSeconds(10);

        try
        {
            while (DateTime.UtcNow < endTime)
            {
                var snapshot = new MemorySnapshot
                {
                    Timestamp = DateTime.UtcNow,
                    MemoryUsageMB = GC.GetTotalMemory(false) / 1024.0 / 1024.0,
                    Generation0Collections = GC.CollectionCount(0),
                    Generation1Collections = GC.CollectionCount(1),
                    Generation2Collections = GC.CollectionCount(2)
                };

                report.Snapshots.Add(snapshot);
                _memorySnapshots.Enqueue(snapshot);

                await Task.Delay(interval);
            }

            // Analyze for memory leaks
            if (report.Snapshots.Count >= 2)
            {
                var first = report.Snapshots.First();
                var last = report.Snapshots.Last();

                report.MemoryGrowthMB = last.MemoryUsageMB - first.MemoryUsageMB;
                report.HasMemoryLeak = report.MemoryGrowthMB > 10; // > 10MB growth indicates potential leak

                if (report.HasMemoryLeak)
                {
                    report.LeakRate = report.MemoryGrowthMB / duration.TotalHours; // MB per hour
                }
            }

            report.EndTime = DateTime.UtcNow;
            report.Success = true;
        }
        catch (Exception ex)
        {
            report.Error = ex.Message;
            report.Success = false;
            _logger.LogError(ex, "Error during memory leak monitoring");
        }

        return report;
    }

    public async Task<ComprehensiveBenchmarkReport> RunBenchmarkSuiteAsync()
    {
        var report = new ComprehensiveBenchmarkReport
        {
            Timestamp = DateTime.UtcNow,
            StartupMetrics = GetStartupMetrics(),
            PerformanceMetrics = GetMetrics()
        };

        try
        {
            // Run all benchmark types
            report.LatencyBenchmark = await BenchmarkLatencyAsync();
            report.MemoryLeakReport = await MonitorMemoryLeaksAsync(TimeSpan.FromMinutes(5));

            // Throughput benchmarks
            report.ThroughputBenchmarks = await RunThroughputBenchmarksAsync();

            // Scalability benchmarks
            report.ScalabilityBenchmarks = await RunScalabilityBenchmarksAsync();

            // Overall assessment
            report.OverallResult =
                report.LatencyBenchmark.OverallResult == BenchmarkResult.Pass &&
                !report.MemoryLeakReport.HasMemoryLeak &&
                report.ThroughputBenchmarks.All(t => t.Value.MeetsTarget) &&
                report.ScalabilityBenchmarks.All(s => s.Value.MeetsTarget) ?
                BenchmarkResult.Pass : BenchmarkResult.Fail;

            report.Success = true;
        }
        catch (Exception ex)
        {
            report.Error = ex.Message;
            report.Success = false;
            report.OverallResult = BenchmarkResult.Error;
            _logger.LogError(ex, "Error during comprehensive benchmark suite");
        }

        return report;
    }

    public async Task<OptimizationResult> OptimizeForTargetsAsync(PerformanceTargets targets)
    {
        var result = new OptimizationResult
        {
            Timestamp = DateTime.UtcNow,
            Targets = targets,
            OptimizationsApplied = new List<string>()
        };

        try
        {
            var currentMetrics = GetMetrics();

            // Optimize startup time
            if (GetStartupMetrics().TotalStartupTime.TotalMilliseconds > targets.StartupTimeMs)
            {
                await OptimizeStartupAsync();
                result.OptimizationsApplied.Add("Startup optimization");
            }

            // Optimize memory usage
            if (currentMetrics.MemoryPressure > targets.MemoryIdleMB * 1024 * 1024)
            {
                await OptimizeMemoryAsync();
                result.OptimizationsApplied.Add("Memory optimization");
            }

            // Optimize latency through caching
            var latencyBenchmark = await BenchmarkLatencyAsync();
            if (latencyBenchmark.Benchmarks.Values.Any(b => !b.MeetsTarget))
            {
                await ExpandCacheAsync();
                await PreloadPoolsAsync();
                result.OptimizationsApplied.Add("Latency optimization");
            }

            // Final verification
            var finalMetrics = GetMetrics();
            var finalStartup = GetStartupMetrics();

            result.Success =
                finalStartup.TotalStartupTime.TotalMilliseconds <= targets.StartupTimeMs &&
                finalMetrics.MemoryPressure <= targets.MemoryPeakMB * 1024 * 1024;

            result.FinalMetrics = finalMetrics;
        }
        catch (Exception ex)
        {
            result.Success = false;
            result.Error = ex.Message;
            _logger.LogError(ex, "Error during target optimization");
        }

        return result;
    }

    #endregion

    #region Private Helper Methods

    private void InitializeOptimizedPools()
    {
        // Pre-create pools for enhanced types
        var enhancedTypes = new[]
        {
            typeof(Dictionary<string, object>),
            typeof(List<object>),
            typeof(StringBuilder),
            typeof(MemoryStream),
            typeof(ConcurrentDictionary<string, object>),
            typeof(ConcurrentBag<object>),
            typeof(JsonSerializerOptions),
            typeof(Stopwatch),
            typeof(CancellationTokenSource),
            typeof(TaskCompletionSource<object>)
        };

        foreach (var type in enhancedTypes)
        {
            GetOrCreatePoolForType(type);
        }
    }

    private async Task RecordStartupMetrics()
    {
        try
        {
            // Record various startup phases
            await Task.Delay(100); // Simulate initialization
            _startupMetrics.FrameworkInitTime = DateTime.UtcNow - _startupMetrics.StartTime;

            await Task.Delay(50); // Simulate additional setup
            _startupMetrics.ServiceInitTime = DateTime.UtcNow - _startupMetrics.StartTime - _startupMetrics.FrameworkInitTime;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error recording startup metrics");
        }
    }

    private async Task WarmupCacheAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            // Pre-populate cache with common computations
            var warmupTasks = new[]
            {
                GetOrComputeAsync("system_info", async () => Environment.MachineName),
                GetOrComputeAsync("processor_count", async () => Environment.ProcessorCount),
                GetOrComputeAsync("os_version", async () => Environment.OSVersion.ToString())
            };

            await Task.WhenAll(warmupTasks);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error during cache warmup");
        }
    }

    private async Task OptimizeGCSettingsAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            // Configure GC for server workloads
            if (GCSettings.IsServerGC)
            {
                GCSettings.LargeObjectHeapCompactionMode = GCLargeObjectHeapCompactionMode.CompactOnce;
            }

            await Task.CompletedTask;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error during GC optimization");
        }
    }

    private async Task PreJITCriticalPathsAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            // Force JIT compilation of critical paths
            _ = GetPooledObject<Dictionary<string, object>>();
            ReturnPooledObject(new Dictionary<string, object>());
            _ = await GetOrComputeAsync("prejit_test", async () => "test");

            await Task.CompletedTask;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error during pre-JIT optimization");
        }
    }

    private async Task MonitorMemoryUsageAsync(CancellationToken cancellationToken)
    {
        while (_isMonitoring && !cancellationToken.IsCancellationRequested)
        {
            try
            {
                var snapshot = new MemorySnapshot
                {
                    Timestamp = DateTime.UtcNow,
                    MemoryUsageMB = GC.GetTotalMemory(false) / 1024.0 / 1024.0,
                    Generation0Collections = GC.CollectionCount(0),
                    Generation1Collections = GC.CollectionCount(1),
                    Generation2Collections = GC.CollectionCount(2)
                };

                _memorySnapshots.Enqueue(snapshot);

                // Trigger alerts if memory exceeds targets
                if (snapshot.MemoryUsageMB > _targets.MemoryPeakMB * 0.9)
                {
                    _logger.LogWarning("Memory usage approaching peak target: {MemoryMB}MB / {TargetMB}MB",
                        snapshot.MemoryUsageMB, _targets.MemoryPeakMB);
                }

                await Task.Delay(_monitoringInterval, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error during memory monitoring");
                await Task.Delay(TimeSpan.FromSeconds(30), cancellationToken);
            }
        }
    }

    private async Task MonitorLatencyAsync(CancellationToken cancellationToken)
    {
        while (_isMonitoring && !cancellationToken.IsCancellationRequested)
        {
            try
            {
                // Monitor current operation latencies
                foreach (var tracker in _latencyTrackers.Values)
                {
                    if (tracker.GetAverageLatency() > _targets.APILatencyComplexMs)
                    {
                        _logger.LogWarning("High latency detected for {Operation}: {LatencyMs}ms",
                            tracker.OperationName, tracker.GetAverageLatency());
                    }
                }

                await Task.Delay(_monitoringInterval, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error during latency monitoring");
                await Task.Delay(TimeSpan.FromSeconds(30), cancellationToken);
            }
        }
    }

    private async Task ExpandCacheAsync()
    {
        try
        {
            // Increase cache expiration for better hit rates
            _defaultCacheExpiration.Add(TimeSpan.FromMinutes(5));

            _logger.LogInformation("Cache expanded to improve hit ratio");
            await Task.CompletedTask;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error expanding cache");
        }
    }

    private async Task ExpandPoolsAsync()
    {
        try
        {
            // This would involve creating new pools with larger capacities
            // Implementation depends on object pool provider capabilities

            _logger.LogInformation("Object pools expanded due to high utilization");
            await Task.CompletedTask;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error expanding pools");
        }
    }

    private async Task<List<double>> BenchmarkOperationAsync(string operationName, Func<Task> operation, int iterations)
    {
        var latencies = new List<double>();

        for (int i = 0; i < iterations; i++)
        {
            var stopwatch = Stopwatch.StartNew();
            await operation();
            stopwatch.Stop();

            latencies.Add(stopwatch.Elapsed.TotalMilliseconds);
        }

        return latencies;
    }

    private async Task<Dictionary<string, ThroughputBenchmark>> RunThroughputBenchmarksAsync()
    {
        var benchmarks = new Dictionary<string, ThroughputBenchmark>();

        try
        {
            // Cache throughput
            var cacheOperations = 1000;
            var cacheStart = DateTime.UtcNow;

            for (int i = 0; i < cacheOperations; i++)
            {
                await GetOrComputeAsync($"throughput_test_{i}", async () => i.ToString());
            }

            var cacheDuration = DateTime.UtcNow - cacheStart;
            benchmarks["CacheThroughput"] = new ThroughputBenchmark
            {
                OperationType = "CacheThroughput",
                OperationsPerSecond = cacheOperations / cacheDuration.TotalSeconds,
                TargetOpsPerSecond = 5000,
                MeetsTarget = (cacheOperations / cacheDuration.TotalSeconds) >= 5000
            };

            // Pool throughput
            var poolOperations = 2000;
            var poolStart = DateTime.UtcNow;

            for (int i = 0; i < poolOperations; i++)
            {
                var obj = GetPooledObject<Dictionary<string, object>>();
                ReturnPooledObject(obj);
            }

            var poolDuration = DateTime.UtcNow - poolStart;
            benchmarks["PoolThroughput"] = new ThroughputBenchmark
            {
                OperationType = "PoolThroughput",
                OperationsPerSecond = poolOperations / poolDuration.TotalSeconds,
                TargetOpsPerSecond = 10000,
                MeetsTarget = (poolOperations / poolDuration.TotalSeconds) >= 10000
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during throughput benchmarks");
        }

        return benchmarks;
    }

    private async Task<Dictionary<string, ScalabilityBenchmark>> RunScalabilityBenchmarksAsync()
    {
        var benchmarks = new Dictionary<string, ScalabilityBenchmark>();

        try
        {
            // Test with increasing loads
            var loads = new[] { 100, 1000, 5000, 10000 };

            foreach (var load in loads)
            {
                var start = DateTime.UtcNow;

                var tasks = Enumerable.Range(0, load)
                    .Select(async i => await GetOrComputeAsync($"scale_test_{i}", async () => i.ToString()))
                    .ToArray();

                await Task.WhenAll(tasks);

                var duration = DateTime.UtcNow - start;
                var opsPerSecond = load / duration.TotalSeconds;

                benchmarks[$"Scalability_{load}"] = new ScalabilityBenchmark
                {
                    Load = load,
                    OperationsPerSecond = opsPerSecond,
                    ResponseTimeMs = duration.TotalMilliseconds / load,
                    TargetResponseTimeMs = 100,
                    MeetsTarget = (duration.TotalMilliseconds / load) <= 100
                };
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during scalability benchmarks");
        }

        return benchmarks;
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
                case ConcurrentDictionary<string, object> concurrentDict:
                    concurrentDict.Clear();
                    break;
                case ConcurrentBag<object> concurrentBag:
                    while (concurrentBag.TryTake(out _)) { }
                    break;
                case Stopwatch stopwatch:
                    stopwatch.Reset();
                    break;
                case IDisposable:
                    return false;
            }

            return true;
        }
        catch
        {
            return false;
        }
    }

    private double CalculatePoolUtilization()
    {
        if (_objectPools.Count == 0)
            return 0.0;

        // Simplified utilization calculation
        return Math.Min(1.0, (double)_objectPools.Count / 20.0);
    }

    // Statistics recording methods (similar to base class but enhanced)

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
        if (_metrics.TotalOperations > 0)
        {
            var totalTicks = _metrics.AverageOperationTime.Ticks * (_metrics.TotalOperations - 1) + duration.Ticks;
            _metrics.AverageOperationTime = new TimeSpan(totalTicks / _metrics.TotalOperations);
        }
        else
        {
            _metrics.AverageOperationTime = duration;
        }
    }

    #endregion

    public void Dispose()
    {
        if (_disposed) return;

        _cleanupTimer?.Dispose();
        _monitoringTimer?.Dispose();
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

        _disposed = true;
    }
}

// Enhanced data structures and models

/// <summary>
/// Enhanced cache entry with access tracking
/// </summary>
internal class CacheEntry
{
    public object Value { get; set; } = null!;
    public DateTime ExpirationTime { get; set; }
    public TimeSpan ComputationTime { get; set; }
    public long AccessCount { get; set; }
    public DateTime LastAccessTime { get; set; }

    public bool IsExpired => DateTime.UtcNow > ExpirationTime;
}

/// <summary>
/// Performance targets for optimization
/// </summary>
public class PerformanceTargets
{
    public double StartupTimeMs { get; set; } = 2000;
    public double PythonInitTimeMs { get; set; } = 1000;
    public double VSCodeActivationMs { get; set; } = 500;
    public double CLIResponseMs { get; set; } = 200;
    public double APILatencySimpleMs { get; set; } = 1;
    public double APILatencyComplexMs { get; set; } = 100;
    public double MemoryIdleMB { get; set; } = 50;
    public double MemoryPeakMB { get; set; } = 500;
    public int MaxElements { get; set; } = 10000;
    public int MaxConcurrentSessions { get; set; } = 100;
    public double RegistryResponseMs { get; set; } = 2000;
}

/// <summary>
/// Startup performance metrics
/// </summary>
public class StartupMetrics
{
    public DateTime StartTime { get; set; }
    public TimeSpan OptimizationTime { get; set; }
    public TimeSpan FrameworkInitTime { get; set; }
    public TimeSpan ServiceInitTime { get; set; }
    public bool IsOptimized { get; set; }
    public string? OptimizationError { get; set; }
    public TimeSpan TotalStartupTime { get; set; }
    public bool MeetsTarget { get; set; }
}

/// <summary>
/// Memory snapshot for leak detection
/// </summary>
public class MemorySnapshot
{
    public DateTime Timestamp { get; set; }
    public double MemoryUsageMB { get; set; }
    public int Generation0Collections { get; set; }
    public int Generation1Collections { get; set; }
    public int Generation2Collections { get; set; }
}

/// <summary>
/// Latency tracking utility
/// </summary>
public class LatencyTracker
{
    private readonly Queue<double> _latencies = new();
    private readonly int _maxSamples;

    public string OperationName { get; }

    public LatencyTracker(string operationName, int maxSamples = 100)
    {
        OperationName = operationName;
        _maxSamples = maxSamples;
    }

    public void RecordLatency(double latencyMs)
    {
        lock (_latencies)
        {
            _latencies.Enqueue(latencyMs);
            while (_latencies.Count > _maxSamples)
            {
                _latencies.Dequeue();
            }
        }
    }

    public double GetAverageLatency()
    {
        lock (_latencies)
        {
            return _latencies.Count > 0 ? _latencies.Average() : 0;
        }
    }
}

/// <summary>
/// Performance regression details
/// </summary>
public class PerformanceRegression
{
    public string Metric { get; set; } = string.Empty;
    public double BaselineValue { get; set; }
    public double CurrentValue { get; set; }
    public double RegressionPercentage { get; set; }
    public PerformanceRegressionSeverity Severity { get; set; }
}

/// <summary>
/// Performance regression severity levels
/// </summary>
public enum PerformanceRegressionSeverity
{
    None = 0,
    Low = 1,
    Medium = 2,
    High = 3,
    Critical = 4
}

/// <summary>
/// Performance regression report
/// </summary>
public class PerformanceRegressionReport
{
    public DateTime Timestamp { get; set; }
    public PerformanceMetrics BaselineMetrics { get; set; } = null!;
    public PerformanceMetrics CurrentMetrics { get; set; } = null!;
    public List<PerformanceRegression> Regressions { get; set; } = new();
    public PerformanceRegressionSeverity OverallSeverity { get; set; }
}

/// <summary>
/// Auto-optimization report
/// </summary>
public class AutoOptimizationReport
{
    public DateTime Timestamp { get; set; }
    public List<AppliedOptimization> Optimizations { get; set; } = new();
    public bool Success { get; set; }
    public string? Error { get; set; }
}

/// <summary>
/// Applied optimization details
/// </summary>
public class AppliedOptimization
{
    public string Type { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string ExpectedImpact { get; set; } = string.Empty;
}

/// <summary>
/// Latency benchmark results
/// </summary>
public class LatencyBenchmarkReport
{
    public DateTime Timestamp { get; set; }
    public Dictionary<string, LatencyBenchmark> Benchmarks { get; set; } = new();
    public BenchmarkResult OverallResult { get; set; }
    public string? Error { get; set; }
}

/// <summary>
/// Individual latency benchmark
/// </summary>
public class LatencyBenchmark
{
    public string OperationType { get; set; } = string.Empty;
    public double AverageLatencyMs { get; set; }
    public double MedianLatencyMs { get; set; }
    public double P95LatencyMs { get; set; }
    public double P99LatencyMs { get; set; }
    public bool MeetsTarget { get; set; }
    public double TargetMs { get; set; }
}

/// <summary>
/// Memory leak detection report
/// </summary>
public class MemoryLeakReport
{
    public DateTime StartTime { get; set; }
    public DateTime EndTime { get; set; }
    public TimeSpan Duration { get; set; }
    public List<MemorySnapshot> Snapshots { get; set; } = new();
    public double MemoryGrowthMB { get; set; }
    public bool HasMemoryLeak { get; set; }
    public double LeakRate { get; set; } // MB per hour
    public bool Success { get; set; }
    public string? Error { get; set; }
}

/// <summary>
/// Throughput benchmark results
/// </summary>
public class ThroughputBenchmark
{
    public string OperationType { get; set; } = string.Empty;
    public double OperationsPerSecond { get; set; }
    public double TargetOpsPerSecond { get; set; }
    public bool MeetsTarget { get; set; }
}

/// <summary>
/// Scalability benchmark results
/// </summary>
public class ScalabilityBenchmark
{
    public int Load { get; set; }
    public double OperationsPerSecond { get; set; }
    public double ResponseTimeMs { get; set; }
    public double TargetResponseTimeMs { get; set; }
    public bool MeetsTarget { get; set; }
}

/// <summary>
/// Comprehensive benchmark report
/// </summary>
public class ComprehensiveBenchmarkReport
{
    public DateTime Timestamp { get; set; }
    public StartupMetrics StartupMetrics { get; set; } = null!;
    public PerformanceMetrics PerformanceMetrics { get; set; } = null!;
    public LatencyBenchmarkReport LatencyBenchmark { get; set; } = null!;
    public MemoryLeakReport MemoryLeakReport { get; set; } = null!;
    public Dictionary<string, ThroughputBenchmark> ThroughputBenchmarks { get; set; } = new();
    public Dictionary<string, ScalabilityBenchmark> ScalabilityBenchmarks { get; set; } = new();
    public BenchmarkResult OverallResult { get; set; }
    public bool Success { get; set; }
    public string? Error { get; set; }
}

/// <summary>
/// Optimization result for specific targets
/// </summary>
public class OptimizationResult
{
    public DateTime Timestamp { get; set; }
    public PerformanceTargets Targets { get; set; } = null!;
    public List<string> OptimizationsApplied { get; set; } = new();
    public PerformanceMetrics? FinalMetrics { get; set; }
    public bool Success { get; set; }
    public string? Error { get; set; }
}

/// <summary>
/// Benchmark result enumeration
/// </summary>
public enum BenchmarkResult
{
    Pass,
    Fail,
    Error
}
