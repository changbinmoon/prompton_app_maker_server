# Integration Test Instructions

## Purpose

Validate interactions among the single Worker unit's modules and its external dependencies: SQS, S3, DynamoDB, kiro-cli, Gradle, and the Android SDK. Local component integration is safe and repeatable. Live integration mutates AWS dev resources and consumes model/build capacity, so run it only in an isolated test environment or during an approved test window.

## Test Layers

| Layer | Services | Current status |
|---|---|---|
| Local component integration | boto3 with moto, orchestrator with injected dependencies | Executed as part of the 105-test suite; passed |
| CLI compatibility | Installed kiro-cli command and model discovery | Executed non-destructively; version 2.18.1 and model `claude-opus-5` confirmed |
| Live service integration | Real SQS, S3, DynamoDB, kiro-cli model call, Gradle/Android | Not executed; requires approved AWS mutation and a backend-valid requirements payload |

## Local Integration Suite

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync --extra dev --frozen
uv run pytest \
  tests/test_s3_client.py \
  tests/test_dynamo_client.py \
  tests/test_orchestrator.py \
  tests/test_visibility_extender.py \
  tests/test_ai_generator.py \
  tests/test_builder.py
```

Key interactions covered:
- S3 download, filtering, archive upload, APK upload, and post-upload size verification
- DynamoDB status, progress, artifact key, and append-only logs through moto
- Orchestrator ordering from ANALYZING through SUCCESS
- Failure-to-FAILED mapping and preservation of failed SQS messages
- Visibility extension lifecycle
- kiro-cli and Gradle subprocess command construction through deterministic fakes

## Live Integration Prerequisites

1. Use dedicated test SQS/DLQ, S3, and DynamoDB resources whenever possible.
2. Confirm the EC2 Instance Profile has only the required permissions.
3. Confirm the final `requirements.json` contract with the Backend team. The Worker currently validates only that it is a JSON object.
4. Confirm tool compatibility:

```bash
kiro-cli --version
kiro-cli chat --help
kiro-cli chat --list-models --format json-pretty
gradle --version
java -version
test -d "$ANDROID_HOME"
```

5. Load the test environment without static AWS keys:

```bash
set -a
source /etc/prompton-worker/env
set +a
aws sts get-caller-identity
aws sqs get-queue-attributes \
  --queue-url "$SQS_QUEUE_URL" \
  --attribute-names VisibilityTimeout RedrivePolicy
aws s3api head-bucket --bucket "$S3_BUCKET_NAME"
aws dynamodb describe-table --table-name "$DYNAMODB_TABLE_NAME"
```

## Scenario 1: Successful Job Across All Dependencies

### Setup

Use a Backend-produced canonical v1 payload before invoking the model:

```bash
set -euo pipefail
JOB_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
REQ_FILE="/tmp/requirements-${JOB_ID}.json"
cat > "$REQ_FILE" <<'JSON'
{
  "schemaVersion": "1.0",
  "clientPayload": {
    "requirements": "Backend-approved deterministic smoke application"
  },
  "android": {
    "applicationId": "com.prompton.integration.smoke",
    "minSdk": 26,
    "targetSdk": 35,
    "language": "Kotlin",
    "uiToolkit": "Jetpack Compose"
  },
  "assets": []
}
JSON

aws dynamodb put-item \
  --table-name "$DYNAMODB_TABLE_NAME" \
  --item "{\"jobId\":{\"S\":\"${JOB_ID}\"},\"status\":{\"S\":\"QUEUED\"},\"progress\":{\"N\":\"10\"}}"

aws s3 cp "$REQ_FILE" \
  "s3://${S3_BUCKET_NAME}/jobs/${JOB_ID}/requirements/requirements.json"

MESSAGE_BODY="$(python3 - "$JOB_ID" "$S3_BUCKET_NAME" <<'PY'
import json
import sys
job_id, bucket = sys.argv[1:]
print(json.dumps({
    "schemaVersion": "1.0",
    "jobId": job_id,
    "requirements": {
        "bucket": bucket,
        "key": f"jobs/{job_id}/requirements/requirements.json",
    },
    "assetsPrefix": f"jobs/{job_id}/assets/",
}))
PY
)"

