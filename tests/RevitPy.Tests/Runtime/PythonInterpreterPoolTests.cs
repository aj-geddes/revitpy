using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using RevitPy.Core.Configuration;
using RevitPy.Runtime;

namespace RevitPy.Tests.Runtime;

public class PythonInterpreterPoolTests : IDisposable
{
    private readonly IServiceProvider _serviceProvider;
    private readonly IPythonInterpreterPool _pool;

    public PythonInterpreterPoolTests()
    {
        var services = new ServiceCollection();
        services.AddLogging(builder => builder.AddConsole().SetMinimumLevel(LogLevel.Debug));
        services.Configure<RevitPyOptions>(options =>
        {
            options.PythonVersion = "3.11";
            options.MaxInterpreters = 3;
            options.PythonTimeout = 30000;
        });
        services.AddTransient<IPythonInterpreter, PythonInterpreter>();
        services.AddSingleton<IPythonInterpreterPool, PythonInterpreterPool>();

        _serviceProvider = services.BuildServiceProvider();
        _pool = _serviceProvider.GetRequiredService<IPythonInterpreterPool>();
    }

    [Fact]
    public async Task InitializeAsync_ShouldCreateInitialInterpreters()
    {
        // Act
        await _pool.InitializeAsync();

        // Assert
        _pool.AvailableCount.Should().BeGreaterThan(0);
        _pool.TotalCount.Should().BeGreaterThan(0);
        _pool.BusyCount.Should().Be(0);
    }

    [Fact]
    public async Task RentAsync_ShouldReturnValidInterpreter()
    {
        // Arrange
        await _pool.InitializeAsync();

        // Act
        using var rental = await _pool.RentAsync();

        // Assert
        rental.Should().NotBeNull();
        rental.Interpreter.Should().NotBeNull();
        rental.Interpreter.IsInitialized.Should().BeTrue();
        rental.IsValid.Should().BeTrue();
        rental.RentedAt.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(1));
    }

    [Fact]
    public async Task RentAsync_MultipleConcurrent_ShouldHandleCorrectly()
    {
        // Arrange
        await _pool.InitializeAsync();
        var rentalTasks = new List<Task<IRentedInterpreter>>();

        // Act
        for (int i = 0; i < 3; i++)
        {
            rentalTasks.Add(_pool.RentAsync());
        }

        var rentals = await Task.WhenAll(rentalTasks);

        // Assert
        rentals.Should().HaveCount(3);
        rentals.Should().OnlyContain(r => r.IsValid);
        rentals.Select(r => r.Interpreter.Id).Should().OnlyHaveUniqueItems();

        // Cleanup
        foreach (var rental in rentals)
        {
            rental.Dispose();
        }
    }

    [Fact]
    public async Task RentAsync_WhenPoolExhausted_ShouldWaitOrTimeout()
    {
        // Arrange
        await _pool.InitializeAsync();
        var maxInterpreters = 3;
        var rentals = new List<IRentedInterpreter>();

        // Rent all available interpreters
        for (int i = 0; i < maxInterpreters; i++)
        {
            rentals.Add(await _pool.RentAsync());
        }

        // Act & Assert
        using var cts = new CancellationTokenSource(TimeSpan.FromMilliseconds(100));
        await Assert.ThrowsAsync<TimeoutException>(
            () => _pool.RentAsync(TimeSpan.FromMilliseconds(50), cts.Token));

        // Cleanup
        rentals.ForEach(r => r.Dispose());
    }

    [Fact]
    public async Task ReturnInterpreter_ShouldMakeInterpreterAvailableAgain()
    {
        // Arrange
        await _pool.InitializeAsync();
        var initialAvailable = _pool.AvailableCount;

        // Act
        using (var rental = await _pool.RentAsync())
        {
            // Interpreter is rented
            _pool.AvailableCount.Should().Be(initialAvailable - 1);
            _pool.BusyCount.Should().Be(1);
        } // Rental is disposed here

        // Give some time for the return to be processed
        await Task.Delay(100);

        // Assert
        _pool.AvailableCount.Should().Be(initialAvailable);
        _pool.BusyCount.Should().Be(0);
    }

    [Fact]
    public async Task GetStats_ShouldReturnValidStatistics()
    {
        // Arrange
        await _pool.InitializeAsync();

        // Perform some operations
        using (var rental = await _pool.RentAsync())
        {
            await rental.Interpreter.ExecuteAsync("x = 1 + 1");
        }

        // Act
        var stats = _pool.GetStats();

        // Assert
        stats.Should().NotBeNull();
        stats.TotalCreated.Should().BeGreaterThan(0);
        stats.TotalRentals.Should().BeGreaterThan(0);
        stats.CurrentPoolSize.Should().BeGreaterThan(0);
        stats.Uptime.Should().BePositive();
    }

    [Fact]
    public async Task HealthCheckAsync_ShouldReturnHealthInformation()
    {
        // Arrange
        await _pool.InitializeAsync();

        // Act
        var health = await _pool.HealthCheckAsync();

        // Assert
        health.Should().NotBeNull();
        health.CheckedAt.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
        health.InterpreterResults.Should().NotBeEmpty();
        health.InterpreterResults.Should().OnlyContain(r => r.IsHealthy);
        health.IsHealthy.Should().BeTrue();
    }

    [Fact]
    public async Task ResetPoolAsync_ShouldRecreateAllInterpreters()
    {
        // Arrange
        await _pool.InitializeAsync();
        var originalStats = _pool.GetStats();

        // Act
        await _pool.ResetPoolAsync();

        // Assert
        var newStats = _pool.GetStats();
        newStats.LastResetAt.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
        newStats.TotalDestroyed.Should().BeGreaterThan(originalStats.TotalDestroyed);
        _pool.TotalCount.Should().BeGreaterThan(0);
        _pool.AvailableCount.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task RentedInterpreter_ShouldExecutePythonCorrectly()
    {
        // Arrange
        await _pool.InitializeAsync();

        // Act
        using var rental = await _pool.RentAsync();
        var result = await rental.Interpreter.ExecuteAsync("result = 5 * 10");

        // Assert
        result.Success.Should().BeTrue();
        result.Exception.Should().BeNull();

        var value = await rental.Interpreter.GetVariableAsync<int>("result");
        value.Should().Be(50);
    }

    [Fact]
    public async Task Pool_ShouldHandleConcurrentOperations()
    {
        // Arrange
        await _pool.InitializeAsync();
        const int concurrentOperations = 10;
        var tasks = new List<Task>();

        // Act
        for (int i = 0; i < concurrentOperations; i++)
        {
            var operationIndex = i;
            tasks.Add(Task.Run(async () =>
            {
                using var rental = await _pool.RentAsync();
                await rental.Interpreter.ExecuteAsync($"x = {operationIndex} * 2");
                var result = await rental.Interpreter.GetVariableAsync<int>("x");
                result.Should().Be(operationIndex * 2);
            }));
        }

        // Assert
        await Task.WhenAll(tasks);

        // All operations should complete successfully
        tasks.Should().OnlyContain(t => t.IsCompletedSuccessfully);
    }

    public void Dispose()
    {
        _pool?.Dispose();
        (_serviceProvider as IDisposable)?.Dispose();
    }
}
