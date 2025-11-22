using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Moq;
using RevitPy.Bridge;
using RevitPy.Core.Configuration;
using RevitPy.Core.Exceptions;
using RevitPy.Core.Logging;
using System.Text.Json;
using Xunit.Abstractions;

namespace RevitPy.Tests.Unit.CSharp;

/// <summary>
/// Comprehensive unit tests for the RevitPy bridge functionality.
/// Tests the core communication layer between Python and .NET.
/// </summary>
public class BridgeTests : IDisposable
{
    private readonly IServiceProvider _serviceProvider;
    private readonly Mock<IRevitApplication> _mockRevitApp;
    private readonly Mock<IRevitDocument> _mockDocument;
    private readonly Mock<IRevitPyLogger> _mockLogger;
    private readonly RevitBridge _bridge;
    private readonly ITestOutputHelper _output;

    public BridgeTests(ITestOutputHelper output)
    {
        _output = output;

        // Setup mock services
        _mockRevitApp = new Mock<IRevitApplication>();
        _mockDocument = new Mock<IRevitDocument>();
        _mockLogger = new Mock<IRevitPyLogger>();

        // Setup service collection
        var services = new ServiceCollection();
        services.AddLogging(builder => builder.AddConsole().SetMinimumLevel(LogLevel.Debug));
        services.Configure<RevitPyOptions>(options =>
        {
            options.PythonVersion = "3.11";
            options.PythonTimeout = 30000;
            options.MaxInterpreters = 5;
            options.EnableBridgeLogging = true;
        });

        services.AddSingleton(_mockRevitApp.Object);
        services.AddSingleton(_mockLogger.Object);
        services.AddTransient<IRevitBridge, RevitBridge>();
        services.AddTransient<IRevitTypeConverter, RevitTypeConverter>();
        services.AddTransient<ITransactionManager, TransactionManager>();

        _serviceProvider = services.BuildServiceProvider();
        _bridge = _serviceProvider.GetRequiredService<IRevitBridge>() as RevitBridge;
    }

