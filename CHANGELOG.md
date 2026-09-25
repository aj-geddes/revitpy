# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

This release makes RevitPy work against a live Revit model and brings the feature modules in line with the external standards and services they target.

### Breaking changes

- `WebhookHandler.handle_event()` now verifies the `x-adsk-signature` HMAC by default (`verify=True`). Pass `raw_body=` and `signature=`.
- `SafetyGuard` in its default `CAUTIOUS` mode requires confirmation for `MODIFY` tools. Without a `confirmation_callback`, those tools are denied.
- Compliance APIs require explicit inputs. `check_ashrae` needs a `climate_zone`. LL97 needs an occupancy/property type and selects the compliance period by year. EPBD needs limits supplied by the caller.
- `revitpy[interop]` now requires `specklepy>=3.0.0`. `revitpy[ifc]` requires `ifcopenshell>=0.8.0` (plus `ifctester` and `defusedxml`).
- `RevitDocumentProvider.start_transaction()` raises `TransactionError` for documents without `StartTransaction`. It no longer pretends to open a transaction.
- Speckle "stream / branch / commit" names are deprecated in favour of "project / model / version". The old names still work but emit a `DeprecationWarning`.
- The ORM factory functions `create_wall` / `create_room` / `create_door` / `create_window` raise `revitpy.orm.exceptions.ValidationError` instead of pydantic's `ValidationError`. The `.validation_errors` attribute maps each field to its messages, and `.cause` holds the original pydantic error. Constructing the models directly (for example `WallElement(...)`) still raises pydantic's error.
- `RevitAPI` must be connected (`api.connect(...)`) before `query()`, `elements` or `transaction()`.

### Added

- **RevitPy Live Server** (`revitpy.revit.live`): an authenticated JSON-RPC-over-WebSocket endpoint inside Revit that development tools use to run code in the open session.
  - Methods: `live/status`, `live/execute`, `live/runFile`, `live/reload`, `debug/start` (starts debugpy), `bridge/listAnalyses` and `bridge/analyze`.
  - It is started from the new **Live Server** ribbon button or by setting `start_live_server = true`.
  - A bearer token is mandatory. The server publishes its URL and token in the user-only discovery file `~/.revitpy/live.json`.
  - Analyses register with `@register_analysis(name, main_thread=...)` or through the `revitpy.analyses` entry-point group.
  - See `docs/developer/live-server.md`.
- `revitpy.live_client` (`LiveClient`, `call_live`) and `revitpy live status|run|exec|reload|debug`.
- `revitpy.rpc.JsonRpcWebSocketServer`: the shared authenticated JSON-RPC base class now used by both `McpServer` and the Live Server.
- VS Code extension (`vscode-extension/`), rebuilt as a Live Server client:
  - Run Script and Run Selection in Revit, reload on save, and Attach Debugger through debugpy.
  - Create Project via `revitpy-dev`, and configuration of a Revit API stubs folder for Pylance.
  - The custom language server, debug adapter and `.rvtpy` language were removed.
- Dev server (`dev-server/`, 2.0.0), rebuilt as a focused file watcher: `revitpy-dev-server watch --run entry.py` reloads changed modules and re-runs the script through the Live Server. The WebView/UI hot reload, asset pipeline and unmeasured performance claims were removed.
- pyRevit bridge (`pyrevit-bridge/`, replacing `bridge/`):
  - A single `revitpy_bridge.py` for pyRevit that is compatible with IronPython 2.7 and CPython 3, plus a sample pyRevit extension.
  - The `revitpy-bridge-analyses` package: element summary, parameter statistics, quantity take-off, embodied carbon and bounding-box clash shortlist.
  - Communication goes through the Live Server; the named-pipe, file-exchange and custom WebSocket transports were removed.
- Live Revit connectivity (`revitpy.revit`):
  - pythonnet adapters map `Autodesk.Revit.DB` objects to RevitPy's protocols.
  - `RevitAPI.connect(__revit__)` wraps a `UIApplication` or `Application` automatically.
  - Values use Revit internal units (feet).
- Typed element classes `Wall`, `Floor`, `Door`, `Window`, `Room` and `Level`. Elements are wrapped by category, so `api.query(Wall)` works.
- Real Revit transactions. A nested transaction becomes a `SubTransaction`, and an exception rolls back. Parameter writes apply immediately inside the open transaction.
- `revitpy.revit.host`:
  - `call_on_revit_thread()` dispatches work to Revit's main thread through an `ExternalEvent`.
  - `in_revit_host()` reports whether code is running inside the add-in.
  - An in-Revit MCP server (`start_mcp_server` / `stop_mcp_server` / `toggle_mcp_server`) uses a bearer token and a Revit `TaskDialog` to confirm model-changing tools.
