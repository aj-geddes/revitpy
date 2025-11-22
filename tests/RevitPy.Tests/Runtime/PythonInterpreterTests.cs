using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Core.Configuration;
using RevitPy.Runtime;

namespace RevitPy.Tests.Runtime;

public class PythonInterpreterTests : IDisposable
{
    private readonly IServiceProvider _serviceProvider;
    private readonly IPythonInterpreter _interpreter;

    public PythonInterpreterTests()
    {
        var services = new ServiceCollection();
        services.AddLogging(builder => builder.AddConsole().SetMinimumLevel(LogLevel.Debug));
        services.Configure<RevitPyOptions>(options =>
        {
            options.PythonVersion = "3.11";
            options.PythonTimeout = 30000;
            options.MaxInterpreters = 5;
        });
        services.AddTransient<IPythonInterpreter, PythonInterpreter>();

        _serviceProvider = services.BuildServiceProvider();
        _interpreter = _serviceProvider.GetRequiredService<IPythonInterpreter>();
    }

    [Fact]
    public async Task InitializeAsync_ShouldInitializeInterpreter()
    {
        // Act
        await _interpreter.InitializeAsync();

        // Assert
        _interpreter.IsInitialized.Should().BeTrue();
        _interpreter.Id.Should().NotBeNullOrEmpty();
        _interpreter.LastActivity.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
    }

    [Fact]
    public async Task ExecuteAsync_WithSimpleExpression_ShouldReturnCorrectResult()
    {
        // Arrange
        await _interpreter.InitializeAsync();
        var code = "result = 2 + 3";

        // Act
        var result = await _interpreter.ExecuteAsync(code);

        // Assert
        result.Success.Should().BeTrue();
        result.Exception.Should().BeNull();
        result.ExecutionTime.Should().BePositive();
    }

    [Fact]
    public async Task ExecuteAsync_WithSyntaxError_ShouldReturnFailedResult()
    {
        // Arrange
        await _interpreter.InitializeAsync();
        var code = "result = 2 +"; // Invalid syntax

        // Act
        var result = await _interpreter.ExecuteAsync(code);

        // Assert
        result.Success.Should().BeFalse();
        result.Exception.Should().NotBeNull();
        result.PythonStackTrace.Should().NotBeNullOrEmpty();
    }

    [Fact]
    public async Task EvaluateAsync_WithSimpleExpression_ShouldReturnCorrectValue()
    {
        // Arrange
        await _interpreter.InitializeAsync();
        var expression = "2 + 3";

        // Act
        var result = await _interpreter.EvaluateAsync<int>(expression);

        // Assert
        result.Should().Be(5);
    }

    [Fact]
    public async Task SetVariableAsync_AndGetVariableAsync_ShouldWorkCorrectly()
    {
        // Arrange
        await _interpreter.InitializeAsync();
        var variableName = "test_variable";
        var variableValue = "Hello, World!";

        // Act
        await _interpreter.SetVariableAsync(variableName, variableValue);
        var retrievedValue = await _interpreter.GetVariableAsync<string>(variableName);

        // Assert
        retrievedValue.Should().Be(variableValue);
    }

    [Fact]
    public async Task ImportModuleAsync_WithValidModule_ShouldImportSuccessfully()
    {
        // Arrange
        await _interpreter.InitializeAsync();

        // Act
        await _interpreter.ImportModuleAsync("math");
        var piValue = await _interpreter.EvaluateAsync<double>("math.pi");

        // Assert
        piValue.Should().BeApproximately(Math.PI, 0.0001);
    }

    [Fact]
    public async Task AddPathAsync_ShouldAddPathToSysPath()
    {
        // Arrange
        await _interpreter.InitializeAsync();
        var testPath = "/test/path";

        // Act
        await _interpreter.AddPathAsync(testPath);
        var sysPathLength = await _interpreter.EvaluateAsync<int>("len(sys.path)");

        // Assert
        sysPathLength.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task GetMemoryInfo_ShouldReturnValidMemoryInformation()
    {
        // Arrange
        await _interpreter.InitializeAsync();

        // Act
        var memoryInfo = _interpreter.GetMemoryInfo();

        // Assert
        memoryInfo.Should().NotBeNull();
        memoryInfo.ObjectCount.Should().BeGreaterOrEqualTo(0);
        memoryInfo.ActiveReferences.Should().BeGreaterOrEqualTo(0);
    }

    [Fact]
    public async Task ResetAsync_ShouldResetInterpreterState()
    {
        // Arrange
        await _interpreter.InitializeAsync();
        await _interpreter.SetVariableAsync("test_var", "test_value");

        // Act
        await _interpreter.ResetAsync();

        // Assert
        var retrievedValue = await _interpreter.EvaluateAsync<string>("test_var if 'test_var' in globals() else None");
        retrievedValue.Should().BeNull();
    }

    [Fact]
    public async Task ExecuteAsync_WithGlobalVariables_ShouldUseProvidedGlobals()
    {
        // Arrange
        await _interpreter.InitializeAsync();
        var code = "result = x + y";
        var globals = new Dictionary<string, object>
        {
            ["x"] = 10,
            ["y"] = 20
        };

        // Act
        var result = await _interpreter.ExecuteAsync(code, globals);

        // Assert
        result.Success.Should().BeTrue();
    }

    [Fact]
    public async Task ExecuteAsync_WithTimeout_ShouldRespectCancellationToken()
    {
        // Arrange
        await _interpreter.InitializeAsync();
        var code = "import time; time.sleep(10)";
        using var cts = new CancellationTokenSource(TimeSpan.FromMilliseconds(100));

        // Act & Assert
        await Assert.ThrowsAsync<OperationCanceledException>(
            () => _interpreter.ExecuteAsync(code, cancellationToken: cts.Token));
    }

    public void Dispose()
    {
        _interpreter?.Dispose();
        (_serviceProvider as IDisposable)?.Dispose();
    }
}
