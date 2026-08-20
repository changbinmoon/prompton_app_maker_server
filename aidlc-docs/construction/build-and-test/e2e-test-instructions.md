# End-to-End Test Instructions

## Purpose

Validate the complete workflow from a backend-produced Job through SQS reception, S3 input retrieval, Opus 5 Android code generation, Gradle APK build, S3 output upload, DynamoDB SUCCESS, and SQS deletion.

## Safety Boundary

This test mutates AWS resources, consumes model capacity, writes local build data, and may take more than 30 minutes. Run it only with explicit approval in a dedicated dev/test environment. Never purge a shared queue as cleanup.

## Preconditions

- Backend-approved, versioned `requirements.json` schema and fixture
- Dedicated test queue and DLQ with `maxReceiveCount=3`
- Dedicated S3 prefix or bucket and DynamoDB test records
- EC2 Instance Profile with least-privilege access
- kiro-cli 2.18.1 authenticated and `claude-opus-5` listed
- Gradle, Java, Android SDK, and writable cache paths validated
- Worker source synchronized with `uv sync --extra dev --frozen`
- systemd writable paths include `${WORK_DIR}` and the chosen Gradle cache

Preflight:

```bash
kiro-cli --version
kiro-cli chat --list-models --format json-pretty
gradle --version
java -version
aws sts get-caller-identity
sudo systemctl cat prompton-worker.service
sudo systemctl is-active prompton-worker.service
```

## E2E Scenario: Valid Job

1. Create a unique Job ID.
2. Insert a QUEUED DynamoDB item.
3. Upload the approved requirements fixture and optional PNG/JPEG assets.
4. Send the schema version 1.0 SQS message.
5. Observe state and progress transitions.
6. Wait for SUCCESS or FAILED without imposing a Worker timeout.
7. Verify source archive and APK objects.
8. Verify the DynamoDB `artifactKey` and sanitized logs.
9. Verify the SQS message is no longer receivable after SUCCESS.
10. Download the APK and perform basic Android artifact checks.

Use the setup and polling commands in `integration-test-instructions.md`.

## APK Verification

```bash
mkdir -p test-results/e2e
aws s3 cp \
  "s3://${S3_BUCKET_NAME}/jobs/${JOB_ID}/artifact/app-debug.apk" \
  "test-results/e2e/${JOB_ID}-app-debug.apk"
test -s "test-results/e2e/${JOB_ID}-app-debug.apk"
sha256sum "test-results/e2e/${JOB_ID}-app-debug.apk" \
  > "test-results/e2e/${JOB_ID}-app-debug.apk.sha256"
```

If Android Build Tools are available:

```bash
apkanalyzer manifest application-id \
  "test-results/e2e/${JOB_ID}-app-debug.apk"
apkanalyzer apk summary \
  "test-results/e2e/${JOB_ID}-app-debug.apk"
```

Optional emulator or device smoke test:

```bash
adb install -r "test-results/e2e/${JOB_ID}-app-debug.apk"
adb shell monkey -p "${EXPECTED_APPLICATION_ID}" 1
```

`EXPECTED_APPLICATION_ID` must come from the approved requirements contract.

## Acceptance Criteria

- Backend stores the original UTF-8 Client JSON object at the SQS-referenced key within 64 KiB.
- States appear in order: ANALYZING, GENERATING_CODE, BUILDING, SUCCESS.
- Progress values appear in order: 25, 50, 75, 100.
- Hermes runs before Kiro and records completion or explicit raw fallback without logging Client values.
- Kiro receives the raw JSON, assets, Android guardrails, and `refined-prompt.md` when available.
- Visibility extension prevents concurrent duplicate processing.
- Source archive and non-empty APK exist under the exact Job prefix.
- `artifactKey` points to the existing APK.
- Required logs exist and contain no credentials, tokens, signed URLs, internal paths, or user secrets.
- Message deletion happens only after SUCCESS.
- Downloaded APK is parseable by Android tooling and can be installed on the target API-level emulator or device.

## Failure-Path E2E

Use a separate Job in a dedicated queue:
- Force a deterministic generation or build failure.
- Verify FAILED and the correct error code.
- Verify last progress is preserved.
- Verify no artifact key is written.
- Verify the SQS message is retained and eventually redriven to the DLQ after three receives.
- Verify a retry recreates the Job directory cleanly.

## Cleanup

```bash
aws s3 rm "s3://${S3_BUCKET_NAME}/jobs/${JOB_ID}/" --recursive
aws dynamodb delete-item \
  --table-name "$DYNAMODB_TABLE_NAME" \
  --key "{\"jobId\":{\"S\":\"${JOB_ID}\"}}"
rm -rf "test-results/e2e/${JOB_ID}-"*
```

Handle any retained message by receipt handle on the dedicated test queue. Do not use `purge-queue` on a shared queue.

## Current Execution Status

Not executed in this Build and Test session. Raw Client JSON ingress, Hermes v0.20.4 command/retry/output handling, `refined-prompt.md`, and Kiro fallback are implemented and locally tested. A real run still requires the actual Backend endpoint to store/enqueue the raw object, provisioned service-user Hermes configuration, approved AWS mutations, Hermes provider usage, and Opus 5 usage. These remain production-readiness gates.