- C# host add-in `src/RevitPy.Addin` (`RevitPy.Addin.RevitPyApplication`):
  - Targets Revit 2024 (net48), 2025/2026 (net8.0-windows) and 2027 (net10.0-windows).
  - Adds a RevitPy ribbon tab with Run Script, Rerun, MCP Server and About.
  - Reads `%APPDATA%\RevitPy\settings.ini`, overridable with `REVITPY_PYTHON_*` environment variables.
  - `scripts/install-addin.ps1` builds and installs it.
- CLI commands: `revitpy version`, `revitpy doctor [--json]`, `revitpy mcp-serve [--host --port --token]`.
- MCP server authentication: `McpServerConfig.auth_token` and `allowed_origins`, plus `SafetyGuard(confirmation_callback=...)`.
- `RevitContext.update(entity, **changes)` sets properties and records them as tracked changes.
- Cloud: region-aware Design Automation base path (`region`, `da_base_path`), configurable HTTP timeouts, and webhook signature verification helpers.
- Speckle: projects/models/versions API on specklepy 3.
- IFC: `IdsValidator.validate_ifc_file()` via `ifctester`, and BCF-XML 2.1 archives (reads 2.1 and 3.0) parsed with `defusedxml`.
- Top-level exports `FilterOperator`, `EventType`, `EventPriority`, and `revitpy.orm.create_context`.
- CI builds the add-in for every supported Revit version and tests on Python 3.11–3.13.

### Changed

- ORM `QueryPlan.optimize()` no longer changes results. It only moves a filter ahead of an immediately preceding `order_by`, and never moves one across `select`, `skip`/`take` or `distinct`.
- ORM result caching is skipped for plans that contain callables (`where`/`select`/`order_by` lambdas). The new `QueryBuilder.is_cacheable` and `plan_is_cacheable(plan)` report whether a plan can be cached.
- ORM `select()` keeps the source element type and no longer mutates the parent builder. Builders are immutable.
- `QueryBuilder.as_streaming(batch_size)` yields lazily consumed batches of at most `batch_size` elements.
- `ChangeTracker.track_property_change(None, ...)` raises `ValueError`.
- `AsyncRevitContext.save_changes_async()` persists through the configured `IUnitOfWork` (`commit_async` / `commit`) and raises on failure. Without a unit of work, changes are only tracked.
- The pytest configuration lives in `pyproject.toml`. Slow stress tests are excluded by default (`pytest -m slow` runs them).
- Supported Python: 3.11–3.13. `pydantic>=2.5,<3`, `httpx>=0.25`.
- Project URLs now point to `github.com/aj-geddes/revitpy` and `aj-geddes.github.io/revitpy`.
- `revitpy.performance` exports only the classes that exist: `PerformanceOptimizer`, `OptimizationConfig`, `AdaptiveCache`, `ObjectPool`, `BenchmarkSuite`, `BenchmarkRunner`, `BenchmarkConfiguration`, `MemoryManager`, `MemoryLeakDetector`, `MetricsCollector`, `PerformanceMonitor`, `AlertingSystem`.
- `examples/` rewritten as runnable scripts: `query_elements.py`, `bulk_update_parameters.py`, `room_schedule_export.py`, `orm_usage.py` and `mcp_server_in_revit.py`. The old example projects were removed.
- Documentation rewritten against the current code (README, getting started, architecture, API reference, FAQ, troubleshooting).
- `proof-of-concepts/` rebuilt as five small runnable demos: energy analytics, space planning, IoT monitoring, structural analysis and facade progress from photos.
  - They read model data through `RevitAPI` (`api.query(...)`, typed elements, `QuantityExtractor`, `revitpy.sustainability`) and write results back inside `api.transaction(...)`.
  - They run against `__revit__` in Revit, or a `MockApplication` demo building elsewhere.
  - One `proof-of-concepts/pyproject.toml` (`revitpy-pocs`) declares only the packages actually imported: numpy, pandas, scipy, scikit-learn, plotly and loguru.
  - Each PoC has `python -m` entry points, pytest suites and a `pocs` CI job.
  - Removed: the private `revitpy_mock`, the pyRevit exchange snippets, and mocked TensorFlow/OpenCV/cloud-IoT code. Also removed the aspirational `requirements.txt` files and the `MARKET_VALIDATION_FRAMEWORK.md` / `ROI_CALCULATOR.md` marketing documents.

### Fixed

- Package manager:
  - Its test suite now passes (691 tests; previously 116 failed, 41 errored, and the integration tests were skipped).
  - Package list, search and version queries always returned nothing because Python `not` was applied to SQLAlchemy columns.
  - Model columns work on SQLite as well as Postgres.
  - `APIKey.user_id` gained its missing foreign key.
  - The dependency resolver installed packages in the wrong order and never detected cycles.
  - API-key creation always failed.
  - `revitpy-install` and `revitpy-build` crashed on import.
  - Several configuration environment variables were ignored.
