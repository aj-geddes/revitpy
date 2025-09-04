using System.Collections.Concurrent;
using System.Diagnostics;
using System.Reflection;
using Microsoft.Extensions.Logging;
using RevitPy.Core.Exceptions;

namespace RevitPy.Bridge;

/// <summary>
/// High-performance bridge for Revit parameter operations with type safety and caching
/// </summary>
public interface IParameterBridge
{
    /// <summary>
    /// Gets a parameter value from an element
    /// </summary>
    Task<object?> GetParameterValueAsync(object element, string parameterName, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets parameter values for multiple parameters from an element
    /// </summary>
    Task<Dictionary<string, object?>> GetParameterValuesAsync(object element, IEnumerable<string> parameterNames, CancellationToken cancellationToken = default);

    /// <summary>
    /// Sets a parameter value on an element
    /// </summary>
    Task<bool> SetParameterValueAsync(object element, string parameterName, object? value, CancellationToken cancellationToken = default);

    /// <summary>
    /// Sets multiple parameter values on an element in a single transaction
    /// </summary>
    Task<Dictionary<string, bool>> SetParameterValuesAsync(object element, Dictionary<string, object?> parameters, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets all parameters from an element
    /// </summary>
    Task<Dictionary<string, object?>> GetAllParametersAsync(object element, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets parameter information including type, storage type, and whether it's read-only
    /// </summary>
    Task<ParameterInfo?> GetParameterInfoAsync(object element, string parameterName, CancellationToken cancellationToken = default);

    /// <summary>
    /// Checks if a parameter exists on an element
    /// </summary>
    Task<bool> HasParameterAsync(object element, string parameterName, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets parameters filtered by type or category
    /// </summary>
    Task<IEnumerable<ParameterInfo>> GetParametersByFilterAsync(object element, ParameterFilter filter, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets parameter bridge statistics
    /// </summary>
    ParameterBridgeStats GetStats();
}

/// <summary>
/// High-performance implementation of parameter bridge with advanced caching and type safety
/// </summary>
public class ParameterBridge : IParameterBridge
{
    private readonly ILogger<ParameterBridge> _logger;
    private readonly IRevitTypeConverter _typeConverter;
    private readonly ITransactionManager _transactionManager;
    private readonly ConcurrentDictionary<string, ParameterInfo> _parameterInfoCache;
    private readonly ConcurrentDictionary<string, object?> _parameterValueCache;
    private readonly ConcurrentDictionary<Type, PropertyInfo[]> _elementParameterProperties;
    private readonly ParameterBridgeStats _stats;
    private readonly object _statsLock = new();
    private readonly SemaphoreSlim _batchSemaphore;

    // Parameter type mappings for efficient conversion
    private readonly Dictionary<string, Type> _parameterTypeMap;
    private readonly Dictionary<string, Func<object, object?>> _parameterGetters;
    private readonly Dictionary<string, Action<object, object?>> _parameterSetters;

    public ParameterBridge(
        ILogger<ParameterBridge> logger,
        IRevitTypeConverter typeConverter,
        ITransactionManager transactionManager)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _typeConverter = typeConverter ?? throw new ArgumentNullException(nameof(typeConverter));
        _transactionManager = transactionManager ?? throw new ArgumentNullException(nameof(transactionManager));

        _parameterInfoCache = new ConcurrentDictionary<string, ParameterInfo>();
        _parameterValueCache = new ConcurrentDictionary<string, object?>();
        _elementParameterProperties = new ConcurrentDictionary<Type, PropertyInfo[]>();
        _stats = new ParameterBridgeStats { LastReset = DateTime.UtcNow };
        _batchSemaphore = new SemaphoreSlim(Environment.ProcessorCount, Environment.ProcessorCount);

        _parameterTypeMap = new Dictionary<string, Type>();
        _parameterGetters = new Dictionary<string, Func<object, object?>>();
        _parameterSetters = new Dictionary<string, Action<object, object?>>();

        InitializeParameterMappings();
    }

    /// <inheritdoc/>
    public async Task<object?> GetParameterValueAsync(object element, string parameterName, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentException.ThrowIfNullOrEmpty(parameterName);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var cacheKey = GenerateValueCacheKey(element, parameterName);
            
            // Check cache first
            if (_parameterValueCache.TryGetValue(cacheKey, out var cachedValue))
            {
                RecordCacheHit(stopwatch.Elapsed);
                return _typeConverter.ConvertToPython(cachedValue);
            }

            // Get parameter value from Revit API
            var parameter = await GetParameterFromElement(element, parameterName, cancellationToken);
            if (parameter == null)
            {
                RecordParameterNotFound(parameterName, stopwatch.Elapsed);
                return null;
            }

            var value = await ExtractParameterValue(parameter, cancellationToken);
            
            // Cache the value (with expiration for performance)
            _parameterValueCache[cacheKey] = value;
            
            RecordParameterRead(parameterName, stopwatch.Elapsed);
            return _typeConverter.ConvertToPython(value);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get parameter '{ParameterName}' from element", parameterName);
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Failed to get parameter value: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<Dictionary<string, object?>> GetParameterValuesAsync(
        object element, 
        IEnumerable<string> parameterNames, 
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentNullException.ThrowIfNull(parameterNames);

        var names = parameterNames.ToList();
        if (names.Count == 0)
            return new Dictionary<string, object?>();

        var stopwatch = Stopwatch.StartNew();
        var result = new Dictionary<string, object?>();

        try
        {
            await _batchSemaphore.WaitAsync(cancellationToken);
            try
            {
                // Process parameters in parallel for better performance
                var tasks = names.Select(async name =>
                {
                    try
                    {
                        var value = await GetParameterValueAsync(element, name, cancellationToken);
                        return new KeyValuePair<string, object?>(name, value);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, "Failed to get parameter '{ParameterName}' in batch operation", name);
                        return new KeyValuePair<string, object?>(name, null);
                    }
                }).ToArray();

                var results = await Task.WhenAll(tasks);
                foreach (var kvp in results)
                {
                    result[kvp.Key] = kvp.Value;
                }
            }
            finally
            {
                _batchSemaphore.Release();
            }

            RecordBatchParameterRead(names.Count, result.Count(r => r.Value != null), stopwatch.Elapsed);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get parameter values in batch");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Batch parameter read failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<bool> SetParameterValueAsync(
        object element, 
        string parameterName, 
        object? value, 
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentException.ThrowIfNullOrEmpty(parameterName);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            return await _transactionManager.ExecuteInTransactionAsync(
                $"Set parameter '{parameterName}'",
                async () =>
                {
                    var parameter = await GetParameterFromElement(element, parameterName, cancellationToken);
                    if (parameter == null)
                    {
                        RecordParameterNotFound(parameterName, stopwatch.Elapsed);
                        return false;
                    }

                    // Check if parameter is read-only
                    if (await IsParameterReadOnly(parameter, cancellationToken))
                    {
                        _logger.LogWarning("Attempt to set read-only parameter '{ParameterName}'", parameterName);
                        return false;
                    }

                    // Convert value to appropriate Revit type
                    var parameterInfo = await GetParameterInfoInternal(parameter, cancellationToken);
                    var convertedValue = ConvertValueForParameter(value, parameterInfo);

                    // Set the parameter value
                    var success = await SetParameterValueInternal(parameter, convertedValue, cancellationToken);
                    
                    if (success)
                    {
                        // Invalidate cache for this parameter
                        var cacheKey = GenerateValueCacheKey(element, parameterName);
                        _parameterValueCache.TryRemove(cacheKey, out _);
                        
                        RecordParameterWrite(parameterName, stopwatch.Elapsed);
                    }

                    return success;
                },
                GetDocumentFromElement(element),
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to set parameter '{ParameterName}' to value '{Value}'", parameterName, value);
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Failed to set parameter value: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<Dictionary<string, bool>> SetParameterValuesAsync(
        object element, 
        Dictionary<string, object?> parameters, 
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentNullException.ThrowIfNull(parameters);

        if (parameters.Count == 0)
            return new Dictionary<string, bool>();

        var stopwatch = Stopwatch.StartNew();
        var result = new Dictionary<string, bool>();

        try
        {
            return await _transactionManager.ExecuteInTransactionAsync(
                $"Set {parameters.Count} parameters",
                async () =>
                {
                    foreach (var kvp in parameters)
                    {
                        try
                        {
                            // Use the single parameter set method but without transaction wrapping
                            var success = await SetParameterValueInternal(element, kvp.Key, kvp.Value, cancellationToken);
                            result[kvp.Key] = success;
                        }
                        catch (Exception ex)
                        {
                            _logger.LogWarning(ex, "Failed to set parameter '{ParameterName}' in batch operation", kvp.Key);
                            result[kvp.Key] = false;
                        }
                    }

                    RecordBatchParameterWrite(parameters.Count, result.Count(r => r.Value), stopwatch.Elapsed);
                    return result;
                },
                GetDocumentFromElement(element),
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to set parameter values in batch");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Batch parameter write failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<Dictionary<string, object?>> GetAllParametersAsync(object element, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var parameters = await GetAllParametersFromElement(element, cancellationToken);
            var result = new Dictionary<string, object?>();

            foreach (var parameter in parameters)
            {
                try
                {
                    var name = await GetParameterName(parameter, cancellationToken);
                    var value = await ExtractParameterValue(parameter, cancellationToken);
                    
                    if (!string.IsNullOrEmpty(name))
                    {
                        result[name] = _typeConverter.ConvertToPython(value);
                        
                        // Cache parameter info and value
                        var infoCacheKey = GenerateInfoCacheKey(element, name);
                        var valueCacheKey = GenerateValueCacheKey(element, name);
                        
                        var paramInfo = await GetParameterInfoInternal(parameter, cancellationToken);
                        _parameterInfoCache[infoCacheKey] = paramInfo;
                        _parameterValueCache[valueCacheKey] = value;
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogDebug(ex, "Error processing parameter in GetAllParameters");
                }
            }

            RecordAllParametersRead(result.Count, stopwatch.Elapsed);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get all parameters from element");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Failed to get all parameters: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<ParameterInfo?> GetParameterInfoAsync(object element, string parameterName, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentException.ThrowIfNullOrEmpty(parameterName);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var cacheKey = GenerateInfoCacheKey(element, parameterName);
            
            // Check cache first
            if (_parameterInfoCache.TryGetValue(cacheKey, out var cachedInfo))
            {
                RecordCacheHit(stopwatch.Elapsed);
                return cachedInfo;
            }

            var parameter = await GetParameterFromElement(element, parameterName, cancellationToken);
            if (parameter == null)
            {
                RecordParameterNotFound(parameterName, stopwatch.Elapsed);
                return null;
            }

            var parameterInfo = await GetParameterInfoInternal(parameter, cancellationToken);
            
            // Cache the parameter info
            _parameterInfoCache[cacheKey] = parameterInfo;
            
            RecordParameterInfoQuery(parameterName, stopwatch.Elapsed);
            return parameterInfo;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get parameter info for '{ParameterName}'", parameterName);
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Failed to get parameter info: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<bool> HasParameterAsync(object element, string parameterName, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentException.ThrowIfNullOrEmpty(parameterName);

        try
        {
            var parameter = await GetParameterFromElement(element, parameterName, cancellationToken);
            return parameter != null;
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Error checking if parameter '{ParameterName}' exists", parameterName);
            return false;
        }
    }

    /// <inheritdoc/>
    public async Task<IEnumerable<ParameterInfo>> GetParametersByFilterAsync(
        object element, 
        ParameterFilter filter, 
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentNullException.ThrowIfNull(filter);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var allParameters = await GetAllParametersFromElement(element, cancellationToken);
            var result = new List<ParameterInfo>();

            foreach (var parameter in allParameters)
            {
                try
                {
                    var parameterInfo = await GetParameterInfoInternal(parameter, cancellationToken);
                    
                    if (filter.Matches(parameterInfo))
                    {
                        result.Add(parameterInfo);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogDebug(ex, "Error processing parameter in filter operation");
                }
            }

            RecordFilterQuery(filter.GetType(), result.Count, stopwatch.Elapsed);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get parameters by filter");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Parameter filter query failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public ParameterBridgeStats GetStats()
    {
        lock (_statsLock)
        {
            return new ParameterBridgeStats
            {
                TotalOperations = _stats.TotalOperations,
                ParameterReads = _stats.ParameterReads,
                ParameterWrites = _stats.ParameterWrites,
                CacheHits = _stats.CacheHits,
                CacheMisses = _stats.CacheMisses,
                FailedOperations = _stats.FailedOperations,
                ParametersNotFound = _stats.ParametersNotFound,
                AverageOperationTime = _stats.AverageOperationTime,
                BatchOperationCount = _stats.BatchOperationCount,
                FilterQueryCount = _stats.FilterQueryCount,
                InfoCacheSize = _parameterInfoCache.Count,
                ValueCacheSize = _parameterValueCache.Count,
                LastReset = _stats.LastReset
            };
        }
    }

    // Private helper methods for Revit API integration
    // These would be implemented with actual Revit API calls

    private void InitializeParameterMappings()
    {
        // Initialize common parameter type mappings for faster lookup
        // This would be expanded with actual Revit parameter definitions
        
        _parameterTypeMap["Length"] = typeof(double);
        _parameterTypeMap["Area"] = typeof(double);
        _parameterTypeMap["Volume"] = typeof(double);
        _parameterTypeMap["Text"] = typeof(string);
        _parameterTypeMap["Integer"] = typeof(int);
        _parameterTypeMap["YesNo"] = typeof(bool);
    }

    private async Task<object?> GetParameterFromElement(object element, string parameterName, CancellationToken cancellationToken)
    {
        // This would use actual Revit API: element.get_Parameter(parameterName) or element.LookupParameter(parameterName)
        await Task.Delay(1, cancellationToken); // Simulate API call
        
        // Mock implementation
        return new { Name = parameterName, Element = element, HasValue = true };
    }

    private async Task<IEnumerable<object>> GetAllParametersFromElement(object element, CancellationToken cancellationToken)
    {
        // This would use actual Revit API: element.Parameters
        await Task.Delay(5, cancellationToken); // Simulate API call
        
        // Mock implementation
        var commonParameters = new[] { "Name", "Type", "Level", "Comments", "Mark" };
        return commonParameters.Select(name => new { Name = name, Element = element, HasValue = true });
    }

    private async Task<object?> ExtractParameterValue(object parameter, CancellationToken cancellationToken)
    {
        // This would use actual Revit API based on parameter storage type
        await Task.Delay(1, cancellationToken); // Simulate API call
        
        // Mock implementation - would check parameter.StorageType and call appropriate AsXXX() method
        return $"Value for {parameter}";
    }

    private async Task<string> GetParameterName(object parameter, CancellationToken cancellationToken)
    {
        // This would use actual Revit API: parameter.Definition.Name
        await Task.Delay(1, cancellationToken); // Simulate API call
        
        // Mock implementation
        var nameProperty = parameter.GetType().GetProperty("Name");
        return nameProperty?.GetValue(parameter)?.ToString() ?? "Unknown";
    }

    private async Task<bool> IsParameterReadOnly(object parameter, CancellationToken cancellationToken)
    {
        // This would use actual Revit API: parameter.IsReadOnly
        await Task.Delay(1, cancellationToken); // Simulate API call
        
        return false; // Mock implementation
    }

    private async Task<ParameterInfo> GetParameterInfoInternal(object parameter, CancellationToken cancellationToken)
    {
        // This would extract comprehensive parameter information from Revit API
        await Task.Delay(1, cancellationToken); // Simulate API call
        
        var name = await GetParameterName(parameter, cancellationToken);
        return new ParameterInfo
        {
            Name = name,
            StorageType = ParameterStorageType.String, // Mock
            ParameterType = ParameterType.Text, // Mock
            IsReadOnly = await IsParameterReadOnly(parameter, cancellationToken),
            Unit = "None", // Mock
            GroupName = "General", // Mock
            IsShared = false, // Mock
            HasValue = true // Mock
        };
    }

    private object? ConvertValueForParameter(object? value, ParameterInfo parameterInfo)
    {
        if (value == null)
            return null;

        // Convert based on parameter storage type
        return parameterInfo.StorageType switch
        {
            ParameterStorageType.Double => _typeConverter.ConvertFromPython<double>(value),
            ParameterStorageType.Integer => _typeConverter.ConvertFromPython<int>(value),
            ParameterStorageType.String => _typeConverter.ConvertFromPython<string>(value),
            ParameterStorageType.ElementId => _typeConverter.ConvertFromPython<object>(value), // ElementId conversion
            _ => _typeConverter.ConvertFromPython<object>(value)
        };
    }

    private async Task<bool> SetParameterValueInternal(object parameter, object? convertedValue, CancellationToken cancellationToken)
    {
        // This would use actual Revit API: parameter.Set(value) or parameter.SetValueString(value), etc.
        await Task.Delay(2, cancellationToken); // Simulate API call
        
        return true; // Mock implementation
    }

    private async Task<bool> SetParameterValueInternal(object element, string parameterName, object? value, CancellationToken cancellationToken)
    {
        var parameter = await GetParameterFromElement(element, parameterName, cancellationToken);
        if (parameter == null)
            return false;

        var parameterInfo = await GetParameterInfoInternal(parameter, cancellationToken);
        var convertedValue = ConvertValueForParameter(value, parameterInfo);

        return await SetParameterValueInternal(parameter, convertedValue, cancellationToken);
    }

    private object? GetDocumentFromElement(object element)
    {
        // This would use actual Revit API: element.Document
        var documentProperty = element.GetType().GetProperty("Document");
        return documentProperty?.GetValue(element);
    }

    private string GenerateValueCacheKey(object element, string parameterName)
    {
        var elementHash = element.GetHashCode();
        return $"value:{elementHash}:{parameterName}";
    }

    private string GenerateInfoCacheKey(object element, string parameterName)
    {
        var elementHash = element.GetHashCode();
        return $"info:{elementHash}:{parameterName}";
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

    private void RecordParameterRead(string parameterName, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.ParameterReads++;
            _stats.CacheMisses++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordParameterWrite(string parameterName, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.ParameterWrites++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordParameterNotFound(string parameterName, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.ParametersNotFound++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordBatchParameterRead(int requested, int found, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.BatchOperationCount++;
            _stats.TotalOperations++;
            _stats.ParameterReads += found;
            UpdateAverageTime(duration);
        }
    }

    private void RecordBatchParameterWrite(int requested, int written, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.BatchOperationCount++;
            _stats.TotalOperations++;
            _stats.ParameterWrites += written;
            UpdateAverageTime(duration);
        }
    }

    private void RecordAllParametersRead(int count, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.ParameterReads += count;
            UpdateAverageTime(duration);
        }
    }

    private void RecordParameterInfoQuery(string parameterName, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.CacheMisses++;
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
/// Information about a Revit parameter
/// </summary>
public class ParameterInfo
{
    /// <summary>
    /// Gets or sets the parameter name
    /// </summary>
    public string Name { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the parameter storage type
    /// </summary>
    public ParameterStorageType StorageType { get; set; }

    /// <summary>
    /// Gets or sets the parameter type
    /// </summary>
    public ParameterType ParameterType { get; set; }

    /// <summary>
    /// Gets or sets whether the parameter is read-only
    /// </summary>
    public bool IsReadOnly { get; set; }

    /// <summary>
    /// Gets or sets the parameter unit
    /// </summary>
    public string Unit { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the parameter group name
    /// </summary>
    public string GroupName { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets whether the parameter is shared
    /// </summary>
    public bool IsShared { get; set; }

    /// <summary>
    /// Gets or sets whether the parameter has a value
    /// </summary>
    public bool HasValue { get; set; }

    /// <summary>
    /// Gets or sets additional parameter metadata
    /// </summary>
    public Dictionary<string, object> Metadata { get; set; } = new();
}

/// <summary>
/// Parameter storage types
/// </summary>
public enum ParameterStorageType
{
    None,
    Integer,
    Double,
    String,
    ElementId
}

/// <summary>
/// Parameter types
/// </summary>
public enum ParameterType
{
    Text,
    Integer,
    Number,
    Length,
    Area,
    Volume,
    Angle,
    YesNo,
    Currency,
    ElementId,
    Material,
    FamilyType
}

/// <summary>
/// Base class for parameter filters
/// </summary>
public abstract class ParameterFilter
{
    /// <summary>
    /// Determines if a parameter matches this filter
    /// </summary>
    public abstract bool Matches(ParameterInfo parameterInfo);
}

/// <summary>
/// Filter parameters by type
/// </summary>
public class ParameterTypeFilter : ParameterFilter
{
    public ParameterType ParameterType { get; set; }

    public ParameterTypeFilter(ParameterType parameterType)
    {
        ParameterType = parameterType;
    }

    public override bool Matches(ParameterInfo parameterInfo)
    {
        return parameterInfo.ParameterType == ParameterType;
    }
}

/// <summary>
/// Filter parameters by group
/// </summary>
public class ParameterGroupFilter : ParameterFilter
{
    public string GroupName { get; set; }

    public ParameterGroupFilter(string groupName)
    {
        GroupName = groupName ?? throw new ArgumentNullException(nameof(groupName));
    }

    public override bool Matches(ParameterInfo parameterInfo)
    {
        return string.Equals(parameterInfo.GroupName, GroupName, StringComparison.OrdinalIgnoreCase);
    }
}

/// <summary>
/// Filter parameters by read-only status
/// </summary>
public class ParameterReadOnlyFilter : ParameterFilter
{
    public bool ReadOnly { get; set; }

    public ParameterReadOnlyFilter(bool readOnly = true)
    {
        ReadOnly = readOnly;
    }

    public override bool Matches(ParameterInfo parameterInfo)
    {
        return parameterInfo.IsReadOnly == ReadOnly;
    }
}

/// <summary>
/// Statistics for parameter bridge operations
/// </summary>
public class ParameterBridgeStats
{
    /// <summary>
    /// Gets or sets the total number of operations performed
    /// </summary>
    public long TotalOperations { get; set; }

    /// <summary>
    /// Gets or sets the number of parameter read operations
    /// </summary>
    public long ParameterReads { get; set; }

    /// <summary>
    /// Gets or sets the number of parameter write operations
    /// </summary>
    public long ParameterWrites { get; set; }

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
    /// Gets or sets the number of parameters not found
    /// </summary>
    public long ParametersNotFound { get; set; }

    /// <summary>
    /// Gets or sets the average operation time
    /// </summary>
    public TimeSpan AverageOperationTime { get; set; }

    /// <summary>
    /// Gets or sets the number of batch operations
    /// </summary>
    public long BatchOperationCount { get; set; }

    /// <summary>
    /// Gets or sets the number of filter queries
    /// </summary>
    public long FilterQueryCount { get; set; }

    /// <summary>
    /// Gets or sets the parameter info cache size
    /// </summary>
    public int InfoCacheSize { get; set; }

    /// <summary>
    /// Gets or sets the parameter value cache size
    /// </summary>
    public int ValueCacheSize { get; set; }

    /// <summary>
    /// Gets or sets the cache hit ratio
    /// </summary>
    public double CacheHitRatio => TotalOperations > 0 ? (double)CacheHits / TotalOperations : 0.0;

    /// <summary>
    /// Gets or sets the success ratio for parameter operations
    /// </summary>
    public double SuccessRatio => TotalOperations > 0 ? (double)(TotalOperations - FailedOperations) / TotalOperations : 0.0;

    /// <summary>
    /// Gets or sets the last reset time
    /// </summary>
    public DateTime LastReset { get; set; }
}