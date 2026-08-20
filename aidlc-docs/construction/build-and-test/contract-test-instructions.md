# Contract Test Instructions

## Scope

The Worker exposes no HTTP API. Its contracts are event and storage contracts shared with the Backend:
- SQS message schema version 1.0
- `requirements.json` object
- DynamoDB Job record fields and state values
- S3 input and output key conventions
- kiro-cli invocation and generated Gradle project marker

## Automated Contract Checks

Run the current executable contract tests:

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync --extra dev --frozen
uv run pytest \
  tests/test_requirements_contract.py \
  tests/test_sqs_client.py \
  tests/test_s3_client.py \
  tests/test_dynamo_client.py \
  tests/test_orchestrator.py \
  tests/test_ai_generator.py
```

These tests verify required SQS fields, schema version, UUID parsing, JSON object validation, fixed progress values, artifact keys, terminal-state behavior, and subprocess command construction.

## SQS Message Contract

Required payload:

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
- `schemaVersion` equals `1.0`.
- `jobId` parses as a UUID.
- `requirements.bucket` and `requirements.key` are non-empty strings.
- `assetsPrefix` is a string and may point to an empty prefix.
- Invalid messages are not deleted by the Worker.

## Requirements Contract

The Worker now enforces the canonical v1 contract:
- Maximum UTF-8 document size of 64 KiB
- JSON object with `schemaVersion`, `clientPayload`, `android`, and `assets`
- Draft 2020-12 schema at `contracts/requirements.schema.json`
- Unknown-field rejection outside arbitrary `clientPayload`
- Valid application ID, SDK range 21-35, Kotlin, and Jetpack Compose
- At most five basename-only PNG/JPEG asset descriptors
- Custom `minSdk <= targetSdk` cross-field validation

Shared valid and invalid fixtures live under `contracts/fixtures/`. Worker consumer tests execute every fixture. Backend producer CI still needs to consume the same schema and fixtures before live E2E or production readiness can be claimed.

## DynamoDB Contract

| Field | Type | Rule |
|---|---|---|
| `jobId` | String | Partition key, UUID text |
| `status` | String | Defined `JobStatus` value |
| `progress` | Number | 25, 50, 75, or 100 for Worker transitions |
| `message` | String | User-safe Korean status or failure message |
| `errorCode` | String | Present on failure |
| `artifactKey` | String | Present only after verified APK upload |
| `logs` | List of String | Append-only Worker-visible log entries |

Run a live contract read only in a test environment:

```bash
aws dynamodb describe-table --table-name "$DYNAMODB_TABLE_NAME"
aws dynamodb get-item \
  --table-name "$DYNAMODB_TABLE_NAME" \
  --key "{\"jobId\":{\"S\":\"${JOB_ID}\"}}" \
  --consistent-read
```

## S3 Key Contract

For each Job ID:
- Input requirements: `jobs/{jobId}/requirements/requirements.json`
- Optional assets: `jobs/{jobId}/assets/`
- Source output: `jobs/{jobId}/source/project.zip`
- APK output: `jobs/{jobId}/artifact/app-debug.apk`

Verify the APK object only after a successful live test:

```bash
aws s3api head-object \
  --bucket "$S3_BUCKET_NAME" \
  --key "jobs/${JOB_ID}/artifact/app-debug.apk"
```

## kiro-cli Contract

Validated local CLI contract:
- Version: 2.18.1
- Subcommand: `chat`
- Non-interactive option: `--no-interactive`
- Model: `claude-opus-5`
- Trusted tools: `fs_read,fs_write`

Compatibility check:

```bash
kiro-cli --version
kiro-cli chat --help
kiro-cli chat --list-models --format json-pretty
```

A prior `generate` assumption was rejected by the real CLI with exit status 2 and was corrected during Build and Test.

## Contract Release Gate

Contract status is partially verified. The versioned schema, shared fixtures, and Worker consumer checks are implemented alongside SQS, DynamoDB, S3 path, and CLI checks. Production release remains blocked until the Backend producer validates the same contract and live E2E passes.
