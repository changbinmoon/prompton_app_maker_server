# Unit Test Execution

## Test Environment

- Python 3.12.3
- pytest 8.3.4
- moto 5.0.28
- boto3 1.35.99
- uv 0.8.12

AWS calls are isolated with fakes or moto. Unit tests do not require AWS credentials, a live queue, a live bucket, a live table, kiro-cli model execution, Gradle execution, or an Android SDK.

## Run Unit Tests

### 1. Synchronize the frozen development environment

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync --extra dev --frozen
```

### 2. Execute all tests

```bash
uv run pytest
```

Expected result for the current revision:
- Collected: 105
- Passed: 105
- Failed: 0
- Errors: 0

The suite can emit botocore `datetime.utcnow()` deprecation warnings through moto. They are currently non-blocking, but new warning categories should be reviewed rather than ignored globally.

### 3. Run component-focused tests

```bash
uv run pytest tests/test_config.py
uv run pytest tests/test_sqs_client.py
uv run pytest tests/test_s3_client.py
uv run pytest tests/test_dynamo_client.py
uv run pytest tests/test_ai_generator.py
uv run pytest tests/test_builder.py
uv run pytest tests/test_visibility_extender.py
uv run pytest tests/test_orchestrator.py
uv run pytest tests/test_cleanup.py
```

### 4. Run one failing test with full diagnostics

```bash
uv run pytest path/to/test_file.py::test_name -vv --showlocals --tb=long
```

Replace `path/to/test_file.py::test_name` with the node ID printed by pytest.

### 5. Generate a machine-readable report

```bash
mkdir -p test-results/unit
uv run pytest --junitxml=test-results/unit/pytest.xml
```

Report location: `test-results/unit/pytest.xml`.

## Test Coverage by Area

| Area | Main behaviors covered |
|---|---|
| Config | Required variables, defaults, validation, boto retry policy |
| SQS | Long polling, schema parsing, deletion, visibility extension |
| S3 | Requirements and assets, source archive, APK upload verification |
| DynamoDB | Status updates, progress preservation, logs, sanitization |
| AI generation | Real CLI argument shape via subprocess fake, model selection, output validation, failures |
| APK build | Wrapper handling, assembleDebug invocation, artifact discovery, failures |
| Orchestration | State sequence, idempotency, failure mapping, SQS deletion order, shutdown |
| Visibility extender | Interval, repeated extension, failure tolerance, stop behavior |
| Cleanup and log security | Work-directory lifecycle and sensitive-value redaction |

## Coverage Measurement

Statement or branch coverage is not currently configured, and no coverage percentage is claimed. The test gate is behavior-based: all 105 tests, lint, and strict type checking must pass. If a numeric coverage gate is introduced, add a pinned `pytest-cov` dependency through an explicit dependency-update change and record the agreed threshold before enforcing it.

## Failure Triage

1. Re-run the failing node ID with `-vv --showlocals --tb=long`.
2. Determine whether the failure is code, test isolation, dependency drift, or environment setup.
3. For moto failures, confirm the locked boto3, botocore, and moto versions were installed with `--frozen`.
4. For subprocess tests, verify they use `RunRecorder` or `GradleStub`; unit tests must not call a real model or real Gradle build.
5. Fix the cause, rerun the focused file, then rerun all 105 tests.
6. Run Ruff and mypy after every code change:

```bash
uv run ruff check .
uv run mypy main.py config models sqs s3 dynamo ai build utils worker
```
