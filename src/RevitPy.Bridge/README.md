# RevitPy Bridge

The RevitPy Bridge is the core component that provides seamless bidirectional communication between Python code and the Revit API. It combines high-performance type conversion, transaction management, and comprehensive API access through a unified interface.

## 🚀 Features

- **Python.NET Integration**: Seamless execution of Python code within Revit's .NET environment
- **High-Performance Type Conversion**: Automatic conversion between Python objects and Revit API types
- **Transaction Management**: Safe, nested transaction support with automatic rollback
- **Element Operations**: High-performance element querying, creation, and modification
- **Geometry Processing**: Advanced geometry operations with caching and optimization
- **Parameter Management**: Comprehensive parameter access with type safety
- **Memory Management**: Intelligent caching and automatic cleanup to prevent memory leaks
- **Performance Monitoring**: Real-time statistics and performance tracking
- **Health Checks**: Comprehensive health monitoring for production environments

## 📦 Installation

The RevitPy Bridge is automatically included when you install the RevitPy package. For manual installation:

```bash
# Install the main package
pip install revitpy

# Or install directly from source
git clone https://github.com/revitpy/revitpy.git
cd revitpy
pip install -e .
```

## 🏁 Quick Start

### Basic Setup

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using RevitPy.Bridge;

// Add RevitPy Bridge to your service collection
var host = Host.CreateDefaultBuilder()
    .ConfigureServices(services =>
    {
        // For production environments
        services.AddRevitPyBridgeHighPerformance();

        // Or for development
        // services.AddRevitPyBridgeDevelopment();
    })
    .Build();

