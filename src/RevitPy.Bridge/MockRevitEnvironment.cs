using Microsoft.Extensions.Logging;

namespace RevitPy.Bridge.Testing;

/// <summary>
/// Mock Revit environment for comprehensive testing without requiring actual Revit installation
/// </summary>
public class MockRevitEnvironment : IDisposable
{
    private readonly ILogger<MockRevitEnvironment> _logger;
    private readonly Dictionary<string, object> _mockApplicationProperties;
    private readonly Dictionary<string, object> _mockDocuments;
    private readonly Dictionary<string, object> _mockElements;
    private readonly Dictionary<string, Dictionary<string, object>> _mockParameters;
    private readonly Dictionary<string, object> _mockGeometries;
    private bool _disposed;

    public MockRevitEnvironment(ILogger<MockRevitEnvironment> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));

        _mockApplicationProperties = new Dictionary<string, object>();
        _mockDocuments = new Dictionary<string, object>();
        _mockElements = new Dictionary<string, object>();
        _mockParameters = new Dictionary<string, Dictionary<string, object>>();
        _mockGeometries = new Dictionary<string, object>();

        InitializeMockEnvironment();
    }

    /// <summary>
    /// Gets a mock Revit application instance
    /// </summary>
    public object CreateMockApplication()
    {
        return new MockRevitApplication(this);
    }

    /// <summary>
    /// Gets a mock Revit document
    /// </summary>
    public object CreateMockDocument(string documentId = "TestDocument")
    {
        var document = new MockRevitDocument(this, documentId);
        _mockDocuments[documentId] = document;
        return document;
    }

    /// <summary>
    /// Gets a mock Revit element
    /// </summary>
    public object CreateMockElement(string elementId, string elementType = "Wall")
    {
        var element = new MockRevitElement(this, elementId, elementType);
        _mockElements[elementId] = element;
        return element;
    }

    /// <summary>
    /// Gets a mock geometry object
    /// </summary>
    public object CreateMockGeometry(string geometryType, Dictionary<string, object>? properties = null)
    {
        return geometryType switch
        {
            "Point" => new MockRevitPoint(properties?.GetValueOrDefault("X", 0.0),
                                        properties?.GetValueOrDefault("Y", 0.0),
                                        properties?.GetValueOrDefault("Z", 0.0)),
            "Line" => new MockRevitLine(properties?.GetValueOrDefault("StartPoint"),
                                      properties?.GetValueOrDefault("EndPoint")),
            "Plane" => new MockRevitPlane(properties?.GetValueOrDefault("Origin"),
                                        properties?.GetValueOrDefault("Normal")),
            _ => new MockGeometry(geometryType, properties ?? new Dictionary<string, object>())
        };
    }

    /// <summary>
    /// Adds a parameter to a mock element
    /// </summary>
    public void AddElementParameter(string elementId, string parameterName, object value, string parameterType = "Text")
    {
        if (!_mockParameters.ContainsKey(elementId))
        {
            _mockParameters[elementId] = new Dictionary<string, object>();
        }

        _mockParameters[elementId][parameterName] = new MockRevitParameter(parameterName, value, parameterType);
    }

    /// <summary>
    /// Gets parameters for a mock element
    /// </summary>
    public Dictionary<string, object> GetElementParameters(string elementId)
    {
        return _mockParameters.GetValueOrDefault(elementId, new Dictionary<string, object>());
    }

    /// <summary>
    /// Simulates a delay for testing performance
    /// </summary>
    public async Task SimulateDelay(int milliseconds = 10)
    {
        await Task.Delay(milliseconds);
    }

    /// <summary>
    /// Simulates an error for testing error handling
    /// </summary>
    public void SimulateError(string errorType = "TestError")
    {
        throw new MockRevitException(errorType, $"Simulated {errorType} for testing");
    }

    private void InitializeMockEnvironment()
    {
        // Initialize mock application properties
        _mockApplicationProperties["VersionName"] = "Autodesk Revit 2024";
        _mockApplicationProperties["VersionNumber"] = "2024";
        _mockApplicationProperties["VersionBuild"] = "20240101_1200(x64)";
        _mockApplicationProperties["Language"] = "English";

        // Create default mock elements
        var defaultElement = CreateMockElement("DefaultWall", "Wall");
        AddElementParameter("DefaultWall", "Name", "Test Wall", "Text");
        AddElementParameter("DefaultWall", "Height", 3000.0, "Length");
        AddElementParameter("DefaultWall", "Width", 200.0, "Length");

        _logger.LogInformation("Mock Revit environment initialized");
    }

    public void Dispose()
    {
        if (!_disposed)
        {
            _mockApplicationProperties.Clear();
            _mockDocuments.Clear();
            _mockElements.Clear();
            _mockParameters.Clear();
            _mockGeometries.Clear();

            _disposed = true;
            _logger.LogInformation("Mock Revit environment disposed");
        }
    }
}

