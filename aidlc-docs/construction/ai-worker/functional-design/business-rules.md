# Business Rules - ai-worker Status API Target

## Document Authority

These rules define the target Functional Design for the active Status API migration. They supersede DynamoDB status-read/write and persistent-log clauses in the historical Worker baseline. Rules for the existing SQS, S3, Hermes, Kiro, Gradle, visibility, and workspace behavior remain unless explicitly changed below.

## 1. Message Lifecycle Rules

### BR-001: Process Every Valid Delivery from the Beginning

- A validated `SQSMessage` always starts a complete processing attempt.
- The Worker must not query Job status through DynamoDB or Backend GET.
- The Worker must not skip SUCCESS or CANCELED Jobs and must not delete a message based on a preflight status.
- Reprocessing deletes and recreates the local Job workspace before downloading inputs.
- Repeated status commands and overwrites of the same source/artifact S3 keys are allowed.

### BR-002: SQS Deletion Gate

The only successful deletion order is:

1. APK build succeeds.
2. Artifact upload succeeds.
3. HeadObject confirms the object and remote size matches local size.
4. SUCCESS PATCH is attempted as a mandatory command.
5. SUCCESS receives any 2xx response.
6. `DeleteMessage` is called.

No earlier event authorizes message deletion.

### BR-003: Failure Preserves the Message

- Requirements, AI, build, artifact, mandatory SUCCESS, and unexpected processing failures do not delete the message.
- FAILED reporting success or failure does not change this rule.
- Visibility expiry and queue redrive policy control subsequent delivery and DLQ behavior.
- If `DeleteMessage` itself fails after accepted SUCCESS, log an acknowledgment failure and leave the message for redelivery; do not issue a contradictory FAILED command after an accepted SUCCESS.

## 2. Status Command Rules

### BR-004: Per-Attempt Status Emission Order

The Worker attempts statuses in this order within one processing attempt:

1. ANALYZING immediately after workspace preparation and visibility start, before requirements download.
2. GENERATING_CODE after inputs are available, before Hermes and Kiro.
3. BUILDING after code generation succeeds, before Gradle.
4. SUCCESS only after verified artifact upload.

A failed best-effort status command can be absent from Backend state without changing the local phase order. FAILED may be attempted from any processing failure path before message deletion.

### BR-005: Exact Status Payloads

| Status | Required JSON fields | Omitted fields |
|---|---|---|
| ANALYZING | `status=ANALYZING`, `progress=25`, `message=요구조건을 분석하고 있습니다.` | `artifactKey`, `errorCode` |
| GENERATING_CODE | `status=GENERATING_CODE`, `progress=50`, `message=Android 코드를 생성하고 있습니다.` | `artifactKey`, `errorCode` |
| BUILDING | `status=BUILDING`, `progress=75`, `message=APK를 빌드하고 있습니다.` | `artifactKey`, `errorCode` |
| SUCCESS | `status=SUCCESS`, `progress=100`, `message=앱 생성이 완료되었습니다.`, verified `artifactKey` | `errorCode` |
| FAILED | `status=FAILED`, safe `message`, approved `errorCode` | `progress`, `artifactKey` |

Each command is one JSON object. Optional fields with `None` values are omitted rather than serialized as JSON null.

### BR-006: Artifact Key Gate

- The SUCCESS artifact key is exactly `jobs/{jobId}/artifact/app-debug.apk`.
- It can enter a SUCCESS command only after upload plus HeadObject/size verification returns normally.
- Source upload outcome cannot bypass or reorder this gate.

### BR-007: Progress Semantics

- ANALYZING uses 25, GENERATING_CODE 50, BUILDING 75, and SUCCESS 100.
- FAILED does not send progress, so Backend may preserve its previously stored value.
- The Worker does not calculate intermediate percentages outside this mapping.

### BR-008: Error Classification and Safe Messages

| Error source | `errorCode` | Safe FAILED message |
|---|---|---|
| Requirements download/read failure | `REQUIREMENTS_READ_FAILED` | `요구조건 파일을 읽지 못했습니다.` |
| Requirements or raw JSON validation failure | `INVALID_REQUIREMENTS` | `요구조건 형식이 올바르지 않습니다.` |
| Kiro generation or generated-project validation failure | `AI_GENERATION_FAILED` | `앱 코드 생성에 실패했습니다.` |
| Gradle or APK build failure | `BUILD_FAILED` | `APK 빌드에 실패했습니다.` |
| Required artifact upload or verification failure | `ARTIFACT_UPLOAD_FAILED` | `빌드 결과 업로드에 실패했습니다.` |
| Mandatory SUCCESS failure or unclassified internal failure | `INTERNAL_ERROR` | `내부 오류가 발생했습니다.` |

