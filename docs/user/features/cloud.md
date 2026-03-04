---
layout: page
title: Cloud & Design Automation
description: Submit APS Design Automation jobs, batch-process Revit files in the cloud, and generate CI/CD pipelines with RevitPy. Includes webhooks and rate limiting.
doc_tier: user
---

# Cloud & Design Automation

RevitPy includes a cloud layer for running Revit workloads through the Autodesk Platform Services (APS) Design Automation API. The `revitpy.cloud` module provides OAuth2 authentication, job submission and monitoring, parallel batch processing with retry, CI/CD pipeline generation, and webhook event handling.

Install the cloud extras with:

```bash
pip install revitpy[cloud]
```

## Quick Start

For simple one-shot operations, use the convenience functions at module level:

```python
from revitpy.cloud import submit_job, batch_process, generate_ci_config
from revitpy.cloud import ApsCredentials, JobConfig, BatchConfig

credentials = ApsCredentials(
    client_id="your-client-id",
    client_secret="your-client-secret",
)

# Submit a single job
job_id = await submit_job(
    credentials,
    JobConfig(
        activity_id="RevitPy.Validate+prod",
        input_file="https://bucket.s3.amazonaws.com/model.rvt",
    ),
)

# Batch-process multiple jobs
configs = [
    JobConfig(activity_id="RevitPy.Validate+prod", input_file=f)
    for f in rvt_file_urls
]
result = await batch_process(
    credentials,
    configs,
    batch_config=BatchConfig(max_parallel=5, retry_count=2),
)
print(f"{result.completed}/{result.total_jobs} succeeded")

# Generate a CI pipeline
yaml = generate_ci_config(provider="github", script_path="validate.py")
```

## ApsCredentials

`ApsCredentials` holds the OAuth2 client credentials used throughout the cloud module.

| Field | Type | Default | Description |
|---|---|---|---|
| `client_id` | `str` | -- | APS application client ID |
| `client_secret` | `str` | -- | APS application client secret |
| `region` | `CloudRegion` | `CloudRegion.US` | Target cloud region |

```python
from revitpy.cloud import ApsCredentials, CloudRegion

credentials = ApsCredentials(
    client_id="your-client-id",
    client_secret="your-client-secret",
    region=CloudRegion.EMEA,
)
```

### CloudRegion Enum

| Value | Description |
|---|---|
| `US` | United States region |
| `EMEA` | Europe, Middle East, and Africa region |

## ApsAuthenticator

`ApsAuthenticator` implements the OAuth2 client-credentials flow against the APS token endpoint. It caches the issued token and transparently refreshes it when it nears expiry (with a 60-second buffer).

```python
from revitpy.cloud import ApsAuthenticator, ApsCredentials

credentials = ApsCredentials(
    client_id="your-client-id",
    client_secret="your-client-secret",
)
auth = ApsAuthenticator(credentials)

# Perform a fresh authentication
token = await auth.authenticate()
print(token.access_token, token.expires_in, token.scope)

# Get a cached token (auto-refreshes if expired)
token = await auth.get_token()

# Check validity manually
if auth.is_token_valid():
    print("Token is still valid")
```

### ApsToken Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `access_token` | `str` | -- | OAuth2 access token string |
| `token_type` | `str` | `"Bearer"` | Token type |
| `expires_in` | `int` | `3600` | Token lifetime in seconds |
| `scope` | `str` | `""` | Granted OAuth2 scopes |
| `issued_at` | `float` | `time.time()` | Unix timestamp when the token was issued |

The `is_expired` property returns `True` when the current time is within 60 seconds of expiry:

```python
if token.is_expired:
    token = await auth.authenticate()
```

### AuthMethod Enum

| Value | Description |
|---|---|
| `CLIENT_CREDENTIALS` | Service-to-service OAuth2 flow (used by `ApsAuthenticator`) |
| `AUTHORIZATION_CODE` | User-interactive three-legged OAuth2 flow |
| `DEVICE_CODE` | Device authorization grant for headless environments |

## ApsClient

`ApsClient` is the base HTTP client for all APS API requests. It wraps `httpx.AsyncClient` and provides automatic Bearer-token injection, sliding-window rate limiting (20 requests per second), and exponential-backoff retry on transient failures.