/// <summary>
/// Mock Revit application
/// </summary>
public class MockRevitApplication
{
    private readonly MockRevitEnvironment _environment;
    private readonly Dictionary<string, object> _properties;

    public MockRevitApplication(MockRevitEnvironment environment)
    {
        _environment = environment ?? throw new ArgumentNullException(nameof(environment));
        _properties = new Dictionary<string, object>
        {
            ["VersionName"] = "Autodesk Revit 2024",
            ["VersionNumber"] = "2024",
            ["VersionBuild"] = "20240101_1200(x64)",
            ["Language"] = "English"
        };
    }

    public string VersionName => (string)_properties["VersionName"];
    public string VersionNumber => (string)_properties["VersionNumber"];
    public string VersionBuild => (string)_properties["VersionBuild"];
    public string Language => (string)_properties["Language"];

    public object? ActiveUIDocument => _environment.CreateMockDocument("ActiveDocument");

    public object GetProperty(string propertyName)
    {
        return _properties.GetValueOrDefault(propertyName, $"Mock_{propertyName}");
    }
}

/// <summary>
/// Mock Revit document
/// </summary>
public class MockRevitDocument
{
    private readonly MockRevitEnvironment _environment;
    private readonly string _documentId;
    private readonly Dictionary<string, object> _elements;

    public MockRevitDocument(MockRevitEnvironment environment, string documentId)
    {
        _environment = environment ?? throw new ArgumentNullException(nameof(environment));
        _documentId = documentId ?? throw new ArgumentNullException(nameof(documentId));
        _elements = new Dictionary<string, object>();
    }

    public string Id => _documentId;
    public string Title => $"Mock Document {_documentId}";
    public bool IsModified => false;

    public object? GetElement(string elementId)
    {
        return _elements.GetValueOrDefault(elementId);
    }

    public IEnumerable<object> GetElements()
    {
        return _elements.Values;
    }

    public object CreateElement(string elementType, Dictionary<string, object>? parameters = null)
    {
        var elementId = Guid.NewGuid().ToString();
        var element = _environment.CreateMockElement(elementId, elementType);
        _elements[elementId] = element;
        return element;
    }

    public bool DeleteElement(string elementId)
    {
        return _elements.Remove(elementId);
    }
}

/// <summary>
/// Mock Revit element
/// </summary>
public class MockRevitElement
{
    private readonly MockRevitEnvironment _environment;
    private readonly string _elementId;
    private readonly string _elementType;
    private readonly Dictionary<string, object> _properties;

    public MockRevitElement(MockRevitEnvironment environment, string elementId, string elementType)
    {
        _environment = environment ?? throw new ArgumentNullException(nameof(environment));
        _elementId = elementId ?? throw new ArgumentNullException(nameof(elementId));
        _elementType = elementType ?? throw new ArgumentNullException(nameof(elementType));
        _properties = new Dictionary<string, object>
        {
            ["Id"] = elementId,
            ["Type"] = elementType,
            ["Name"] = $"Mock {elementType} {elementId}"
        };
    }

    public string Id => _elementId;
    public string Type => _elementType;
    public string Name => (string)_properties["Name"];

    public object? GetParameter(string parameterName)
    {
        var parameters = _environment.GetElementParameters(_elementId);
        return parameters.GetValueOrDefault(parameterName);
    }

    public IEnumerable<object> GetParameters()
    {
        var parameters = _environment.GetElementParameters(_elementId);
        return parameters.Values;
    }

