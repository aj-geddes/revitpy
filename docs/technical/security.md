---
layout: page
title: Security
description: RevitPy security model covering Pydantic input validation, ruff security linting, thread safety, CI checks, cloud token management, and AI guardrails.
doc_tier: technical
---

# Security

This document covers RevitPy's security posture: input validation via Pydantic, security-focused linting rules, thread safety patterns, the exception hierarchy, and the CI security pipeline.

## Input Validation

### Pydantic v2 Validators

All ORM entity types inherit from `BaseElement` (in `revitpy/orm/validation.py`), which uses Pydantic v2 with `validate_assignment=True`. This means every attribute write -- not just construction -- passes through validation.

Key validation constraints enforced at the model level:

| Entity | Field | Constraint | Rationale |
|---|---|---|---|
| `BaseElement` | `name` | `max_length=1000`, whitespace stripped | Prevent oversized strings |
| `BaseElement` | `category` | `max_length=255`, whitespace stripped | Prevent oversized strings |
| `BaseElement` | `family_name` | `max_length=255` | Bound string length |
| `BaseElement` | `type_name` | `max_length=255` | Bound string length |
| `BaseElement` | `version` | `ge=1` | Prevent invalid versions |
| `WallElement` | `height`, `length`, `width` | `gt=0` | Reject non-positive dimensions |
| `WallElement` | `area`, `volume` | `ge=0` | Reject negative measurements |
| `WallElement` | `fire_rating` | `ge=0, le=4` | Bound to valid hour range |
| `RoomElement` | `number` | `min_length=1, max_length=50`, alphanumeric+`.-_` only | Prevent injection via room numbers |
| `RoomElement` | `area` | `ge=0` | Reject negative area |
| `RoomElement` | `temperature` | `ge=-50, le=150` | Fahrenheit range bounds |
| `RoomElement` | `humidity` | `ge=0, le=100` | Percentage bounds |
| `DoorElement` | `width`, `height` | `gt=0` | Reject non-positive dimensions |
| `DoorElement` | `fire_rating` | `ge=0, le=4` | Bound to valid hour range |
| `DoorElement` | `hand` | `pattern=^(Left\|Right)$` | Regex constraint |
| `WindowElement` | `width`, `height` | `gt=0` | Reject non-positive dimensions |
| `WindowElement` | `solar_heat_gain` | `ge=0, le=1` | SHGC coefficient range |
| `WindowElement` | `sound_transmission_class` | `ge=0, le=100` | STC rating range |

### Custom Validation Rules

The `ElementValidator` supports runtime-configurable validation rules via `ValidationRule` objects. Each rule specifies a `ConstraintType`:

- `REQUIRED` -- value must not be `None` or empty string.
- `MIN_VALUE` / `MAX_VALUE` -- numeric bounds.
- `MIN_LENGTH` / `MAX_LENGTH` -- string length bounds.
- `PATTERN` -- regex match via `re.match()`.
- `CUSTOM` -- reserved for user-defined logic.

Rules can be added and removed at runtime via `add_custom_rule()` and `remove_custom_rule()`.

### Type Safety Enforcement

The `TypeSafetyMixin` class (in `validation.py`) provides `ensure_type_safety(obj, expected_type)`, which:

1. Checks `isinstance(obj, expected_type)`.
2. If `obj` is a `dict` and `expected_type` is a `BaseElement` subclass, attempts `model_validate()` conversion.
3. If the object is a `BaseElement`, runs `assert_valid()` which raises `ORMValidationError` on failure.

### Parameter Value Validation

The `ParameterValue` model (in `api/element.py`) validates parameter values based on their `storage_type`:

- `Double` storage: attempts `float()` conversion, raises `ValidationError` on failure.
- `Integer` storage: attempts `int()` conversion, raises `ValidationError` on failure.

### Query Input Validation

`QueryBuilder` validates inputs at the method level:

- `skip(count)` -- raises `ValueError` if `count < 0`.
- `take(count)` -- raises `ValueError` if `count <= 0`.