### Creating a Client

```python
from revitpy.cloud import ApsAuthenticator, ApsClient, CloudRegion

auth = ApsAuthenticator(credentials)
client = ApsClient(auth, region=CloudRegion.US)
```

### Making Requests

The client exposes `get`, `post`, and `delete` convenience methods, plus a general `request` method. All return parsed JSON as a `dict`:

```python
# GET request
data = await client.get("/da/us-east/v3/workitems/abc123")

# POST request
data = await client.post("/da/us-east/v3/workitems", json=payload)

# DELETE request
data = await client.delete("/da/us-east/v3/workitems/abc123")

# General request
data = await client.request("PATCH", "/some/endpoint", json=body)
```

### Rate Limiting and Retry

`ApsClient` enforces a sliding-window rate limit of 20 requests per second. When the limit is reached, subsequent requests are delayed until a slot opens.

Transient HTTP errors (status codes 429, 500, 502, 503) and connection errors are retried up to 3 times with exponential backoff starting at 1 second. Non-retryable errors raise `ApsApiError` immediately.

| Setting | Value |
|---|---|
| Max requests per second | 20 |
| Retryable status codes | 429, 500, 502, 503 |
| Max retries | 3 |
| Initial backoff | 1.0 second |
| Backoff multiplier | 2x per attempt |

## JobManager

`JobManager` wraps the APS Design Automation v3 WorkItems API and provides high-level operations for submitting, polling, downloading, and cancelling cloud-based Revit processing jobs.

### Creating a Job Manager

```python
from revitpy.cloud import ApsAuthenticator, ApsClient, JobManager

auth = ApsAuthenticator(credentials)
client = ApsClient(auth)
manager = JobManager(client)
```

### Submitting a Job

```python
from revitpy.cloud import JobConfig

config = JobConfig(
    activity_id="RevitPy.Validate+prod",
    input_file="https://bucket.s3.amazonaws.com/model.rvt",
    output_file="https://bucket.s3.amazonaws.com/result.json",
    script_path="https://bucket.s3.amazonaws.com/validate.py",
    parameters={"version": "2024"},
    timeout=600.0,
)

job_id = await manager.submit(config)
print(f"Submitted: {job_id}")
```

### JobConfig Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `activity_id` | `str` | -- | Design Automation activity identifier |
| `input_file` | `str \| Path` | -- | URL or path to the input Revit file |
| `output_file` | `str \| Path \| None` | `None` | URL or path for the output file |
| `script_path` | `str \| Path \| None` | `None` | URL or path to the processing script |
| `parameters` | `dict[str, Any]` | `{}` | Additional parameters passed to the activity |
| `timeout` | `float` | `600.0` | Maximum job duration in seconds |

### Polling for Completion

```python
# Check status once
status = await manager.get_status(job_id)
print(status)  # JobStatus.RUNNING

# Poll until terminal state (blocks up to timeout)
result = await manager.wait_for_completion(
    job_id,
    timeout=600.0,
    poll_interval=5.0,
)
print(result.status, result.duration_ms)
```

`wait_for_completion` raises `JobExecutionError` if the job fails or times out. On success, it returns a `JobResult`.

### Downloading Results

```python
from pathlib import Path

downloaded = await manager.download_results(
    job_id,
    output_dir=Path("./results"),
)
for path in downloaded:
    print(f"Downloaded: {path}")
```

### Cancelling a Job

```python
success = await manager.cancel(job_id)
if success:
    print("Job cancelled")
```

### Retrieving Logs

```python
logs = await manager.get_logs(job_id)
print(logs)
```

### JobResult Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `job_id` | `str` | -- | Work-item identifier |
| `status` | `JobStatus` | -- | Final status of the job |
| `output_files` | `list[str]` | `[]` | URLs of output files |
| `logs` | `str` | `""` | URL to the execution report |
| `duration_ms` | `float` | `0.0` | Total execution time in milliseconds |
| `error` | `str \| None` | `None` | Error message if the job failed |

### JobStatus Enum