    [Fact]
    [Trait("Category", "Unit")]
    public void Constructor_ShouldInitializeWithDefaults()
    {
        // Assert
        _bridge.Should().NotBeNull();
        _bridge.IsConnected.Should().BeFalse();
        _bridge.Version.Should().NotBeNullOrEmpty();
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task ConnectAsync_WithValidRevitApp_ShouldConnectSuccessfully()
    {
        // Arrange
        _mockRevitApp.Setup(x => x.Documents).Returns(new Mock<IDocumentCollection>().Object);
        _mockRevitApp.Setup(x => x.VersionNumber).Returns("2024");
        _mockRevitApp.Setup(x => x.Application).Returns(_mockRevitApp.Object);

        // Act
        var result = await _bridge.ConnectAsync(_mockRevitApp.Object);

        // Assert
        result.Should().BeTrue();
        _bridge.IsConnected.Should().BeTrue();
        _mockLogger.Verify(x => x.LogInfo(It.IsAny<string>()), Times.AtLeastOnce);
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task ConnectAsync_WithNullRevitApp_ShouldThrowException()
    {
        // Act & Assert
        await FluentActions
            .Invoking(() => _bridge.ConnectAsync(null))
            .Should()
            .ThrowAsync<ArgumentNullException>();
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task CallAsync_WithValidMethod_ShouldExecuteSuccessfully()
    {
        // Arrange
        await SetupConnectedBridge();
        SetupMockDocument();

        var parameters = JsonSerializer.Serialize(new { elementId = 12345 });

        _mockDocument
            .Setup(x => x.GetElement(It.IsAny<ElementId>()))
            .Returns(CreateMockElement(12345, "Test Wall"));

        // Act
        var result = await _bridge.CallAsync("GetElement", parameters);

        // Assert
        result.Should().NotBeNull();
        var response = JsonSerializer.Deserialize<Dictionary<string, object>>(result);
        response.Should().ContainKey("Id");
        response["Id"].ToString().Should().Be("12345");
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task CallAsync_WithInvalidMethod_ShouldThrowRevitPyException()
    {
        // Arrange
        await SetupConnectedBridge();
        var parameters = "{}";

        // Act & Assert
        await FluentActions
            .Invoking(() => _bridge.CallAsync("NonExistentMethod", parameters))
            .Should()
            .ThrowAsync<RevitPyException>()
            .WithMessage("*NonExistentMethod*");
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task CallAsync_WithInvalidJson_ShouldThrowRevitPyException()
    {
        // Arrange
        await SetupConnectedBridge();
        var invalidJson = "{ invalid json }";

        // Act & Assert
        await FluentActions
            .Invoking(() => _bridge.CallAsync("GetElement", invalidJson))
            .Should()
            .ThrowAsync<RevitPyException>()
            .WithMessage("*JSON*");
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task CallAsync_WithTimeout_ShouldRespectTimeout()
    {
        // Arrange
        await SetupConnectedBridge();
        var parameters = JsonSerializer.Serialize(new { elementId = 12345 });

        // Setup mock to simulate long operation
        _mockDocument
            .Setup(x => x.GetElement(It.IsAny<ElementId>()))
            .Returns(() =>
            {
                Thread.Sleep(2000); // 2 second delay
                return CreateMockElement(12345, "Test Wall");
            });

        // Act & Assert
        await FluentActions
            .Invoking(() => _bridge.CallAsync("GetElement", parameters, 500)) // 500ms timeout
            .Should()
            .ThrowAsync<TimeoutException>();
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task GetElementsAsync_ShouldReturnFilteredElements()
    {
        // Arrange
        await SetupConnectedBridge();
        SetupMockDocument();

        var mockElements = new List<IElement>
        {
            CreateMockElement(1001, "Wall 1", "Walls"),
            CreateMockElement(1002, "Wall 2", "Walls"),
            CreateMockElement(2001, "Door 1", "Doors")
        };

        _mockDocument
            .Setup(x => x.GetElements(It.IsAny<IElementFilter>()))
            .Returns(mockElements.Where(e => e.Category.Name == "Walls"));

        var parameters = JsonSerializer.Serialize(new { category = "Walls" });

        // Act
        var result = await _bridge.CallAsync("GetElements", parameters);

        // Assert
        result.Should().NotBeNull();
        var elements = JsonSerializer.Deserialize<List<Dictionary<string, object>>>(result);
        elements.Should().HaveCount(2);
        elements.All(e => e["Category"].ToString() == "Walls").Should().BeTrue();
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task UpdateElementAsync_ShouldModifyElementParameters()
    {
        // Arrange
        await SetupConnectedBridge();
        SetupMockDocument();

        var mockElement = CreateMockElement(12345, "Test Wall");
        var mockTransaction = new Mock<ITransaction>();

        _mockDocument.Setup(x => x.GetElement(It.IsAny<ElementId>())).Returns(mockElement);
        _mockDocument.Setup(x => x.NewTransaction(It.IsAny<string>())).Returns(mockTransaction.Object);
        mockTransaction.Setup(x => x.Start()).Returns(TransactionStatus.Started);
        mockTransaction.Setup(x => x.Commit()).Returns(TransactionStatus.Committed);

        var parameters = JsonSerializer.Serialize(new
        {
            elementId = 12345,
            parameters = new Dictionary<string, object>
            {
                { "Height", 3500.0 },
                { "Comments", "Updated by RevitPy" }
            }
        });

        // Act
        var result = await _bridge.CallAsync("UpdateElement", parameters);

        // Assert
        result.Should().NotBeNull();
        mockTransaction.Verify(x => x.Start(), Times.Once);
        mockTransaction.Verify(x => x.Commit(), Times.Once);

        var response = JsonSerializer.Deserialize<Dictionary<string, object>>(result);
        response["success"].ToString().Should().Be("True");
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task UpdateElementAsync_TransactionFailure_ShouldRollback()
    {
        // Arrange
        await SetupConnectedBridge();
        SetupMockDocument();

        var mockElement = CreateMockElement(12345, "Test Wall");
        var mockTransaction = new Mock<ITransaction>();

        _mockDocument.Setup(x => x.GetElement(It.IsAny<ElementId>())).Returns(mockElement);
        _mockDocument.Setup(x => x.NewTransaction(It.IsAny<string>())).Returns(mockTransaction.Object);
        mockTransaction.Setup(x => x.Start()).Returns(TransactionStatus.Started);
        mockTransaction.Setup(x => x.Commit()).Throws(new InvalidOperationException("Transaction failed"));

        var parameters = JsonSerializer.Serialize(new
        {
            elementId = 12345,
            parameters = new Dictionary<string, object> { { "Height", 3500.0 } }
        });

        // Act & Assert
        await FluentActions
            .Invoking(() => _bridge.CallAsync("UpdateElement", parameters))
            .Should()
            .ThrowAsync<RevitPyException>();

        mockTransaction.Verify(x => x.RollBack(), Times.Once);
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task CreateElementAsync_ShouldCreateNewElement()
    {
        // Arrange
        await SetupConnectedBridge();
        SetupMockDocument();

        var mockTransaction = new Mock<ITransaction>();
        var mockNewElement = CreateMockElement(99999, "New Wall");

        _mockDocument.Setup(x => x.NewTransaction(It.IsAny<string>())).Returns(mockTransaction.Object);
        _mockDocument.Setup(x => x.Create(It.IsAny<ElementCreationData>())).Returns(mockNewElement);
        mockTransaction.Setup(x => x.Start()).Returns(TransactionStatus.Started);
        mockTransaction.Setup(x => x.Commit()).Returns(TransactionStatus.Committed);

        var parameters = JsonSerializer.Serialize(new
        {
            elementType = "Wall",
            wallType = "Basic Wall",
            curve = new { startPoint = new { x = 0, y = 0, z = 0 }, endPoint = new { x = 1000, y = 0, z = 0 } },
            height = 3000.0
        });

        // Act
        var result = await _bridge.CallAsync("CreateElement", parameters);

        // Assert
        result.Should().NotBeNull();
        var response = JsonSerializer.Deserialize<Dictionary<string, object>>(result);
        response.Should().ContainKey("Id");
        response["Id"].ToString().Should().Be("99999");
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task DeleteElementAsync_ShouldRemoveElement()
    {
        // Arrange
        await SetupConnectedBridge();
        SetupMockDocument();

        var mockElement = CreateMockElement(12345, "Test Wall");
        var mockTransaction = new Mock<ITransaction>();

        _mockDocument.Setup(x => x.GetElement(It.IsAny<ElementId>())).Returns(mockElement);
        _mockDocument.Setup(x => x.NewTransaction(It.IsAny<string>())).Returns(mockTransaction.Object);
        _mockDocument.Setup(x => x.Delete(It.IsAny<ElementId>())).Returns(true);
        mockTransaction.Setup(x => x.Start()).Returns(TransactionStatus.Started);
        mockTransaction.Setup(x => x.Commit()).Returns(TransactionStatus.Committed);

        var parameters = JsonSerializer.Serialize(new { elementId = 12345 });

        // Act
        var result = await _bridge.CallAsync("DeleteElement", parameters);

        // Assert
        result.Should().NotBeNull();
        var response = JsonSerializer.Deserialize<Dictionary<string, object>>(result);
        response["success"].ToString().Should().Be("True");

        _mockDocument.Verify(x => x.Delete(It.IsAny<ElementId>()), Times.Once);
    }

    [Fact]
    [Trait("Category", "Unit")]
    [Trait("Category", "Performance")]
    public async Task CallAsync_ConcurrentCalls_ShouldHandleThreadSafety()
    {
        // Arrange
        await SetupConnectedBridge();
        SetupMockDocument();

        _mockDocument
            .Setup(x => x.GetElement(It.IsAny<ElementId>()))
            .Returns<ElementId>(id => CreateMockElement(id.IntegerValue, $"Element {id.IntegerValue}"));

        var tasks = new List<Task<string>>();
        const int concurrentCalls = 50;

        // Act
        for (int i = 1; i <= concurrentCalls; i++)
        {
            var parameters = JsonSerializer.Serialize(new { elementId = i });
            tasks.Add(_bridge.CallAsync("GetElement", parameters));
        }

        var results = await Task.WhenAll(tasks);

        // Assert
        results.Should().HaveCount(concurrentCalls);
        results.Should().OnlyContain(r => !string.IsNullOrEmpty(r));

        // Verify each result contains the correct element ID
        for (int i = 0; i < concurrentCalls; i++)
        {
            var response = JsonSerializer.Deserialize<Dictionary<string, object>>(results[i]);
            response["Id"].ToString().Should().Be((i + 1).ToString());
        }
    }

    [Fact]
    [Trait("Category", "Unit")]
    [Trait("Category", "Security")]
    public async Task CallAsync_WithMaliciousInput_ShouldValidateAndReject()
    {
        // Arrange
        await SetupConnectedBridge();

        // Test various malicious inputs
        var maliciousInputs = new[]
        {
            "{ \"elementId\": \"'; DROP TABLE Elements; --\" }",
            "{ \"script\": \"<script>alert('xss')</script>\" }",
            "{ \"path\": \"../../../etc/passwd\" }",
            "{ \"command\": \"rm -rf /\" }"
        };

        // Act & Assert
        foreach (var input in maliciousInputs)
        {
            await FluentActions
                .Invoking(() => _bridge.CallAsync("GetElement", input))
                .Should()
                .ThrowAsync<RevitPyException>()
                .WithMessage("*validation*");
        }
    }

    [Fact]
    [Trait("Category", "Unit")]
    [Trait("Category", "Security")]
    public async Task CallAsync_WithLargePayload_ShouldRespectLimits()
    {
        // Arrange
        await SetupConnectedBridge();

        // Create payload larger than typical limits (e.g., 10MB)
        var largeData = new string('x', 10 * 1024 * 1024);
        var parameters = JsonSerializer.Serialize(new { data = largeData });

        // Act & Assert
        await FluentActions
            .Invoking(() => _bridge.CallAsync("ProcessData", parameters))
            .Should()
            .ThrowAsync<RevitPyException>()
            .WithMessage("*payload size*");
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task DisconnectAsync_WhenConnected_ShouldDisconnectCleanly()
    {
        // Arrange
        await SetupConnectedBridge();

        // Act
        await _bridge.DisconnectAsync();

        // Assert
        _bridge.IsConnected.Should().BeFalse();
        _mockLogger.Verify(x => x.LogInfo(It.Is<string>(s => s.Contains("Disconnected"))), Times.Once);
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task DisconnectAsync_WhenNotConnected_ShouldNotThrow()
    {
        // Act & Assert
        await FluentActions
            .Invoking(() => _bridge.DisconnectAsync())
            .Should()
            .NotThrowAsync();
    }

    [Fact]
    [Trait("Category", "Unit")]
    [Trait("Category", "Memory")]
    public async Task LongRunningOperations_ShouldNotLeakMemory()
    {
        // Arrange
        await SetupConnectedBridge();
        SetupMockDocument();

        _mockDocument
            .Setup(x => x.GetElement(It.IsAny<ElementId>()))
            .Returns<ElementId>(id => CreateMockElement(id.IntegerValue, $"Element {id.IntegerValue}"));

        var initialMemory = GC.GetTotalMemory(true);

        // Act - Perform many operations
        for (int i = 0; i < 1000; i++)
        {
            var parameters = JsonSerializer.Serialize(new { elementId = i % 100 + 1 });
            await _bridge.CallAsync("GetElement", parameters);
        }

        // Force garbage collection
        GC.Collect();
        GC.WaitForPendingFinalizers();
        GC.Collect();

        var finalMemory = GC.GetTotalMemory(false);

        // Assert - Memory increase should be minimal (less than 10MB)
        var memoryIncrease = finalMemory - initialMemory;
        memoryIncrease.Should().BeLessThan(10 * 1024 * 1024,
            $"Memory increased by {memoryIncrease / 1024 / 1024}MB");
    }

    [Theory]
    [Trait("Category", "Unit")]
    [InlineData("GetElement")]
    [InlineData("GetElements")]
    [InlineData("UpdateElement")]
    [InlineData("CreateElement")]
    [InlineData("DeleteElement")]
    public async Task CallAsync_WithSupportedMethods_ShouldExecute(string methodName)
    {
        // Arrange
        await SetupConnectedBridge();
        SetupMockDocument();

        var parameters = methodName switch
        {
            "GetElement" => JsonSerializer.Serialize(new { elementId = 12345 }),
            "GetElements" => JsonSerializer.Serialize(new { category = "Walls" }),
            "UpdateElement" => JsonSerializer.Serialize(new { elementId = 12345, parameters = new { Height = 3000.0 } }),
            "CreateElement" => JsonSerializer.Serialize(new { elementType = "Wall", wallType = "Basic Wall" }),
            "DeleteElement" => JsonSerializer.Serialize(new { elementId = 12345 }),
            _ => "{}"
        };

        // Setup appropriate mocks based on method
        SetupMethodSpecificMocks(methodName);

        // Act
        var result = await _bridge.CallAsync(methodName, parameters);

        // Assert
        result.Should().NotBeNull();
    }

    private async Task SetupConnectedBridge()
    {
        _mockRevitApp.Setup(x => x.Documents).Returns(new Mock<IDocumentCollection>().Object);
        _mockRevitApp.Setup(x => x.VersionNumber).Returns("2024");
        await _bridge.ConnectAsync(_mockRevitApp.Object);
    }

    private void SetupMockDocument()
    {
        var mockDocuments = new Mock<IDocumentCollection>();
        mockDocuments.Setup(x => x.Size).Returns(1);
        mockDocuments.Setup(x => x.get_Item(0)).Returns(_mockDocument.Object);

        _mockRevitApp.Setup(x => x.Documents).Returns(mockDocuments.Object);
    }

    private IElement CreateMockElement(int id, string name, string category = "Walls")
    {
        var mockElement = new Mock<IElement>();
        var mockCategory = new Mock<ICategory>();
        var mockElementId = new Mock<IElementId>();

        mockElementId.Setup(x => x.IntegerValue).Returns(id);
        mockCategory.Setup(x => x.Name).Returns(category);

        mockElement.Setup(x => x.Id).Returns(mockElementId.Object);
        mockElement.Setup(x => x.Name).Returns(name);
        mockElement.Setup(x => x.Category).Returns(mockCategory.Object);

        return mockElement.Object;
    }

    private void SetupMethodSpecificMocks(string methodName)
    {
        switch (methodName)
        {
            case "GetElement":
                _mockDocument
                    .Setup(x => x.GetElement(It.IsAny<ElementId>()))
                    .Returns(CreateMockElement(12345, "Test Wall"));
                break;

            case "GetElements":
                _mockDocument
                    .Setup(x => x.GetElements(It.IsAny<IElementFilter>()))
                    .Returns(new List<IElement> { CreateMockElement(12345, "Test Wall") });
                break;

            case "UpdateElement":
            case "DeleteElement":
                var mockTransaction = new Mock<ITransaction>();
                _mockDocument.Setup(x => x.GetElement(It.IsAny<ElementId>()))
                    .Returns(CreateMockElement(12345, "Test Wall"));
                _mockDocument.Setup(x => x.NewTransaction(It.IsAny<string>()))
                    .Returns(mockTransaction.Object);
                mockTransaction.Setup(x => x.Start()).Returns(TransactionStatus.Started);
                mockTransaction.Setup(x => x.Commit()).Returns(TransactionStatus.Committed);
                break;

            case "CreateElement":
                var createTransaction = new Mock<ITransaction>();
                _mockDocument.Setup(x => x.NewTransaction(It.IsAny<string>()))
                    .Returns(createTransaction.Object);
                _mockDocument.Setup(x => x.Create(It.IsAny<ElementCreationData>()))
                    .Returns(CreateMockElement(99999, "New Wall"));
                createTransaction.Setup(x => x.Start()).Returns(TransactionStatus.Started);
                createTransaction.Setup(x => x.Commit()).Returns(TransactionStatus.Committed);
                break;
        }
    }

    public void Dispose()
    {
        _bridge?.Dispose();
        (_serviceProvider as IDisposable)?.Dispose();
    }
}

/// <summary>
/// Additional tests for edge cases and error conditions.
/// </summary>
public class BridgeEdgeCaseTests : IDisposable
{
    private readonly Mock<IRevitApplication> _mockRevitApp;
    private readonly Mock<IRevitPyLogger> _mockLogger;
    private readonly RevitBridge _bridge;

    public BridgeEdgeCaseTests()
    {
        _mockRevitApp = new Mock<IRevitApplication>();
        _mockLogger = new Mock<IRevitPyLogger>();

        var services = new ServiceCollection();
        services.AddSingleton(_mockRevitApp.Object);
        services.AddSingleton(_mockLogger.Object);
        services.AddTransient<IRevitBridge, RevitBridge>();

        var serviceProvider = services.BuildServiceProvider();
        _bridge = serviceProvider.GetRequiredService<IRevitBridge>() as RevitBridge;
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task CallAsync_WhenNotConnected_ShouldThrowException()
    {
        // Act & Assert
        await FluentActions
            .Invoking(() => _bridge.CallAsync("GetElement", "{}"))
            .Should()
            .ThrowAsync<InvalidOperationException>()
            .WithMessage("*not connected*");
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task CallAsync_WithNullParameters_ShouldUseDefaults()
    {
        // This test would verify handling of null parameters
        // Implementation depends on specific bridge requirements
    }

    [Fact]
    [Trait("Category", "Unit")]
    public async Task CallAsync_WithEmptyParameters_ShouldUseDefaults()
    {
        // This test would verify handling of empty parameter strings
        // Implementation depends on specific bridge requirements
    }

    public void Dispose()
    {
        _bridge?.Dispose();
    }
}
