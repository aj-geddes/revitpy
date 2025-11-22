using System.Collections.Concurrent;
using System.Diagnostics;
using Microsoft.Extensions.Logging;
using RevitPy.Core.Exceptions;

namespace RevitPy.Bridge;

/// <summary>
/// High-performance transaction manager with nested transaction support and comprehensive error handling
/// </summary>
public class TransactionManager : ITransactionManager
{
    private readonly ILogger<TransactionManager> _logger;
    private readonly ConcurrentDictionary<string, ITransactionScope> _activeTransactions;
    private readonly ConcurrentQueue<ITransactionInfo> _transactionHistory;
    private readonly List<ITransactionFailureHandler> _failureHandlers;
    private readonly object _failureHandlersLock = new();
    private readonly TransactionStats _stats;
    private readonly object _statsLock = new();
    private TransactionFailureHandlingMode _failureHandlingMode;

    [ThreadStatic]
    private static Stack<TransactionScope>? _transactionStack;

    public TransactionManager(ILogger<TransactionManager> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _activeTransactions = new ConcurrentDictionary<string, ITransactionScope>();
        _transactionHistory = new ConcurrentQueue<ITransactionInfo>();
        _failureHandlers = new List<ITransactionFailureHandler>();
        _stats = new TransactionStats { LastReset = DateTime.UtcNow };
        _failureHandlingMode = TransactionFailureHandlingMode.AutoRollback;
    }

    /// <inheritdoc/>
    public bool HasActiveTransaction => CurrentTransactionStack.Count > 0;

    /// <inheritdoc/>
    public ITransactionInfo? ActiveTransaction => CurrentTransactionStack.Count > 0
        ? CurrentTransactionStack.Peek().TransactionInfo
        : null;

    /// <inheritdoc/>
    public TransactionStats Stats
    {
        get
        {
            lock (_statsLock)
            {
                return new TransactionStats
                {
                    TotalTransactions = _stats.TotalTransactions,
                    CommittedTransactions = _stats.CommittedTransactions,
                    RolledBackTransactions = _stats.RolledBackTransactions,
                    FailedTransactions = _stats.FailedTransactions,
                    AverageTransactionDuration = _stats.AverageTransactionDuration,
                    ActiveTransactions = _activeTransactions.Count,
                    PeakConcurrentTransactions = _stats.PeakConcurrentTransactions,
                    LastReset = _stats.LastReset
                };
            }
        }
    }

