---
layout: page
title: Troubleshooting
description: Troubleshooting guide for RevitPy covering API and ORM exception hierarchies, common error messages, connection issues, and step-by-step fix solutions.
doc_tier: user
---

# Troubleshooting

This guide covers the exception classes in RevitPy and common issues you may encounter.

## API Exceptions

These exceptions are defined in `revitpy.api.exceptions`.

### RevitAPIError

The base exception for all RevitPy API errors.

```python
from revitpy.api.exceptions import RevitAPIError

try:
    api.open_document("nonexistent.rvt")
except RevitAPIError as e:
    print(e)           # Error message
    print(e.cause)     # Original exception, if any
```

**Attributes:**
- `cause` -- The underlying exception, or `None`.

### ConnectionError

Raised when RevitPy cannot connect to the Revit application or when an operation is attempted without a connection.

```python
from revitpy.api.exceptions import ConnectionError
```

**Common causes:**
- Calling `api.elements` or `api.transaction()` before calling `api.connect()`.
- Calling `api.connect()` without providing a Revit application object.
- The Revit application is not running or not accessible.

**Solutions:**
- Ensure `api.connect(revit_application)` is called before any operations.
- Verify that the Revit application object is valid and accessible.
- Use `api.is_connected` to check the connection status before operations.

### ElementNotFoundError

Raised when an element cannot be found by ID or when a parameter does not exist on an element.

```python
from revitpy.api.exceptions import ElementNotFoundError
```

**Attributes:**
- `element_id` -- The ID that was searched for.
- `element_type` -- The type name, if applicable.
- `cause` -- The underlying exception.

**Common causes:**
- Looking up an element by an ID that does not exist in the document.
- Accessing a parameter name that does not exist on the element.
- The element was deleted between the time its ID was obtained and the lookup.

**Solutions:**
- Use `api.get_element_by_id()` which returns `None` for missing elements instead of raising.
- Use `first_or_default()` instead of `first()` when the query may return no results.
- Verify parameter names match exactly (they are case-sensitive).

### TransactionError

Raised during transaction operations (start, commit, rollback).

```python
from revitpy.api.exceptions import TransactionError
```

**Attributes:**
- `transaction_name` -- Name of the transaction.
- `cause` -- The underlying exception.

**Common causes:**
- Attempting to start a transaction that has already been started.
- Committing a transaction that is not in the `STARTED` state.
- An operation failing inside a transaction, triggering a rollback.

**Solutions:**
- Use transactions as context managers (`with api.transaction(...)`) to ensure proper start/commit/rollback handling.
- Check `transaction.status` before calling `commit()` or `rollback()` manually.
- Use `retry_transaction()` for operations that may fail transiently.

### ValidationError

Raised when a parameter value fails validation.

```python
from revitpy.api.exceptions import ValidationError
```

**Attributes:**
- `field` -- The field/parameter name.
- `value` -- The invalid value.
- `cause` -- The underlying exception.

**Common causes:**
- Setting a parameter to a value that cannot be converted to the expected type (e.g., setting a numeric parameter to a non-numeric string).
- Setting a parameter that fails Revit-side validation.

**Solutions:**
- Verify the expected type before setting parameter values. Use `ParameterValue.storage_type` to check.
- Ensure values match the parameter's storage type (`String`, `Double`, `Integer`).

### PermissionError

Raised when attempting a disallowed operation, such as writing to a read-only parameter.

```python
from revitpy.api.exceptions import PermissionError
```

**Attributes:**
- `operation` -- The operation that was denied.

**Solutions:**
- Check `ParameterValue.is_read_only` before attempting to write.
- Use `ElementProperty.read_only` when defining custom property descriptors.

### ModelError

Raised when the model is in an invalid state, such as failing to create or open a document.

```python
from revitpy.api.exceptions import ModelError
```

**Common causes:**
- `open_document()` returns `None` from Revit.
- `create_document()` returns `None`.

**Solutions:**
- Verify the file path exists and is accessible.
- Ensure the template path is valid for `create_document()`.

## ORM Exceptions

These exceptions are defined in `revitpy.orm.exceptions`. They all inherit from `ORMException`.

### ORMException

Base exception for all ORM errors.

**Attributes:**
- `operation` -- The ORM operation that failed (e.g., `"save_changes"`, `"query"`, `"get_by_id"`).
- `entity_type` -- The entity type name, if applicable.
- `entity_id` -- The entity ID, if applicable.
- `cause` -- The underlying exception.

### QueryError

Raised when a query operation fails.

**Attributes:**
- `query_expression` -- String representation of the query.
- `query_operation` -- The operation that failed (e.g., `"first"`, `"single"`).
- `element_count` -- Number of elements found (useful for `single()` errors).

