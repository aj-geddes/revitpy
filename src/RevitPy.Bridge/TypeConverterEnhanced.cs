using System.Collections.Concurrent;
using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using RevitPy.Core.Exceptions;

namespace RevitPy.Bridge;

/// <summary>
/// Enhanced high-performance type converter with comprehensive Revit API support
/// </summary>
public class TypeConverterEnhanced : IRevitTypeConverter
{
    private readonly ILogger<TypeConverterEnhanced> _logger;
    private readonly ConcurrentDictionary<Type, Type> _pythonToRevitTypeMap;
    private readonly ConcurrentDictionary<Type, Type> _revitToPythonTypeMap;
    private readonly ConcurrentDictionary<(Type, Type), Func<object?, object?>> _customConverters;
    private readonly ConcurrentDictionary<Type, PropertyInfo[]> _typePropertyCache;
    private readonly ConcurrentDictionary<Type, MethodInfo[]> _typeMethodCache;
    private readonly ConcurrentDictionary<string, object> _objectCache;
    private readonly TypeConversionStats _stats;
    private readonly object _statsLock = new();
    private readonly object _cacheLock = new();

    public TypeConverterEnhanced(ILogger<TypeConverterEnhanced> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _pythonToRevitTypeMap = new ConcurrentDictionary<Type, Type>();
        _revitToPythonTypeMap = new ConcurrentDictionary<Type, Type>();
        _customConverters = new ConcurrentDictionary<(Type, Type), Func<object?, object?>>();
        _typePropertyCache = new ConcurrentDictionary<Type, PropertyInfo[]>();
        _typeMethodCache = new ConcurrentDictionary<Type, MethodInfo[]>();
        _objectCache = new ConcurrentDictionary<string, object>();
        _stats = new TypeConversionStats { LastReset = DateTime.UtcNow };

        InitializeBuiltInConverters();
        InitializeRevitTypeConverters();
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
                list.Add(ConvertToPython(arr.GetValue(i)) ?? new object());
            }
            return list;
        });

        RegisterBuiltInConverter<List<object>, Array>(list => list.ToArray());

        _logger.LogInformation("Initialized {Count} built-in type converters", _customConverters.Count);
    }

    private void InitializeRevitTypeConverters()
    {
        // XYZ Point conversions (Revit geometry)
        RegisterBidirectionalConverter<double[], object>(
            // Revit XYZ to Python array
            xyz => xyz switch
            {
                var o when IsRevitXYZ(o) => new[] { GetXYZProperty(o, "X"), GetXYZProperty(o, "Y"), GetXYZProperty(o, "Z") },
                _ => Array.Empty<double>()
            },
            // Python array to Revit XYZ
            arr => arr.Length >= 3 ? CreateRevitXYZ(arr[0], arr[1], arr[2]) : CreateRevitXYZ(0, 0, 0)
        );

        RegisterBidirectionalConverter<Dictionary<string, double>, object>(
            // Revit XYZ to Python dict
            xyz => xyz switch
            {
                var o when IsRevitXYZ(o) => new Dictionary<string, double>
                {
                    ["X"] = GetXYZProperty(o, "X"),
                    ["Y"] = GetXYZProperty(o, "Y"),
                    ["Z"] = GetXYZProperty(o, "Z")
                },
                _ => new Dictionary<string, double>()
            },
            // Python dict to Revit XYZ
            dict => CreateRevitXYZ(
                dict.GetValueOrDefault("X", 0),
                dict.GetValueOrDefault("Y", 0),
                dict.GetValueOrDefault("Z", 0))
        );

        // UV Point conversions (2D coordinates)
        RegisterBidirectionalConverter<double[], object>(
            // Revit UV to Python array
            uv => uv switch
            {
                var o when IsRevitUV(o) => new[] { GetUVProperty(o, "U"), GetUVProperty(o, "V") },
                _ => Array.Empty<double>()
            },
            // Python array to Revit UV
            arr => arr.Length >= 2 ? CreateRevitUV(arr[0], arr[1]) : CreateRevitUV(0, 0)
        );

        // Element ID conversions
        RegisterBidirectionalConverter<long, object>(
            // Revit ElementId to long
            elementId => elementId switch
            {
                var id when IsRevitElementId(id) => GetElementIdValue(id),
                _ => -1L
            },
            // Long to Revit ElementId
            value => CreateRevitElementId(value)
        );

        RegisterBidirectionalConverter<string, object>(
            // Revit ElementId to string
            elementId => elementId switch
            {
                var id when IsRevitElementId(id) => GetElementIdValue(id).ToString(),
                _ => "-1"
            },
            // String to Revit ElementId
            value => long.TryParse(value, out var longValue) ? CreateRevitElementId(longValue) : CreateRevitElementId(-1)
        );

        // BuiltInParameter enum conversions
        RegisterBidirectionalConverter<string, object>(
            // Revit BuiltInParameter to string
            param => param switch
            {
                var p when IsRevitBuiltInParameter(p) => p.ToString(),
                _ => "INVALID"
            },
            // String to Revit BuiltInParameter
            value => ParseRevitBuiltInParameter(value)
        );

        // Transform matrix conversions
        RegisterBidirectionalConverter<double[][], object>(
            // Revit Transform to 2D array
            transform => transform switch
            {
                var t when IsRevitTransform(t) => ConvertTransformToMatrix(t),
                _ => Array.Empty<double[]>()
            },
            // 2D array to Revit Transform
            matrix => CreateRevitTransform(matrix)
        );

        // Color conversions
        RegisterBidirectionalConverter<Dictionary<string, int>, object>(
            // Revit Color to RGB dict
            color => color switch
            {
                var c when IsRevitColor(c) => new Dictionary<string, int>
                {
                    ["Red"] = GetColorProperty(c, "Red"),
                    ["Green"] = GetColorProperty(c, "Green"),
                    ["Blue"] = GetColorProperty(c, "Blue")
                },
                _ => new Dictionary<string, int> { ["Red"] = 0, ["Green"] = 0, ["Blue"] = 0 }
            },
            // RGB dict to Revit Color
            dict => CreateRevitColor(
                dict.GetValueOrDefault("Red", 0),
                dict.GetValueOrDefault("Green", 0),
                dict.GetValueOrDefault("Blue", 0))
        );

        RegisterBidirectionalConverter<int[], object>(
            // Revit Color to RGB array
            color => color switch
            {
                var c when IsRevitColor(c) => new[] { GetColorProperty(c, "Red"), GetColorProperty(c, "Green"), GetColorProperty(c, "Blue") },
                _ => new[] { 0, 0, 0 }
            },
            // RGB array to Revit Color
            rgb => rgb.Length >= 3 ? CreateRevitColor(rgb[0], rgb[1], rgb[2]) : CreateRevitColor(0, 0, 0)
        );

        // Unit conversion support
        RegisterBidirectionalConverter<Dictionary<string, object>, object>(
            // Revit Unit to Python dict
            unit => unit switch
            {
                var u when IsRevitUnit(u) => new Dictionary<string, object>
                {
                    ["TypeId"] = GetUnitProperty(u, "TypeId")?.ToString() ?? "",
                    ["DisplayName"] = GetUnitProperty(u, "DisplayName")?.ToString() ?? "",
                    ["Symbol"] = GetUnitProperty(u, "Symbol")?.ToString() ?? ""
                },
                _ => new Dictionary<string, object>()
            },
            // Python dict to Revit Unit placeholder
            dict => new { TypeId = dict.GetValueOrDefault("TypeId", ""), __type__ = "Unit" }
        );

        _logger.LogInformation("Initialized Revit-specific type converters with {Count} converters",
            _customConverters.Count);
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

        // Check object cache for performance
        var cacheKey = $"{sourceType.Name}_{revitObject.GetHashCode()}_{preserveType}";
        lock (_cacheLock)
        {
            if (_objectCache.TryGetValue(cacheKey, out var cachedResult) &&
                _objectCache.Count < 10000) // Prevent memory leaks
            {
                return cachedResult;
            }
        }

        // Check custom converters first
        var customConverterKey = _customConverters.Keys.FirstOrDefault(k => k.Item1 == sourceType);
        if (customConverterKey != default)
        {
            var result = _customConverters[customConverterKey](revitObject);
            CacheResult(cacheKey, result);
            return result;
        }

        // Handle primitive types
        if (sourceType.IsPrimitive || sourceType == typeof(string) || sourceType == typeof(decimal))
        {
            return revitObject;
        }

        // Handle enums
        if (sourceType.IsEnum)
        {
            var result = preserveType ? new { Type = sourceType.Name, Value = revitObject.ToString() } : revitObject.ToString();
            CacheResult(cacheKey, result);
            return result;
        }

        // Handle arrays and collections
        if (revitObject is Array array)
        {
            return ConvertArrayToPython(array, preserveType);
        }

        // Handle complex objects
        if (sourceType.GetCustomAttribute<PythonConvertibleAttribute>() != null)
        {
            var result = ConvertComplexObjectToPython(revitObject, preserveType);
            CacheResult(cacheKey, result);
            return result;
        }

        // Default: return object as-is with metadata if preserveType is true
        if (preserveType)
        {
            var result = new { Type = sourceType.Name, Value = revitObject };
            CacheResult(cacheKey, result);
            return result;
        }

        return revitObject;
    }

    private void CacheResult(string key, object? result)
    {
        lock (_cacheLock)
        {
            if (_objectCache.Count < 10000 && result != null)
            {
                _objectCache[key] = result;
            }
        }
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

    // Helper methods for Revit type detection and manipulation
    private static bool IsRevitXYZ(object obj) => obj?.GetType().Name == "XYZ";
    private static bool IsRevitUV(object obj) => obj?.GetType().Name == "UV";
    private static bool IsRevitElementId(object obj) => obj?.GetType().Name == "ElementId";
    private static bool IsRevitBuiltInParameter(object obj) => obj?.GetType().Name == "BuiltInParameter";
    private static bool IsRevitTransform(object obj) => obj?.GetType().Name == "Transform";
    private static bool IsRevitColor(object obj) => obj?.GetType().Name == "Color";
    private static bool IsRevitUnit(object obj) => obj?.GetType().Name == "Unit";

    private static double GetXYZProperty(object xyz, string property)
    {
        try
        {
            return (double)(xyz.GetType().GetProperty(property)?.GetValue(xyz) ?? 0.0);
        }
        catch
        {
            return 0.0;
        }
    }

    private static double GetUVProperty(object uv, string property)
    {
        try
        {
            return (double)(uv.GetType().GetProperty(property)?.GetValue(uv) ?? 0.0);
        }
        catch
        {
            return 0.0;
        }
    }

    private static long GetElementIdValue(object elementId)
    {
        try
        {
            // Try IntegerValue property first (newer Revit versions)
            var integerValue = elementId.GetType().GetProperty("IntegerValue")?.GetValue(elementId);
            if (integerValue != null)
                return (long)integerValue;

            // Fallback to older property names
            var value = elementId.GetType().GetProperty("Value")?.GetValue(elementId);
            return value != null ? Convert.ToInt64(value) : -1L;
        }
        catch
        {
            return -1L;
        }
    }

    private static int GetColorProperty(object color, string property)
    {
        try
        {
            return (int)(color.GetType().GetProperty(property)?.GetValue(color) ?? 0);
        }
        catch
        {
            return 0;
        }
    }

    private static object? GetUnitProperty(object unit, string property)
    {
        try
        {
            return unit.GetType().GetProperty(property)?.GetValue(unit);
        }
        catch
        {
            return null;
        }
    }

    private static object CreateRevitXYZ(double x, double y, double z)
    {
        // This would use reflection or dynamic instantiation to create XYZ
        // For now, return a placeholder that would be replaced with actual Revit API calls
        return new { X = x, Y = y, Z = z, __type__ = "XYZ" };
    }

    private static object CreateRevitUV(double u, double v)
    {
        return new { U = u, V = v, __type__ = "UV" };
    }

    private static object CreateRevitElementId(long value)
    {
        return new { IntegerValue = value, __type__ = "ElementId" };
    }

    private static object ParseRevitBuiltInParameter(string value)
    {
        // This would parse the enum value using Revit API
        return new { Name = value, __type__ = "BuiltInParameter" };
    }

    private static double[][] ConvertTransformToMatrix(object transform)
    {
        try
        {
            // Extract transform properties and convert to 4x4 matrix
            var type = transform.GetType();
            var basis = type.GetProperty("BasisX")?.GetValue(transform);
            // This is a simplified placeholder - actual implementation would extract full matrix
            return new[]
            {
                new double[] { 1, 0, 0, 0 },
                new double[] { 0, 1, 0, 0 },
                new double[] { 0, 0, 1, 0 },
                new double[] { 0, 0, 0, 1 }
            };
        }
        catch
        {
            return Array.Empty<double[]>();
        }
    }

    private static object CreateRevitTransform(double[][] matrix)
    {
        return new { Matrix = matrix, __type__ = "Transform" };
    }

    private static object CreateRevitColor(int red, int green, int blue)
    {
        return new { Red = red, Green = green, Blue = blue, __type__ = "Color" };
    }

    /// <summary>
    /// Clears the object cache to prevent memory leaks
    /// </summary>
    public void ClearCache()
    {
        lock (_cacheLock)
        {
            _objectCache.Clear();
        }
        _logger.LogInformation("Cleared type converter object cache");
    }

    /// <summary>
    /// Gets cache statistics
    /// </summary>
    public Dictionary<string, object> GetCacheStats()
    {
        lock (_cacheLock)
        {
            return new Dictionary<string, object>
            {
                ["CachedObjectCount"] = _objectCache.Count,
                ["PropertyCacheSize"] = _typePropertyCache.Count,
                ["MethodCacheSize"] = _typeMethodCache.Count,
                ["TypeMappingCount"] = _pythonToRevitTypeMap.Count + _revitToPythonTypeMap.Count
            };
        }
    }
}
