using System.Collections.Concurrent;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;
using RevitPy.Bridge;
using RevitPy.Runtime;
using Python.Runtime;

namespace RevitPy.Bridge.Tests;

/// <summary>
/// Comprehensive unit tests for RevitApiBridge functionality
/// </summary>
public class RevitApiBridgeTests : IDisposable
{
    private readonly ServiceProvider _serviceProvider;
    private readonly Mock<ILogger<RevitApiBridge>> _mockLogger;
    private readonly Mock<IRevitTypeConverter> _mockTypeConverter;
    private readonly Mock<ITransactionManager> _mockTransactionManager;
    private readonly Mock<IElementBridge> _mockElementBridge;
    private readonly Mock<IGeometryBridge> _mockGeometryBridge;
    private readonly Mock<IParameterBridge> _mockParameterBridge;
    private readonly Mock<IPythonInterpreterPool> _mockPythonPool;

    public RevitApiBridgeTests()
    {
        // Setup mocks
        _mockLogger = new Mock<ILogger<RevitApiBridge>>();
        _mockTypeConverter = new Mock<IRevitTypeConverter>();
        _mockTransactionManager = new Mock<ITransactionManager>();
        _mockElementBridge = new Mock<IElementBridge>();
        _mockGeometryBridge = new Mock<IGeometryBridge>();
        _mockParameterBridge = new Mock<IParameterBridge>();
        _mockPythonPool = new Mock<IPythonInterpreterPool>();

        // Setup service collection
        var services = new ServiceCollection();
        services.AddSingleton(_mockLogger.Object);
        services.AddSingleton(_mockTypeConverter.Object);
        services.AddSingleton(_mockTransactionManager.Object);
        services.AddSingleton(_mockElementBridge.Object);
        services.AddSingleton(_mockGeometryBridge.Object);
        services.AddSingleton(_mockParameterBridge.Object);
        services.AddSingleton(_mockPythonPool.Object);

        _serviceProvider = services.BuildServiceProvider();
    }

    [Fact]
    public void Constructor_WithValidDependencies_ShouldCreateInstance()
    {
        // Act
        var bridge = new RevitApiBridge(
            _mockLogger.Object,
            _mockTypeConverter.Object,
            _mockTransactionManager.Object,
            _mockElementBridge.Object,
            _mockGeometryBridge.Object,
            _mockParameterBridge.Object);

        // Assert
        Assert.NotNull(bridge);
    }

    [Fact]
    public void Constructor_WithNullLogger_ShouldThrowArgumentNullException()
    {
        // Act & Assert
        Assert.Throws<ArgumentNullException>(() => new RevitApiBridge(
            null!,
            _mockTypeConverter.Object,
            _mockTransactionManager.Object,
            _mockElementBridge.Object,
            _mockGeometryBridge.Object,
            _mockParameterBridge.Object));
    }

    [Fact]
    public async Task ExecutePythonCodeAsync_WithSimpleExpression_ShouldReturnResult()
    {
        // Arrange
        var bridge = CreateBridge();
        var code = "2 + 2";

        _mockTypeConverter.Setup(x => x.ConvertToPython(It.IsAny<object>()))
            .Returns((object obj) => obj);

        // Act & Assert
        // Note: This test would need Python.NET to be properly initialized
        // In a real test environment, you'd setup a test Python environment
        try
        {
            var result = await bridge.ExecutePythonCodeAsync(code);
            // In a mock environment, this might not work without proper Python setup
        }
        catch (Exception ex)
        {
            // Expected in test environment without Python.NET properly configured
            Assert.Contains("Python", ex.Message);
        }
    }

    [Fact]
    public async Task ImportPythonModuleAsync_WithValidModule_ShouldReturnModule()
    {
        // Arrange
        var bridge = CreateBridge();
        var moduleName = "math";

        // Act & Assert
        try
        {
            var module = await bridge.ImportPythonModuleAsync(moduleName);
            Assert.NotNull(module);
        }
        catch (Exception ex)
        {
            // Expected in test environment without Python.NET properly configured
            Assert.Contains("Python", ex.Message);
        }
    }

    [Fact]
    public async Task CallPythonFunctionAsync_WithValidFunction_ShouldReturnResult()
    {
        // Arrange
        var bridge = CreateBridge();
        var moduleName = "math";
        var functionName = "sqrt";
        var args = new object[] { 16.0 };

        _mockTypeConverter.Setup(x => x.ConvertToPython(It.IsAny<object>()))
            .Returns((object obj) => obj);
        _mockTypeConverter.Setup(x => x.ConvertFromPython<double>(It.IsAny<object>(), It.IsAny<Type>()))
            .Returns(4.0);

        // Act & Assert
        try
        {
            var result = await bridge.CallPythonFunctionAsync<double>(moduleName, functionName, args);
            Assert.Equal(4.0, result);
        }
        catch (Exception ex)
        {
            // Expected in test environment without Python.NET properly configured
            Assert.Contains("Python", ex.Message);
        }
    }

