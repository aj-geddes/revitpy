using System.Collections.Concurrent;
using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using RevitPy.Core.Exceptions;

namespace RevitPy.Bridge;

/// <summary>
/// High-performance type converter for Python-Revit API marshaling
/// </summary>
public class TypeConverter : IRevitTypeConverter
{
    private readonly ILogger<TypeConverter> _logger;
    private readonly ConcurrentDictionary<Type, Type> _pythonToRevitTypeMap;
    private readonly ConcurrentDictionary<Type, Type> _revitToPythonTypeMap;
    private readonly ConcurrentDictionary<(Type, Type), Func<object?, object?>> _customConverters;
    private readonly ConcurrentDictionary<Type, PropertyInfo[]> _typePropertyCache;
    private readonly ConcurrentDictionary<Type, MethodInfo[]> _typeMethodCache;
    private readonly TypeConversionStats _stats;
    private readonly object _statsLock = new();

    public TypeConverter(ILogger<TypeConverter> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _pythonToRevitTypeMap = new ConcurrentDictionary<Type, Type>();
        _revitToPythonTypeMap = new ConcurrentDictionary<Type, Type>();
        _customConverters = new ConcurrentDictionary<(Type, Type), Func<object?, object?>>();
        _typePropertyCache = new ConcurrentDictionary<Type, PropertyInfo[]>();
        _typeMethodCache = new ConcurrentDictionary<Type, MethodInfo[]>();
        _stats = new TypeConversionStats { LastReset = DateTime.UtcNow };

        InitializeBuiltInConverters();
    }

    /// <inheritdoc/>
    public T? ConvertFromPython<T>(object? pythonObject, Type? targetType = null)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            targetType ??= typeof(T);
            var result = ConvertFromPythonInternal(pythonObject, targetType);
            