    public object GetProperty(string propertyName)
    {
        return _properties.GetValueOrDefault(propertyName, $"Mock_{propertyName}");
    }

    public void SetProperty(string propertyName, object value)
    {
        _properties[propertyName] = value;
    }

    public IEnumerable<object> GetGeometry()
    {
        // Return mock geometries based on element type
        return _elementType switch
        {
            "Wall" => new[]
            {
                _environment.CreateMockGeometry("Face", new Dictionary<string, object> { ["Area"] = 100.0 }),
                _environment.CreateMockGeometry("Edge", new Dictionary<string, object> { ["Length"] = 10.0 })
            },
            "Point" => new[]
            {
                _environment.CreateMockGeometry("Point", new Dictionary<string, object>
                {
                    ["X"] = 0.0, ["Y"] = 0.0, ["Z"] = 0.0
                })
            },
            _ => new[]
            {
                _environment.CreateMockGeometry("Generic", new Dictionary<string, object>())
            }
        };
    }
}

/// <summary>
/// Mock Revit parameter
/// </summary>
public class MockRevitParameter
{
    public MockRevitParameter(string name, object value, string parameterType)
    {
        Name = name ?? throw new ArgumentNullException(nameof(name));
        Value = value;
        ParameterType = parameterType ?? throw new ArgumentNullException(nameof(parameterType));
        StorageType = DetermineStorageType(value);
        IsReadOnly = false;
    }

    public string Name { get; }
    public object Value { get; set; }
    public string ParameterType { get; }
    public string StorageType { get; }
    public bool IsReadOnly { get; set; }
    public bool HasValue => Value != null;

    public object? AsString() => Value?.ToString();
    public double AsDouble() => Convert.ToDouble(Value ?? 0.0);
    public int AsInteger() => Convert.ToInt32(Value ?? 0);
    public bool AsBoolean() => Convert.ToBoolean(Value ?? false);

    public bool Set(object newValue)
    {
        if (IsReadOnly)
            return false;

        Value = newValue;
        return true;
    }

    private string DetermineStorageType(object value)
    {
        return value switch
        {
            string => "String",
            int => "Integer",
            double => "Double",
            float => "Double",
            bool => "Integer",
            _ => "String"
        };
    }
}

/// <summary>
/// Mock geometry classes
/// </summary>
public class MockRevitPoint
{
    public MockRevitPoint(object? x, object? y, object? z)
    {
        X = Convert.ToDouble(x ?? 0.0);
        Y = Convert.ToDouble(y ?? 0.0);
        Z = Convert.ToDouble(z ?? 0.0);
    }

    public double X { get; set; }
    public double Y { get; set; }
    public double Z { get; set; }

    public double DistanceTo(MockRevitPoint other)
    {
        var dx = X - other.X;
        var dy = Y - other.Y;
        var dz = Z - other.Z;
        return Math.Sqrt(dx * dx + dy * dy + dz * dz);
    }

    public override string ToString()
    {
        return $"({X:F3}, {Y:F3}, {Z:F3})";
    }
}

public class MockRevitLine
{
    public MockRevitLine(object? startPoint, object? endPoint)
    {
        StartPoint = startPoint as MockRevitPoint ?? new MockRevitPoint(0, 0, 0);
        EndPoint = endPoint as MockRevitPoint ?? new MockRevitPoint(1, 0, 0);
    }

    public MockRevitPoint StartPoint { get; set; }
    public MockRevitPoint EndPoint { get; set; }

    public double Length => StartPoint.DistanceTo(EndPoint);

    public MockRevitPoint GetEndPoint(int index)
    {
        return index == 0 ? StartPoint : EndPoint;
    }

    public override string ToString()
    {
        return $"Line[{StartPoint} -> {EndPoint}]";
    }
}

public class MockRevitPlane
{
    public MockRevitPlane(object? origin, object? normal)
    {
        Origin = origin as MockRevitPoint ?? new MockRevitPoint(0, 0, 0);
        Normal = normal as MockRevitPoint ?? new MockRevitPoint(0, 0, 1);
    }

    public MockRevitPoint Origin { get; set; }
    public MockRevitPoint Normal { get; set; }

    public override string ToString()
    {
        return $"Plane[Origin: {Origin}, Normal: {Normal}]";
    }
}