    /// <inheritdoc/>
    public async Task<ITransactionScope> BeginTransactionAsync(string name, object? document = null, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(name);

        try
        {
            var transactionId = Guid.NewGuid().ToString();
            var transactionInfo = new TransactionInfo
            {
                Id = transactionId,
                Name = name,
                Type = TransactionType.Regular,
                Status = TransactionStatus.Active,
                StartTime = DateTime.UtcNow,
                Document = document,
                Metadata = new Dictionary<string, object>()
            };

            var scope = new TransactionScope(this, transactionInfo, _logger);
            _activeTransactions[transactionId] = scope;
            CurrentTransactionStack.Push(scope);

            UpdateStats(statsAction: s => { s.TotalTransactions++; s.ActiveTransactions++; });

            _logger.LogInformation("Started transaction {TransactionId} '{TransactionName}'",
                transactionId, name);

            return scope;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to begin transaction '{TransactionName}'", name);
            throw new RevitApiException($"Failed to begin transaction '{name}': {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<ITransactionScope> BeginSubTransactionAsync(string name, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(name);

        if (!HasActiveTransaction)
            throw new InvalidOperationException("Cannot begin sub-transaction without an active parent transaction");

        try
        {
            var parentTransaction = ActiveTransaction!;
            var transactionId = Guid.NewGuid().ToString();

            var transactionInfo = new TransactionInfo
            {
                Id = transactionId,
                Name = name,
                Type = TransactionType.SubTransaction,
                Status = TransactionStatus.Active,
                StartTime = DateTime.UtcNow,
                Document = parentTransaction.Document,
                Parent = parentTransaction,
                Metadata = new Dictionary<string, object>()
            };

            var scope = new TransactionScope(this, transactionInfo, _logger);
            _activeTransactions[transactionId] = scope;
            CurrentTransactionStack.Push(scope);

            UpdateStats(statsAction: s => { s.TotalTransactions++; s.ActiveTransactions++; });

            _logger.LogInformation("Started sub-transaction {TransactionId} '{TransactionName}' under parent {ParentId}",
                transactionId, name, parentTransaction.Id);

            return scope;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to begin sub-transaction '{TransactionName}'", name);
            throw new RevitApiException($"Failed to begin sub-transaction '{name}': {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<ITransactionGroup> BeginTransactionGroupAsync(string name, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(name);

        try
        {
            var groupId = Guid.NewGuid().ToString();
            var group = new TransactionGroup(groupId, name, _logger);

            _logger.LogInformation("Started transaction group {GroupId} '{GroupName}'", groupId, name);

            return group;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to begin transaction group '{GroupName}'", name);
            throw new RevitApiException($"Failed to begin transaction group '{name}': {ex.Message}", ex);
        }
    }

    /// <inheritdoc/>
    public async Task<T> ExecuteInTransactionAsync<T>(
        string name,
        Func<Task<T>> action,
        object? document = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(name);
        ArgumentNullException.ThrowIfNull(action);

        using var transaction = await BeginTransactionAsync(name, document, cancellationToken);

        try
        {
            var result = await action();
            await transaction.CommitAsync(cancellationToken);
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Transaction '{TransactionName}' failed, attempting rollback", name);
            await HandleTransactionFailure(transaction.TransactionInfo, ex, cancellationToken);
            throw;
        }
    }

    /// <inheritdoc/>
    public async Task ExecuteInTransactionAsync(
        string name,
        Func<Task> action,
        object? document = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(name);
        ArgumentNullException.ThrowIfNull(action);

        using var transaction = await BeginTransactionAsync(name, document, cancellationToken);

        try
        {
            await action();
            await transaction.CommitAsync(cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Transaction '{TransactionName}' failed, attempting rollback", name);
            await HandleTransactionFailure(transaction.TransactionInfo, ex, cancellationToken);
            throw;
        }
    }

    /// <inheritdoc/>
    public async Task ForceCommitAsync(CancellationToken cancellationToken = default)
    {
        if (!HasActiveTransaction)
            throw new InvalidOperationException("No active transaction to commit");

        var currentTransaction = CurrentTransactionStack.Peek();
        await currentTransaction.CommitAsync(cancellationToken);
    }

    /// <inheritdoc/>
    public async Task ForceRollbackAsync(CancellationToken cancellationToken = default)
    {
        if (!HasActiveTransaction)
            throw new InvalidOperationException("No active transaction to rollback");

        var currentTransaction = CurrentTransactionStack.Peek();
        await currentTransaction.RollbackAsync(cancellationToken);
    }

    /// <inheritdoc/>
    public void SetFailureHandlingMode(TransactionFailureHandlingMode mode)
    {
        _failureHandlingMode = mode;
        _logger.LogInformation("Transaction failure handling mode set to {Mode}", mode);
    }

    /// <inheritdoc/>
    public IDisposable RegisterFailureHandler(ITransactionFailureHandler handler)
    {
        ArgumentNullException.ThrowIfNull(handler);

        lock (_failureHandlersLock)
        {
            _failureHandlers.Add(handler);
        }

        _logger.LogInformation("Registered transaction failure handler {HandlerType}",
            handler.GetType().Name);

        return new FailureHandlerRegistration(() =>
        {
            lock (_failureHandlersLock)
            {
                _failureHandlers.Remove(handler);
            }
        });
    }

    internal async Task CompleteTransactionAsync(TransactionScope scope, bool committed, CancellationToken cancellationToken)
    {
        try
        {
            var transactionInfo = (TransactionInfo)scope.TransactionInfo;
            transactionInfo.EndTime = DateTime.UtcNow;
            transactionInfo.Status = committed ? TransactionStatus.Committed : TransactionStatus.RolledBack;

            // Remove from active transactions
            _activeTransactions.TryRemove(transactionInfo.Id, out _);

            // Remove from transaction stack
            if (CurrentTransactionStack.Count > 0 && CurrentTransactionStack.Peek() == scope)
            {
                CurrentTransactionStack.Pop();
            }

            // Add to history
            _transactionHistory.Enqueue(transactionInfo);

            // Trim history if it gets too large
            while (_transactionHistory.Count > 1000)
            {
                _transactionHistory.TryDequeue(out _);
            }

            // Update statistics
            UpdateStats(statsAction: s =>
            {
                s.ActiveTransactions--;
                if (committed)
                    s.CommittedTransactions++;
                else
                    s.RolledBackTransactions++;

                // Update average duration
                var duration = transactionInfo.Duration;
                var totalDuration = s.AverageTransactionDuration.Ticks * (s.TotalTransactions - 1) + duration.Ticks;
                s.AverageTransactionDuration = new TimeSpan(totalDuration / s.TotalTransactions);
            });

            _logger.LogInformation("Completed transaction {TransactionId} '{TransactionName}' - {Status} in {Duration}ms",
                transactionInfo.Id, transactionInfo.Name, transactionInfo.Status,
                transactionInfo.Duration.TotalMilliseconds);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error completing transaction {TransactionId}", scope.TransactionInfo.Id);
        }
    }

    internal async Task HandleTransactionFailure(ITransactionInfo transaction, Exception exception, CancellationToken cancellationToken)
    {
        var transactionInfo = (TransactionInfo)transaction;
        transactionInfo.Error = exception;
        transactionInfo.Status = TransactionStatus.Failed;

        UpdateStats(statsAction: s => s.FailedTransactions++);

        _logger.LogError(exception, "Transaction {TransactionId} '{TransactionName}' failed",
            transaction.Id, transaction.Name);

        try
        {
            switch (_failureHandlingMode)
            {
                case TransactionFailureHandlingMode.AutoRollback:
                    await AutoRollbackTransaction(transaction, cancellationToken);
                    break;

                case TransactionFailureHandlingMode.CustomHandler:
                    await ExecuteCustomFailureHandlers(transaction, exception, cancellationToken);
                    break;

                case TransactionFailureHandlingMode.ThrowException:
                    // Exception will be re-thrown by caller
                    break;
            }
        }
        catch (Exception handlerException)
        {
            _logger.LogError(handlerException, "Error handling transaction failure for {TransactionId}",
                transaction.Id);
        }
    }

    private static Stack<TransactionScope> CurrentTransactionStack
    {
        get
        {
            _transactionStack ??= new Stack<TransactionScope>();
            return _transactionStack;
        }
    }

    private async Task AutoRollbackTransaction(ITransactionInfo transaction, CancellationToken cancellationToken)
    {
        try
        {
            if (_activeTransactions.TryGetValue(transaction.Id, out var scope))
            {
                await scope.RollbackAsync(cancellationToken);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to auto-rollback transaction {TransactionId}", transaction.Id);
        }
    }

    private async Task ExecuteCustomFailureHandlers(ITransactionInfo transaction, Exception exception, CancellationToken cancellationToken)
    {
        List<ITransactionFailureHandler> handlers;
        lock (_failureHandlersLock)
        {
            handlers = new List<ITransactionFailureHandler>(_failureHandlers);
        }

        foreach (var handler in handlers)
        {
            try
            {
                var result = await handler.HandleFailureAsync(transaction, exception, cancellationToken);

                switch (result)
                {
                    case TransactionFailureHandlingResult.Rollback:
                        await AutoRollbackTransaction(transaction, cancellationToken);
                        return;

                    case TransactionFailureHandlingResult.Retry:
                        // Retry logic would need to be implemented by caller
                        _logger.LogInformation("Handler requested retry for transaction {TransactionId}", transaction.Id);
                        return;

                    case TransactionFailureHandlingResult.Continue:
                        _logger.LogInformation("Handler requested continue for transaction {TransactionId}", transaction.Id);
                        return;

                    case TransactionFailureHandlingResult.Propagate:
                        // Exception will be re-thrown by caller
                        return;
                }
            }
            catch (Exception handlerEx)
            {
                _logger.LogError(handlerEx, "Transaction failure handler {HandlerType} threw exception",
                    handler.GetType().Name);
            }
        }
    }

    private void UpdateStats(Action<TransactionStats> statsAction)
    {
        lock (_statsLock)
        {
            statsAction(_stats);

            if (_stats.ActiveTransactions > _stats.PeakConcurrentTransactions)
            {
                _stats.PeakConcurrentTransactions = _stats.ActiveTransactions;
            }
        }
    }

    private class FailureHandlerRegistration : IDisposable
    {
        private readonly Action _unregister;
        private bool _disposed;

        public FailureHandlerRegistration(Action unregister)
        {
            _unregister = unregister ?? throw new ArgumentNullException(nameof(unregister));
        }

        public void Dispose()
        {
            if (!_disposed)
            {
                _unregister();
                _disposed = true;
            }
        }
    }
}

/// <summary>
/// Implementation of transaction scope with automatic cleanup
/// </summary>
public class TransactionScope : ITransactionScope
{
    private readonly TransactionManager _manager;
    private readonly ILogger _logger;
    private bool _disposed;
    private bool _completed;

    public TransactionScope(TransactionManager manager, ITransactionInfo transactionInfo, ILogger logger)
    {
        _manager = manager ?? throw new ArgumentNullException(nameof(manager));
        TransactionInfo = transactionInfo ?? throw new ArgumentNullException(nameof(transactionInfo));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc/>
    public ITransactionInfo TransactionInfo { get; }

    /// <inheritdoc/>
    public bool IsCommitted { get; private set; }

    /// <inheritdoc/>
    public bool IsRolledBack { get; private set; }

    /// <inheritdoc/>
    public async Task CommitAsync(CancellationToken cancellationToken = default)
    {
        if (_disposed)
            throw new ObjectDisposedException(nameof(TransactionScope));

        if (_completed)
            throw new InvalidOperationException("Transaction has already been completed");

        try
        {
            // Perform actual Revit API commit here
            // This would integrate with the actual Revit Transaction API

            IsCommitted = true;
            _completed = true;
            await _manager.CompleteTransactionAsync(this, true, cancellationToken);
        }
        catch (Exception ex)
        {
            await _manager.HandleTransactionFailure(TransactionInfo, ex, cancellationToken);
            throw;
        }
    }

    /// <inheritdoc/>
    public async Task RollbackAsync(CancellationToken cancellationToken = default)
    {
        if (_disposed)
            throw new ObjectDisposedException(nameof(TransactionScope));

        if (_completed)
            throw new InvalidOperationException("Transaction has already been completed");

        try
        {
            // Perform actual Revit API rollback here
            // This would integrate with the actual Revit Transaction API

            IsRolledBack = true;
            _completed = true;
            await _manager.CompleteTransactionAsync(this, false, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during transaction rollback for {TransactionId}", TransactionInfo.Id);
            throw;
        }
    }

    /// <inheritdoc/>
    public async ValueTask DisposeAsync()
    {
        if (!_disposed)
        {
            if (!_completed)
            {
                try
                {
                    // Auto-rollback if not explicitly committed
                    await RollbackAsync();
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error during auto-rollback in dispose for {TransactionId}",
                        TransactionInfo.Id);
                }
            }

            _disposed = true;
        }
    }
}

/// <summary>
/// Implementation of transaction group
/// </summary>
public class TransactionGroup : ITransactionGroup
{
    private readonly ILogger _logger;
    private readonly List<ITransactionInfo> _transactions;
    private bool _disposed;
    private bool _completed;

    public TransactionGroup(string id, string name, ILogger logger)
    {
        Id = id ?? throw new ArgumentNullException(nameof(id));
        Name = name ?? throw new ArgumentNullException(nameof(name));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _transactions = new List<ITransactionInfo>();
    }

    /// <inheritdoc/>
    public string Name { get; }

    /// <inheritdoc/>
    public string Id { get; }

    /// <inheritdoc/>
    public IReadOnlyList<ITransactionInfo> Transactions => _transactions.AsReadOnly();

    /// <inheritdoc/>
    public bool IsCommitted { get; private set; }

    /// <inheritdoc/>
    public async Task CommitAsync(CancellationToken cancellationToken = default)
    {
        if (_disposed)
            throw new ObjectDisposedException(nameof(TransactionGroup));

        if (_completed)
            throw new InvalidOperationException("Transaction group has already been completed");

        try
        {
            // Commit all transactions in the group
            // This would integrate with the actual Revit TransactionGroup API

            IsCommitted = true;
            _completed = true;

            _logger.LogInformation("Committed transaction group {GroupId} '{GroupName}' with {TransactionCount} transactions",
                Id, Name, _transactions.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to commit transaction group {GroupId}", Id);
            throw;
        }
    }

    /// <inheritdoc/>
    public async Task RollbackAsync(CancellationToken cancellationToken = default)
    {
        if (_disposed)
            throw new ObjectDisposedException(nameof(TransactionGroup));

        try
        {
            // Rollback all transactions in the group
            // This would integrate with the actual Revit TransactionGroup API

            _completed = true;

            _logger.LogInformation("Rolled back transaction group {GroupId} '{GroupName}' with {TransactionCount} transactions",
                Id, Name, _transactions.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to rollback transaction group {GroupId}", Id);
            throw;
        }
    }

    /// <inheritdoc/>
    public async ValueTask DisposeAsync()
    {
        if (!_disposed)
        {
            if (!_completed)
            {
                try
                {
                    await RollbackAsync();
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error during auto-rollback in dispose for group {GroupId}", Id);
                }
            }

            _disposed = true;
        }
    }
}

/// <summary>
/// Implementation of transaction information
/// </summary>
public class TransactionInfo : ITransactionInfo
{
    /// <inheritdoc/>
    public string Name { get; set; } = string.Empty;

    /// <inheritdoc/>
    public string Id { get; set; } = string.Empty;

    /// <inheritdoc/>
    public TransactionType Type { get; set; }

    /// <inheritdoc/>
    public TransactionStatus Status { get; set; }

    /// <inheritdoc/>
    public DateTime StartTime { get; set; }

    /// <inheritdoc/>
    public DateTime? EndTime { get; set; }

    /// <inheritdoc/>
    public TimeSpan Duration => EndTime.HasValue ? EndTime.Value - StartTime : DateTime.UtcNow - StartTime;

    /// <inheritdoc/>
    public object? Document { get; set; }

    /// <inheritdoc/>
    public ITransactionInfo? Parent { get; set; }

    /// <inheritdoc/>
    public Exception? Error { get; set; }

    /// <inheritdoc/>
    public Dictionary<string, object> Metadata { get; set; } = new();
}