| Value | Description |
|---|---|
| `PENDING` | Job has been accepted but not yet queued |
| `QUEUED` | Job is waiting for a processing slot |
| `RUNNING` | Job is actively executing |
| `COMPLETED` | Job finished successfully |
| `FAILED` | Job encountered an error |
| `CANCELLED` | Job was cancelled by the caller |
| `TIMED_OUT` | Job exceeded its timeout |

## BatchProcessor

`BatchProcessor` runs multiple `JobConfig` items in parallel with bounded concurrency, automatic retry on failure, and optional progress and cancellation callbacks.

### Creating a Batch Processor

```python
from revitpy.cloud import JobManager, BatchProcessor, BatchConfig

processor = BatchProcessor(
    job_manager=manager,
    config=BatchConfig(
        max_parallel=5,
        retry_count=2,
        retry_delay=30.0,
        continue_on_error=True,
    ),
)
```

### BatchConfig Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `max_parallel` | `int` | `5` | Maximum concurrent jobs |
| `retry_count` | `int` | `2` | Number of retries per failed job |
| `retry_delay` | `float` | `30.0` | Seconds to wait between retries |
| `continue_on_error` | `bool` | `True` | Continue processing remaining jobs when one fails |

### Processing a List of Jobs

```python
import asyncio

configs = [
    JobConfig(activity_id="RevitPy.Validate+prod", input_file=url)
    for url in file_urls
]

# Optional progress callback
def on_progress(completed: int, total: int):
    print(f"Progress: {completed}/{total}")

# Optional cancellation event
cancel = asyncio.Event()

result = await processor.process(
    configs,
    progress=on_progress,
    cancel=cancel,
)

print(f"Total: {result.total_jobs}")
print(f"Completed: {result.completed}")
print(f"Failed: {result.failed}")
print(f"Cancelled: {result.cancelled}")
print(f"Duration: {result.total_duration_ms:.0f}ms")

# Inspect individual results
for job_result in result.results:
    print(job_result.job_id, job_result.status.value)
```

When `continue_on_error` is `False`, the processor sets the `cancel` event on the first failure, preventing new jobs from starting.

### Processing a Directory of .rvt Files

`process_directory` is a convenience method that discovers all `.rvt` files in a directory, creates a `JobConfig` for each, and processes them:

```python
from pathlib import Path

result = await processor.process_directory(
    input_dir=Path("./models"),
    script_path=Path("./scripts/validate.py"),
    activity_id="RevitPy.Validate+prod",
)
print(f"Processed {result.total_jobs} Revit files")
```

### BatchResult Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `total_jobs` | `int` | `0` | Total number of jobs submitted |
| `completed` | `int` | `0` | Number of successfully completed jobs |
| `failed` | `int` | `0` | Number of failed jobs |
| `cancelled` | `int` | `0` | Number of cancelled jobs |
| `results` | `list[JobResult]` | `[]` | Per-job results |
| `total_duration_ms` | `float` | `0.0` | Total batch processing time in milliseconds |

## CIHelper

`CIHelper` generates CI/CD pipeline configurations for GitHub Actions and GitLab CI that automate Revit model validation using Design Automation.

### Generating a GitHub Actions Workflow

```python
from revitpy.cloud import CIHelper

helper = CIHelper()

yaml = helper.generate_github_workflow(
    name="revitpy-validation",
    script_path="validate.py",
    revit_version="2024",
    branches="main",
    runner="ubuntu-latest",
    python_version="3.11",
)
print(yaml)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | `"revitpy-validation"` | Workflow name |
| `script_path` | `str` | `"validate.py"` | Path to the validation script |
| `revit_version` | `str` | `"2024"` | Target Revit version |
| `branches` | `str` | `"main"` | Comma-separated branch triggers |
| `runner` | `str` | `"ubuntu-latest"` | GitHub Actions runner label |
| `python_version` | `str` | `"3.11"` | Python version |

### Generating a GitLab CI Pipeline

```python
yaml = helper.generate_gitlab_ci(
    name="revitpy-validation",
    script_path="validate.py",
    revit_version="2024",
    python_version="3.11",
)
print(yaml)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | `"revitpy-validation"` | Job name |
| `script_path` | `str` | `"validate.py"` | Path to the validation script |
| `revit_version` | `str` | `"2024"` | Target Revit version |
| `python_version` | `str` | `"3.11"` | Python version for the Docker image |