public class MockGeometry
{
    public MockGeometry(string geometryType, Dictionary<string, object> properties)
    {
        GeometryType = geometryType ?? throw new ArgumentNullException(nameof(geometryType));
        Properties = properties ?? throw new ArgumentNullException(nameof(properties));
    }

    public string GeometryType { get; }
    public Dictionary<string, object> Properties { get; }

    public object? GetProperty(string propertyName)
    {
        return Properties.GetValueOrDefault(propertyName);
    }

    public void SetProperty(string propertyName, object value)
    {
        Properties[propertyName] = value;
    }

    public override string ToString()
    {
        return $"MockGeometry[{GeometryType}]";
    }
}

/// <summary>
/// Mock Revit exception for testing error handling
/// </summary>
public class MockRevitException : Exception
{
    public string ErrorType { get; }
    public string RevitErrorMessage { get; }

    public MockRevitException(string errorType, string message) : base(message)
    {
        ErrorType = errorType ?? "Unknown";
        RevitErrorMessage = message ?? "Mock Revit error";
    }

    public MockRevitException(string errorType, string message, Exception innerException) : base(message, innerException)
    {
        ErrorType = errorType ?? "Unknown";
        RevitErrorMessage = message ?? "Mock Revit error";
    }
}

/// <summary>
/// Mock transaction for testing transaction management
/// </summary>
public class MockRevitTransaction : IDisposable
{
    private readonly string _name;
    private bool _committed;
    private bool _rolledBack;
    private bool _disposed;

    public MockRevitTransaction(string name)
    {
        _name = name ?? throw new ArgumentNullException(nameof(name));
        Status = MockTransactionStatus.Started;
    }

    public string Name => _name;
    public MockTransactionStatus Status { get; private set; }
    public bool HasEnded => _committed || _rolledBack;

    public void Commit()
    {
        if (HasEnded)
            throw new InvalidOperationException("Transaction has already ended");

        _committed = true;
        Status = MockTransactionStatus.Committed;
    }

    public void RollBack()
    {
        if (HasEnded)
            throw new InvalidOperationException("Transaction has already ended");

        _rolledBack = true;
        Status = MockTransactionStatus.RolledBack;
    }

    public void Dispose()
    {
        if (!_disposed)
        {
            if (!HasEnded)
            {
                RollBack();
            }
            _disposed = true;
        }
    }
}

public enum MockTransactionStatus
{
    Started,
    Committed,
    RolledBack
}

/// <summary>
/// Factory for creating mock Revit objects consistently
/// </summary>
public static class MockRevitFactory
{
    public static MockRevitEnvironment CreateEnvironment(ILogger<MockRevitEnvironment>? logger = null)
    {
        logger ??= CreateMockLogger<MockRevitEnvironment>();
        return new MockRevitEnvironment(logger);
    }

    public static ILogger<T> CreateMockLogger<T>()
    {
        return new MockLogger<T>();
    }

    public static MockRevitPoint CreatePoint(double x = 0, double y = 0, double z = 0)
    {
        return new MockRevitPoint(x, y, z);
    }

    public static MockRevitLine CreateLine(MockRevitPoint? start = null, MockRevitPoint? end = null)
    {
        start ??= CreatePoint(0, 0, 0);
        end ??= CreatePoint(1, 0, 0);
        return new MockRevitLine(start, end);
    }

    public static MockRevitPlane CreatePlane(MockRevitPoint? origin = null, MockRevitPoint? normal = null)
    {
        origin ??= CreatePoint(0, 0, 0);
        normal ??= CreatePoint(0, 0, 1);
        return new MockRevitPlane(origin, normal);
    }
}

/// <summary>
/// Simple mock logger for testing
/// </summary>
public class MockLogger<T> : ILogger<T>
{
    private readonly List<string> _logMessages = new();

    public IDisposable BeginScope<TState>(TState state) => new MockDisposable();

    public bool IsEnabled(LogLevel logLevel) => true;

    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
    {
        var message = formatter(state, exception);
        _logMessages.Add($"[{logLevel}] {message}");
    }

    public IReadOnlyList<string> LogMessages => _logMessages.AsReadOnly();

    private class MockDisposable : IDisposable
    {
        public void Dispose() { }
    }
}
