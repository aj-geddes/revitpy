namespace RevitPy.Runtime;

/// <summary>
/// Manages a pool of Python interpreters for efficient resource utilization
/// </summary>
public interface IPythonInterpreterPool : IDisposable
{
    /// <summary>
    /// Gets the number of available interpreters
    /// </summary>
    int AvailableCount { get; }

    /// <summary>
    /// Gets the number of busy interpreters
    /// </summary>
    int BusyCount { get; }

    /// <summary>
    /// Gets the total number of interpreters
    /// </summary>
    int TotalCount { get; }

    /// <summary>
    /// Initializes the interpreter pool
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the initialization</returns>
    Task InitializeAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Rents an interpreter from the pool
    /// </summary>
    /// <param name="timeout">Timeout for acquiring an interpreter</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Rented interpreter</returns>
    Task<IRentedInterpreter> RentAsync(TimeSpan? timeout = null, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets pool statistics
    /// </summary>
    /// <returns>Pool statistics</returns>
    PythonInterpreterPoolStats GetStats();

    /// <summary>
    /// Performs health check on all interpreters
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Health check results</returns>
    Task<PythonInterpreterPoolHealth> HealthCheckAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Clears the pool and recreates interpreters
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the reset</returns>
    Task ResetPoolAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Represents a rented interpreter that will be automatically returned to the pool
/// </summary>
public interface IRentedInterpreter : IDisposable
{
    /// <summary>
    /// Gets the underlying Python interpreter
    /// </summary>
    IPythonInterpreter Interpreter { get; }

    /// <summary>
    /// Gets the rental timestamp
    /// </summary>
    DateTime RentedAt { get; }

    /// <summary>
    /// Gets a value indicating whether the interpreter is still valid
    /// </summary>
    bool IsValid { get; }
}

/// <summary>
/// Statistics for the Python interpreter pool
/// </summary>
public class PythonInterpreterPoolStats
{
    /// <summary>
    /// Gets or sets the total number of interpreters created
    /// </summary>
    public long TotalCreated { get; set; }

    /// <summary>
    /// Gets or sets the total number of interpreters destroyed
    /// </summary>
    public long TotalDestroyed { get; set; }

    /// <summary>
    /// Gets or sets the total number of rental requests
    /// </summary>
    public long TotalRentals { get; set; }

    /// <summary>
    /// Gets or sets the total number of failed rental requests
    /// </summary>
    public long FailedRentals { get; set; }

    /// <summary>
    /// Gets or sets the average rental duration
    /// </summary>
    public TimeSpan AverageRentalDuration { get; set; }

    /// <summary>
    /// Gets or sets the peak concurrent rentals
    /// </summary>
    public int PeakConcurrentRentals { get; set; }

    /// <summary>
    /// Gets or sets the current pool size
    /// </summary>
    public int CurrentPoolSize { get; set; }

    /// <summary>
    /// Gets or sets the number of healthy interpreters
    /// </summary>
    public int HealthyInterpreters { get; set; }

    /// <summary>
    /// Gets or sets the memory usage across all interpreters
    /// </summary>
    public long TotalMemoryUsage { get; set; }

    /// <summary>
    /// Gets or sets the last reset timestamp
    /// </summary>
    public DateTime? LastResetAt { get; set; }

    /// <summary>
    /// Gets or sets the uptime since last reset
    /// </summary>
    public TimeSpan Uptime { get; set; }
}

/// <summary>
/// Health information for the interpreter pool
/// </summary>
public class PythonInterpreterPoolHealth
{
    /// <summary>
    /// Gets or sets a value indicating whether the pool is healthy
    /// </summary>
    public bool IsHealthy { get; set; }

    /// <summary>
    /// Gets or sets the health check timestamp
    /// </summary>
    public DateTime CheckedAt { get; set; }

    /// <summary>
    /// Gets or sets individual interpreter health results
    /// </summary>
    public List<InterpreterHealthResult> InterpreterResults { get; set; } = new();

    /// <summary>
    /// Gets or sets any health issues detected
    /// </summary>
    public List<string> Issues { get; set; } = new();

    /// <summary>
    /// Gets or sets recommended actions
    /// </summary>
    public List<string> RecommendedActions { get; set; } = new();
}

/// <summary>
/// Health result for an individual interpreter
/// </summary>
public class InterpreterHealthResult
{
    /// <summary>
    /// Gets or sets the interpreter ID
    /// </summary>
    public string InterpreteId { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets a value indicating whether the interpreter is healthy
    /// </summary>
    public bool IsHealthy { get; set; }

    /// <summary>
    /// Gets or sets the response time
    /// </summary>
    public TimeSpan ResponseTime { get; set; }

    /// <summary>
    /// Gets or sets the memory usage
    /// </summary>
    public PythonMemoryInfo MemoryInfo { get; set; } = new();

    /// <summary>
    /// Gets or sets any error message
    /// </summary>
    public string? ErrorMessage { get; set; }

    /// <summary>
    /// Gets or sets the last successful execution timestamp
    /// </summary>
    public DateTime? LastSuccessfulExecution { get; set; }
}