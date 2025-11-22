"""
Transaction management with context managers and batch operations.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import uuid4

from loguru import logger

from .exceptions import TransactionError


class TransactionStatus(Enum):
    """Transaction status enumeration."""

    NOT_STARTED = "not_started"
    STARTED = "started"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class TransactionOptions:
    """Options for transaction configuration."""

    name: str | None = None
    description: str | None = None
    auto_commit: bool = True
    timeout_seconds: float | None = None
    retry_count: int = 0
    retry_delay: float = 1.0
    suppress_warnings: bool = False

    def __post_init__(self) -> None:
        if self.name is None:
            self.name = f"Transaction_{uuid4().hex[:8]}"


class ITransactionProvider(ABC):
    """Abstract interface for transaction providers."""

    @abstractmethod
    def start_transaction(self, name: str) -> Any:
        """Start a new transaction."""
        pass

    @abstractmethod
    def commit_transaction(self, transaction: Any) -> bool:
        """Commit a transaction."""
        pass

    @abstractmethod
    def rollback_transaction(self, transaction: Any) -> bool:
        """Rollback a transaction."""
        pass

    @abstractmethod
    def is_in_transaction(self) -> bool:
        """Check if currently in a transaction."""
        pass


class Transaction:
    """
    Pythonic transaction wrapper with context manager support.
    """

    def __init__(
        self, provider: ITransactionProvider, options: TransactionOptions | None = None
    ) -> None:
        self._provider = provider
        self._options = options or TransactionOptions()
        self._transaction: Any | None = None
        self._status = TransactionStatus.NOT_STARTED
        self._operations: list[Callable] = []
        self._rollback_handlers: list[Callable] = []
        self._commit_handlers: list[Callable] = []
        self._start_time: float | None = None
        self._end_time: float | None = None

    @property
    def name(self) -> str:
        """Get transaction name."""
        return self._options.name or "Unknown"

    @property
    def status(self) -> TransactionStatus:
        """Get transaction status."""
        return self._status

    @property
    def is_active(self) -> bool:
        """Check if transaction is active."""
        return self._status == TransactionStatus.STARTED

    @property
    def duration(self) -> float | None:
        """Get transaction duration in seconds."""
        if self._start_time is None:
            return None

        end_time = self._end_time or asyncio.get_event_loop().time()
        return end_time - self._start_time

    def add_operation(self, operation: Callable) -> None:
        """Add an operation to be executed in this transaction."""
        if not self.is_active:
            raise TransactionError("Cannot add operation to inactive transaction")

        self._operations.append(operation)

    def add_rollback_handler(self, handler: Callable) -> None:
        """Add a rollback handler."""
        self._rollback_handlers.append(handler)

    def add_commit_handler(self, handler: Callable) -> None:
        """Add a commit handler."""
        self._commit_handlers.append(handler)

    def start(self) -> None:
        """Start the transaction."""
        if self._status != TransactionStatus.NOT_STARTED:
            raise TransactionError(
                f"Transaction already started with status: {self._status}"
            )

        try:
            self._start_time = asyncio.get_event_loop().time()
            self._transaction = self._provider.start_transaction(self.name)
            self._status = TransactionStatus.STARTED

            logger.debug(f"Started transaction: {self.name}")

        except Exception as e:
            self._status = TransactionStatus.FAILED
            logger.error(f"Failed to start transaction {self.name}: {e}")
            raise TransactionError(f"Failed to start transaction: {e}", self.name, e)

    def commit(self) -> None:
        """Commit the transaction."""
        if self._status != TransactionStatus.STARTED:
            raise TransactionError(
                f"Cannot commit transaction with status: {self._status}"
            )

        try:
            # Execute pending operations
            for operation in self._operations:
                try:
                    operation()
                except Exception as e:
                    logger.error(f"Operation failed in transaction {self.name}: {e}")
                    self.rollback()
                    raise TransactionError(f"Operation failed: {e}", self.name, e)

            # Commit the transaction
            success = self._provider.commit_transaction(self._transaction)
            if not success:
                raise TransactionError(
                    "Provider failed to commit transaction", self.name
                )

            self._status = TransactionStatus.COMMITTED
            self._end_time = asyncio.get_event_loop().time()

            # Execute commit handlers
            for handler in self._commit_handlers:
                try:
                    handler()
                except Exception as e:
                    logger.warning(
                        f"Commit handler failed for transaction {self.name}: {e}"
                    )

            logger.debug(
                f"Committed transaction: {self.name} (duration: {self.duration:.3f}s)"
            )

        except Exception:
            if self._status == TransactionStatus.STARTED:
                self.rollback()
            raise

    def rollback(self) -> None:
        """Rollback the transaction."""
        if self._status not in (TransactionStatus.STARTED, TransactionStatus.FAILED):
            logger.warning(
                f"Attempting to rollback transaction with status: {self._status}"
            )
            return

        try:
            if self._transaction:
                success = self._provider.rollback_transaction(self._transaction)
                if not success:
                    logger.error(f"Provider failed to rollback transaction {self.name}")

            self._status = TransactionStatus.ROLLED_BACK
            self._end_time = asyncio.get_event_loop().time()

            # Execute rollback handlers
            for handler in self._rollback_handlers:
                try:
                    handler()
                except Exception as e:
                    logger.warning(
                        f"Rollback handler failed for transaction {self.name}: {e}"
                    )

            logger.debug(f"Rolled back transaction: {self.name}")

        except Exception as e:
            self._status = TransactionStatus.FAILED
            logger.error(f"Failed to rollback transaction {self.name}: {e}")
            raise TransactionError(f"Failed to rollback transaction: {e}", self.name, e)

    def __enter__(self) -> Transaction:
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Context manager exit."""
        try:
            if exc_type is None and self._options.auto_commit:
                self.commit()
            else:
                self.rollback()
        except Exception as e:
            logger.error(f"Error in transaction exit: {e}")
            raise

        # Don't suppress exceptions
        return False

    async def __aenter__(self) -> Transaction:
        """Async context manager entry."""
        self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Async context manager exit."""
        try:
            if exc_type is None and self._options.auto_commit:
                self.commit()
            else:
                self.rollback()
        except Exception as e:
            logger.error(f"Error in async transaction exit: {e}")
            raise

        # Don't suppress exceptions
        return False


class TransactionGroup:
    """
    Group of transactions that are managed together.
    """

    def __init__(self, provider: ITransactionProvider, name: str | None = None) -> None:
        self._provider = provider
        self._name = name or f"TransactionGroup_{uuid4().hex[:8]}"
        self._transactions: list[Transaction] = []
        self._status = TransactionStatus.NOT_STARTED

    @property
    def name(self) -> str:
        """Get transaction group name."""
        return self._name

    @property
    def status(self) -> TransactionStatus:
        """Get transaction group status."""
        return self._status

    def add_transaction(self, options: TransactionOptions | None = None) -> Transaction:
        """Add a new transaction to the group."""
        if self._status != TransactionStatus.NOT_STARTED:
            raise TransactionError("Cannot add transaction to started group")

        transaction_options = options or TransactionOptions(auto_commit=False)
        transaction = Transaction(self._provider, transaction_options)
        self._transactions.append(transaction)

        return transaction

    def start_all(self) -> None:
        """Start all transactions in the group."""
        if self._status != TransactionStatus.NOT_STARTED:
            raise TransactionError("Transaction group already started")

        self._status = TransactionStatus.STARTED

        try:
            for transaction in self._transactions:
                transaction.start()

            logger.debug(
                f"Started transaction group: {self.name} ({len(self._transactions)} transactions)"
            )

        except Exception as e:
            self.rollback_all()
            raise TransactionError(
                f"Failed to start transaction group: {e}", self.name, e
            )

    def commit_all(self) -> None:
        """Commit all transactions in the group."""
        if self._status != TransactionStatus.STARTED:
            raise TransactionError("Transaction group not started")

        committed_transactions = []

        try:
            for transaction in self._transactions:
                transaction.commit()
                committed_transactions.append(transaction)

            self._status = TransactionStatus.COMMITTED
            logger.debug(f"Committed transaction group: {self.name}")

        except Exception as e:
            # Rollback committed transactions
            for transaction in committed_transactions:
                try:
                    transaction.rollback()
                except Exception as rollback_error:
                    logger.error(
                        f"Failed to rollback transaction during group commit failure: {rollback_error}"
                    )

            self._status = TransactionStatus.FAILED
            raise TransactionError(
                f"Failed to commit transaction group: {e}", self.name, e
            )

    def rollback_all(self) -> None:
        """Rollback all transactions in the group."""
        if self._status not in (TransactionStatus.STARTED, TransactionStatus.FAILED):
            return

        for transaction in self._transactions:
            try:
                transaction.rollback()
            except Exception as e:
                logger.error(
                    f"Failed to rollback transaction in group {self.name}: {e}"
                )

        self._status = TransactionStatus.ROLLED_BACK
        logger.debug(f"Rolled back transaction group: {self.name}")

    def __enter__(self) -> TransactionGroup:
        """Context manager entry."""
        self.start_all()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Context manager exit."""
        try:
            if exc_type is None:
                self.commit_all()
            else:
                self.rollback_all()
        except Exception as e:
            logger.error(f"Error in transaction group exit: {e}")
            raise

        return False

    async def __aenter__(self) -> TransactionGroup:
        """Async context manager entry."""
        self.start_all()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Async context manager exit."""
        try:
            if exc_type is None:
                self.commit_all()
            else:
                self.rollback_all()
        except Exception as e:
            logger.error(f"Error in async transaction group exit: {e}")
            raise

        return False


# Convenience functions for common transaction patterns


def transaction(
    provider: ITransactionProvider,
    name: str | None = None,
    auto_commit: bool = True,
    retry_count: int = 0,
    retry_delay: float = 1.0,
) -> Transaction:
    """Create a transaction with common options."""
    options = TransactionOptions(
        name=name,
        auto_commit=auto_commit,
        retry_count=retry_count,
        retry_delay=retry_delay,
    )
    return Transaction(provider, options)


@contextmanager
def transaction_scope(
    provider: ITransactionProvider, name: str | None = None, **kwargs
) -> Iterator[Transaction]:
    """Context manager for transaction scope."""
    trans = transaction(provider, name, **kwargs)
    with trans:
        yield trans


@asynccontextmanager
async def async_transaction_scope(
    provider: ITransactionProvider, name: str | None = None, **kwargs
) -> AsyncIterator[Transaction]:
    """Async context manager for transaction scope."""
    trans = transaction(provider, name, **kwargs)
    async with trans:
        yield trans


def retry_transaction(
    provider: ITransactionProvider,
    operation: Callable[[], Any],
    max_retries: int = 3,
    delay: float = 1.0,
    name: str | None = None,
) -> Any:
    """Execute operation in transaction with automatic retry."""
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            with transaction_scope(provider, name):
                return operation()

        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(
                    f"Transaction attempt {attempt + 1} failed, retrying: {e}"
                )
                import time

                time.sleep(delay)
            else:
                logger.error(
                    f"Transaction failed after {max_retries + 1} attempts: {e}"
                )

    raise last_exception
