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
  tests/test_prompt_refiner.py \
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

## Raw Client Requirements Contract

The Worker runtime accepts the original Client JSON object:
- Maximum UTF-8 document size of 64 KiB, checked before parsing
- Valid UTF-8 and JSON syntax
- Top-level object
- Arbitrary root and nested fields preserved
- No runtime enforcement of the optional canonical envelope schema

`tests/test_s3_client.py` proves raw objects, Unicode, empty objects, and former schema-invalid
objects are accepted while malformed, non-object, non-UTF-8, and oversized inputs are rejected.

The Draft 2020-12 schema and fixtures under `contracts/` remain optional reference artifacts.
`tests/test_requirements_contract.py` validates them independently and does not represent the S3
consumer boundary.

## Hermes and Kiro Prompt Contract

- Hermes command: `--ignore-rules --toolsets context_engine --oneshot {prompt}`
- Provider/model: Hermes host configuration
- Android guardrails: Kotlin, Jetpack Compose, API level range/defaults, Job-based application ID
- Output: non-empty, no NUL, maximum 64 KiB, atomic `refined-prompt.md`
- Retry: three total attempts with 1-second and 2-second delays
- Fallback: Kiro reads original JSON and assets with the same guardrails
- Logging: Client JSON and Hermes stdout/stderr are not logged

`tests/test_prompt_refiner.py`, `tests/test_ai_generator.py`, and `tests/test_orchestrator.py`
validate command construction, retry, output rejection, refined prompt use, and raw fallback.

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

Contract status is locally verified for raw S3 ingress, Hermes command/retry/output behavior, Kiro fallback, SQS, DynamoDB, and S3 paths. Production release remains blocked until the actual Backend stores the raw object and enqueues its pointer, the service-user Hermes host configuration is provisioned, and live E2E passes.