The `ElementFilter` dataclass (in `orm/types.py`) validates that the `operator` field is one of a fixed set: `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `contains`, `startswith`, `endswith`, `in`, `not_in`, `is_null`, `is_not_null`, `regex`.

## Security Linting (Ruff S Rules)

RevitPy's ruff configuration (in `pyproject.toml`) includes the `S` rule set (flake8-bandit security rules):

```toml
[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "B", "C4", "UP",
    "S",  # flake8-bandit security rules
]
```

### What the S Rules Check

The flake8-bandit rules flag potential security issues including:

| Rule | Category | Example |
|---|---|---|
| `S101` | Assert usage | `assert` statements (disabled in test files) |
| `S105`, `S106` | Hardcoded passwords | Password strings in code (disabled in test files) |
| `S110` | try-except-pass | Silently swallowing exceptions (explicitly ignored project-wide) |
| `S112` | try-except-continue | Silently continuing past exceptions (explicitly ignored) |
| `S311` | Pseudo-random generators | Weak random number generation (disabled for proof-of-concepts) |
| `S324` | Insecure hash functions | Use of MD5/SHA1 for security purposes |
| `S603` | subprocess calls | Subprocess invocations (explicitly ignored) |
| `S607` | Partial executable paths | Incomplete paths in subprocess (explicitly ignored) |

### Per-File Overrides

From `pyproject.toml`:

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**/*" = ["S101", "D", "F401", "E402"]
"**/tests/**/*" = ["S101", "S105", "S106", "D", "F401", "E402"]
"revitpy-package-manager/**/*" = ["F401", "E402", "F403", "F405", "S"]
"proof-of-concepts/**/*" = ["S311"]
```

Tests are allowed to use `assert` (`S101`) and hardcoded credentials (`S105`, `S106`) for test fixtures. The package manager subproject has all S rules disabled. Proof-of-concept code is allowed to use pseudo-random generators.

### Known Exceptions in Source

The codebase has one annotated security-related suppression:

- `query_builder.py` line 120: `hashlib.md5(plan_str.encode()).hexdigest()  # noqa: S324` -- MD5 is used for query plan hashing (cache key generation), not for cryptographic security. This is a performance optimization where collision resistance is not a security requirement.

## Thread Safety