**Common causes:**
- Calling `first()` on an empty result set.
- Calling `single()` when zero or more than one element matches.
- An error in a predicate function.

**Solutions:**
- Use `first_or_default()` or `single_or_default()` when results may be empty.
- Verify predicates do not raise exceptions by testing them independently.

### RelationshipError

Raised when relationship loading or configuration fails.

**Attributes:**
- `relationship_name` -- The relationship that failed.
- `source_entity` -- The source entity.
- `target_entity` -- The target entity.

**Common causes:**
- Calling `load_relationship()` without a configured relationship manager.

**Solutions:**
- Call `context.configure_relationship()` before loading relationships.

### CacheError

Raised when cache operations fail.

**Attributes:**
- `cache_key` -- The cache key involved.
- `cache_operation` -- The cache operation that failed.

### ChangeTrackingError

Raised when change tracking operations fail.

**Attributes:**
- `entity` -- The entity involved.
- `property_name` -- The property name, if applicable.
- `tracking_operation` -- The operation that failed.

### LazyLoadingError

Raised when lazy loading of a property or relationship fails.

**Attributes:**
- `property_name` -- The property being loaded.
- `entity` -- The entity being loaded.

### AsyncOperationError

Raised when an async ORM operation fails.

**Attributes:**
- `async_operation` -- The async operation name.
- `task_id` -- The task ID, if applicable.

### BatchOperationError

Raised when a batch operation partially or fully fails.

**Attributes:**
- `batch_size` -- Total batch size.
- `failed_operations` -- List of failed operation details.
- `successful_operations` -- Number of operations that succeeded.

### ValidationError (ORM)

Raised when entity validation fails in the ORM layer.

**Attributes:**
- `validation_errors` -- Dictionary of field names to lists of error messages.
- `entity` -- The entity that failed validation.

### ConcurrencyError

Raised when concurrent modifications conflict.

**Attributes:**
- `entity` -- The entity with conflicts.
- `conflicting_changes` -- Dictionary of conflicting property changes.

### TransactionError (ORM)

Raised when ORM transaction operations fail.

**Attributes:**
- `transaction_id` -- The transaction ID.
- `transaction_state` -- The transaction state at the time of failure.
- `nested_level` -- The nesting level.

## Common Issues and Solutions

### "No active document" error

**Problem:** You see `ConnectionError: No active document` when calling `api.elements`, `api.query()`, or `api.transaction()`.

**Solution:** Open or create a document first:
```python
api.connect(revit_application)
api.open_document("path/to/project.rvt")
# Now api.active_document is set
```

### "RevitContext has been disposed" error

**Problem:** You see `ORMException: RevitContext has been disposed` when calling context methods.

**Solution:** The context was used after exiting a `with` block or after calling `dispose()`. Create a new context:
```python
# Wrong
with RevitContext(provider) as ctx:
    pass
ctx.query()  # Error: context is disposed

# Right
with RevitContext(provider) as ctx:
    ctx.query()  # Use inside the block
```

### Circular dependency in DI container

**Problem:** `RuntimeError: Circular dependency detected: A -> B -> A`

**Solution:** Refactor to break the cycle. Options include:
- Use a factory function that resolves one dependency lazily.
- Use `register_singleton` with a pre-created instance for one of the services.
- Restructure the dependency graph.

### "Service X is not registered" error

**Problem:** `ValueError: Service MyService is not registered` when calling `container.get_service()`.

**Solution:** Register the service before resolving it:
```python
container.register_singleton(MyService, instance=my_instance)
service = container.get_service(MyService)
```

### Event handler disabled after errors

**Problem:** An event handler stops executing after repeated failures.

**Solution:** The `@event_handler` decorator disables a handler after `max_errors` failures (default 10). Fix the underlying error, then either:
- Increase `max_errors` in the decorator.
- Re-register the handler.
- Use `@retry_on_error` to add retry logic.

### Slow queries

**Problem:** Queries take a long time to execute.

**Solution:**
- Add more specific filters to reduce the result set.
- Use `take()` to limit the number of results.
- Enable caching in the ORM context (`CachePolicy.MEMORY` or `CachePolicy.AGGRESSIVE`).
- For large datasets, use the ORM `as_streaming()` method for batch processing.
- Check `context.cache_statistics` to verify cache hit rates.

### Transaction timeout

**Problem:** A transaction times out before completing.

**Solution:**
- Increase `timeout_seconds` in `TransactionOptions`.
- Break large operations into smaller transactions using `TransactionGroup`.
- Use batch processing with `AsyncRevit.update_elements_async()` for bulk updates.
