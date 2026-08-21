# Component Methods - Prompton AI Worker Status API Target Design

## Method Design Principles

- Public component methods remain synchronous because the Worker processes one Job at a time.
- `StatusApiClient` owns HTTP mechanics; `WorkerOrchestrator` owns status criticality and SQS lifecycle.
- Any 2xx returns normally. Final transport or HTTP failure raises a sanitized typed exception.
- Optional payload fields are omitted when `None`; FAILED therefore omits `progress`.
- Detailed algorithms and rule pseudocode are deferred to Functional and NFR Design.

## 1. Status API Module

### `StatusApiClient.__init__`

```python
def __init__(
    self,
    config: Config,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] | None = None,
) -> None:
    ...
```

- **Purpose**: Bind normalized base URL, optional API key, HTTP session, timeout policy, and deterministic sleep seam.
- **Production defaults**: A real `requests.Session` and `time.sleep`.
- **Security boundary**: Does not expose or log the API key.

### `StatusApiClient.update_job_status`

```python
def update_job_status(
    self,
    job_id: str,
    status: JobStatus,
    progress: int | None = None,
    message: str | None = None,
    artifact_key: str | None = None,
    error_code: ErrorCode | None = None,
) -> None:
    ...
```

- **Purpose**: PATCH one approved Job status payload.
- **Input**: Previously validated UUID Job ID, enum status, and optional approved fields.
- **Output**: `None` after any 2xx; response body parsing is not required.
- **Raises**: `StatusApiError` after a final 4xx, exhausted 5xx, connection error, or connect/read timeout.
- **Payload mapping**: Python `artifact_key` and `error_code` become JSON `artifactKey` and `errorCode`; `None` fields are absent.
- **Retry ownership**: This method owns the approved HTTP attempt policy, not the orchestrator.

### Internal HTTP Helpers

```python
def _build_url(self, job_id: str) -> str:
    ...

def _build_headers(self) -> dict[str, str]:
    ...

def _build_payload(
    self,
    status: JobStatus,
    progress: int | None,
    message: str | None,
    artifact_key: str | None,
    error_code: ErrorCode | None,
) -> dict[str, object]:
    ...
```

- `_build_url` strips only trailing base-URL slashes and appends the fixed status path.
- `_build_headers` always returns content type and conditionally adds `x-api-key`.
- `_build_payload` serializes enum values and omits all `None` values.

### `StatusApiError`

A dedicated `WorkerError` subtype represents final Status API failure.

- Mandatory SUCCESS failure maps to `ErrorCode.INTERNAL_ERROR` through existing classification.
- Safe attributes may include failure category, HTTP status code, and attempt count.
- The exception must not contain API key, request JSON, full response body, credentials, or signed URLs.

## 2. WorkerOrchestrator

### Constructor

```python
def __init__(
    self,
    config: Config,
    sqs_client: SQSClient | None = None,
    s3_client: S3Client | None = None,
    status_client: StatusApiClient | None = None,
    prompt_refiner: PromptRefiner | None = None,
    ai_generator: AIGenerator | None = None,
    apk_builder: ApkBuilder | None = None,
) -> None:
    ...
```

- Replaces `dynamo_client` with `status_client` while preserving constructor injection.
- Creates the real `StatusApiClient` only when no test double is supplied.

### `run`

```python
def run(self) -> None:
    ...
```

- Preserves SQS polling, cleanup, shutdown, and loop-continuation behavior.

### `process_job`

```python
def process_job(self, message: SQSMessage) -> None:
    ...
```

- Processes every delivered message from the beginning; no status lookup or terminal skip occurs.
- Recreates the Job workspace, starts visibility extension, executes phases, and stops extension in `finally`.
- Converts any uncaught processing error, including mandatory SUCCESS failure, into the existing failure-reporting path without deleting the message.

### Best-Effort Intermediate Reporting

```python
def _report_intermediate_status(
    self,
    job_id: str,
    status: JobStatus,
) -> None:
    ...
```

- Valid only for ANALYZING, GENERATING_CODE, and BUILDING.
- Supplies the fixed progress and message for that status.
- Catches `StatusApiError`, logs a sanitized warning, and allows AI/build processing to continue.

