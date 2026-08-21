# Unit Test Instructions - ai-worker Status API Target

## 1. Scope

The test suite validates the outbound Status API client, Worker lifecycle ordering, configuration/startup safety, retained SQS/S3/Hermes/Kiro/Gradle behavior, visibility extension, workspace cleanup, and optional reference requirements schema.

All tests are deterministic and local:

- Status API calls use injected fake sessions and sleep recorders.
- Orchestrator interactions use injected fakes and ordered call records.
- S3/SQS tests use moto or local stubs.
- Hermes, Kiro, and Gradle tests use subprocess recorders/stubs.
- No AWS credentials, live queue/bucket, live HTTP endpoint, model invocation, Android SDK, or deployment is required.

## 2. Test Environment

| Tool/dependency | Required version/contract |
|---|---|
| Python | 3.12 |
| pytest | 8.3.4 |
| moto | 5.0.28 with SQS/S3 extras only |
| boto3 | 1.35.99 |
| requests | 2.34.2 |
| uv | Compatible with committed `uv.lock` |

Prepare the frozen environment from the repository root:

```bash
set -euo pipefail
uv lock --check
uv sync --frozen --extra dev
```

## 3. Run the Complete Suite

```bash
uv run pytest -q
```

Expected result for this revision:

- Collected: 149.
- Passed: 149.
- Failed/errors: 0.
- Warnings: 70 botocore `datetime.utcnow()` deprecation warnings emitted by moto-backed S3 tests.

A new warning category or a count change must be reviewed. Do not add a global warning suppression merely to preserve the expected count.

## 4. Suite Inventory

| Test file | Tests | Primary evidence |
|---|---:|---|
| `tests/test_ai_generator.py` | 9 | Refined/raw prompt selection, Kiro command shape, output/failure handling. |
| `tests/test_builder.py` | 7 | Gradle wrapper/build command, APK discovery/copy, failure handling. |
| `tests/test_cleanup.py` | 17 | Workspace recreation/cleanup, owner-only mode, log sanitization. |
| `tests/test_config.py` | 18 | Required API URL, optional key normalization, repr protection, defaults, boto retry config. |
| `tests/test_main.py` | 2 | Safe API-base startup output, key/table exclusion, config failure. |
| `tests/test_orchestrator.py` | 24 | Status sequence, criticality, redelivery, artifact/SUCCESS/delete ordering, failure preservation, visibility/shutdown/log safety. |
| `tests/test_prompt_refiner.py` | 10 | Hermes command, retry/output limits, atomic output, safe fallback/logging. |
| `tests/test_requirements_contract.py` | 11 | Optional canonical reference schema only; not the runtime S3 ingress boundary. |
| `tests/test_s3_client.py` | 15 | Raw JSON ingress, assets, source archive, artifact upload and HeadObject/size verification. |
| `tests/test_sqs_client.py` | 11 | Long polling, one-message receive, schema validation, delete/visibility/attributes. |
| `tests/test_status_api_client.py` | 19 | URL, headers, payload omission, any-2xx, timeout, retry matrix, typed failures, log secrecy. |
| `tests/test_visibility_extender.py` | 6 | 50% cadence, repeated extension, warning-only failure, stop behavior. |
| **Total** | **149** | Complete deterministic Worker gate. |

## 5. Focused Test Commands

### Status API transport contract

```bash
uv run pytest -q tests/test_status_api_client.py
```

Required behaviors:

- PATCH-only normalized URL.
- Always `Content-Type: application/json`.
- Optional `x-api-key` only for a nonblank configured key.
- Exact field names and omission of every `None` value.
- Every 2xx succeeds without response-body parsing.
- 5xx only: three total attempts and delays `[1.0, 2.0]`.
- 4xx, connection error, connect timeout, read timeout, and other non-2xx/non-5xx fail immediately.
- Every attempt uses `timeout=(3, 10)` with default TLS verification.
- Typed sanitized failure and zero key/payload/body/raw-exception disclosure.

### Orchestrator lifecycle and ordering

```bash
uv run pytest -q tests/test_orchestrator.py
```

Required behaviors:

- Every valid redelivery recreates the workspace and performs the full pipeline.
- No Worker status GET and no terminal-state skip.
- ANALYZING, GENERATING_CODE, and BUILDING final reporting failures are warning-only.
- Artifact upload plus HeadObject/size verification precedes SUCCESS.
- SUCCESS 2xx precedes SQS DeleteMessage.
- SUCCESS failure becomes `INTERNAL_ERROR`, attempts best-effort FAILED, and preserves the message.
- FAILED omits progress/artifact and a FAILED-reporting failure preserves the original classification.
- Delete failure after accepted SUCCESS emits no contradictory FAILED.
- Visibility extension starts/stops on every tested path.

### Configuration and startup safety

```bash
uv run pytest -q tests/test_config.py tests/test_main.py
```

Required behaviors:

- Required `SQS_QUEUE_URL`, `S3_BUCKET_NAME`, and `PROMPTON_API_BASE_URL` reject missing/blank values.
- Trailing API-base slashes are normalized.
- Blank/whitespace optional key becomes `None` and is absent from Config repr.
- Startup logs the API base but not the key or removed table setting.

### Retained AWS data-plane behavior

```bash
uv run pytest -q \
  tests/test_sqs_client.py \
  tests/test_s3_client.py \
  tests/test_visibility_extender.py
```

### Retained AI/build behavior

```bash
uv run pytest -q \
  tests/test_prompt_refiner.py \
  tests/test_ai_generator.py \
  tests/test_builder.py
```

### Workspace, log safety, and optional schema

```bash
uv run pytest -q \
  tests/test_cleanup.py \
  tests/test_requirements_contract.py
```

## 6. Security and Non-Disclosure Assertions

The automated gate must retain sentinel coverage proving logs do not contain:

- API key or authentication header values.
- Raw Client JSON.
- Hermes stdout/stderr.
- AWS access keys/session tokens.
- Signed URLs.
- Backend response-body content.
- Raw requests/network exception text.

Run the security-relevant focused set:

```bash
uv run pytest -q \
  tests/test_status_api_client.py \
  tests/test_orchestrator.py \
  tests/test_config.py \
  tests/test_main.py \
  tests/test_cleanup.py
```

## 7. Static Quality Coupled to Unit Tests

After any source or test change:

```bash
uv run ruff check .
uv run mypy .
uv run python -m compileall -q .
```

Expected:

- Ruff exits 0.
- strict mypy reports no issues across 39 files.
- compileall exits 0.

Do not narrow the mypy target, weaken strict settings, add broad ignores, or skip a failing file.

## 8. Optional Machine-Readable Result

```bash
mkdir -p test-results/unit
uv run pytest -q --junitxml=test-results/unit/pytest.xml
```

The generated report may contain test names and local paths. Review it for sensitive values before attaching it to an external evidence bundle.

## 9. Coverage Policy

No statement or branch coverage percentage was approved, and `pytest-cov` is not a project dependency. The release gate is behavior-based: all 149 tests and static quality checks must pass. Do not invent a percentage or install an unpinned plugin merely for this stage.

## 10. Failure Triage

1. Copy the failing node ID from pytest output.
2. Rerun it with full diagnostics:

```bash
uv run pytest 'path/to/test_file.py::test_name' -vv --showlocals --tb=long
```

3. Determine whether the cause is implementation behavior, test isolation, dependency drift, or host configuration.
4. Confirm `uv lock --check` and frozen sync before changing code.
5. For HTTP tests, confirm no real `requests.Session` or sleep path escaped injection.
6. For AWS tests, confirm moto/stubs are active and no credential chain reaches a live account.
7. For subprocess tests, confirm recorders/stubs are used; do not invoke Hermes, Kiro, or Gradle to diagnose a unit failure.
8. Fix the narrow cause, rerun the focused file, then rerun all 149 tests and static gates.

## 11. Requirement and Story Evidence

- `TR-SA-001` and `US-SA-05`: `tests/test_status_api_client.py`.
- `TR-SA-002`, `US-SA-02`, `US-SA-03`, and `US-SA-04`: `tests/test_orchestrator.py` plus retained component suites.
- `FR-SA-017`, `US-SA-01`, and `US-SA-06`: config/main/security-focused tests.
- `TR-SA-003` and automated portion of `US-SA-07`: full pytest, Ruff, mypy, compileall, lock, and frozen sync.
- `TR-SA-004` and live portions of `US-SA-03`, `US-SA-06`, and `US-SA-07`: not unit-test evidence; use the separately authorized integration/E2E instructions.
