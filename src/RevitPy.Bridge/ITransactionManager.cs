namespace RevitPy.Bridge;

/// <summary>
/// Manages Revit transactions for safe model modifications
/// </summary>
public interface ITransactionManager
{
    /// <summary>
    /// Gets a value indicating whether a transaction is currently active
    /// </summary>
    bool HasActiveTransaction { get; }

    /// <summary>
    /// Gets the active transaction information
    /// </summary>
    ITransactionInfo? ActiveTransaction { get; }

    /// <summary>
    /// Gets transaction statistics
    /// </summary>
    TransactionStats Stats { get; }

    /// <summary>
    /// Begins a new transaction
    /// </summary>
    /// <param name="name">Transaction name</param>
    /// <param name="document">Document to operate on</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Transaction scope</returns>
    Task<ITransactionScope> BeginTransactionAsync(
        string name, 
        object? document = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Begins a new sub-transaction within the current transaction
    /// </summary>
    /// <param name="name">Sub-transaction name</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Sub-transaction scope</returns>
    Task<ITransactionScope> BeginSubTransactionAsync(
        string name,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Begins a new transaction group for multiple related transactions
    /// </summary>
    /// <param name="name">Group name</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Transaction group scope</returns>
    Task<ITransactionGroup> BeginTransactionGroupAsync(
        string name,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Executes an action within a transaction
    /// </summary>
    /// <typeparam name="T">Return type</typeparam>
    /// <param name="name">Transaction name</param>
    /// <param name="action">Action to execute</param>
    /// <param name="document">Document to operate on</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Action result</returns>
    Task<T> ExecuteInTransactionAsync<T>(
        string name,
        Func<Task<T>> action,
        object? document = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Executes an action within a transaction without return value
    /// </summary>
    /// <param name="name">Transaction name</param>
    /// <param name="action">Action to execute</param>
    /// <param name="document">Document to operate on</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the operation</returns>
    Task ExecuteInTransactionAsync(
        string name,
        Func<Task> action,
        object? document = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Forces commit of the current transaction
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the commit</returns>
    Task ForceCommitAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Forces rollback of the current transaction
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the rollback</returns>
    Task ForceRollbackAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Sets the transaction failure handling mode
    /// </summary>
    /// <param name="mode">Failure handling mode</param>
    void SetFailureHandlingMode(TransactionFailureHandlingMode mode);

    /// <summary>
    /// Registers a transaction failure handler
    /// </summary>
    /// <param name="handler">Failure handler</param>
    /// <returns>Handler registration</returns>
    IDisposable RegisterFailureHandler(ITransactionFailureHandler handler);
}

/// <summary>
/// Represents a transaction scope that manages transaction lifecycle
/// </summary>
public interface ITransactionScope : IAsyncDisposable
{
    /// <summary>
    /// Gets the transaction information
    /// </summary>
    ITransactionInfo TransactionInfo { get; }

    /// <summary>
    /// Gets a value indicating whether the transaction was committed
    /// </summary>
    bool IsCommitted { get; }

    /// <summary>
    /// Gets a value indicating whether the transaction was rolled back
    /// </summary>
    bool IsRolledBack { get; }

    /// <summary>
    /// Commits the transaction
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the commit</returns>
    Task CommitAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Rolls back the transaction
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the rollback</returns>
    Task RollbackAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Represents a transaction group that can contain multiple transactions
/// </summary>
public interface ITransactionGroup : IAsyncDisposable
{
    /// <summary>
    /// Gets the group name
    /// </summary>
    string Name { get; }

    /// <summary>
    /// Gets the group ID
    /// </summary>
    string Id { get; }

    /// <summary>
    /// Gets the transactions in this group
    /// </summary>
    IReadOnlyList<ITransactionInfo> Transactions { get; }

    /// <summary>
    /// Gets a value indicating whether the group is committed
    /// </summary>
    bool IsCommitted { get; }

    /// <summary>
    /// Commits all transactions in the group
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the commit</returns>
    Task CommitAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Rolls back all transactions in the group
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Task representing the rollback</returns>
    Task RollbackAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Information about a transaction
/// </summary>
public interface ITransactionInfo
{
    /// <summary>
    /// Gets the transaction name
    /// </summary>
    string Name { get; }

    /// <summary>
    /// Gets the transaction ID
    /// </summary>
    string Id { get; }

    /// <summary>
    /// Gets the transaction type
    /// </summary>
    TransactionType Type { get; }

    /// <summary>
    /// Gets the transaction status
    /// </summary>
    TransactionStatus Status { get; }

    /// <summary>
    /// Gets the start time
    /// </summary>
    DateTime StartTime { get; }

    /// <summary>
    /// Gets the end time (if completed)
    /// </summary>
    DateTime? EndTime { get; }

    /// <summary>
    /// Gets the duration
    /// </summary>
    TimeSpan Duration { get; }

    /// <summary>
    /// Gets the document the transaction operates on
    /// </summary>
    object? Document { get; }

    /// <summary>
    /// Gets the parent transaction (for sub-transactions)
    /// </summary>
    ITransactionInfo? Parent { get; }

    /// <summary>
    /// Gets any error that occurred
    /// </summary>
    Exception? Error { get; }

    /// <summary>
    /// Gets transaction metadata
    /// </summary>
    Dictionary<string, object> Metadata { get; }
}

/// <summary>
/// Handles transaction failures
/// </summary>
public interface ITransactionFailureHandler
{
    /// <summary>
    /// Handles a transaction failure
    /// </summary>
    /// <param name="transaction">Failed transaction</param>
    /// <param name="exception">Failure exception</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Failure handling result</returns>
    Task<TransactionFailureHandlingResult> HandleFailureAsync(
        ITransactionInfo transaction,
        Exception exception,
        CancellationToken cancellationToken = default);
}

/// <summary>
/// Transaction types
/// </summary>
public enum TransactionType
{
    Regular,
    SubTransaction,
    ReadOnly
}

/// <summary>
/// Transaction status
/// </summary>
public enum TransactionStatus
{
    Active,
    Committed,
    RolledBack,
    Failed
}

/// <summary>
/// Transaction failure handling modes
/// </summary>
public enum TransactionFailureHandlingMode
{
    /// <summary>
    /// Automatically rollback on failure
    /// </summary>
    AutoRollback,

    /// <summary>
    /// Let custom failure handlers decide
    /// </summary>
    CustomHandler,

    /// <summary>
    /// Throw exceptions on failure
    /// </summary>
    ThrowException
}

/// <summary>
/// Result of transaction failure handling
/// </summary>
public enum TransactionFailureHandlingResult
{
    /// <summary>
    /// Rollback the transaction
    /// </summary>
    Rollback,

    /// <summary>
    /// Retry the transaction
    /// </summary>
    Retry,

    /// <summary>
    /// Continue despite the failure
    /// </summary>
    Continue,

    /// <summary>
    /// Propagate the exception
    /// </summary>
    Propagate
}

/// <summary>
/// Transaction manager statistics
/// </summary>
public class TransactionStats
{
    /// <summary>
    /// Gets or sets the total number of transactions started
    /// </summary>
    public long TotalTransactions { get; set; }

    /// <summary>
    /// Gets or sets the number of committed transactions
    /// </summary>
    public long CommittedTransactions { get; set; }

    /// <summary>
    /// Gets or sets the number of rolled back transactions
    /// </summary>
    public long RolledBackTransactions { get; set; }

    /// <summary>
    /// Gets or sets the number of failed transactions
    /// </summary>
    public long FailedTransactions { get; set; }

    /// <summary>
    /// Gets or sets the average transaction duration
    /// </summary>
    public TimeSpan AverageTransactionDuration { get; set; }

    /// <summary>
    /// Gets or sets the number of active transactions
    /// </summary>
    public int ActiveTransactions { get; set; }

    /// <summary>
    /// Gets or sets the peak concurrent transactions
    /// </summary>
    public int PeakConcurrentTransactions { get; set; }

    /// <summary>
    /// Gets or sets the last reset time
    /// </summary>
    public DateTime LastReset { get; set; }
}