- Dev CLI (`cli/`):
  - The package could not build (missing `README.md`) and crashed on start.
  - Its console script clashed with the core `revitpy` command, so it is now `revitpy-dev`.
- Sustainability: EPD matching, compliance calculations, and material extraction.
- Extraction: cost, material, and quantity calculations.
- IFC: the exporter writes a proper spatial hierarchy (Project > Site > Building > one Storey per level). Every product gets a local placement and storey containment. Element mapping falls back to the element's `category`.
- Interop: sync and subscriptions.
- ORM: `any()`, `all()`, `first_or_default()` and `single()` could return wrong answers because queries with different lambdas collided in the result cache.
- ORM: reordering a filter across `take`/`skip` or `select` changed query results.
- AI: MCP protocol handling and tool execution. Built-in tools now report "not connected" instead of returning placeholder data.
- Events: `register_class_handlers()` registered unbound methods, so every dispatch failed. Handlers are now bound to the instance.
- Events: `connect_to_revit()` imported a module that did not exist. It now forwards `DocumentOpened` / `DocumentSaved` / `DocumentClosing` / `DocumentChanged` into the `EventManager` (`revitpy.events.revit_bridge`).
- Extensions: disposing an extension no longer leaves an un-awaited `dispose()` coroutine or recurses into itself. There is a new `DIContainer.dispose_async()`.
- `TransactionGroup` commits and rolls back innermost-first, which is the order Revit requires for nested sub-transactions.
- `Element.discard_changes()` restores values that were never read before being written. Repeated writes keep the original value.
- After a rollback, every element wrapper handed out is refreshed, not only the ones fetched by id.
- `order_by_descending()` sorted text ascending. Multi-key sorts with mixed directions and mixed value types now work.
- ORM `reject_changes()` only reverts properties that were changed, restoring the value from before the first change.
- `AsyncRevitContext.get_all_async()` / `get_by_id_async()` work with providers that only have sync methods, such as the Revit document provider.
- `QuantityExtractor` reads `Area` / `Volume` / `Length` from Revit parameters on element wrappers and converts them from feet to metric. Elements without a `Level` parameter no longer break extraction.
- The IFC mapper recognises the `Wall` / `Door` / `Window` / `Floor` / `Room` wrappers and Revit categories (`OST_*` and display names).
- `Level` on live elements returns the level name instead of its element id.
- `MockRevit` parameters report a `StorageType`, so numbers read back as numbers.
- `revitpy.performance` imports without `psutil`; memory metrics report 0.
- `RevitDocumentProvider` transactions were in-memory placeholders and `Element` rollback never reached the model. Both now drive the document's real transactions.

### Removed

- The `asyncio-mqtt` dependency.
- The `docs` extra (MkDocs). The documentation site is Jekyll (`docs/`).
- The `testing` extra.
- `pytest.ini` (the configuration moved into `pyproject.toml`).
- Mentions of nonexistent performance classes (`LatencyTracker`, `IntelligentCacheManager`, `RevitPyProfiler`).
- The legacy C# projects (`RevitPy.Core`, `Runtime`, `Bridge`, `Host`, `WebHost`, `Compatibility`) and their C# tests, which never compiled, the unbuilt WiX `installer/`, and the duplicated Node tools under `src/` (`RevitPy.DevTools`, `RevitPy.HotReload`, `RevitPy.VSCodeExtension`). They are replaced by `src/RevitPy.Addin`. The `dev-server/` and `vscode-extension/` projects remain.
- The stub `templates/` directory (the real project templates ship with the dev CLI in `cli/templates/`) and the orphaned `scripts/test_maintenance.py`.

### Security

- Package manager (`revitpy-package-manager`):
  - `python-jose` was replaced with PyJWT; dependency pins cleared 113 known vulnerabilities.
  - The storage service's path-traversal hole is closed (`../../etc/passwd` became an absolute path).
  - The server refuses to start in production with the built-in development JWT secret.
  - Only superusers can create `admin`-scope API keys.
  - Login no longer leaks through timing whether a username exists.
  - Weak-password errors no longer echo the plaintext password.
  - `/auth/refresh` requires a dedicated refresh token, and sessions are capped at `JWT_REFRESH_EXPIRE_DAYS` after login. This is a breaking change: clients must keep the `refresh_token` returned by login.
  - Docker Compose files no longer ship default credentials.
- The MCP server supports bearer-token authentication and an Origin allow-list, and warns when bound to a non-loopback address without a token.
- Model-changing AI tools need explicit confirmation by default.
- APS webhooks are HMAC-verified by default.
- BCF XML is parsed with `defusedxml`.

### Previously unreleased

- CI matrix testing, security job (pip-audit and ruff bandit rules), and ruff format checking.
- Mypy pre-commit hook, SECURITY.md, and Dependabot configuration.
- Replaced black and isort with ruff format. Magic numbers in async and event decorators became named constants.