### Mandatory SUCCESS Reporting

```python
def _report_success(self, job_id: str, artifact_key: str) -> None:
    ...
```

- Supplies SUCCESS, progress 100, the approved message, and verified `artifactKey`.
- Does not absorb `StatusApiError`; failure enters `process_job` exception handling as `INTERNAL_ERROR`.
- Returns before `SQSClient.delete_message` can be called.

### Best-Effort Failure Reporting

```python
def _handle_failure(self, job_id: str, exc: BaseException) -> None:
    ...
```

- Captures `classify_error(exc)` and `user_message_for(exc)` before attempting the API call.
- Sends FAILED, message, and errorCode without progress.
- Catches reporting failure and logs it without replacing the original exception classification.
- Never deletes the SQS message.

### Finalization

```python
def _phase_finalize(
    self,
    message: SQSMessage,
    work: JobWorkDir,
    paths: S3Paths,
) -> None:
    ...
```

Required component-call order:
1. Best-effort source upload.
2. Required APK upload and HeadObject/size verification.
3. Mandatory SUCCESS report.
4. SQS message deletion.

## 3. Config Module

### Target `Config` Fields

```python
@dataclass(frozen=True)
class Config:
    aws_region: str
    sqs_queue_url: str
    s3_bucket_name: str
    prompton_api_base_url: str
    prompton_status_api_key: str | None
    work_dir: str
    visibility_timeout: int
    cleanup_hours: int
    log_level: str
    hermes_cli_path: str
    kiro_cli_path: str
    gradle_path: str
```

### `load_config`

```python
def load_config() -> Config:
    ...
```

- Requires non-empty `SQS_QUEUE_URL`, `S3_BUCKET_NAME`, and `PROMPTON_API_BASE_URL`.
- Treats absent, empty, or whitespace-only `PROMPTON_STATUS_API_KEY` as `None`.
- Removes `DYNAMODB_TABLE_NAME` from required values and returned configuration.
- Existing numeric and log-level validation remains unchanged.

## 4. S3Client

```python
def download_requirements(
    self, bucket: str, key: str, dest_path: Path
) -> dict[str, Any]:
    ...

def download_assets(
    self, bucket: str, prefix: str, dest_dir: Path
) -> list[Path]:
    ...

def upload_source(self, project_dir: Path, key: str) -> str:
    ...

def upload_artifact(self, apk_path: Path, key: str) -> str:
    ...
```

- Interfaces remain unchanged.
- `upload_artifact` remains the required verification boundary and returns only after HeadObject/size validation.

## 5. SQSClient and VisibilityExtender

```python
def receive_message(self) -> SQSMessage | None:
    ...

def delete_message(self, receipt_handle: str) -> None:
    ...

def extend_visibility(self, receipt_handle: str, timeout_seconds: int) -> None:
    ...

def get_visibility_timeout(self, fallback: int) -> int:
    ...
```

```python
def start(self) -> None:
    ...

def stop(self) -> None:
    ...
```

- Interfaces remain unchanged.
- Only the orchestrator may authorize deletion, after mandatory SUCCESS returns.

## 6. AI and Build Components

```python
def refine(
    self,
    requirements_path: Path,
    output_path: Path,
    job_id: str,
) -> Path | None:
    ...

def generate_code(
    self,
    requirements_path: Path,
    assets_dir: Path,
    output_dir: Path,
    *,
    job_id: str,
    refined_prompt_path: Path | None = None,
) -> Path:
    ...

def build_apk(self, project_dir: Path, output_path: Path) -> Path:
    ...
```

- Existing contracts remain intact.
- Phase logs are emitted locally; no component receives a persistent Job-log client.

## Removed Methods

| Removed method or parameter | Design disposition |
|---|---|
| `DynamoClient.get_job_status` | Deleted; no replacement and no Worker GET. |
| `DynamoClient.update_status` | Replaced by `StatusApiClient.update_job_status`. |
| `DynamoClient.append_log` | Deleted; Python logging only. |
| `WorkerOrchestrator._skip_if_already_done` | Deleted; every message is fully processed. |
| `WorkerOrchestrator(..., dynamo_client=...)` | Replaced by `status_client`. |
| `Config.dynamodb_table_name` | Deleted. |