Hermes exhaustion alone is not a Job failure and proceeds to raw JSON fallback.

### BR-009: FAILED Is Best-Effort and Preserves the Original Error

- Capture the original exception, errorCode, and safe message before reporting FAILED.
- Send only FAILED, safe message, and errorCode.
- If FAILED reporting fails, log sanitized reporting metadata and preserve the original values.
- Never raise the reporting failure in place of the original failure.
- Never include stack trace, internal path, credential, token, API key, raw Client JSON, or Backend response body in the user message.

## 3. Status API Transport Decision Rules

### BR-010: Endpoint and URL Joining

- Method is PATCH.
- Base URL comes from required `PROMPTON_API_BASE_URL`.
- Path is `/v1/jobs/{jobId}/status`.
- Strip trailing slash characters from the base before appending the fixed path.
- Job ID is the UUID already validated by `SQSMessage` parsing.
- No GET operation exists in the Worker client.

### BR-011: Header Construction

- Always send `Content-Type: application/json`.
- Add `x-api-key` only when normalized `PROMPTON_STATUS_API_KEY` is non-empty.
- Header construction is centralized in the Status API client.
- The key must not appear in logs, exceptions, source, or test evidence.

### BR-012: Response Classification

| Final result | Decision |
|---|---|
| Any 2xx | Success; return without parsing response JSON |
| Any 4xx | Final failure; no retry |
| Any 5xx | Apply BR-013 bounded retry |
| Connection error | Final failure; no retry |
| Connect or read timeout | Final failure; no retry |
| Other final non-2xx response | Final failure; no retry because only 5xx is retryable |

The response body is not an input to success classification and is never logged in full.

### BR-013: 5xx Retry and Timeout

- Maximum is three total HTTP attempts, including the initial request.
- After first 5xx, wait 1 second.
- After second 5xx, wait 2 seconds.
- After third 5xx, raise final `StatusApiFailure`.
- A later 2xx completes successfully without another attempt.
- A 4xx, connection error, or timeout on any attempt stops immediately without sleep.
- Every request uses connect timeout 3 seconds and read timeout 10 seconds.

### BR-014: Status Criticality

| Status | Final Status API failure handling |
|---|---|
| ANALYZING | Warning; continue requirements, AI, and build flow |
| GENERATING_CODE | Warning; continue Hermes and Kiro flow |
| BUILDING | Warning; continue Gradle flow |
| SUCCESS | Propagate as completion failure; do not delete SQS |
| FAILED | Error log; preserve original failure; do not delete SQS |

Transport logic raises the same typed failure contract; the orchestrator applies this criticality table.

### BR-015: Mandatory SUCCESS Failure

- A final SUCCESS command failure is classified as `INTERNAL_ERROR`.
- The Worker then attempts one FAILED command through the normal Status API client policy.
- FAILED reporting remains best-effort and does not authorize deletion.
- The previously verified S3 artifact is not removed by this flow.

## 4. Visibility and Queue Rules

### BR-016: Visibility Extension Lifecycle

- Start after clean workspace preparation and before ANALYZING reporting.
- Use the queue Visibility Timeout and the existing 50% extension interval.
- Stop in `finally` after success, processing failure, status failure, or delete attempt.

### BR-017: Visibility Extension Failure

An extension error is logged locally and does not stop Job processing. The Worker makes no status read to resolve possible duplicate execution.

## 5. Input, AI, Build, and S3 Rules

### BR-018: SQS Message Validation and Reporting Boundary

- Required fields are `schemaVersion`, `jobId`, `requirements.bucket`, `requirements.key`, and `assetsPrefix`.
- Supported schema version is `1.0`; Job ID must be a UUID.
- Status API activity begins only after a complete validated `SQSMessage` exists.
- An invalid envelope without a validated Job ID cannot address the Job status endpoint; retain it for queue redrive and log only sanitized validation metadata.

### BR-019: Raw Requirements Validation

- Download from the message-specified S3 bucket/key.
- Maximum size is 64 KiB before JSON parsing.
- Require UTF-8, valid JSON, and a top-level object.
- Preserve arbitrary root/nested fields; the canonical reference schema is not runtime ingress enforcement.
- Read failures map to `REQUIREMENTS_READ_FAILED`; content validation failures map to `INVALID_REQUIREMENTS`.