// Get the bridge instance
var bridge = host.Services.GetRequiredService<IRevitBridge>();
```

### Python Code Execution

```csharp
// Execute Python code with Revit API access
var result = await bridge.ExecutePythonCodeAsync(@"
import clr
clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import *

# Access the active document
doc = revit_context.ActiveDocument

# Query all walls
walls = FilteredElementCollector(doc).OfClass(Wall).ToElements()
wall_count = len(walls)

# Return result
wall_count
");

Console.WriteLine($"Found {result} walls in the document");
```

### Function Calls

```csharp
// Import a Python module
var mathModule = await bridge.ImportPythonModuleAsync("math");

// Call a function with automatic type conversion
var sqrt16 = await bridge.CallPythonFunctionAsync<double>(
    "math", "sqrt", new object[] { 16.0 });

Console.WriteLine($"sqrt(16) = {sqrt16}"); // Output: sqrt(16) = 4
```

## 📋 Core Components

### 1. Type Converter

Handles seamless conversion between Python and Revit API types:

```csharp
var converter = serviceProvider.GetService<IRevitTypeConverter>();

// Convert Revit XYZ to Python
var revitPoint = new XYZ(1, 2, 3);
var pythonPoint = converter.ConvertToPython(revitPoint);

// Convert Python array to Revit XYZ
var pythonArray = new double[] { 1, 2, 3 };
var revitXYZ = converter.ConvertFromPython<XYZ>(pythonArray);
```

### 2. Element Bridge

High-performance element operations with caching:

```csharp
var elementBridge = serviceProvider.GetService<IElementBridge>();

// Get element by ID
var element = await elementBridge.GetElementByIdAsync(document, elementId);

// Batch operations
var elementIds = new[] { id1, id2, id3 };
var elements = await elementBridge.GetElementsByIdsAsync(document, elementIds);

// Create new element
var newElement = await elementBridge.CreateElementAsync(
    document, "Wall", new object[] { level, curve });
```

### 3. Geometry Bridge

Advanced geometry processing with optimization:

```csharp
var geometryBridge = serviceProvider.GetService<IGeometryBridge>();

// Create geometry
var point = await geometryBridge.CreatePointAsync(1, 2, 3);
var line = await geometryBridge.CreateLineAsync(startPoint, endPoint);

// Perform calculations
var distance = await geometryBridge.CalculateDistanceAsync(point1, point2);
var area = await geometryBridge.CalculateAreaAsync(surface);

// Boolean operations
var union = await geometryBridge.BooleanOperationAsync(
    solid1, solid2, BooleanOperationType.Union);
```

### 4. Parameter Bridge

Type-safe parameter management:

```csharp
var paramBridge = serviceProvider.GetService<IParameterBridge>();

// Get parameter value
var height = await paramBridge.GetParameterValueAsync(wall, "Height");

// Set parameter value
var success = await paramBridge.SetParameterValueAsync(wall, "Height", 3000.0);

// Batch parameter operations
var parameters = new Dictionary<string, object>
{
    ["Height"] = 3000.0,
    ["Width"] = 200.0,
    ["Comments"] = "Updated wall"
};
var results = await paramBridge.SetParameterValuesAsync(wall, parameters);
```

### 5. Transaction Manager

Safe transaction handling with nesting support:

```csharp
var transactionManager = serviceProvider.GetService<ITransactionManager>();

// Simple transaction
using var transaction = await transactionManager.BeginTransactionAsync("Create Wall");
try
{
    // Perform Revit API operations
    var wall = Wall.Create(document, curve, levelId, false);

    await transaction.CommitAsync();
}
catch (Exception)
{
    await transaction.RollbackAsync();
    throw;
}

// Execute with automatic transaction management
var result = await transactionManager.ExecuteInTransactionAsync(
    "Batch Update",
    async () =>
    {
        // All operations here are automatically transacted
        foreach (var element in elements)
        {
            // Modify elements safely
        }
        return elements.Count;
    });
```

## 🔧 Configuration

### High-Performance Configuration

For production environments with high throughput requirements:

```csharp
services.AddRevitPyBridge(config =>
{
    config.EnableCaching = true;
    config.CacheSettings = new CacheSettings
    {
        MaxObjectCacheSize = 50000,     // Large cache for better performance
        MaxModuleCacheSize = 500,       // Cache many Python modules
        CacheTTL = TimeSpan.FromHours(1) // Long cache lifetime
    };
    config.EnablePerformanceMonitoring = true;
    config.EnableDebugLogging = false;  // Reduce logging overhead
    config.MaxConcurrentPythonOperations = Environment.ProcessorCount * 2;
    config.EnableMemoryOptimization = true;
});
```

### Development Configuration

For development environments with debugging capabilities:

```csharp
services.AddRevitPyBridge(config =>
{
    config.EnableCaching = true;
    config.CacheSettings = new CacheSettings
    {
        MaxObjectCacheSize = 1000,      // Smaller cache for debugging
        MaxModuleCacheSize = 50,
        CacheTTL = TimeSpan.FromMinutes(5) // Short cache for rapid iteration
    };
    config.EnablePerformanceMonitoring = true;
    config.EnableDebugLogging = true;   // Detailed logging
    config.MaxConcurrentPythonOperations = Environment.ProcessorCount;
    config.EnableMemoryOptimization = false; // Disable for debugging
});
```

## 📊 Performance Monitoring

### Getting Statistics

```csharp
var stats = bridge.GetStats();

Console.WriteLine($"Total Operations: {stats.TotalOperations}");
Console.WriteLine($"Success Rate: {stats.SuccessRatio:P2}");
Console.WriteLine($"Average Operation Time: {stats.AverageOperationTime.TotalMilliseconds}ms");
Console.WriteLine($"Memory Usage: {stats.MemoryUsageMB}MB");
Console.WriteLine($"Cache Size: {stats.CacheSize} objects");

// Component-specific statistics
Console.WriteLine($"Element Operations: {stats.ElementOperations}");
Console.WriteLine($"Geometry Operations: {stats.GeometryOperations}");
Console.WriteLine($"Parameter Operations: {stats.ParameterOperations}");
Console.WriteLine($"Type Conversions: {stats.TypeConversions}");
```

### Performance Benchmarks

The bridge meets these performance targets:

- **Type Conversion**: < 1ms for simple types, < 10ms for complex objects
- **Element Queries**: < 100ms for collections up to 10,000 elements
- **Geometry Operations**: < 50ms for standard calculations
- **Parameter Access**: < 5ms for individual parameters
- **Python Execution**: < 50ms for simple scripts
- **Memory Usage**: < 500MB for typical workloads

## 🏥 Health Monitoring

### Health Checks

```csharp
var healthCheck = serviceProvider.GetService<IRevitBridgeHealthCheck>();

// Quick health check
var isHealthy = await healthCheck.IsHealthyAsync();

// Comprehensive health check
var healthStatus = await healthCheck.CheckHealthAsync();

if (!healthStatus.IsHealthy)
{
    foreach (var issue in healthStatus.Issues)
    {
        Console.WriteLine($"Health Issue: {issue}");
    }

    foreach (var action in healthStatus.RecommendedActions)
    {
        Console.WriteLine($"Recommended: {action}");
    }
}
```

### Memory Management

```csharp
// Manual memory optimization
await bridge.OptimizeMemoryAsync();

// Check memory statistics
var cacheStats = converter.GetCacheStats();
Console.WriteLine($"Cached Objects: {cacheStats["CachedObjectCount"]}");
Console.WriteLine($"Memory Freed: {memoryFreed}MB");
```

## 🔒 Error Handling

The bridge provides comprehensive error handling:

```csharp
try
{
    var result = await bridge.ExecutePythonCodeAsync("invalid python code");
}
catch (RevitApiException ex)
{
    // Revit API specific errors
    Console.WriteLine($"Revit API Error: {ex.Message}");
    Console.WriteLine($"Inner Exception: {ex.InnerException?.Message}");
}
catch (PythonException ex)
{
    // Python execution errors
    Console.WriteLine($"Python Error: {ex.Message}");
}
catch (Exception ex)
{
    // General errors
    Console.WriteLine($"Error: {ex.Message}");
}
```

## 🧪 Testing

### Unit Tests

```csharp
[Fact]
public async Task ExecutePythonCode_WithSimpleExpression_ShouldReturnResult()
{
    // Arrange
    var bridge = CreateTestBridge();
    var code = "2 + 2";

    // Act
    var result = await bridge.ExecutePythonCodeAsync(code);

    // Assert
    Assert.Equal(4, result);
}
```

### Performance Tests

```csharp
[Fact]
public async Task TypeConversion_Performance_ShouldMeetTargets()
{
    // Arrange
    var converter = CreateTestConverter();
    var testObject = new XYZ(1, 2, 3);
    const int iterations = 10000;

    // Act
    var stopwatch = Stopwatch.StartNew();
    for (int i = 0; i < iterations; i++)
    {
        var result = converter.ConvertToPython(testObject);
    }
    stopwatch.Stop();

    // Assert
    var averageTime = stopwatch.ElapsedMilliseconds / (double)iterations;
    Assert.True(averageTime < 1.0, $"Average time {averageTime}ms exceeds 1ms target");
}
```

### Integration Tests

```csharp
[Fact]
public async Task FullWorkflow_CreateAndModifyWall_ShouldSucceed()
{
    // Arrange
    var bridge = CreateIntegrationTestBridge();
    var document = GetTestDocument();

    // Act
    var result = await bridge.ExecutePythonCodeAsync(@"
        # Create a wall
        curve = Line.CreateBound(XYZ(0, 0, 0), XYZ(10, 0, 0))
        wall = Wall.Create(doc, curve, level_id, False)

        # Set parameters
        height_param = wall.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM)
        height_param.Set(3000.0)  # 3 meters

        # Return wall ID
        wall.Id.IntegerValue
    ", new Dictionary<string, object?>
    {
        ["doc"] = document,
        ["level_id"] = GetFirstLevelId(document)
    });

    // Assert
    Assert.True((long)result > 0);

    // Verify wall was created
    var wallId = new ElementId((long)result);
    var createdWall = document.GetElement(wallId);
    Assert.NotNull(createdWall);
    Assert.IsType<Wall>(createdWall);
}
```

## 🚀 Advanced Usage

### Custom Type Converters

Register custom converters for specialized types:

```csharp
var converter = serviceProvider.GetService<IRevitTypeConverter>();

