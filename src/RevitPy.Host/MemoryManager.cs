using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Core.Configuration;
using System.Diagnostics;

namespace RevitPy.Host;

/// <summary>
/// Implementation of IMemoryManager for monitoring and managing memory usage
/// </summary>
public class MemoryManager : IMemoryManager, IDisposable
{
    private readonly ILogger<MemoryManager> _logger;
    private readonly RevitPyOptions _options;
    private readonly Timer? _monitoringTimer;
    private readonly object _lock = new();

    private bool _isRunning;
    private bool _isDisposed;
    private long _memoryThresholdBytes;
    private MemoryManagerStats _stats = new();

    public MemoryManagerStats Stats
    {
        get
        {
            lock (_lock)
            {
                return new MemoryManagerStats
                {
                    AutomaticGcTriggers = _stats.AutomaticGcTriggers,
                    ManualGcCalls = _stats.ManualGcCalls,
                    PeakMemoryUsage = _stats.PeakMemoryUsage,
                    CurrentThreshold = _memoryThresholdBytes,
                    LastCleanup = _stats.LastCleanup,
                    AverageMemoryAfterCleanup = _stats.AverageMemoryAfterCleanup
                };
            }
        }
    }

    public MemoryManager(ILogger<MemoryManager> logger, IOptions<RevitPyOptions> options)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        
        _memoryThresholdBytes = _options.MaxMemoryUsageMB * 1024 * 1024;

        if (_options.EnableMemoryProfiling)
        {
            _monitoringTimer = new Timer(async _ => await MonitorMemoryAsync(), 
                null, 
                TimeSpan.FromMilliseconds(_options.MemoryCheckInterval),
                TimeSpan.FromMilliseconds(_options.MemoryCheckInterval));
        }
    }

    public MemoryUsageInfo GetMemoryUsage()
    {
        var process = Process.GetCurrentProcess();
        var managedMemory = GC.GetTotalMemory(false);

        var memoryInfo = new MemoryUsageInfo
        {
            TotalManagedMemory = managedMemory,
            WorkingSet = process.WorkingSet64,
            PrivateMemory = process.PrivateMemorySize64,
            VirtualMemory = process.VirtualMemorySize64,
            Timestamp = DateTime.UtcNow
        };

        // Update peak memory usage
        lock (_lock)
        {
            if (memoryInfo.TotalManagedMemory > _stats.PeakMemoryUsage)
            {
                _stats.PeakMemoryUsage = memoryInfo.TotalManagedMemory;
            }
        }

        // Add Python memory information if available
        try
        {
            // This would integrate with Python.NET to get Python-specific memory info
            memoryInfo.PythonMemory["interpreter_count"] = 0; // Placeholder
            memoryInfo.PythonMemory["allocated_objects"] = 0; // Placeholder
        }
        catch (Exception ex)
        {
            _logger.LogDebug("Could not retrieve Python memory information: {Error}", ex.Message);
        }

        return memoryInfo;
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (_isRunning || !_options.EnableMemoryProfiling)
            return;

        _logger.LogInformation("Starting memory monitoring with threshold {ThresholdMB}MB", 
            _options.MaxMemoryUsageMB);

        _isRunning = true;
        await Task.CompletedTask;
    }

    public async Task StopAsync(CancellationToken cancellationToken = default)
    {
        if (!_isRunning)
            return;

        _logger.LogInformation("Stopping memory monitoring");
        _isRunning = false;
        await Task.CompletedTask;
    }

    public async Task ForceGarbageCollectionAsync(int? generation = null, CancellationToken cancellationToken = default)
    {
        _logger.LogDebug("Forcing garbage collection (generation: {Generation})", generation?.ToString() ?? "all");

        await Task.Run(() =>
        {
            var memoryBefore = GC.GetTotalMemory(false);
            
            if (generation.HasValue)
            {
                GC.Collect(generation.Value, GCCollectionMode.Forced, true);
            }
            else
            {
                GC.Collect();
                GC.WaitForPendingFinalizers();
                GC.Collect();
            }

            var memoryAfter = GC.GetTotalMemory(true);
            var memoryFreed = memoryBefore - memoryAfter;

            lock (_lock)
            {
                _stats.ManualGcCalls++;
                _stats.LastCleanup = DateTime.UtcNow;
                
                // Update running average of memory after cleanup
                if (_stats.AverageMemoryAfterCleanup == 0)
                {
                    _stats.AverageMemoryAfterCleanup = memoryAfter;
                }
                else
                {
                    _stats.AverageMemoryAfterCleanup = 
                        (_stats.AverageMemoryAfterCleanup + memoryAfter) / 2;
                }
            }

            _logger.LogInformation("Garbage collection completed. Freed {FreedMB:F2}MB (before: {BeforeMB:F2}MB, after: {AfterMB:F2}MB)",
                memoryFreed / 1024.0 / 1024.0,
                memoryBefore / 1024.0 / 1024.0,
                memoryAfter / 1024.0 / 1024.0);
        }, cancellationToken);
    }

    public void SetMemoryThreshold(int thresholdMB)
    {
        if (thresholdMB <= 0)
            throw new ArgumentException("Memory threshold must be positive", nameof(thresholdMB));

        lock (_lock)
        {
            _memoryThresholdBytes = thresholdMB * 1024 * 1024;
            _logger.LogInformation("Memory threshold updated to {ThresholdMB}MB", thresholdMB);
        }
    }

    private async Task MonitorMemoryAsync()
    {
        if (!_isRunning || _isDisposed)
            return;

        try
        {
            var memoryInfo = GetMemoryUsage();
            
            // Check if we've exceeded the threshold
            if (memoryInfo.TotalManagedMemory > _memoryThresholdBytes)
            {
                _logger.LogWarning("Memory usage {CurrentMB:F2}MB exceeds threshold {ThresholdMB}MB, triggering cleanup",
                    memoryInfo.TotalManagedMemory / 1024.0 / 1024.0,
                    _memoryThresholdBytes / 1024.0 / 1024.0);

                lock (_lock)
                {
                    _stats.AutomaticGcTriggers++;
                }

                await ForceGarbageCollectionAsync();
            }
            else
            {
                _logger.LogTrace("Memory usage: {CurrentMB:F2}MB (threshold: {ThresholdMB}MB)",
                    memoryInfo.TotalManagedMemory / 1024.0 / 1024.0,
                    _memoryThresholdBytes / 1024.0 / 1024.0);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during memory monitoring");
        }
    }

    public void Dispose()
    {
        if (_isDisposed)
            return;

        _isDisposed = true;
        _isRunning = false;

        _logger.LogInformation("Disposing memory manager");

        _monitoringTimer?.Dispose();

        // Final cleanup
        if (_options.EnableMemoryProfiling)
        {
            try
            {
                GC.Collect();
                GC.WaitForPendingFinalizers();
                GC.Collect();
                
                var finalMemory = GC.GetTotalMemory(true);
                _logger.LogInformation("Final memory usage after cleanup: {MemoryMB:F2}MB", 
                    finalMemory / 1024.0 / 1024.0);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error during final memory cleanup");
            }
        }
    }
}