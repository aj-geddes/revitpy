namespace RevitPy.Bridge;

/// <summary>
/// Handles type conversion between Python and Revit API objects
/// </summary>
public interface IRevitTypeConverter
{
    /// <summary>
    /// Converts a Python object to a Revit API object
    /// </summary>
    /// <typeparam name="T">Target Revit type</typeparam>
    /// <param name="pythonObject">Python object to convert</param>
    /// <param name="targetType">Target type information</param>
    /// <returns>Converted Revit object</returns>
    T? ConvertFromPython<T>(object? pythonObject, Type? targetType = null);

    /// <summary>
    /// Converts a Revit API object to a Python-compatible object
    /// </summary>
    /// <param name="revitObject">Revit object to convert</param>
    /// <param name="preserveType">Whether to preserve the original type information</param>
    /// <returns>Python-compatible object</returns>
    object? ConvertToPython(object? revitObject, bool preserveType = false);

    /// <summary>
    /// Converts an array of Python objects to Revit API objects
    /// </summary>
    /// <typeparam name="T">Target element type</typeparam>
    /// <param name="pythonArray">Python array</param>
    /// <param name="elementType">Element type information</param>
    /// <returns>Converted array</returns>
    T[]? ConvertArrayFromPython<T>(object? pythonArray, Type? elementType = null);

    /// <summary>
    /// Converts an array of Revit objects to Python-compatible array
    /// </summary>
    /// <param name="revitArray">Revit array</param>
    /// <param name="preserveType">Whether to preserve type information</param>
    /// <returns>Python-compatible array</returns>
    object? ConvertArrayToPython(object? revitArray, bool preserveType = false);

    /// <summary>
    /// Checks if a type can be converted from Python to Revit
    /// </summary>
    /// <param name="pythonType">Python type</param>
    /// <param name="targetType">Target Revit type</param>
    /// <returns>True if conversion is possible</returns>
    bool CanConvertFromPython(Type pythonType, Type targetType);

    /// <summary>
    /// Checks if a type can be converted from Revit to Python
    /// </summary>
    /// <param name="revitType">Revit type</param>
    /// <returns>True if conversion is possible</returns>
    bool CanConvertToPython(Type revitType);

    /// <summary>
    /// Gets the Revit type equivalent of a Python type
    /// </summary>
    /// <param name="pythonType">Python type</param>
    /// <returns>Equivalent Revit type or null</returns>
    Type? GetRevitType(Type pythonType);

    /// <summary>
    /// Gets the Python type equivalent of a Revit type
    /// </summary>
    /// <param name="revitType">Revit type</param>
    /// <returns>Equivalent Python type or null</returns>
    Type? GetPythonType(Type revitType);

    /// <summary>
    /// Registers a custom type converter
    /// </summary>
    /// <typeparam name="TFrom">Source type</typeparam>
    /// <typeparam name="TTo">Target type</typeparam>
    /// <param name="converter">Converter function</param>
    void RegisterConverter<TFrom, TTo>(Func<TFrom, TTo> converter);

    /// <summary>
    /// Registers a bidirectional type converter
    /// </summary>
    /// <typeparam name="TPython">Python type</typeparam>
    /// <typeparam name="TRevit">Revit type</typeparam>
    /// <param name="toPython">Python converter</param>
    /// <param name="toRevit">Revit converter</param>
    void RegisterBidirectionalConverter<TPython, TRevit>(
        Func<TRevit, TPython> toPython,
        Func<TPython, TRevit> toRevit);

    /// <summary>
    /// Gets conversion statistics
    /// </summary>
    /// <returns>Conversion statistics</returns>
    TypeConversionStats GetStats();
}

/// <summary>
/// Statistics for type conversion operations
/// </summary>
public class TypeConversionStats
{
    /// <summary>
    /// Gets or sets the total number of conversions performed
    /// </summary>
    public long TotalConversions { get; set; }

    /// <summary>
    /// Gets or sets the number of successful conversions
    /// </summary>
    public long SuccessfulConversions { get; set; }

    /// <summary>
    /// Gets or sets the number of failed conversions
    /// </summary>
    public long FailedConversions { get; set; }

    /// <summary>
    /// Gets or sets the number of Python to Revit conversions
    /// </summary>
    public long PythonToRevitConversions { get; set; }

    /// <summary>
    /// Gets or sets the number of Revit to Python conversions
    /// </summary>
    public long RevitToPythonConversions { get; set; }

    /// <summary>
    /// Gets or sets the conversion statistics by type
    /// </summary>
    public Dictionary<string, long> ConversionsByType { get; set; } = new();

    /// <summary>
    /// Gets or sets the average conversion time
    /// </summary>
    public TimeSpan AverageConversionTime { get; set; }

    /// <summary>
    /// Gets or sets the number of custom converters registered
    /// </summary>
    public int CustomConvertersCount { get; set; }

    /// <summary>
    /// Gets or sets the last reset time
    /// </summary>
    public DateTime LastReset { get; set; }
}

/// <summary>
/// Attribute to mark classes as convertible to/from Python
/// </summary>
[AttributeUsage(AttributeTargets.Class | AttributeTargets.Struct)]
public class PythonConvertibleAttribute : Attribute
{
    /// <summary>
    /// Gets or sets the Python type name
    /// </summary>
    public string? PythonTypeName { get; set; }

    /// <summary>
    /// Gets or sets whether the type should be wrapped
    /// </summary>
    public bool ShouldWrap { get; set; } = true;

    /// <summary>
    /// Gets or sets whether to preserve the original type information
    /// </summary>
    public bool PreserveType { get; set; } = true;
}

/// <summary>
/// Attribute to mark properties as convertible to/from Python
/// </summary>
[AttributeUsage(AttributeTargets.Property)]
public class PythonPropertyAttribute : Attribute
{
    /// <summary>
    /// Gets or sets the Python property name
    /// </summary>
    public string? PythonName { get; set; }

    /// <summary>
    /// Gets or sets whether the property is read-only
    /// </summary>
    public bool ReadOnly { get; set; }

    /// <summary>
    /// Gets or sets whether to ignore this property
    /// </summary>
    public bool Ignore { get; set; }
}

/// <summary>
/// Attribute to mark methods as callable from Python
/// </summary>
[AttributeUsage(AttributeTargets.Method)]
public class PythonMethodAttribute : Attribute
{
    /// <summary>
    /// Gets or sets the Python method name
    /// </summary>
    public string? PythonName { get; set; }

    /// <summary>
    /// Gets or sets whether the method is async
    /// </summary>
    public bool IsAsync { get; set; }

    /// <summary>
    /// Gets or sets whether to ignore this method
    /// </summary>
    public bool Ignore { get; set; }
}