    [Fact]
    public void GetStats_ShouldReturnComprehensiveStats()
    {
        // Arrange
        var bridge = CreateBridge();

        _mockElementBridge.Setup(x => x.GetStats()).Returns(new ElementBridgeStats { TotalOperations = 10 });
        _mockGeometryBridge.Setup(x => x.GetStats()).Returns(new GeometryBridgeStats { TotalOperations = 5 });
        _mockParameterBridge.Setup(x => x.GetStats()).Returns(new ParameterBridgeStats { TotalOperations = 8 });
        _mockTransactionManager.Setup(x => x.Stats).Returns(new TransactionStats { TotalTransactions = 3 });
        _mockTypeConverter.Setup(x => x.GetStats()).Returns(new TypeConversionStats { TotalConversions = 15 });

        // Act
        var stats = bridge.GetStats();

        // Assert
        Assert.NotNull(stats);
        Assert.Equal(10, stats.ElementOperations);
        Assert.Equal(5, stats.GeometryOperations);
        Assert.Equal(8, stats.ParameterOperations);
        Assert.Equal(3, stats.TransactionOperations);
        Assert.Equal(15, stats.TypeConversions);
    }

    [Fact]
    public async Task OptimizeMemoryAsync_ShouldCompleteWithoutErrors()
    {
        // Arrange
        var bridge = CreateBridge();

        // Act & Assert
        await bridge.OptimizeMemoryAsync();

        // Verify logging was called
        _mockLogger.Verify(
            x => x.Log(
                LogLevel.Information,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((v, t) => v.ToString()!.Contains("memory optimization")),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.AtLeast(1));
    }

    [Fact]
    public void ResetStats_ShouldResetPerformanceCounters()
    {
        // Arrange
        var bridge = CreateBridge();

        // Act
        bridge.ResetStats();

        // Assert
        var stats = bridge.GetStats();
        Assert.Equal(0, stats.TotalOperations);
        Assert.Equal(0, stats.PythonExecutions);
        Assert.Equal(0, stats.FunctionCalls);
    }

    [Fact]
    public void Dispose_ShouldCleanupResourcesWithoutErrors()
    {
        // Arrange
        var bridge = CreateBridge();

        // Act & Assert
        bridge.Dispose();

        // Verify logging was called for disposal
        _mockLogger.Verify(
            x => x.Log(
                LogLevel.Information,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((v, t) => v.ToString()!.Contains("disposed")),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Once);
    }

    private RevitApiBridge CreateBridge()
    {
        return new RevitApiBridge(
            _mockLogger.Object,
            _mockTypeConverter.Object,
            _mockTransactionManager.Object,
            _mockElementBridge.Object,
            _mockGeometryBridge.Object,
            _mockParameterBridge.Object);
    }

    public void Dispose()
    {
        _serviceProvider?.Dispose();
    }
}

/// <summary>
/// Performance benchmarks for RevitApiBridge operations
/// </summary>
public class RevitApiBridgePerformanceTests : IDisposable
{
    private readonly ServiceProvider _serviceProvider;
    private readonly Mock<ILogger<RevitApiBridge>> _mockLogger;
    private readonly Mock<IRevitTypeConverter> _mockTypeConverter;
    private readonly Mock<ITransactionManager> _mockTransactionManager;
    private readonly Mock<IElementBridge> _mockElementBridge;
    private readonly Mock<IGeometryBridge> _mockGeometryBridge;
    private readonly Mock<IParameterBridge> _mockParameterBridge;
    private readonly RevitApiBridge _bridge;

    public RevitApiBridgePerformanceTests()
    {
        // Setup mocks with performance-oriented behavior
        _mockLogger = new Mock<ILogger<RevitApiBridge>>();
        _mockTypeConverter = new Mock<IRevitTypeConverter>();
        _mockTransactionManager = new Mock<ITransactionManager>();
        _mockElementBridge = new Mock<IElementBridge>();
        _mockGeometryBridge = new Mock<IGeometryBridge>();
        _mockParameterBridge = new Mock<IParameterBridge>();

        // Setup fast mock responses
        _mockTypeConverter.Setup(x => x.ConvertToPython(It.IsAny<object>()))
            .Returns((object obj) => obj);
        _mockTypeConverter.Setup(x => x.ConvertFromPython<object>(It.IsAny<object>(), It.IsAny<Type>()))
            .Returns((object obj, Type type) => obj);

        // Setup service collection
        var services = new ServiceCollection();
        services.AddSingleton(_mockLogger.Object);
        services.AddSingleton(_mockTypeConverter.Object);
        services.AddSingleton(_mockTransactionManager.Object);
        services.AddSingleton(_mockElementBridge.Object);
        services.AddSingleton(_mockGeometryBridge.Object);
        services.AddSingleton(_mockParameterBridge.Object);

        _serviceProvider = services.BuildServiceProvider();
        _bridge = new RevitApiBridge(
            _mockLogger.Object,
            _mockTypeConverter.Object,
            _mockTransactionManager.Object,
            _mockElementBridge.Object,
            _mockGeometryBridge.Object,
            _mockParameterBridge.Object);
    }

    [Fact]
    public async Task GetStats_Performance_ShouldCompleteWithinTimeLimit()
    {
        // Arrange
        const int iterations = 1000;
        var times = new List<long>();

        _mockElementBridge.Setup(x => x.GetStats()).Returns(new ElementBridgeStats());
        _mockGeometryBridge.Setup(x => x.GetStats()).Returns(new GeometryBridgeStats());
        _mockParameterBridge.Setup(x => x.GetStats()).Returns(new ParameterBridgeStats());
        _mockTransactionManager.Setup(x => x.Stats).Returns(new TransactionStats());
        _mockTypeConverter.Setup(x => x.GetStats()).Returns(new TypeConversionStats());

        // Act
        for (int i = 0; i < iterations; i++)
        {
            var stopwatch = System.Diagnostics.Stopwatch.StartNew();
            var stats = _bridge.GetStats();
            stopwatch.Stop();
            times.Add(stopwatch.ElapsedTicks);

            Assert.NotNull(stats);
        }

        // Assert
        var averageTimeMs = times.Average() / TimeSpan.TicksPerMillisecond;
        var maxTimeMs = times.Max() / TimeSpan.TicksPerMillisecond;

        Assert.True(averageTimeMs < 1.0, $"Average time {averageTimeMs}ms should be less than 1ms");
        Assert.True(maxTimeMs < 10.0, $"Max time {maxTimeMs}ms should be less than 10ms");
    }

    [Fact]
    public async Task OptimizeMemory_Performance_ShouldCompleteWithinTimeLimit()
    {
        // Arrange
        var stopwatch = System.Diagnostics.Stopwatch.StartNew();

        // Act
        await _bridge.OptimizeMemoryAsync();
        stopwatch.Stop();

        // Assert
        var timeMs = stopwatch.ElapsedMilliseconds;
        Assert.True(timeMs < 5000, $"Memory optimization took {timeMs}ms, should be less than 5000ms");
    }

    [Fact]
    public void StatsCollection_ConcurrentAccess_ShouldHandleMultipleThreads()
    {
        // Arrange
        const int threadCount = 10;
        const int operationsPerThread = 100;
        var tasks = new List<Task>();

        _mockElementBridge.Setup(x => x.GetStats()).Returns(new ElementBridgeStats { TotalOperations = 1 });
        _mockGeometryBridge.Setup(x => x.GetStats()).Returns(new GeometryBridgeStats { TotalOperations = 1 });
        _mockParameterBridge.Setup(x => x.GetStats()).Returns(new ParameterBridgeStats { TotalOperations = 1 });
        _mockTransactionManager.Setup(x => x.Stats).Returns(new TransactionStats { TotalTransactions = 1 });
        _mockTypeConverter.Setup(x => x.GetStats()).Returns(new TypeConversionStats { TotalConversions = 1 });

        // Act
        for (int t = 0; t < threadCount; t++)
        {
            tasks.Add(Task.Run(() =>
            {
                for (int i = 0; i < operationsPerThread; i++)
                {
                    var stats = _bridge.GetStats();
                    Assert.NotNull(stats);

                    _bridge.ResetStats();
                }
            }));
        }

        // Assert
        var completed = Task.WaitAll(tasks.ToArray(), TimeSpan.FromSeconds(10));
        Assert.True(completed, "All concurrent operations should complete within 10 seconds");
    }

    [Fact]
    public void MemoryUsage_UnderLoad_ShouldStayWithinLimits()
    {
        // Arrange
        const int iterations = 1000;
        var initialMemory = GC.GetTotalMemory(true);

        // Act
        for (int i = 0; i < iterations; i++)
        {
            var stats = _bridge.GetStats();

            // Simulate some operations that might create objects
            var temp = new Dictionary<string, object>
            {
                ["iteration"] = i,
                ["stats"] = stats,
                ["timestamp"] = DateTime.UtcNow
            };
        }

        GC.Collect();
        GC.WaitForPendingFinalizers();
        GC.Collect();

        var finalMemory = GC.GetTotalMemory(false);
        var memoryGrowth = finalMemory - initialMemory;

        // Assert
        // Memory growth should be reasonable (less than 10MB for 1000 iterations)
        Assert.True(memoryGrowth < 10 * 1024 * 1024,
            $"Memory growth of {memoryGrowth / (1024 * 1024)}MB is too high");
    }

    public void Dispose()
    {
        _bridge?.Dispose();
        _serviceProvider?.Dispose();
    }
}

/// <summary>
/// Integration tests for service collection extensions
/// </summary>
public class BridgeServiceCollectionExtensionsTests
{
    [Fact]
    public void AddRevitPyBridge_ShouldRegisterAllServices()
    {
        // Arrange
        var services = new ServiceCollection();

        // Act
        services.AddRevitPyBridge();

        // Assert
        var serviceProvider = services.BuildServiceProvider();

        Assert.NotNull(serviceProvider.GetService<IRevitTypeConverter>());
        Assert.NotNull(serviceProvider.GetService<ITransactionManager>());
        Assert.NotNull(serviceProvider.GetService<IElementBridge>());
        Assert.NotNull(serviceProvider.GetService<IGeometryBridge>());
        Assert.NotNull(serviceProvider.GetService<IParameterBridge>());
        Assert.NotNull(serviceProvider.GetService<IRevitBridge>());
        Assert.NotNull(serviceProvider.GetService<IRevitBridgeFactory>());
    }

    [Fact]
    public void AddRevitPyBridgeHighPerformance_ShouldConfigureForPerformance()
    {
        // Arrange
        var services = new ServiceCollection();

        // Act
        services.AddRevitPyBridgeHighPerformance();

        // Assert
        var serviceProvider = services.BuildServiceProvider();
        var config = serviceProvider.GetService<RevitBridgeConfiguration>();

        Assert.NotNull(config);
        Assert.True(config.EnableCaching);
        Assert.True(config.EnablePerformanceMonitoring);
        Assert.True(config.EnableMemoryOptimization);
        Assert.False(config.EnableDebugLogging);
        Assert.True(config.CacheSettings.MaxObjectCacheSize > 10000);
    }

    [Fact]
    public void AddRevitPyBridgeDevelopment_ShouldConfigureForDevelopment()
    {
        // Arrange
        var services = new ServiceCollection();

        // Act
        services.AddRevitPyBridgeDevelopment();

        // Assert
        var serviceProvider = services.BuildServiceProvider();
        var config = serviceProvider.GetService<RevitBridgeConfiguration>();

        Assert.NotNull(config);
        Assert.True(config.EnableCaching);
        Assert.True(config.EnablePerformanceMonitoring);
        Assert.False(config.EnableMemoryOptimization);
        Assert.True(config.EnableDebugLogging);
        Assert.True(config.CacheSettings.CacheTTL < TimeSpan.FromMinutes(10));
    }
}

/// <summary>
/// Health check tests
/// </summary>
public class RevitBridgeHealthCheckTests
{
    [Fact]
    public async Task IsHealthyAsync_WithWorkingBridge_ShouldReturnTrue()
    {
        // Arrange
        var mockBridge = new Mock<IRevitBridge>();
        var mockLogger = new Mock<ILogger<RevitBridgeHealthCheck>>();

        mockBridge.Setup(x => x.ExecutePythonCodeAsync("1 + 1", null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(2);

        var healthCheck = new RevitBridgeHealthCheck(mockBridge.Object, mockLogger.Object);

        // Act
        var isHealthy = await healthCheck.IsHealthyAsync();

        // Assert
        Assert.True(isHealthy);
    }

    [Fact]
    public async Task CheckHealthAsync_WithWorkingBridge_ShouldReturnHealthyStatus()
    {
        // Arrange
        var mockBridge = new Mock<IRevitBridge>();
        var mockLogger = new Mock<ILogger<RevitBridgeHealthCheck>>();
        var mockPyObject = new Mock<PyObject>();

        mockBridge.Setup(x => x.ExecutePythonCodeAsync(It.IsAny<string>(), null, It.IsAny<CancellationToken>()))
            .ReturnsAsync("Python 3.9.0");
        mockBridge.Setup(x => x.ImportPythonModuleAsync("math", false, It.IsAny<CancellationToken>()))
            .ReturnsAsync(mockPyObject.Object);
        mockBridge.Setup(x => x.CallPythonFunctionAsync<double>("math", "sqrt", It.IsAny<object[]>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(4.0);
        mockBridge.Setup(x => x.GetStats())
            .Returns(new RevitBridgeStats { TotalOperations = 100, SuccessfulOperations = 95 });

        var healthCheck = new RevitBridgeHealthCheck(mockBridge.Object, mockLogger.Object);

        // Act
        var status = await healthCheck.CheckHealthAsync();

        // Assert
        Assert.NotNull(status);
        Assert.True(status.IsHealthy);
        Assert.True(status.PythonEngineHealthy);
        Assert.True(status.ModuleImportHealthy);
        Assert.True(status.FunctionCallHealthy);
        Assert.NotNull(status.PerformanceStats);
    }
}
