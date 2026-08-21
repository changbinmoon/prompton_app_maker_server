# Contract Test Instructions - ai-worker Status API Target

## 1. Contract Ownership

The Worker exposes no inbound HTTP API. It consumes an SQS/S3 contract and produces outbound Backend Status API PATCH commands plus S3 outputs.

| Contract | Worker ownership | External ownership |
|---|---|---|
| Status command construction/transport | URL, headers, JSON omission, timeout/retry/response classification | Backend persistence, duplicate-command idempotency, GET representation |
| SQS message | Parsing/validation, one-message processing, visibility/delete behavior | Backend producer and queue/DLQ configuration |
| S3 input/output | Raw requirements validation, asset handling, exact source/APK keys, artifact verification | Backend upload/pointer wiring and bucket policy |
| Hermes/Kiro/Gradle | Command shape, fallback, output expectations | Installed tool/provider/model/runtime compatibility |
| Mobile | None | Backend GET consumption and display |

## 2. Automated Contract Gate

```bash
set -euo pipefail
uv sync --frozen --extra dev
uv run pytest -q \
  tests/test_status_api_client.py \
  tests/test_orchestrator.py \
  tests/test_sqs_client.py \
  tests/test_s3_client.py \
  tests/test_requirements_contract.py \
  tests/test_prompt_refiner.py \
  tests/test_ai_generator.py
```

Expected: 99 tests pass. Run all 149 tests for the release gate.

## 3. Status API Request Contract

### Endpoint and headers

- Method: PATCH only.
- Path: `/v1/jobs/{jobId}/status` appended to normalized `PROMPTON_API_BASE_URL`.
- Always: `Content-Type: application/json`.
- Optional: `x-api-key` only for a configured nonblank `PROMPTON_STATUS_API_KEY`.
- Worker has no status GET method.

### Commands

ANALYZING:

```json
{
  "status": "ANALYZING",
  "progress": 25,
  "message": "요구조건을 분석하고 있습니다."
}
```

GENERATING_CODE:

```json
{
  "status": "GENERATING_CODE",
  "progress": 50,
  "message": "Android 코드를 생성하고 있습니다."
}
```

BUILDING:

```json
{
  "status": "BUILDING",
  "progress": 75,
  "message": "APK를 빌드하고 있습니다."
}
```

SUCCESS:

```json
{
  "status": "SUCCESS",
  "progress": 100,
  "message": "앱 생성이 완료되었습니다.",
  "artifactKey": "jobs/{jobId}/artifact/app-debug.apk"
}
```

Representative FAILED:

```json
{
  "status": "FAILED",
  "message": "APK 빌드에 실패했습니다.",
  "errorCode": "BUILD_FAILED"
}
```

FAILED omits `progress` and `artifactKey`. Every optional field whose value is `None` is omitted rather than sent as JSON null.

Approved error codes:

- `REQUIREMENTS_READ_FAILED`
- `INVALID_REQUIREMENTS`
- `AI_GENERATION_FAILED`
- `BUILD_FAILED`
- `ARTIFACT_UPLOAD_FAILED`
- `INTERNAL_ERROR`

### Response and retry contract

| Outcome | Worker treatment |
|---|---|
| Any 2xx | Success without parsing/reading the response body. |
| 5xx | Up to three total attempts with 1.0 and 2.0 second delays. |
| 4xx | Immediate typed failure; no retry. |
| Connection error | Immediate typed failure; no retry. |
| Connect/read timeout | Immediate typed failure; no retry. |
| Other non-2xx/non-5xx | Immediate typed failure. |

Every attempt uses requests timeout `(3, 10)` and default certificate verification.

### Criticality contract

- ANALYZING, GENERATING_CODE, BUILDING: best-effort; final failure logs a warning and processing continues.
- FAILED: best-effort; failure cannot replace the original Job error.
- SUCCESS: mandatory; final failure preserves the SQS message.
- SQS delete is permitted only after verified artifact and accepted SUCCESS.

## 4. External Backend Contract Tests

These tests mutate a dedicated dev Job and require explicit approval. They must be implemented/run by an authorized Backend harness or joint test participant, not by adding Worker GET production code.

