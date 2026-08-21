# Components - Prompton AI Worker Status API Target Design

## Document Status

- **Stage**: Application Design
- **Scope**: Single deployable `ai-worker` process
- **Authoritative requirements**: `status-api-requirements.md`
- **Design rule**: Backend owns status persistence; the Worker emits PATCH requests and never reads Job status.

## 1. WorkerOrchestrator

**Purpose**: Coordinate one delivered SQS Job from a clean workspace through AI generation, APK verification, status reporting, and conditional message deletion.

**Responsibilities**:
- Poll SQS and process one Job at a time.
- Recreate `/data/jobs/{jobId}` for every delivery; never skip based on remote status.
- Start and stop the existing visibility extender around processing.
- Invoke ANALYZING, GENERATING_CODE, and BUILDING reports as best-effort operations.
- Invoke SUCCESS as a mandatory operation after verified S3 artifact upload.
- Delete the SQS message only after mandatory SUCCESS returns successfully.
- Classify processing failures and invoke FAILED as best-effort without replacing the original error.
- Emit sanitized phase and outcome events through Python logging.

**Interfaces**:
- Receives `SQSMessage` from `SQSClient`.
- Constructor-injects `StatusApiClient`, `SQSClient`, `S3Client`, `PromptRefiner`, `AIGenerator`, and `ApkBuilder` for deterministic testing.
- Does not construct or call any DynamoDB resource and does not call a Backend GET endpoint.

## 2. StatusApiClient

**Purpose**: Encapsulate the outbound Backend Status API transport contract.

**Responsibilities**:
- Join `PROMPTON_API_BASE_URL` with `/v1/jobs/{jobId}/status` without duplicate slashes.
- Build JSON payloads and omit fields whose value is `None`.
- Always send `Content-Type: application/json`.
- Add `x-api-key` only when `PROMPTON_STATUS_API_KEY` is non-empty.
- Call PATCH with connect/read timeout `(3, 10)` and default TLS verification.
- Treat any 2xx as success without parsing a response body.
- Apply the approved retry policy only to 5xx responses.
- Raise a sanitized typed exception after a final 4xx, 5xx, connection, or timeout failure.
- Log status, HTTP class, attempt count, and retry decisions without logging secrets, request bodies, or full response bodies.

**Interfaces**:
- Public operation: `update_job_status(...) -> None`.
- Production dependencies: `requests.Session` and a sleep function.
- Test seams: injectable session and sleep callable.
- No GET method exists.

## 3. Config

**Purpose**: Validate environment configuration and provide immutable runtime values to components.

**Responsibilities**:
- Require `SQS_QUEUE_URL`, `S3_BUCKET_NAME`, and non-empty `PROMPTON_API_BASE_URL`.
- Read optional `PROMPTON_STATUS_API_KEY`; normalize missing or empty input to `None`.
- Preserve existing AWS region, work directory, visibility, cleanup, logging, Hermes, Kiro, and Gradle settings.
- Remove `DYNAMODB_TABLE_NAME` from the model and startup contract.
- Never render the API key in errors or startup logs.

## 4. SQSClient

**Purpose**: Receive, validate, extend, and delete SQS messages through the existing AWS SDK boundary.

**Responsibilities**:
- Short-poll for one message and return a validated `SQSMessage`; the orchestrator waits 0.5 seconds after an empty response.
- Extend visibility through the existing API.
- Delete only when instructed by `WorkerOrchestrator` after mandatory SUCCESS.
- Preserve existing boto3 retry and IAM behavior.

**Status migration impact**: No public interface change. Terminal-status lookup and early message deletion are removed from the orchestrator, not moved into this component.

## 5. S3Client

**Purpose**: Manage Job inputs, optional source output, and the required APK artifact.

**Responsibilities**:
- Preserve raw Client JSON and asset ingress behavior.
- Upload source as an existing best-effort operation.
- Upload the APK, call HeadObject, compare remote and local sizes, and return the artifact key only after verification.
- Raise `ArtifactUploadError` before SUCCESS reporting when upload or verification fails.

**Status migration impact**: Update documentation language from “before DynamoDB SUCCESS” to “before mandatory Status API SUCCESS”; no public interface change is required.

## 6. PromptRefiner

**Purpose**: Run Hermes one-shot prompt refinement with the existing bounded retry and raw JSON fallback.

**Status migration impact**: No interface change. Phase activity is logged locally rather than appended to a DynamoDB `logs` array.

## 7. AIGenerator

**Purpose**: Run Kiro code generation and validate the Android project output.

**Status migration impact**: No interface change. The orchestrator sends GENERATING_CODE before invoking this generation path, and operational logs remain sanitized.

## 8. ApkBuilder

**Purpose**: Build and verify the local debug APK through Gradle and the Android SDK.

**Status migration impact**: No interface change. The orchestrator sends BUILDING before invoking this component.

## 9. VisibilityExtender

**Purpose**: Extend SQS visibility in a daemon thread while the current Job is processed.

**Status migration impact**: No interface change. It begins for every delivered message because terminal-status prechecks are removed and always stops in `finally`.

## 10. Shared Models, Exceptions, and Logging

**Purpose**: Provide transport-neutral Job statuses, approved error codes, safe user messages, and sanitized operational events.

**Responsibilities**:
- Reuse `JobStatus` and the six approved `ErrorCode` values.
- Add a typed Status API failure that classifies as `INTERNAL_ERROR` when mandatory SUCCESS fails.
- Ensure FAILED payloads omit progress and preserve the original processing exception if reporting also fails.
- Use Python logging for phase start/completion, PATCH results/retries, and final Job outcomes.
- Never log API keys, raw Client JSON, Hermes stdout/stderr, signed URLs, AWS credentials, or full Backend response bodies.

## Removed Component and Paths

| Removed design element | Replacement |
|---|---|
| `DynamoClient.get_job_status()` | No replacement; every delivered message is fully reprocessed. |
| Terminal SUCCESS/CANCELED skip and early SQS deletion | Removed; only mandatory SUCCESS 2xx authorizes deletion. |
| `DynamoClient.update_status()` | `StatusApiClient.update_job_status()`. |
| `DynamoClient.append_log()` | Sanitized Python logging to journald. |
| `dynamo` package and DynamoDB table construction | Removed from Worker runtime. |
| `DYNAMODB_TABLE_NAME` | Required `PROMPTON_API_BASE_URL` and optional `PROMPTON_STATUS_API_KEY`. |
| DynamoDB IAM actions | No status-storage IAM actions; retain SQS/S3 permissions. |

## External System Boundaries

| External system | Worker relationship | Ownership |
|---|---|---|
| Backend Status API | Outbound HTTPS PATCH only | Backend team |
| Backend GET API | Joint E2E observer; never called by Worker | Backend team |
| API Gateway, Lambda, DynamoDB | Hidden behind Backend API | Backend team |
| Mobile App | External acceptance observer | Mobile team |
| AWS SQS and S3 | Existing Worker data plane | Worker deployment |
| Hermes, Kiro, Gradle | Existing local subprocess dependencies | Worker deployment |