### BR-020: Optional Assets

- No asset is a valid condition.
- Accept PNG and JPEG only, sorted and limited to five.
- Individual asset or listing failure is logged and processing continues with available/empty assets.

### BR-021: Hermes Refinement and Kiro Fallback

- Run after raw JSON and assets are available and after GENERATING_CODE reporting.
- Hermes uses `--ignore-rules --toolsets context_engine --oneshot`.
- Permit three total Hermes attempts with 1-second/2-second delay.
- Accept only non-empty, NUL-free, UTF-8 output at most 64 KiB; write atomically to `refined-prompt.md`.
- On exhaustion, continue Kiro with raw JSON, assets, and the same Android guardrails.
- Do not log raw JSON or Hermes stdout/stderr.
- Kiro failure maps to `AI_GENERATION_FAILED`.

### BR-022: Build and Artifact

- Report BUILDING before Gradle.
- Build through the existing wrapper/assembleDebug flow without a Worker timeout.
- Copy the selected APK to the Job output path.
- Upload to the fixed artifact key and verify HeadObject/size before returning the key.
- Build errors map to `BUILD_FAILED`; artifact errors map to `ARTIFACT_UPLOAD_FAILED`.

### BR-023: Source Upload

- Source archive key is `jobs/{jobId}/source/project.zip`.
- Source upload occurs after APK build and before required artifact finalization.
- Source upload is best-effort; its failure is logged and cannot prevent artifact upload or SUCCESS.

## 6. Workspace and Cleanup Rules

### BR-024: Clean Job Workspace

- Job base path is `/data/jobs/{jobId}` under configured `WORK_DIR`.
- Delete an existing Job directory recursively and recreate it before every processing attempt.
- Restrict the recreated directory to owner access when supported.
- Include requirements, optional refined prompt, assets, generated project, output, and APK paths.

### BR-025: Periodic Cleanup

- Before polling for a new message, remove Job directories older than configured retention (default 24 hours).
- Cleanup failure is warning-only and does not stop polling.

## 7. Logging and Configuration Rules

### BR-026: Journald Event Set

Python logging must emit sanitized events for:
- Job and phase start/completion.
- Status command success/failure, status class, and attempt count.
- Each 5xx retry and delay selection.
- Hermes fallback, source-upload warning, artifact verification, and visibility warning.
- Final Job success or original errorCode.

No DynamoDB `logs` append or Backend log endpoint is used.

### BR-027: Sensitive Data Exclusion

Never log API key, authentication headers, raw Client JSON, Hermes stdout/stderr, AWS credentials, session token, signed URL, or full Backend response body. User-facing messages come only from the approved safe-message mapping.

### BR-028: Target Configuration and Dependency Boundary

- Required: `SQS_QUEUE_URL`, `S3_BUCKET_NAME`, `PROMPTON_API_BASE_URL`.
- Optional: `PROMPTON_STATUS_API_KEY` plus existing non-status settings.
- Remove `DYNAMODB_TABLE_NAME` and all Worker DynamoDB runtime paths.
- Pin `requests==2.34.2`; retain boto3 for SQS/S3.
- TLS certificate verification remains enabled.

## 8. Requirement and Story Traceability

| Source | Functional realization |
|---|---|
| FR-SA-001, FR-SA-002, FR-SA-003 | BR-005, BR-010, BR-011, BR-028 |
| FR-SA-004, FR-SA-005, FR-SA-006, FR-SA-007 | BR-002, BR-004, BR-005, BR-006 |
| FR-SA-008 | BR-008, BR-009, BR-015 |
| FR-SA-009, FR-SA-010, FR-SA-011, FR-SA-012 | BR-012, BR-013, BR-014 |
| FR-SA-013, FR-SA-014 | BR-001, BR-024 |
| FR-SA-015, FR-SA-016 | BR-026, BR-027 |
| FR-SA-017, FR-SA-018 | BR-028 |
| NFR-SA-001, NFR-SA-002, NFR-SA-003 | BR-011, BR-027, BR-028; measurable realization continues in NFR stages |
| TR-SA-001, TR-SA-002, TR-SA-003, TR-SA-004 | Decision tables and injection boundaries define deterministic tests and joint E2E observations |
| US-SA-01, US-SA-02, US-SA-03 | Configuration, phase commands, verified completion, and deletion gate |
| US-SA-04, US-SA-05, US-SA-06, US-SA-07 | Failure preservation, HTTP decisions, protected observability, and acceptance evidence |