Required scenarios:

1. Each valid command returns a 2xx and is observable through Backend GET.
2. Repeating ANALYZING after a prior terminal state is accepted for full redelivery processing.
3. Repeating the same accepted SUCCESS payload returns a 2xx.
4. Repeating FAILED is safe.
5. Empty or malformed request handling returns an agreed 4xx without exposing secrets.
6. Optional-key modes match the configured environment.
7. Backend stores exact message/progress/error/artifact semantics.

Capture HTTP status only unless the Backend team approves a sanitized response schema. Do not include response bodies or authentication values in the evidence bundle.

## 5. SQS Message Contract

Representative message:

```json
{
  "schemaVersion": "1.0",
  "jobId": "00000000-0000-4000-8000-000000000000",
  "requirements": {
    "bucket": "test-bucket",
    "key": "jobs/00000000-0000-4000-8000-000000000000/requirements/requirements.json"
  },
  "assetsPrefix": "jobs/00000000-0000-4000-8000-000000000000/assets/"
}
```

Acceptance rules:

- Top level is a JSON object.
- `schemaVersion` is `1.0`.
- `jobId` is a UUID.
- Requirements bucket/key are nonblank strings.
- `assetsPrefix` is a string and may identify an empty prefix.
- Invalid messages are not deleted by the Worker.
- Receive uses zero-second short polling, maximum one message, and a 0.5-second delay after empty responses.

## 6. Raw Requirements and S3 Contract

Runtime requirements input:

- UTF-8 JSON, at most 64 KiB.
- Top-level object; arbitrary nested Client fields are preserved.
- The optional Draft 2020-12 schema under `contracts/` is reference validation, not runtime enforcement.

Exact keys:

- Requirements: `jobs/{jobId}/requirements/requirements.json`.
- Optional assets: `jobs/{jobId}/assets/`.
- Source: `jobs/{jobId}/source/project.zip`.
- APK: `jobs/{jobId}/artifact/app-debug.apk`.

Artifact success requires upload followed by HeadObject/ContentLength equality with the local APK size before SUCCESS.

After an approved live SUCCESS, record metadata read-only:

```bash
aws s3api head-object \
  --bucket "$S3_BUCKET_NAME" \
  --key "jobs/${JOB_ID}/artifact/app-debug.apk" \
  --query '{ContentLength:ContentLength,ETag:ETag,LastModified:LastModified}'
```

## 7. Hermes, Kiro, and Gradle Contracts

Retained Worker contracts:

- Hermes restricted one-shot refinement, bounded three attempts, validated nonempty output, and raw fallback.
- Client JSON and Hermes stdout/stderr are not logged.
- Kiro uses the configured CLI/model contract and restricted filesystem tools.
- Gradle builder locates/runs the generated wrapper or approved fallback and copies a nonempty debug APK.

Non-mutating compatibility discovery on the approved host:

```bash
hermes --version
hermes --help
kiro-cli --version
kiro-cli chat --help
gradle --version
java -version
```

Version discovery does not prove a real provider/model/build flow; that requires the approved E2E window.

## 8. Contract Evidence Matrix

| Evidence | Local | External/live |
|---|---|---|
| PATCH URL/header/payload/omission | Fake-session tests | Backend request/status evidence |
| 2xx/4xx/5xx/network/timeout | Deterministic response matrix | Optional controlled Backend stub |
| Lifecycle ordering/criticality | Ordered orchestrator fakes | Joint Job evidence |
| Backend duplicate acceptance | N/A | Backend contract harness |
| SQS schema and lease/delete | Unit/moto tests | Queue attributes and Job evidence |
| S3 input/output/artifact verify | Unit/moto tests | Object metadata and APK hash |
| Backend GET/Mobile | N/A | Responsible teams |

## 9. Release Gate

Worker-owned contract automation is complete when the focused suites and full 149-test gate pass. Joint contract acceptance remains pending until an approved dev evidence bundle proves repeated Backend commands, Backend GET state, Mobile final display, verified APK, and SUCCESS-before-delete without sensitive data.