// Register a custom converter
converter.RegisterBidirectionalConverter<MyPythonType, MyRevitType>(
    // Revit to Python
    revit => new MyPythonType(revit.Property1, revit.Property2),
    // Python to Revit
    python => new MyRevitType { Property1 = python.Prop1, Property2 = python.Prop2 }
);
```

### Extension Methods

Create extension methods for common operations:

```csharp
public static class RevitBridgeExtensions
{
    public static async Task<IEnumerable<Wall>> GetAllWallsAsync(this IRevitBridge bridge, Document document)
    {
        var result = await bridge.ExecutePythonCodeAsync(@"
            walls = FilteredElementCollector(doc).OfClass(Wall).ToElements()
            [wall.Id.IntegerValue for wall in walls]
        ", new Dictionary<string, object?> { ["doc"] = document });

        var elementBridge = GetElementBridge(bridge);
        var wallIds = (IEnumerable<long>)result;
        var walls = new List<Wall>();

        foreach (var id in wallIds)
        {
            var wall = await elementBridge.GetElementByIdAsync(document, new ElementId(id));
            if (wall is Wall w)
                walls.Add(w);
        }

        return walls;
    }
}
```

### Batch Operations

Optimize performance with batch operations:

```csharp
// Batch element creation
var elementData = new[]
{
    new { Type = "Wall", Parameters = new { Height = 3000.0, Width = 200.0 } },
    new { Type = "Wall", Parameters = new { Height = 2500.0, Width = 150.0 } },
    // ... more elements
};

var results = await transactionManager.ExecuteInTransactionAsync(
    "Create Multiple Elements",
    async () =>
    {
        var createdElements = new List<Element>();

        foreach (var data in elementData)
        {
            var element = await elementBridge.CreateElementAsync(
                document, data.Type, ConvertParameters(data.Parameters));
            createdElements.Add(element);
        }

        return createdElements;
    });
```

## 🛠️ Troubleshooting

### Common Issues

1. **Python.NET Not Initialized**
   ```
   Error: Python engine is not initialized
   Solution: Ensure Python.NET is properly configured before using the bridge
   ```

2. **Memory Leaks**
   ```
   Solution: Enable memory optimization and call OptimizeMemoryAsync() periodically
   ```

3. **Transaction Conflicts**
   ```
   Solution: Use the transaction manager for all Revit API modifications
   ```

4. **Type Conversion Failures**
   ```
   Solution: Register custom converters for complex types or use preserveType=true
   ```

### Performance Optimization

1. **Enable Caching**: Always enable caching for production environments
2. **Batch Operations**: Group multiple operations into single transactions
3. **Memory Management**: Monitor memory usage and call optimization regularly
4. **Connection Pooling**: Use the Python interpreter pool for concurrent operations

### Debugging

Enable debug logging for detailed information:

```csharp
services.AddRevitPyBridge(config =>
{
    config.EnableDebugLogging = true;
});
```

Check logs for:
- Type conversion details
- Transaction lifecycle events
- Performance metrics
- Error stack traces

## 📈 Roadmap

- **Enhanced Python Integration**: Support for Python virtual environments
- **Advanced Caching**: Intelligent cache invalidation based on document changes
- **Async Improvements**: Full async/await support throughout the API
- **Performance Analytics**: Machine learning-based performance optimization
- **Cloud Integration**: Support for cloud-based Python execution

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](../../../CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../../../LICENSE) file for details.