Thread safety patterns are documented in detail in the [Performance](performance.md#thread-safety-patterns) document. A summary of the security-relevant aspects:

### Concurrent Access Protection

All mutable shared state is protected by `threading.RLock` when thread safety is enabled:

- **Entity state** in `ChangeTracker` -- prevents concurrent modification of entity tracking dictionaries.
- **Cache contents** in `CacheManager` and `MemoryCache` -- prevents race conditions during cache read/write/eviction.
- **Event queue** in `EventDispatcher` -- `RLock` protects the `deque` used for event queuing.
- **Metrics counters** in `PerformanceOptimizer` and `CacheStatistics` -- prevents counter corruption under concurrent access.

### Singleton Safety

`EventManager` uses double-checked locking with a class-level `threading.Lock` to ensure only one instance is created:

```python
class EventManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
```

### Semaphore-Based Rate Limiting

`EventDispatcher` uses `asyncio.Semaphore(max_concurrent_async_handlers)` (default 10) to limit the number of concurrently executing async event handlers, preventing resource exhaustion from event storms.

## Error Handling Hierarchy

### ORM Exception Hierarchy

All ORM exceptions are defined in `revitpy/orm/exceptions.py` and form a single inheritance chain:

```
RevitPyException (from api.exceptions)
  |
  +-- ORMException
        |
        +-- RelationshipError
        +-- CacheError
        +-- ChangeTrackingError
        +-- QueryError
        +-- LazyLoadingError
        +-- AsyncOperationError
        +-- BatchOperationError
        +-- ValidationError
        +-- ConcurrencyError
        +-- TransactionError (orm)
```

Each exception carries context-specific fields:

| Exception | Key Fields |
|---|---|
| `ORMException` | `operation`, `entity_type`, `entity_id`, `cause` |
| `RelationshipError` | `relationship_name`, `source_entity`, `target_entity` |
| `CacheError` | `cache_key`, `cache_operation` |
| `ChangeTrackingError` | `entity`, `property_name`, `tracking_operation` |
| `QueryError` | `query_expression`, `query_operation`, `element_count` |
| `LazyLoadingError` | `property_name`, `entity` |
| `AsyncOperationError` | `async_operation`, `task_id` |
| `BatchOperationError` | `batch_size`, `failed_operations`, `successful_operations` |
| `ValidationError` | `validation_errors` (dict of field to error list), `entity` |
| `ConcurrencyError` | `entity`, `conflicting_changes` |
| `TransactionError` | `transaction_id`, `transaction_state`, `nested_level` |

### API Exception Hierarchy

API-level exceptions are defined in `revitpy/api/exceptions.py`:

```
RevitPyException
  |
  +-- RevitAPIError
  +-- ConnectionError
  +-- ElementNotFoundError
  +-- ModelError
  +-- ValidationError (api)
  +-- PermissionError
  +-- TransactionError (api)
```

### Error Propagation Pattern

The codebase follows a consistent pattern for error handling:

1. **Catch at boundary** -- exceptions from external sources (Revit API, providers) are caught at the boundary.
2. **Wrap and re-raise** -- caught exceptions are wrapped in framework-specific exception types with the original exception as `cause`, using `raise ... from e`.
3. **Log before raising** -- `loguru.logger.error()` is called before raising, ensuring the error is recorded even if the caller swallows the exception.
4. **Context preservation** -- each exception carries structured fields (entity IDs, operation names, property names) to aid debugging.

Example from `RevitContext.get_by_id()`:

```python
except Exception as e:
    logger.error(f"Failed to get element by ID {element_id}: {e}")
    raise ORMException(
        f"Failed to get element by ID {element_id}",
        operation="get_by_id",
        entity_type=element_type.__name__,
        entity_id=element_id,
        cause=e,
    ) from e
```

### Transaction Safety

`Transaction` (in `api/transaction.py`) implements automatic rollback on failure:

- If an exception occurs during `commit()`, all operations rolled back before re-raising.
- The `__exit__` context manager rolls back on any exception, preventing partial commits.
- `TransactionGroup.commit_all()` rolls back all already-committed transactions in the group if any individual commit fails.

## CI Security Job

The CI pipeline (`.github/workflows/ci.yml`) includes a dedicated `security` job:

```yaml
security:
  name: Security
  runs-on: ubuntu-latest
  steps:
    - name: Checkout repository
      uses: actions/checkout@v4
      with:
        fetch-depth: 0

    - name: Set up Python 3.12
      uses: actions/setup-python@v5
      with:
        python-version: "3.12"
        cache: pip
        cache-dependency-path: pyproject.toml

    - name: Install dependencies
      run: pip install -e ".[dev]" pip-audit

    - name: Run pip-audit
      run: pip-audit

    - name: Run ruff security checks
      run: ruff check --select S revitpy/ tests/
```

### What This Checks

1. **pip-audit**: Scans all installed dependencies for known vulnerabilities using the Python Packaging Advisory Database (PyPA advisory database). Fails the build if any dependency has a published CVE.

2. **ruff --select S**: Runs only the flake8-bandit security rules against the entire `revitpy/` and `tests/` directories. This catches:
   - Hardcoded passwords or secrets
   - Use of `assert` for access control (in non-test code)
   - Insecure hash functions used for security
   - Subprocess calls with shell injection risk
   - Pseudo-random number generators used where cryptographic randomness is needed
   - `try-except-pass` patterns that silently swallow errors

### Additional CI Security Measures

- **Repository permissions**: The CI workflow specifies `permissions: contents: read`, following the principle of least privilege.
- **Pinned action versions**: All GitHub Actions use specific major versions (`@v4`, `@v5`).
- **Dependency caching**: Uses `cache: pip` with `cache-dependency-path: pyproject.toml` for reproducible builds.
- **Full history checkout**: `fetch-depth: 0` enables VCS-based versioning via hatch-vcs.

### Type Checking as Security Defense

The `type-check` CI job runs `mypy revitpy` with strict settings (from `pyproject.toml`):

```toml
[tool.mypy]
python_version = "3.11"
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_no_return = true
strict_equality = true
```

While not a security tool per se, mypy catches type-related bugs that could lead to runtime errors or unexpected behaviour, providing an additional layer of defense.

## Cloud Token Management and Scope Control

The `revitpy.cloud` module manages OAuth2 tokens for Autodesk Platform Services (APS) with security controls at multiple levels. For full details see [Infrastructure & Cloud](infrastructure.md).

### Token Lifecycle

`ApsAuthenticator` (in `revitpy/cloud/auth.py`) handles the OAuth2 client-credentials flow. Security-relevant behaviours:

- **Automatic expiry buffer** -- `ApsToken.is_expired` returns `True` when the token is within 60 seconds of its actual expiry time. This prevents requests from failing due to clock skew or in-flight latency.
- **No token persistence** -- tokens are held only in memory (`self._token`). They are never written to disk, logged, or serialised. A new token is obtained on each process start.
- **Minimal scope** -- the requested scope is `code:all data:write data:read bucket:create`, which is the minimum required for Design Automation operations.
- **Credential isolation** -- `ApsCredentials` holds `client_id` and `client_secret` in a dataclass. The CI/CD templates generated by `CIHelper` inject these values from environment variables (`APS_CLIENT_ID`, `APS_CLIENT_SECRET`) sourced from repository secrets, never from hardcoded values.

### Authenticated Request Security

`ApsClient` (in `revitpy/cloud/client.py`) injects the `Authorization` header on every request via `get_token()`, which triggers re-authentication when the cached token is expired:

```python
token = await self._authenticator.get_token()
headers["Authorization"] = f"{token.token_type} {token.access_token}"
```

The client enforces a sliding-window rate limit of 20 requests per second to prevent accidental API abuse, and retries only on status codes `429`, `500`, `502`, and `503` -- non-retryable errors (such as `401 Unauthorized` or `403 Forbidden`) propagate immediately as `ApsApiError`.

### HMAC Webhook Signature Verification

`WebhookHandler.verify_signature()` (in `revitpy/cloud/webhooks.py`) validates incoming webhook payloads using HMAC-SHA256:

```python
def verify_signature(self, payload: bytes, signature: str) -> bool:
    expected = hmac.new(
        self._config.secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

Key properties:

- Uses `hmac.compare_digest` for constant-time comparison, preventing timing side-channel attacks.
- Raises `WebhookError` if called without a configured secret, preventing accidental unverified processing.
- The `WebhookConfig.secret` is expected to be injected at runtime, not hardcoded.

## AI Safety Model

The `revitpy.ai` module includes a safety system that controls which tools an AI agent may execute against a Revit model. This prevents unintended or destructive modifications when the framework is used in an MCP (Model Context Protocol) context.

### Safety Modes

`SafetyGuard` (in `revitpy/ai/safety.py`) enforces one of three safety modes, defined by the `SafetyMode` enum (in `revitpy/ai/types.py`):

| Mode | Value | Behaviour |
|---|---|---|
| `READ_ONLY` | `read_only` | Blocks all tools in `ToolCategory.MODIFY`. Only query, analyse, and export tools are allowed. |
| `CAUTIOUS` | `cautious` | Allows all tool categories but flags tools whose category appears in `SafetyConfig.require_confirmation_for`, indicating the caller should confirm before execution. This is the default mode. |
| `FULL_ACCESS` | `full_access` | Allows all tool categories without confirmation requirements. |

### Tool Categories

Each `ToolDefinition` is assigned a `ToolCategory`:

| Category | Value | Examples |
|---|---|---|
| `QUERY` | `query` | List elements, get parameters |
| `MODIFY` | `modify` | Create/delete elements, change parameters |
| `ANALYZE` | `analyze` | Run validation, compute metrics |
| `EXPORT` | `export` | Export schedules, generate reports |

### Tool Call Validation Pipeline

When the MCP server receives a `tools/call` request, the following validation pipeline executes inside `McpServer._handle_tools_call()` (in `revitpy/ai/server.py`):

1. **Tool lookup** -- `RevitTools.get_tool(tool_name)` resolves the tool name to a `ToolDefinition`. Unknown tools return an MCP error response (code `-32602`).

2. **Safety validation** -- `SafetyGuard.validate_tool_call(tool, arguments)` checks the call against the active policy:
   - If the tool name appears in `SafetyConfig.blocked_tools`, a `SafetyViolationError` is raised unconditionally.
   - In `READ_ONLY` mode, any tool with `ToolCategory.MODIFY` raises `SafetyViolationError`.
   - In `CAUTIOUS` mode, tools whose category is in `require_confirmation_for` are flagged (logged at `INFO` level).

3. **Execution** -- if validation passes, `RevitTools.execute_tool(tool_name, arguments)` runs the tool and returns a `ToolResult`.

4. **Error response** -- if `SafetyViolationError` is raised, the server returns an MCP response with `isError: true` and the violation message, rather than executing the tool.

### SafetyConfig

`SafetyConfig` (in `revitpy/ai/types.py`) controls the safety policy:

| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | `SafetyMode` | `CAUTIOUS` | Active safety enforcement level |
| `max_undo_stack` | `int` | `50` | Maximum number of undo entries retained |
| `require_confirmation_for` | `list[ToolCategory]` | `[]` | Tool categories that require explicit confirmation in `CAUTIOUS` mode |
| `blocked_tools` | `list[str]` | `[]` | Tool names that are always blocked regardless of mode |

### Preview and Undo Mechanism

`SafetyGuard` provides two mechanisms for reversibility:

**Preview** -- `preview_changes(tool, arguments) -> dict` returns a dry-run summary of what a tool call would do, including the tool name, category, arguments, current safety mode, whether confirmation is required, and whether the tool is blocked. No state is modified.

**Undo stack** -- `SafetyGuard` maintains a bounded LIFO stack of operations:

- `push_undo(operation: dict)` adds an entry. When the stack exceeds `max_undo_stack` (default 50), the oldest entry is discarded.
- `undo_last() -> dict | None` pops and returns the most recent entry, or `None` if empty.
- `get_undo_stack() -> list[dict]` returns a copy of the current stack for inspection.

The undo stack is not automatically populated -- callers are responsible for recording reversible operations after successful tool execution.

### AI Exception Hierarchy

All AI/MCP exceptions inherit from `AiError` (in `revitpy/ai/exceptions.py`):

```
AiError
  |
  +-- McpServerError            (host, port)
  +-- ToolExecutionError        (tool_name, arguments)
  +-- SafetyViolationError      (tool_name, safety_mode, reason)
  +-- PromptError               (template_name)
```

`SafetyViolationError` carries the `tool_name`, `safety_mode`, and a human-readable `reason` string, enabling callers and logs to diagnose exactly why a tool call was denied.

### WebSocket Server Security Considerations

`McpServer` (in `revitpy/ai/server.py`) exposes tools over a WebSocket connection. Security-relevant aspects:

- **Default binding** -- the server binds to `localhost:8765` by default (`McpServerConfig`), limiting exposure to the local machine.
- **Connection tracking** -- active connections are tracked in a `set`. The `connections` property returns a copy to prevent external mutation.
- **Error isolation** -- exceptions during message handling are caught per-message and returned as MCP error responses (JSON-RPC error code `-32603`). A single malformed message does not terminate the connection.
- **Graceful shutdown** -- `stop(timeout=5.0)` closes the server and waits for existing connections to drain within the timeout. The connection set is cleared on stop.
- **Safety integration** -- every `tools/call` request passes through `SafetyGuard.validate_tool_call()` before execution, ensuring the configured safety policy is enforced regardless of the client.
- **No built-in authentication** -- the WebSocket server does not implement its own authentication layer. In production deployments, it should be placed behind a reverse proxy or gateway that handles authentication and TLS termination.