aws sqs send-message \
  --queue-url "$SQS_QUEUE_URL" \
  --message-body "$MESSAGE_BODY"
printf 'JOB_ID=%s\n' "$JOB_ID"
```

### Execution

Run the Worker from a dedicated terminal or start the test EC2 service:

```bash
cd /opt/prompton-ai-worker
sudo systemctl start prompton-worker
sudo journalctl -u prompton-worker -f
```

Poll the Job from another terminal:

```bash
while true; do
  STATUS="$(aws dynamodb get-item \
    --table-name "$DYNAMODB_TABLE_NAME" \
    --key "{\"jobId\":{\"S\":\"${JOB_ID}\"}}" \
    --projection-expression '#s' \
    --expression-attribute-names '{"#s":"status"}' \
    --query 'Item.#s.S' --output text)"
  printf '%s status=%s\n' "$(date -u +%FT%TZ)" "$STATUS"
  case "$STATUS" in SUCCESS|FAILED) break ;; esac
  sleep 15
done
```

### Expected Results

- Status order is ANALYZING, GENERATING_CODE, BUILDING, SUCCESS.
- Progress values are 25, 50, 75, 100.
- Required logs are appended without credentials or signed URLs.
- `jobs/${JOB_ID}/source/project.zip` exists when source upload succeeds.
- `jobs/${JOB_ID}/artifact/app-debug.apk` exists and has non-zero size.
- DynamoDB `artifactKey` equals the APK key.
- The SQS message is deleted only after SUCCESS.
- `${WORK_DIR}/${JOB_ID}` is isolated with owner-only permissions.

Verify outputs:

```bash
aws s3api head-object \
  --bucket "$S3_BUCKET_NAME" \
  --key "jobs/${JOB_ID}/artifact/app-debug.apk"
aws dynamodb get-item \
  --table-name "$DYNAMODB_TABLE_NAME" \
  --key "{\"jobId\":{\"S\":\"${JOB_ID}\"}}" \
  --consistent-read
```

### Cleanup

```bash
aws s3 rm "s3://${S3_BUCKET_NAME}/jobs/${JOB_ID}/" --recursive
aws dynamodb delete-item \
  --table-name "$DYNAMODB_TABLE_NAME" \
  --key "{\"jobId\":{\"S\":\"${JOB_ID}\"}}"
rm -f "/tmp/requirements-${JOB_ID}.json"
```

Do not purge a shared queue. If the test fails before message deletion, remove only the identified test message or allow the dedicated test queue's redrive policy to handle it.

## Scenario 2: Failure and Retry Semantics

Run only on a dedicated test queue.

1. Submit a Job whose requirements object is valid JSON but deliberately causes a deterministic generation failure.
2. Verify FAILED contains the expected `errorCode`, retains the last progress value, and has no internal path in the user message.
3. Verify the SQS message is not deleted.
4. Verify redelivery after Visibility Timeout and DLQ movement after `maxReceiveCount=3`.
5. Delete all test resources after recording the receive count and DLQ evidence.

## Scenario 3: Visibility Extension

Use a valid test Job whose generation lasts longer than one configured Visibility Timeout.

1. Set the dedicated queue Visibility Timeout to a known safe value.
2. Observe `ChangeMessageVisibility` in CloudTrail or instrumented logs.
3. Verify extensions occur at approximately 50% of the timeout.
4. Confirm no second Worker receives the same Job while the lease is extended.
5. Confirm processing remains idempotent if one extension call is deliberately denied.

## Integration Logs

- Worker service: `journalctl -u prompton-worker`
- Job-visible logs: DynamoDB `logs`
- SQS delivery evidence: queue attributes and CloudWatch metrics
- Local generated project and APK: `${WORK_DIR}/${JOB_ID}`

Redact Job content and all credentials before sharing logs.