### Using the Convenience Function

The module-level `generate_ci_config` function dispatches to the appropriate generator:

```python
from revitpy.cloud import generate_ci_config

github_yaml = generate_ci_config(provider="github", script_path="validate.py")
gitlab_yaml = generate_ci_config(provider="gitlab", revit_version="2025")
```

Raises `ValueError` if `provider` is not `"github"` or `"gitlab"`.

### Saving to Disk

```python
from pathlib import Path

path = helper.save_workflow(
    content=yaml,
    output_path=".github/workflows/revitpy-validation.yml",
)
print(f"Saved to {path}")
```

`save_workflow` creates parent directories automatically and returns the resolved `Path`.

## WebhookHandler

`WebhookHandler` receives, verifies, and routes incoming APS webhook events. It supports HMAC-SHA256 signature verification and event-type-based callback dispatch.

### Setting Up a Handler

```python
from revitpy.cloud import WebhookHandler, WebhookConfig

handler = WebhookHandler(
    config=WebhookConfig(
        url="https://myapp.example.com/webhooks/aps",
        secret="your-webhook-secret",
        events=["job.completed", "job.failed"],
    ),
)
```

### WebhookConfig Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `url` | `str` | -- | Webhook listener URL |
| `secret` | `str` | -- | Shared secret for HMAC verification |
| `events` | `list[str]` | `[]` | Event types to listen for |

### Verifying Signatures

```python
is_valid = handler.verify_signature(
    payload=request.body,       # raw bytes
    signature=request.headers["X-Signature"],  # hex HMAC-SHA256
)
if not is_valid:
    raise ValueError("Invalid webhook signature")
```

Raises `WebhookError` if no secret is configured.

### Handling Events

```python
event = handler.handle_event(event_data={
    "eventType": "job.completed",
    "jobId": "abc123",
    "status": "completed",
    "timestamp": "2025-01-15T10:30:00Z",
})
print(event.event_type, event.job_id, event.status)
```

`handle_event` parses the payload into a `WebhookEvent`, dispatches registered callbacks, and returns the event. Raises `WebhookError` if required fields (like `eventType`) are missing.

### WebhookEvent Dataclass

| Field | Type | Default | Description |
|---|---|---|---|
| `event_type` | `str` | -- | Event type identifier |
| `job_id` | `str` | -- | Associated job identifier |
| `status` | `JobStatus` | -- | Job status at the time of the event |
| `timestamp` | `str` | -- | ISO timestamp of the event |
| `payload` | `dict[str, Any]` | `{}` | Full raw event payload |

### Registering Callbacks

Register callbacks for specific event types. Callbacks receive a `WebhookEvent` argument. Use `"*"` as the event type to listen for all events:

```python
def on_completed(event):
    print(f"Job {event.job_id} completed")

def on_failed(event):
    print(f"Job {event.job_id} failed")

def on_any(event):
    print(f"Event: {event.event_type}")

handler.register_callback("job.completed", on_completed)
handler.register_callback("job.failed", on_failed)
handler.register_callback("*", on_any)  # wildcard listener
```

Multiple callbacks can be registered for the same event type. They are invoked in registration order.

## Error Handling

All cloud errors inherit from `CloudError`. Specific exception types let you handle different failure modes:

| Exception | Description |
|---|---|
| `CloudError` | Base exception for all cloud errors |
| `AuthenticationError` | OAuth2 authentication failed |
| `ApsApiError` | APS API returned an error response |
| `JobSubmissionError` | Work-item submission was rejected |
| `JobExecutionError` | Job failed during execution or timed out |
| `WebhookError` | Webhook verification or event parsing failed |

```python
from revitpy.cloud import (
    AuthenticationError,
    ApsApiError,
    JobSubmissionError,
    JobExecutionError,
    WebhookError,
)

try:
    job_id = await manager.submit(config)
    result = await manager.wait_for_completion(job_id)
except AuthenticationError as exc:
    print(f"Auth failed: {exc}")
except JobSubmissionError as exc:
    print(f"Submission rejected: {exc}")
except JobExecutionError as exc:
    print(f"Job failed: {exc}")
except ApsApiError as exc:
    print(f"API error: {exc}")
```