            RecordConversion(true, stopwatch.Elapsed, pythonObject?.GetType(), targetType, true);
            return (T?)result;
        }
        catch (Exception ex)
        {
            RecordConversion(false, stopwatch.Elapsed, pythonObject?.GetType(), targetType, true);
            _logger.LogError(ex, "Failed to convert Python object to {TargetType}", targetType?.Name);
            throw new RevitApiException(
                $"Failed to convert Python object to {targetType?.Name}: {ex.Message}", 
                ex);
        }
    }

    /// <inheritdoc/>
    public object? ConvertToPython(object? revitObject, bool preserveType = false)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            var result = ConvertToPythonInternal(revitObject, preserveType);
            
            RecordConversion(true, stopwatch.Elapsed, revitObject?.GetType(), result?.GetType(), false);
            return result;
        }
        catch (Exception ex)
        {
            RecordConversion(false, stopwatch.Elapsed, revitObject?.GetType(), null, false);
            _logger.LogError(ex, "Failed to convert Revit object to Python");
            throw new RevitApiException(
                $"Failed to convert Revit object to Python: {ex.Message}", 
                ex);
        }
    }

    /// <inheritdoc/>
    public T[]? ConvertArrayFromPython<T>(object? pythonArray, Type? elementType = null)
    {
        if (pythonArray == null)
            return null;

        elementType ??= typeof(T);

        if (pythonArray is not Array array)
        {
            // Try to convert single object to array
            var singleValue = ConvertFromPython<T>(pythonArray, elementType);
            return singleValue != null ? new[] { singleValue } : null;
        }

        var result = new T[array.Length];
        for (int i = 0; i < array.Length; i++)
        {
            result[i] = ConvertFromPython<T>(array.GetValue(i), elementType);
        }

        return result;
    }

    /// <inheritdoc/>
    public object? ConvertArrayToPython(object? revitArray, bool preserveType = false)
    {
        if (revitArray == null)
            return null;

        if (revitArray is not Array array)
            return ConvertToPython(revitArray, preserveType);

        var result = new object?[array.Length];
        for (int i = 0; i < array.Length; i++)
        {
            result[i] = ConvertToPython(array.GetValue(i), preserveType);
        }

        return result;
    }

    /// <inheritdoc/>
    public bool CanConvertFromPython(Type pythonType, Type targetType)
    {
        if (pythonType == targetType)
            return true;

        // Check built-in conversions
        if (HasBuiltInConversion(pythonType, targetType))
            return true;

        // Check custom converters
        if (_customConverters.ContainsKey((pythonType, targetType)))
            return true;

        // Check if target type has PythonConvertible attribute
        if (targetType.GetCustomAttribute<PythonConvertibleAttribute>() != null)
            return true;

        // Check for implicit conversions
        return HasImplicitConversion(pythonType, targetType);
    }

    /// <inheritdoc/>
    public bool CanConvertToPython(Type revitType)
    {
        // Most types can be converted to Python objects
        if (revitType.IsPrimitive || revitType == typeof(string))
            return true;

        // Check if type has PythonConvertible attribute
        if (revitType.GetCustomAttribute<PythonConvertibleAttribute>() != null)
            return true;

        // Check for custom converters
        return _customConverters.Keys.Any(k => k.Item1 == revitType);
    }

    /// <inheritdoc/>
    public Type? GetRevitType(Type pythonType)
    {
        return _pythonToRevitTypeMap.GetValueOrDefault(pythonType);
    }

    /// <inheritdoc/>
    public Type? GetPythonType(Type revitType)
    {
        return _revitToPythonTypeMap.GetValueOrDefault(revitType);
    }

    /// <inheritdoc/>
    public void RegisterConverter<TFrom, TTo>(Func<TFrom, TTo> converter)
    {
        ArgumentNullException.ThrowIfNull(converter);

        _customConverters[(typeof(TFrom), typeof(TTo))] = obj => 
        {
            if (obj is TFrom from)
                return converter(from);
            return null;
        };

        lock (_statsLock)
        {
            _stats.CustomConvertersCount++;
        }

        _logger.LogInformation("Registered custom converter from {FromType} to {ToType}", 
            typeof(TFrom).Name, typeof(TTo).Name);
    }

    /// <inheritdoc/>
    public void RegisterBidirectionalConverter<TPython, TRevit>(
        Func<TRevit, TPython> toPython, 
        Func<TPython, TRevit> toRevit)
    {
        ArgumentNullException.ThrowIfNull(toPython);
        ArgumentNullException.ThrowIfNull(toRevit);

        RegisterConverter(toPython);
        RegisterConverter(toRevit);

        // Update type mappings
        _pythonToRevitTypeMap[typeof(TPython)] = typeof(TRevit);
        _revitToPythonTypeMap[typeof(TRevit)] = typeof(TPython);
    }

    /// <inheritdoc/>
    public TypeConversionStats GetStats()
    {
        lock (_statsLock)
        {
            return new TypeConversionStats
            {
                TotalConversions = _stats.TotalConversions,
                SuccessfulConversions = _stats.SuccessfulConversions,
                FailedConversions = _stats.FailedConversions,
                PythonToRevitConversions = _stats.PythonToRevitConversions,
                RevitToPythonConversions = _stats.RevitToPythonConversions,
                ConversionsByType = new Dictionary<string, long>(_stats.ConversionsByType),
                AverageConversionTime = _stats.AverageConversionTime,
                CustomConvertersCount = _stats.CustomConvertersCount,
                LastReset = _stats.LastReset
            };
        }
    }

    private void InitializeBuiltInConverters()
    {
        // Primitive type conversions
        RegisterBuiltInConverter<int, double>(i => i);
        RegisterBuiltInConverter<float, double>(f => f);
        RegisterBuiltInConverter<double, float>(d => (float)d);
        RegisterBuiltInConverter<long, int>(l => (int)l);
        RegisterBuiltInConverter<decimal, double>(d => (double)d);
        
        // String conversions
        RegisterBuiltInConverter<string, object>(s => s);
        RegisterBuiltInConverter<object, string>(o => o?.ToString() ?? string.Empty);
        
        // Boolean conversions
        RegisterBuiltInConverter<bool, string>(b => b.ToString().ToLowerInvariant());
        RegisterBuiltInConverter<string, bool>(s => bool.Parse(s));
        
        // Collection conversions
        RegisterBuiltInConverter<Array, List<object>>(arr => 
        {
            var list = new List<object>();
            for (int i = 0; i < arr.Length; i++)
            {
                list.Add(ConvertToPython(arr.GetValue(i)));
            }
            return list;
        });
        
        RegisterBuiltInConverter<List<object>, Array>(list => list.ToArray());

        _logger.LogInformation("Initialized {Count} built-in type converters", _customConverters.Count);
    }

    private void RegisterBuiltInConverter<TFrom, TTo>(Func<TFrom, TTo> converter)
    {
        RegisterConverter(converter);
    }

    private object? ConvertFromPythonInternal(object? pythonObject, Type targetType)
    {
        if (pythonObject == null)
            return null;

        var sourceType = pythonObject.GetType();

        // Direct type match
        if (sourceType == targetType || targetType.IsAssignableFrom(sourceType))
            return pythonObject;

        // Check custom converters first
        if (_customConverters.TryGetValue((sourceType, targetType), out var customConverter))
        {
            return customConverter(pythonObject);
        }

        // Handle nullable types
        if (targetType.IsGenericType && targetType.GetGenericTypeDefinition() == typeof(Nullable<>))
        {
            var underlyingType = Nullable.GetUnderlyingType(targetType);
            if (underlyingType != null)
            {
                return ConvertFromPythonInternal(pythonObject, underlyingType);
            }
        }

        // Handle enums
        if (targetType.IsEnum)
        {
            if (pythonObject is string enumString)
            {
                return Enum.Parse(targetType, enumString, ignoreCase: true);
            }
            if (pythonObject is int enumInt)
            {
                return Enum.ToObject(targetType, enumInt);
            }
        }

        // Handle collections
        if (targetType.IsArray && pythonObject is Array sourceArray)
        {
            var elementType = targetType.GetElementType()!;
            var targetArray = Array.CreateInstance(elementType, sourceArray.Length);
            for (int i = 0; i < sourceArray.Length; i++)
            {
                var convertedElement = ConvertFromPythonInternal(sourceArray.GetValue(i), elementType);
                targetArray.SetValue(convertedElement, i);
            }
            return targetArray;
        }

        // Handle complex object conversion using reflection
        if (targetType.GetCustomAttribute<PythonConvertibleAttribute>() != null)
        {
            return ConvertComplexObjectFromPython(pythonObject, targetType);
        }

        // Try implicit conversion
        return Convert.ChangeType(pythonObject, targetType);
    }

    private object? ConvertToPythonInternal(object? revitObject, bool preserveType)
    {
        if (revitObject == null)
            return null;

        var sourceType = revitObject.GetType();

        // Check custom converters first
        var customConverterKey = _customConverters.Keys.FirstOrDefault(k => k.Item1 == sourceType);
        if (customConverterKey != default)
        {
            return _customConverters[customConverterKey](revitObject);
        }

        // Handle primitive types
        if (sourceType.IsPrimitive || sourceType == typeof(string) || sourceType == typeof(decimal))
        {
            return revitObject;
        }

        // Handle enums
        if (sourceType.IsEnum)
        {
            return preserveType ? new { Type = sourceType.Name, Value = revitObject.ToString() } : revitObject.ToString();
        }

        // Handle arrays and collections
        if (revitObject is Array array)
        {
            return ConvertArrayToPython(array, preserveType);
        }

        // Handle complex objects
        if (sourceType.GetCustomAttribute<PythonConvertibleAttribute>() != null)
        {
            return ConvertComplexObjectToPython(revitObject, preserveType);
        }

        // Default: return object as-is with metadata if preserveType is true
        if (preserveType)
        {
            return new { Type = sourceType.Name, Value = revitObject };
        }

        return revitObject;
    }

    private object? ConvertComplexObjectFromPython(object pythonObject, Type targetType)
    {
        try
        {
            // Try to create instance of target type
            var instance = Activator.CreateInstance(targetType);
            if (instance == null)
                return null;

            // Get properties with PythonProperty attributes
            var properties = GetCachedProperties(targetType);
            var pythonDict = pythonObject as Dictionary<string, object> ?? 
                           ConvertObjectToDictionary(pythonObject);

            foreach (var property in properties)
            {
                var pythonAttr = property.GetCustomAttribute<PythonPropertyAttribute>();
                if (pythonAttr?.Ignore == true)
                    continue;

                var pythonName = pythonAttr?.PythonName ?? property.Name;
                if (pythonDict?.TryGetValue(pythonName, out var value) == true && property.CanWrite)
                {
                    var convertedValue = ConvertFromPythonInternal(value, property.PropertyType);
                    property.SetValue(instance, convertedValue);
                }
            }

            return instance;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to convert complex object from Python to {TargetType}", targetType.Name);
            throw;
        }
    }

    private object ConvertComplexObjectToPython(object revitObject, bool preserveType)
    {
        var sourceType = revitObject.GetType();
        var result = new Dictionary<string, object?>();

        if (preserveType)
        {
            result["__type__"] = sourceType.Name;
            result["__assembly__"] = sourceType.Assembly.GetName().Name;
        }

        var properties = GetCachedProperties(sourceType);
        foreach (var property in properties)
        {
            var pythonAttr = property.GetCustomAttribute<PythonPropertyAttribute>();
            if (pythonAttr?.Ignore == true || !property.CanRead)
                continue;

            try
            {
                var value = property.GetValue(revitObject);
                var pythonName = pythonAttr?.PythonName ?? property.Name;
                result[pythonName] = ConvertToPythonInternal(value, preserveType);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to convert property {PropertyName} of {ObjectType}", 
                    property.Name, sourceType.Name);
            }
        }

        return result;
    }

    private PropertyInfo[] GetCachedProperties(Type type)
    {
        return _typePropertyCache.GetOrAdd(type, t => 
            t.GetProperties(BindingFlags.Public | BindingFlags.Instance));
    }

    private Dictionary<string, object>? ConvertObjectToDictionary(object obj)
    {
        try
        {
            // Try JSON serialization/deserialization as fallback
            var json = JsonSerializer.Serialize(obj);
            return JsonSerializer.Deserialize<Dictionary<string, object>>(json);
        }
        catch
        {
            return null;
        }
    }

    private bool HasBuiltInConversion(Type sourceType, Type targetType)
    {
        // Check for primitive conversions
        if (sourceType.IsPrimitive && targetType.IsPrimitive)
            return true;

        // Check for string conversions
        if (sourceType == typeof(string) || targetType == typeof(string))
            return true;

        // Check registered conversions
        return _customConverters.ContainsKey((sourceType, targetType));
    }

    private bool HasImplicitConversion(Type sourceType, Type targetType)
    {
        try
        {
            // Check if there's an implicit conversion operator
            var implicitMethod = targetType.GetMethods(BindingFlags.Public | BindingFlags.Static)
                .FirstOrDefault(m => m.Name == "op_Implicit" && 
                               m.ReturnType == targetType && 
                               m.GetParameters().FirstOrDefault()?.ParameterType == sourceType);

            return implicitMethod != null;
        }
        catch
        {
            return false;
        }
    }

    private void RecordConversion(bool success, TimeSpan duration, Type? sourceType, Type? targetType, bool isPythonToRevit)
    {
        lock (_statsLock)
        {
            _stats.TotalConversions++;
            
            if (success)
            {
                _stats.SuccessfulConversions++;
            }
            else
            {
                _stats.FailedConversions++;
            }

            if (isPythonToRevit)
            {
                _stats.PythonToRevitConversions++;
            }
            else
            {
                _stats.RevitToPythonConversions++;
            }

            // Update type-specific statistics
            var typeKey = $"{sourceType?.Name ?? "null"} -> {targetType?.Name ?? "null"}";
            _stats.ConversionsByType[typeKey] = _stats.ConversionsByType.GetValueOrDefault(typeKey) + 1;

            // Update average conversion time
            var totalDuration = _stats.AverageConversionTime.Ticks * (_stats.TotalConversions - 1) + duration.Ticks;
            _stats.AverageConversionTime = new TimeSpan(totalDuration / _stats.TotalConversions);
        }
    }
}