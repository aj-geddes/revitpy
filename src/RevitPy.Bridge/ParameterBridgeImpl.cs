using System.Collections.Concurrent;
using System.Diagnostics;
using System.Reflection;
using Microsoft.Extensions.Logging;
using RevitPy.Core.Exceptions;

namespace RevitPy.Bridge;

/// <summary>
/// Interface for high-performance parameter bridge operations
/// </summary>
public interface IParameterBridge
{
    /// <summary>
    /// Gets a parameter value from an element
    /// </summary>
    Task<object?> GetParameterValueAsync(object element, object parameter, CancellationToken cancellationToken = default);

    /// <summary>
    /// Sets a parameter value on an element
    /// </summary>
    Task<bool> SetParameterValueAsync(object element, object parameter, object? value, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets multiple parameter values in a batch operation
    /// </summary>
    Task<Dictionary<object, object?>> GetParameterValuesAsync(object element, IEnumerable<object> parameters, CancellationToken cancellationToken = default);

    /// <summary>
    /// Sets multiple parameter values in a batch operation
    /// </summary>
    Task<Dictionary<object, bool>> SetParameterValuesAsync(object element, Dictionary<object, object?> parameterValues, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets all parameters for an element
    /// </summary>
    Task<IEnumerable<object>> GetElementParametersAsync(object element, CancellationToken cancellationToken = default);

    /// <summary>
    /// Creates a shared parameter
    /// </summary>
    Task<object> CreateSharedParameterAsync(object document, string parameterName, object parameterType, object categorySet, CancellationToken cancellationToken = default);

    /// <summary>
    /// Creates a project parameter
    /// </summary>
    Task<object> CreateProjectParameterAsync(object document, string parameterName, object parameterType, object categorySet, CancellationToken cancellationToken = default);

    /// <summary>
    /// Validates parameter constraints
    /// </summary>
    Task<ParameterValidationResult> ValidateParameterValueAsync(object parameter, object? value, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets parameter bridge statistics
    /// </summary>
    ParameterBridgeStats GetStats();

    /// <summary>
    /// Clears parameter cache
    /// </summary>
    void ClearCache();
}

/// <summary>
/// High-performance implementation of parameter bridge with comprehensive caching and validation
/// </summary>
public class ParameterBridge : IParameterBridge
{
    private readonly ILogger<ParameterBridge> _logger;
    private readonly IRevitTypeConverter _typeConverter;
    private readonly ITransactionManager _transactionManager;
    private readonly ConcurrentDictionary<string, object> _parameterCache;
    private readonly ConcurrentDictionary<string, ParameterInfo> _parameterInfoCache;
    private readonly ConcurrentDictionary<Type, ParameterDefinition[]> _elementParameterCache;
    private readonly ConcurrentDictionary<string, ParameterValidationRule[]> _validationRulesCache;
    private readonly ParameterBridgeStats _stats;
    private readonly object _statsLock = new();
    private readonly SemaphoreSlim _batchSemaphore;

    public ParameterBridge(
        ILogger<ParameterBridge> logger,
        IRevitTypeConverter typeConverter,
        ITransactionManager transactionManager)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _typeConverter = typeConverter ?? throw new ArgumentNullException(nameof(typeConverter));
        _transactionManager = transactionManager ?? throw new ArgumentNullException(nameof(transactionManager));

        _parameterCache = new ConcurrentDictionary<string, object>();
        _parameterInfoCache = new ConcurrentDictionary<string, ParameterInfo>();
        _elementParameterCache = new ConcurrentDictionary<Type, ParameterDefinition[]>();
        _validationRulesCache = new ConcurrentDictionary<string, ParameterValidationRule[]>();
        _stats = new ParameterBridgeStats { LastReset = DateTime.UtcNow };
        _batchSemaphore = new SemaphoreSlim(Environment.ProcessorCount * 2, Environment.ProcessorCount * 2);

        InitializeBuiltInValidationRules();
    }

    /// <inheritdoc/>
    public async Task<object?> GetParameterValueAsync(object element, object parameter, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentNullException.ThrowIfNull(parameter);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var cacheKey = GenerateParameterCacheKey(element, parameter);

            // Check cache first
            if (_parameterCache.TryGetValue(cacheKey, out var cachedValue))
            {
                RecordCacheHit(stopwatch.Elapsed);
                return _typeConverter.ConvertToPython(cachedValue);
            }

            // Get parameter info
            var paramInfo = await GetParameterInfoAsync(parameter, cancellationToken);

            // Get value from Revit API
            var rawValue = await GetParameterValueFromRevitApi(element, parameter, paramInfo, cancellationToken);

            if (rawValue != null)
            {
                // Convert based on parameter type
                var convertedValue = ConvertParameterValue(rawValue, paramInfo);

                // Cache the converted value
                _parameterCache[cacheKey] = convertedValue;
                RecordCacheMiss(stopwatch.Elapsed);

                return _typeConverter.ConvertToPython(convertedValue);
            }

            RecordCacheMiss(stopwatch.Elapsed);
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get parameter value");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Failed to get parameter value: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<bool> SetParameterValueAsync(object element, object parameter, object? value, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentNullException.ThrowIfNull(parameter);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            // Get parameter info for validation
            var paramInfo = await GetParameterInfoAsync(parameter, cancellationToken);

            // Validate the value
            var validationResult = await ValidateParameterValueAsync(parameter, value, cancellationToken);
            if (!validationResult.IsValid)
            {
                _logger.LogWarning("Parameter validation failed: {ValidationMessage}", validationResult.ValidationMessage);
                RecordValidationFailure(stopwatch.Elapsed);
                return false;
            }

            return await _transactionManager.ExecuteInTransactionAsync(
                $"Set parameter {paramInfo.Name}",
                async () =>
                {
                    // Convert value to Revit type
                    var revitValue = ConvertValueForParameter(value, paramInfo);

                    // Set value in Revit API
                    var success = await SetParameterValueInRevitApi(element, parameter, revitValue, paramInfo, cancellationToken);

                    if (success)
                    {
                        // Update cache
                        var cacheKey = GenerateParameterCacheKey(element, parameter);
                        _parameterCache[cacheKey] = revitValue;
                        RecordParameterSet(paramInfo.Name, stopwatch.Elapsed);
                    }
                    else
                    {
                        RecordFailure(stopwatch.Elapsed);
                    }

                    return success;
                },
                cancellationToken: cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to set parameter value");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Failed to set parameter value: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<Dictionary<object, object?>> GetParameterValuesAsync(object element, IEnumerable<object> parameters, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentNullException.ThrowIfNull(parameters);

        var paramList = parameters.ToList();
        if (paramList.Count == 0)
            return new Dictionary<object, object?>();

        var stopwatch = Stopwatch.StartNew();
        var result = new Dictionary<object, object?>();
        var uncachedParams = new List<object>();

        try
        {
            await _batchSemaphore.WaitAsync(cancellationToken);
            try
            {
                // Check cache for all parameters first
                foreach (var param in paramList)
                {
                    var cacheKey = GenerateParameterCacheKey(element, param);
                    if (_parameterCache.TryGetValue(cacheKey, out var cachedValue))
                    {
                        result[param] = _typeConverter.ConvertToPython(cachedValue);
                    }
                    else
                    {
                        uncachedParams.Add(param);
                    }
                }

                // Batch get uncached parameters
                if (uncachedParams.Count > 0)
                {
                    var batchValues = await GetParameterValuesBatchFromRevitApi(element, uncachedParams, cancellationToken);

                    foreach (var kvp in batchValues)
                    {
                        var cacheKey = GenerateParameterCacheKey(element, kvp.Key);
                        if (kvp.Value != null)
                        {
                            _parameterCache[cacheKey] = kvp.Value;
                        }
                        result[kvp.Key] = _typeConverter.ConvertToPython(kvp.Value);
                    }
                }

                RecordBatchGetOperation(paramList.Count, result.Count, stopwatch.Elapsed);
                return result;
            }
            finally
            {
                _batchSemaphore.Release();
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get parameter values in batch");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Batch parameter retrieval failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<Dictionary<object, bool>> SetParameterValuesAsync(object element, Dictionary<object, object?> parameterValues, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);
        ArgumentNullException.ThrowIfNull(parameterValues);

        if (parameterValues.Count == 0)
            return new Dictionary<object, bool>();

        var stopwatch = Stopwatch.StartNew();
        try
        {
            return await _transactionManager.ExecuteInTransactionAsync(
                $"Set {parameterValues.Count} parameters",
                async () =>
                {
                    var result = new Dictionary<object, bool>();
                    var validatedValues = new Dictionary<object, object?>();

                    // Validate all values first
                    foreach (var kvp in parameterValues)
                    {
                        var validationResult = await ValidateParameterValueAsync(kvp.Key, kvp.Value, cancellationToken);
                        if (validationResult.IsValid)
                        {
                            validatedValues[kvp.Key] = kvp.Value;
                        }
                        else
                        {
                            result[kvp.Key] = false;
                            _logger.LogWarning("Parameter validation failed for {Parameter}: {Message}",
                                kvp.Key, validationResult.ValidationMessage);
                        }
                    }

                    // Set validated values in batch
                    await _batchSemaphore.WaitAsync(cancellationToken);
                    try
                    {
                        var batchResults = await SetParameterValuesBatchInRevitApi(element, validatedValues, cancellationToken);

                        foreach (var kvp in batchResults)
                        {
                            result[kvp.Key] = kvp.Value;

                            if (kvp.Value)
                            {
                                // Update cache
                                var cacheKey = GenerateParameterCacheKey(element, kvp.Key);
                                var paramValue = validatedValues[kvp.Key];
                                if (paramValue != null)
                                {
                                    _parameterCache[cacheKey] = paramValue;
                                }
                            }
                        }

                        RecordBatchSetOperation(parameterValues.Count, result.Count(r => r.Value), stopwatch.Elapsed);
                        return result;
                    }
                    finally
                    {
                        _batchSemaphore.Release();
                    }
                },
                cancellationToken: cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to set parameter values in batch");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Batch parameter setting failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<IEnumerable<object>> GetElementParametersAsync(object element, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(element);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var elementType = element.GetType();

            // Check cache for parameter definitions
            if (_elementParameterCache.TryGetValue(elementType, out var cachedParams))
            {
                RecordCacheHit(stopwatch.Elapsed);
                return cachedParams.Select(p => _typeConverter.ConvertToPython(p)).OfType<object>();
            }

            // Get parameters from Revit API
            var parameters = await GetElementParametersFromRevitApi(element, cancellationToken);
            var paramDefinitions = parameters.Select(CreateParameterDefinition).ToArray();

            // Cache parameter definitions
            _elementParameterCache[elementType] = paramDefinitions;

            RecordCacheMiss(stopwatch.Elapsed);
            return paramDefinitions.Select(p => _typeConverter.ConvertToPython(p)).OfType<object>();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get element parameters");
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Failed to get element parameters: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<object> CreateSharedParameterAsync(object document, string parameterName, object parameterType, object categorySet, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentException.ThrowIfNullOrEmpty(parameterName);
        ArgumentNullException.ThrowIfNull(parameterType);
        ArgumentNullException.ThrowIfNull(categorySet);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            return await _transactionManager.ExecuteInTransactionAsync(
                $"Create shared parameter {parameterName}",
                async () =>
                {
                    var parameter = await CreateSharedParameterInRevitApi(document, parameterName, parameterType, categorySet, cancellationToken);

                    if (parameter != null)
                    {
                        RecordParameterCreation("Shared", parameterName, stopwatch.Elapsed);
                        return _typeConverter.ConvertToPython(parameter)!;
                    }

                    throw new RevitApiException("Shared parameter creation returned null");
                },
                document,
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create shared parameter {ParameterName}", parameterName);
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Shared parameter creation failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<object> CreateProjectParameterAsync(object document, string parameterName, object parameterType, object categorySet, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentException.ThrowIfNullOrEmpty(parameterName);
        ArgumentNullException.ThrowIfNull(parameterType);
        ArgumentNullException.ThrowIfNull(categorySet);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            return await _transactionManager.ExecuteInTransactionAsync(
                $"Create project parameter {parameterName}",
                async () =>
                {
                    var parameter = await CreateProjectParameterInRevitApi(document, parameterName, parameterType, categorySet, cancellationToken);

                    if (parameter != null)
                    {
                        RecordParameterCreation("Project", parameterName, stopwatch.Elapsed);
                        return _typeConverter.ConvertToPython(parameter)!;
                    }

                    throw new RevitApiException("Project parameter creation returned null");
                },
                document,
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create project parameter {ParameterName}", parameterName);
            RecordFailure(stopwatch.Elapsed);
            throw new RevitApiException($"Project parameter creation failed: {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<ParameterValidationResult> ValidateParameterValueAsync(object parameter, object? value, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(parameter);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var paramInfo = await GetParameterInfoAsync(parameter, cancellationToken);
            var validationRules = GetValidationRules(paramInfo);

            foreach (var rule in validationRules)
            {
                var result = rule.Validate(value, paramInfo);
                if (!result.IsValid)
                {
                    RecordValidationFailure(stopwatch.Elapsed);
                    return result;
                }
            }

            RecordValidationSuccess(stopwatch.Elapsed);
            return new ParameterValidationResult { IsValid = true };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Parameter validation failed");
            RecordFailure(stopwatch.Elapsed);
            return new ParameterValidationResult
            {
                IsValid = false,
                ValidationMessage = $"Validation error: {ex.Message}"
            };
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
                CacheHits = _stats.CacheHits,
                CacheMisses = _stats.CacheMisses,
                FailedOperations = _stats.FailedOperations,
                AverageOperationTime = _stats.AverageOperationTime,
                ParametersRead = _stats.ParametersRead,
                ParametersSet = _stats.ParametersSet,
                ParametersCreated = _stats.ParametersCreated,
                ValidationSuccesses = _stats.ValidationSuccesses,
                ValidationFailures = _stats.ValidationFailures,
                BatchOperations = _stats.BatchOperations,
                CacheSize = _parameterCache.Count,
                ParameterInfoCacheSize = _parameterInfoCache.Count,
                LastReset = _stats.LastReset
            };
        }
    }

    /// <inheritdoc/>
    public void ClearCache()
    {
        _parameterCache.Clear();
        _parameterInfoCache.Clear();
        _elementParameterCache.Clear();
        _logger.LogInformation("Cleared parameter bridge caches");
    }

    // Private implementation methods

    private void InitializeBuiltInValidationRules()
    {
        var rules = new[]
        {
            new ParameterValidationRule("NotNull", (value, info) =>
                value != null ? ParameterValidationResult.Valid() :
                ParameterValidationResult.Invalid("Value cannot be null")),

            new ParameterValidationRule("NumericRange", (value, info) =>
            {
                if (info.ParameterType == "Number" && value is double numValue)
                {
                    if (info.MinValue.HasValue && numValue < info.MinValue.Value)
                        return ParameterValidationResult.Invalid($"Value {numValue} is below minimum {info.MinValue}");
                    if (info.MaxValue.HasValue && numValue > info.MaxValue.Value)
                        return ParameterValidationResult.Invalid($"Value {numValue} is above maximum {info.MaxValue}");
                }
                return ParameterValidationResult.Valid();
            }),

            new ParameterValidationRule("StringLength", (value, info) =>
            {
                if (info.ParameterType == "Text" && value is string strValue)
                {
                    if (info.MaxLength.HasValue && strValue.Length > info.MaxLength.Value)
                        return ParameterValidationResult.Invalid($"Text length {strValue.Length} exceeds maximum {info.MaxLength}");
                }
                return ParameterValidationResult.Valid();
            }),

            new ParameterValidationRule("ReadOnly", (value, info) =>
                !info.IsReadOnly ? ParameterValidationResult.Valid() :
                ParameterValidationResult.Invalid("Parameter is read-only"))
        };

        foreach (var rule in rules)
        {
            _validationRulesCache[rule.Name] = new[] { rule };
        }

        _logger.LogInformation("Initialized {Count} built-in parameter validation rules", rules.Length);
    }

    private async Task<ParameterInfo> GetParameterInfoAsync(object parameter, CancellationToken cancellationToken)
    {
        var paramKey = parameter.GetHashCode().ToString();

        if (_parameterInfoCache.TryGetValue(paramKey, out var cachedInfo))
        {
            return cachedInfo;
        }

        var info = await ExtractParameterInfoFromRevitApi(parameter, cancellationToken);
        _parameterInfoCache[paramKey] = info;
        return info;
    }

    private ParameterValidationRule[] GetValidationRules(ParameterInfo paramInfo)
    {
        var allRules = new List<ParameterValidationRule>();

        // Add built-in rules
        foreach (var ruleSet in _validationRulesCache.Values)
        {
            allRules.AddRange(ruleSet);
        }

        return allRules.ToArray();
    }

    private string GenerateParameterCacheKey(object element, object parameter)
    {
        var elementHash = element.GetHashCode();
        var paramHash = parameter.GetHashCode();
        return $"elem:{elementHash}_param:{paramHash}";
    }

    private object ConvertParameterValue(object rawValue, ParameterInfo paramInfo)
    {
        // Convert based on parameter type
        return paramInfo.ParameterType switch
        {
            "Number" => Convert.ToDouble(rawValue),
            "Integer" => Convert.ToInt32(rawValue),
            "Text" => rawValue.ToString() ?? string.Empty,
            "YesNo" => Convert.ToBoolean(rawValue),
            "Length" => Convert.ToDouble(rawValue),
            "Area" => Convert.ToDouble(rawValue),
            "Volume" => Convert.ToDouble(rawValue),
            "Angle" => Convert.ToDouble(rawValue),
            _ => rawValue
        };
    }

    private object ConvertValueForParameter(object? value, ParameterInfo paramInfo)
    {
        if (value == null)
            return null!;

        return paramInfo.ParameterType switch
        {
            "Number" => _typeConverter.ConvertFromPython<double>(value) ?? 0.0,
            "Integer" => _typeConverter.ConvertFromPython<int>(value) ?? 0,
            "Text" => _typeConverter.ConvertFromPython<string>(value) ?? string.Empty,
            "YesNo" => _typeConverter.ConvertFromPython<bool>(value) ?? false,
            "Length" => _typeConverter.ConvertFromPython<double>(value) ?? 0.0,
            "Area" => _typeConverter.ConvertFromPython<double>(value) ?? 0.0,
            "Volume" => _typeConverter.ConvertFromPython<double>(value) ?? 0.0,
            "Angle" => _typeConverter.ConvertFromPython<double>(value) ?? 0.0,
            _ => value
        };
    }

    private ParameterDefinition CreateParameterDefinition(object parameter)
    {
        // Extract parameter definition from Revit parameter
        return new ParameterDefinition
        {
            Name = ExtractParameterName(parameter),
            ParameterType = ExtractParameterType(parameter),
            IsShared = ExtractIsShared(parameter),
            IsReadOnly = ExtractIsReadOnly(parameter),
            GroupName = ExtractGroupName(parameter)
        };
    }

    private string ExtractParameterName(object parameter) =>
        parameter.GetType().GetProperty("Definition")?.GetValue(parameter)?.ToString() ?? "Unknown";

    private string ExtractParameterType(object parameter) =>
        parameter.GetType().GetProperty("StorageType")?.GetValue(parameter)?.ToString() ?? "Unknown";

    private bool ExtractIsShared(object parameter) =>
        parameter.GetType().GetProperty("IsShared")?.GetValue(parameter) is bool shared && shared;

    private bool ExtractIsReadOnly(object parameter) =>
        parameter.GetType().GetProperty("IsReadOnly")?.GetValue(parameter) is bool readOnly && readOnly;

    private string ExtractGroupName(object parameter) =>
        parameter.GetType().GetProperty("Definition")?.GetValue(parameter)?.GetType()
            .GetProperty("ParameterGroup")?.GetValue(parameter)?.ToString() ?? "Other";

    // Mock Revit API integration methods - these would be replaced with actual Revit API calls

    private async Task<object?> GetParameterValueFromRevitApi(object element, object parameter, ParameterInfo paramInfo, CancellationToken cancellationToken)
    {
        await Task.Delay(1, cancellationToken);
        return paramInfo.ParameterType switch
        {
            "Number" => 42.0,
            "Integer" => 42,
            "Text" => "Mock Value",
            "YesNo" => true,
            _ => "Unknown"
        };
    }

    private async Task<Dictionary<object, object?>> GetParameterValuesBatchFromRevitApi(object element, IList<object> parameters, CancellationToken cancellationToken)
    {
        await Task.Delay(parameters.Count, cancellationToken);

        var result = new Dictionary<object, object?>();
        foreach (var param in parameters)
        {
            result[param] = "Batch Mock Value";
        }
        return result;
    }

    private async Task<bool> SetParameterValueInRevitApi(object element, object parameter, object value, ParameterInfo paramInfo, CancellationToken cancellationToken)
    {
        await Task.Delay(2, cancellationToken);
        return true; // Mock success
    }

    private async Task<Dictionary<object, bool>> SetParameterValuesBatchInRevitApi(object element, Dictionary<object, object?> parameterValues, CancellationToken cancellationToken)
    {
        await Task.Delay(parameterValues.Count * 2, cancellationToken);

        var result = new Dictionary<object, bool>();
        foreach (var kvp in parameterValues)
        {
            result[kvp.Key] = true; // Mock success
        }
        return result;
    }

    private async Task<IEnumerable<object>> GetElementParametersFromRevitApi(object element, CancellationToken cancellationToken)
    {
        await Task.Delay(5, cancellationToken);

        return Enumerable.Range(1, 10).Select(i => new { Name = $"Parameter{i}", Type = "Text" });
    }

    private async Task<ParameterInfo> ExtractParameterInfoFromRevitApi(object parameter, CancellationToken cancellationToken)
    {
        await Task.Delay(1, cancellationToken);

        return new ParameterInfo
        {
            Name = $"Param_{parameter.GetHashCode()}",
            ParameterType = "Text",
            IsReadOnly = false,
            IsShared = false,
            GroupName = "General"
        };
    }

    private async Task<object> CreateSharedParameterInRevitApi(object document, string parameterName, object parameterType, object categorySet, CancellationToken cancellationToken)
    {
        await Task.Delay(10, cancellationToken);
        return new { Name = parameterName, Type = "Shared", IsShared = true };
    }

    private async Task<object> CreateProjectParameterInRevitApi(object document, string parameterName, object parameterType, object categorySet, CancellationToken cancellationToken)
    {
        await Task.Delay(8, cancellationToken);
        return new { Name = parameterName, Type = "Project", IsShared = false };
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
            _stats.ParametersRead++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordParameterSet(string parameterName, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.ParametersSet++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordParameterCreation(string parameterType, string parameterName, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.ParametersCreated++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordBatchGetOperation(int requested, int retrieved, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.BatchOperations++;
            _stats.ParametersRead += retrieved;
            UpdateAverageTime(duration);
        }
    }

    private void RecordBatchSetOperation(int requested, int successful, TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.BatchOperations++;
            _stats.ParametersSet += successful;
            UpdateAverageTime(duration);
        }
    }

    private void RecordValidationSuccess(TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.ValidationSuccesses++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordValidationFailure(TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.ValidationFailures++;
            UpdateAverageTime(duration);
        }
    }

    private void RecordFailure(TimeSpan duration)
    {
        lock (_statsLock)
        {
            _stats.TotalOperations++;
            _stats.FailedOperations++;
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
/// Information about a parameter
/// </summary>
public class ParameterInfo
{
    public string Name { get; set; } = string.Empty;
    public string ParameterType { get; set; } = string.Empty;
    public bool IsReadOnly { get; set; }
    public bool IsShared { get; set; }
    public string GroupName { get; set; } = string.Empty;
    public double? MinValue { get; set; }
    public double? MaxValue { get; set; }
    public int? MaxLength { get; set; }
    public string[] AllowedValues { get; set; } = Array.Empty<string>();
}

/// <summary>
/// Definition of a parameter
/// </summary>
public class ParameterDefinition
{
    public string Name { get; set; } = string.Empty;
    public string ParameterType { get; set; } = string.Empty;
    public bool IsShared { get; set; }
    public bool IsReadOnly { get; set; }
    public string GroupName { get; set; } = string.Empty;
}

/// <summary>
/// Result of parameter validation
/// </summary>
public class ParameterValidationResult
{
    public bool IsValid { get; set; }
    public string ValidationMessage { get; set; } = string.Empty;

    public static ParameterValidationResult Valid() => new() { IsValid = true };
    public static ParameterValidationResult Invalid(string message) => new() { IsValid = false, ValidationMessage = message };
}

/// <summary>
/// Parameter validation rule
/// </summary>
public class ParameterValidationRule
{
    public string Name { get; set; }
    public Func<object?, ParameterInfo, ParameterValidationResult> Validate { get; set; }

    public ParameterValidationRule(string name, Func<object?, ParameterInfo, ParameterValidationResult> validate)
    {
        Name = name;
        Validate = validate;
    }
}

/// <summary>
/// Statistics for parameter bridge operations
/// </summary>
public class ParameterBridgeStats
{
    public long TotalOperations { get; set; }
    public long CacheHits { get; set; }
    public long CacheMisses { get; set; }
    public long FailedOperations { get; set; }
    public TimeSpan AverageOperationTime { get; set; }
    public long ParametersRead { get; set; }
    public long ParametersSet { get; set; }
    public long ParametersCreated { get; set; }
    public long ValidationSuccesses { get; set; }
    public long ValidationFailures { get; set; }
    public long BatchOperations { get; set; }
    public int CacheSize { get; set; }
    public int ParameterInfoCacheSize { get; set; }
    public double CacheHitRatio => TotalOperations > 0 ? (double)CacheHits / TotalOperations : 0.0;
    public DateTime LastReset { get; set; }
}
