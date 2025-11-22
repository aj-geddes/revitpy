using System.Collections.Concurrent;
using System.Diagnostics;
using System.Reflection;
using Microsoft.Extensions.Logging;
using RevitPy.Core.Exceptions;

namespace RevitPy.Bridge;

/// <summary>
/// High-performance bridge for Revit element operations with caching and batch processing
/// </summary>
public interface IElementBridge
{
    /// <summary>
    /// Gets an element by its ID
    /// </summary>
    Task<object?> GetElementByIdAsync(object document, object elementId, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets multiple elements by their IDs in a single batch operation
    /// </summary>
    Task<Dictionary<object, object?>> GetElementsByIdsAsync(object document, IEnumerable<object> elementIds, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets all elements of a specific type
    /// </summary>
    Task<IEnumerable<object>> GetElementsByTypeAsync(object document, Type elementType, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets all elements matching a filter
    /// </summary>
    Task<IEnumerable<object>> GetElementsByFilterAsync(object document, object filter, CancellationToken cancellationToken = default);

    /// <summary>
    /// Creates a new element
    /// </summary>
    Task<object> CreateElementAsync(object document, string elementTypeName, object[] parameters, CancellationToken cancellationToken = default);

    /// <summary>
    /// Deletes elements by their IDs
    /// </summary>
    Task<bool> DeleteElementsAsync(object document, IEnumerable<object> elementIds, CancellationToken cancellationToken = default);

    /// <summary>
    /// Copies elements within a document or between documents
    /// </summary>
    Task<Dictionary<object, object>> CopyElementsAsync(object sourceDocument, object targetDocument, IEnumerable<object> elementIds, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets element statistics and cache performance metrics
    /// </summary>
    ElementBridgeStats GetStats();
}

/// <summary>
/// High-performance implementation of element bridge with advanced caching
/// </summary>
public class ElementBridge : IElementBridge
{
    private readonly ILogger<ElementBridge> _logger;
    private readonly IRevitTypeConverter _typeConverter;
    private readonly ITransactionManager _transactionManager;
    private readonly ConcurrentDictionary<string, object> _elementCache;
    private readonly ConcurrentDictionary<Type, PropertyInfo[]> _elementTypeProperties;
    private readonly ConcurrentDictionary<Type, MethodInfo[]> _elementTypeMethods;
    private readonly ElementBridgeStats _stats;
    private readonly object _statsLock = new();
    private readonly SemaphoreSlim _batchSemaphore;

    public ElementBridge(
        ILogger<ElementBridge> logger,
        IRevitTypeConverter typeConverter,
        ITransactionManager transactionManager)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _typeConverter = typeConverter ?? throw new ArgumentNullException(nameof(typeConverter));
        _transactionManager = transactionManager ?? throw new ArgumentNullException(nameof(transactionManager));

        _elementCache = new ConcurrentDictionary<string, object>();
        _elementTypeProperties = new ConcurrentDictionary<Type, PropertyInfo[]>();
        _elementTypeMethods = new ConcurrentDictionary<Type, MethodInfo[]>();
        _stats = new ElementBridgeStats { LastReset = DateTime.UtcNow };
        _batchSemaphore = new SemaphoreSlim(Environment.ProcessorCount, Environment.ProcessorCount);
    }

    /// <inheritdoc/>
    public async Task<object?> GetElementByIdAsync(object document, object elementId, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(elementId);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var cacheKey = GenerateCacheKey(document, elementId);

            // Check cache first
            if (_elementCache.TryGetValue(cacheKey, out var cachedElement))
            {
                RecordCacheHit(stopwatch.Elapsed);
                return _typeConverter.ConvertToPython(cachedElement);
            }

            // Get element from Revit API
            var element = await GetElementFromRevitApi(document, elementId, cancellationToken);

            if (element != null)
            {
                // Cache the element
                _elementCache[cacheKey] = element;
                RecordCacheMiss(stopwatch.Elapsed);

                return _typeConverter.ConvertToPython(element);
            }

            RecordCacheMiss(stopwatch.Elapsed);
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get element by ID");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Failed to get element: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<Dictionary<object, object?>> GetElementsByIdsAsync(
        object document,
        IEnumerable<object> elementIds,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(elementIds);

        var ids = elementIds.ToList();
        if (ids.Count == 0)
            return new Dictionary<object, object?>();

        var stopwatch = Stopwatch.StartNew();
        var result = new Dictionary<object, object?>();
        var uncachedIds = new List<object>();

        try
        {
            // Check cache for all IDs first
            foreach (var id in ids)
            {
                var cacheKey = GenerateCacheKey(document, id);
                if (_elementCache.TryGetValue(cacheKey, out var cachedElement))
                {
                    result[id] = _typeConverter.ConvertToPython(cachedElement);
                }
                else
                {
                    uncachedIds.Add(id);
                }
            }

            // Batch get uncached elements
            if (uncachedIds.Count > 0)
            {
                await _batchSemaphore.WaitAsync(cancellationToken);
                try
                {
                    var batchElements = await GetElementsBatchFromRevitApi(document, uncachedIds, cancellationToken);

                    foreach (var kvp in batchElements)
                    {
                        var cacheKey = GenerateCacheKey(document, kvp.Key);
                        if (kvp.Value != null)
                        {
                            _elementCache[cacheKey] = kvp.Value;
                        }
                        result[kvp.Key] = _typeConverter.ConvertToPython(kvp.Value);
                    }
                }
                finally
                {
                    _batchSemaphore.Release();
                }
            }

            RecordBatchOperation(ids.Count, result.Count(r => r.Value != null), stopwatch.Elapsed);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get elements by IDs in batch");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Batch element retrieval failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<IEnumerable<object>> GetElementsByTypeAsync(
        object document,
        Type elementType,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(elementType);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var elements = await GetElementsByTypeFromRevitApi(document, elementType, cancellationToken);
            var convertedElements = new List<object>();

            foreach (var element in elements)
            {
                var converted = _typeConverter.ConvertToPython(element);
                if (converted != null)
                {
                    convertedElements.Add(converted);

                    // Cache elements for future retrieval
                    var elementId = GetElementId(element);
                    if (elementId != null)
                    {
                        var cacheKey = GenerateCacheKey(document, elementId);
                        _elementCache[cacheKey] = element;
                    }
                }
            }

            RecordTypeQuery(elementType, convertedElements.Count, stopwatch.Elapsed);
            return convertedElements;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get elements by type {ElementType}", elementType.Name);
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Failed to get elements by type: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<IEnumerable<object>> GetElementsByFilterAsync(
        object document,
        object filter,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(filter);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var elements = await GetElementsByFilterFromRevitApi(document, filter, cancellationToken);
            var convertedElements = new List<object>();

            foreach (var element in elements)
            {
                var converted = _typeConverter.ConvertToPython(element);
                if (converted != null)
                {
                    convertedElements.Add(converted);

                    // Cache elements for future retrieval
                    var elementId = GetElementId(element);
                    if (elementId != null)
                    {
                        var cacheKey = GenerateCacheKey(document, elementId);
                        _elementCache[cacheKey] = element;
                    }
                }
            }

            RecordFilterQuery(filter.GetType(), convertedElements.Count, stopwatch.Elapsed);
            return convertedElements;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get elements by filter");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Failed to get elements by filter: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<object> CreateElementAsync(
        object document,
        string elementTypeName,
        object[] parameters,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentException.ThrowIfNullOrEmpty(elementTypeName);
        ArgumentNullException.ThrowIfNull(parameters);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            return await _transactionManager.ExecuteInTransactionAsync(
                $"Create {elementTypeName}",
                async () =>
                {
                    var element = await CreateElementInRevitApi(document, elementTypeName, parameters, cancellationToken);

                    if (element != null)
                    {
                        // Cache the newly created element
                        var elementId = GetElementId(element);
                        if (elementId != null)
                        {
                            var cacheKey = GenerateCacheKey(document, elementId);
                            _elementCache[cacheKey] = element;
                        }

                        RecordElementCreation(elementTypeName, stopwatch.Elapsed);
                        return _typeConverter.ConvertToPython(element);
                    }

                    throw new RevitApiException("Element creation returned null");
                },
                document,
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create element of type {ElementTypeName}", elementTypeName);
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Element creation failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<bool> DeleteElementsAsync(
        object document,
        IEnumerable<object> elementIds,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(elementIds);

        var ids = elementIds.ToList();
        if (ids.Count == 0)
            return true;

        var stopwatch = Stopwatch.StartNew();
        try
        {
            return await _transactionManager.ExecuteInTransactionAsync(
                $"Delete {ids.Count} elements",
                async () =>
                {
                    var success = await DeleteElementsInRevitApi(document, ids, cancellationToken);

                    if (success)
                    {
                        // Remove deleted elements from cache
                        foreach (var id in ids)
                        {
                            var cacheKey = GenerateCacheKey(document, id);
                            _elementCache.TryRemove(cacheKey, out _);
                        }

                        RecordElementDeletion(ids.Count, stopwatch.Elapsed);
                    }

                    return success;
                },
                document,
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to delete {Count} elements", ids.Count);
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Element deletion failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<Dictionary<object, object>> CopyElementsAsync(
        object sourceDocument,
        object targetDocument,
        IEnumerable<object> elementIds,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(sourceDocument);
        ArgumentNullException.ThrowIfNull(targetDocument);
        ArgumentNullException.ThrowIfNull(elementIds);

        var ids = elementIds.ToList();
        if (ids.Count == 0)
            return new Dictionary<object, object>();

        var stopwatch = Stopwatch.StartNew();
        try
        {
            return await _transactionManager.ExecuteInTransactionAsync(
                $"Copy {ids.Count} elements",
                async () =>
                {
                    var copyResults = await CopyElementsInRevitApi(sourceDocument, targetDocument, ids, cancellationToken);

                    // Cache copied elements in target document
                    foreach (var kvp in copyResults)
                    {
                        var newElementId = GetElementId(kvp.Value);
                        if (newElementId != null)
                        {
                            var cacheKey = GenerateCacheKey(targetDocument, newElementId);
                            _elementCache[cacheKey] = kvp.Value;
                        }
                    }

                    RecordElementCopy(ids.Count, copyResults.Count, stopwatch.Elapsed);

                    // Convert results to Python objects
                    var convertedResults = new Dictionary<object, object>();
                    foreach (var kvp in copyResults)
                    {
                        var convertedOriginal = _typeConverter.ConvertToPython(kvp.Key);
                        var convertedCopy = _typeConverter.ConvertToPython(kvp.Value);
                        if (convertedOriginal != null && convertedCopy != null)
                        {
                            convertedResults[convertedOriginal] = convertedCopy;
                        }
                    }

                    return convertedResults;
                },
                targetDocument,
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to copy {Count} elements", ids.Count);
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Element copy failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public ElementBridgeStats GetStats()
    {
        lock (_statsLock)
        {
            return new ElementBridgeStats
            {
                TotalOperations = _stats.TotalOperations,
                CacheHits = _stats.CacheHits,
                CacheMisses = _stats.CacheMisses,
                FailedOperations = _stats.FailedOperations,
                AverageOperationTime = _stats.AverageOperationTime,
                ElementsCreated = _stats.ElementsCreated,
                ElementsDeleted = _stats.ElementsDeleted,
                ElementsCopied = _stats.ElementsCopied,
                CacheSize = _elementCache.Count,
                TypeQueryCount = _stats.TypeQueryCount,
                FilterQueryCount = _stats.FilterQueryCount,
                BatchOperationCount = _stats.BatchOperationCount,
                LastReset = _stats.LastReset
            };
        }
    }

    // Private helper methods for Revit API integration
    // These would be implemented with actual Revit API calls

    private async Task<object?> GetElementFromRevitApi(object document, object elementId, CancellationToken cancellationToken)
    {
        // This would use actual Revit API: document.GetElement(elementId)
        await Task.Delay(1, cancellationToken); // Simulate API call
        return new { Id = elementId, Type = "MockElement" }; // Mock implementation
    }

    private async Task<Dictionary<object, object?>> GetElementsBatchFromRevitApi(object document, IList<object> elementIds, CancellationToken cancellationToken)
    {
        // This would use actual Revit API batch operations
        await Task.Delay(elementIds.Count, cancellationToken); // Simulate API call

        var result = new Dictionary<object, object?>();
        foreach (var id in elementIds)
        {
            result[id] = new { Id = id, Type = "MockElement" }; // Mock implementation
        }
        return result;
    }

    private async Task<IEnumerable<object>> GetElementsByTypeFromRevitApi(object document, Type elementType, CancellationToken cancellationToken)
    {
        // This would use actual Revit API filtered element collector
        await Task.Delay(10, cancellationToken); // Simulate API call

        return Enumerable.Range(1, 5).Select(i => new { Id = i, Type = elementType.Name }); // Mock implementation
    }

    private async Task<IEnumerable<object>> GetElementsByFilterFromRevitApi(object document, object filter, CancellationToken cancellationToken)
    {
        // This would use actual Revit API filtered element collector with custom filter
        await Task.Delay(15, cancellationToken); // Simulate API call

        return Enumerable.Range(1, 3).Select(i => new { Id = i, Filter = filter.GetType().Name }); // Mock implementation
    }

    private async Task<object> CreateElementInRevitApi(object document, string elementTypeName, object[] parameters, CancellationToken cancellationToken)
    {
        // This would use actual Revit API element creation methods
        await Task.Delay(5, cancellationToken); // Simulate API call

        return new { Id = Guid.NewGuid(), Type = elementTypeName, Parameters = parameters }; // Mock implementation
    }

    private async Task<bool> DeleteElementsInRevitApi(object document, IList<object> elementIds, CancellationToken cancellationToken)
    {
        // This would use actual Revit API: document.Delete(elementIds)
        await Task.Delay(elementIds.Count * 2, cancellationToken); // Simulate API call

        return true; // Mock implementation
    }

    private async Task<Dictionary<object, object>> CopyElementsInRevitApi(object sourceDocument, object targetDocument, IList<object> elementIds, CancellationToken cancellationToken)
    {
        // This would use actual Revit API: ElementTransformUtils.CopyElements
        await Task.Delay(elementIds.Count * 3, cancellationToken); // Simulate API call

        var result = new Dictionary<object, object>();
        foreach (var id in elementIds)
        {
            var originalElement = new { Id = id, Type = "Original" };
            var copiedElement = new { Id = Guid.NewGuid(), Type = "Copy" };
            result[originalElement] = copiedElement;
        }
        return result; // Mock implementation
    }

    private object? GetElementId(object element)
    {
        // This would extract the ElementId from a Revit element
        // For now, return a mock ID
        var elementType = element.GetType();
        var idProperty = elementType.GetProperty("Id");
        return idProperty?.GetValue(element);
    }

    private string GenerateCacheKey(object document, object elementId)
    {
        var docHash = document.GetHashCode();
        var idHash = elementId.GetHashCode();
        return $"doc:{docHash}_id:{idHash}";
    }

    // Statistics recording methods

    private void RecordCacheHit(TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.CacheHits++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordCacheMiss(TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.CacheMisses++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordBatchOperation(int requested, int found, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.BatchOperationCount++;
            _stats.TotalOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordTypeQuery(Type elementType, int resultCount, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TypeQueryCount++;
            _stats.TotalOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordFilterQuery(Type filterType, int resultCount, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.FilterQueryCount++;
            _stats.TotalOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordElementCreation(string elementTypeName, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.ElementsCreated++;
            _stats.TotalOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordElementDeletion(int count, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.ElementsDeleted += count;
            _stats.TotalOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordElementCopy(int requested, int copied, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.ElementsCopied += copied;
            _stats.TotalOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordFailure(TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.FailedOperations++;
            _stats.TotalOperations++;
            UpdateAverageTime(duration);
        }
    }

    private void UpdateAverageTime(TimeSpan duration)
    {
        var totalTicks = _stats.AverageOperationTime.Ticks * (_stats.TotalOperations - 1) + duration.Ticks;
        _stats.AverageOperationTime = new TimeSpan(totalTicks / _stats.TotalOperations);
    }
}

/// <summary>
/// Statistics for element bridge operations
/// </summary>
public class ElementBridgeStats
{
    /// <summary>
    /// Gets or sets the total number of operations performed
    /// </summary>
    public long TotalOperations { get; set; }

    /// <summary>
    /// Gets or sets the number of cache hits
    /// </summary>
    public long CacheHits { get; set; }

    /// <summary>
    /// Gets or sets the number of cache misses
    /// </summary>
    public long CacheMisses { get; set; }

    /// <summary>
    /// Gets or sets the number of failed operations
    /// </summary>
    public long FailedOperations { get; set; }

    /// <summary>
    /// Gets or sets the average operation time
    /// </summary>
    public TimeSpan AverageOperationTime { get; set; }

    /// <summary>
    /// Gets or sets the number of elements created
    /// </summary>
    public long ElementsCreated { get; set; }

    /// <summary>
    /// Gets or sets the number of elements deleted
    /// </summary>
    public long ElementsDeleted { get; set; }

    /// <summary>
    /// Gets or sets the number of elements copied
    /// </summary>
    public long ElementsCopied { get; set; }

    /// <summary>
    /// Gets or sets the current cache size
    /// </summary>
    public int CacheSize { get; set; }

    /// <summary>
    /// Gets or sets the number of type queries performed
    /// </summary>
    public long TypeQueryCount { get; set; }

    /// <summary>
    /// Gets or sets the number of filter queries performed
    /// </summary>
    public long FilterQueryCount { get; set; }

    /// <summary>
    /// Gets or sets the number of batch operations performed
    /// </summary>
    public long BatchOperationCount { get; set; }

    /// <summary>
    /// Gets or sets the cache hit ratio
    /// </summary>
    public double CacheHitRatio => TotalOperations > 0 ? (double)CacheHits / TotalOperations : 0.0;

    /// <summary>
    /// Gets or sets the last reset time
    /// </summary>
    public DateTime LastReset { get; set; }
}
