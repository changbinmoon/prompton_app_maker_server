# Integration Test Instructions - ai-worker Status API Target

## 1. Purpose and Safety Boundary

Validate interactions among the single Worker unit's internal components and its external boundaries: Backend Status API, SQS, S3, Hermes, Kiro, Gradle/Android, systemd, and journald.

Two layers are intentionally separate:

| Layer | Authorization | Status |
|---|---|---|
| Local component integration with fakes/moto | Allowed local deterministic gate | Passed within the 149-test suite. |
| Target-host readiness and live joint integration | Requires approved environment, Job ID, participants, and test window | Not executed by instruction generation. |

A live run can mutate Backend state, SQS, and S3; consume Hermes/Kiro capacity; and build an Android project. Do not execute live commands, start/restart the service, submit a Job, alter queue attributes, or clean cloud data without explicit approval.

## 2. Local Component Integration

Prepare the frozen environment and run the interaction-heavy suites:

```bash
set -euo pipefail
uv lock --check
uv sync --frozen --extra dev
uv run pytest -q \
  tests/test_status_api_client.py \
  tests/test_orchestrator.py \
  tests/test_sqs_client.py \
  tests/test_s3_client.py \
  tests/test_visibility_extender.py \
  tests/test_prompt_refiner.py \
  tests/test_ai_generator.py \
  tests/test_builder.py
```

Covered interactions:

- Exact Status API URL/header/payload, timeout, any-2xx, and 5xx-only retry behavior.
- Orchestrator command sequence and intermediate-reporting degradation.
- Full redelivery with workspace recreation and no status read/preflight skip.
- Artifact upload and HeadObject/size verification before SUCCESS.
- Accepted SUCCESS before SQS deletion.
- FAILED omission/original-error preservation and post-SUCCESS delete-failure behavior.
- SQS 500ms empty-response polling cadence, one-message processing, deletion, and visibility extension.
- S3 raw requirements/assets/source/artifact behavior.
- Hermes refinement/fallback, Kiro command, and Gradle build interactions through deterministic recorders.

Expected result: 101 tests pass across these eight files. The complete release gate remains all 149 tests.

## 3. Target-Host Readiness (No Job Submission)

Run only with authorization to inspect the dev/test host and AWS account.

### 3.1 Load protected configuration without printing it

```bash
set -euo pipefail
set -a
# shellcheck disable=SC1091
source /etc/prompton-worker/env
set +a
: "${SQS_QUEUE_URL:?required}"
: "${S3_BUCKET_NAME:?required}"
: "${PROMPTON_API_BASE_URL:?required}"
```

Never run `env`, `set`, `curl -v`, shell tracing, or commands that print `PROMPTON_STATUS_API_KEY`.

### 3.2 Record identity and read-only AWS readiness

```bash
aws sts get-caller-identity
aws sqs get-queue-attributes \
  --queue-url "$SQS_QUEUE_URL" \
  --attribute-names VisibilityTimeout RedrivePolicy
aws s3api head-bucket --bucket "$S3_BUCKET_NAME"
```

Record sanitized outputs. The expected redrive planning value is `maxReceiveCount=3`; if deployed configuration differs, stop and obtain owner review rather than modifying it.

### 3.3 Verify HTTPS/TCP 443 and certificate validation

```bash
python3 - <<'PY'
import os
import socket
import ssl
from urllib.parse import urlparse

url = os.environ["PROMPTON_API_BASE_URL"]
parsed = urlparse(url)
assert parsed.scheme == "https"
assert parsed.hostname
context = ssl.create_default_context()
with socket.create_connection((parsed.hostname, 443), timeout=3) as raw:
    with context.wrap_socket(raw, server_hostname=parsed.hostname) as tls:
        print("TLS", tls.version(), "host", parsed.hostname)
PY
```

This is a non-mutating TLS handshake. It does not validate the PATCH schema or authorize disabling verification.

### 3.4 Verify service and filesystem readiness

```bash
sudo systemctl cat prompton-worker.service
sudo systemctl is-enabled prompton-worker.service
sudo stat -c '%U %G %a %n' /etc/prompton-worker/env
sudo -u prompton test -w /data/jobs
sudo -u prompton test -w /data/hermes
sudo -u prompton test -w /data/gradle
```

Do not start/restart the service as part of readiness inspection.

### 3.5 Verify external tools non-destructively

```bash
hermes --version
hermes --help
kiro-cli --version
kiro-cli chat --help
gradle --version
java -version
test -d "$ANDROID_HOME"
```

Do not invoke Hermes one-shot, Kiro chat generation, or Gradle on a generated project until the test window is approved.

## 4. Joint Success-Path Integration Scenario

### Preconditions

- A dedicated dev/test environment and unique approved Job ID.
- Backend participant able to create the Job, store the raw requirements object, enqueue its S3 pointer, and perform Backend GET observations.
- Worker operator, S3/SQS evidence owner, and Mobile observer identified.
- Target commit/revision deployed through an approved process.
- Status API authentication mode confirmed; any key is injected through the protected environment only.
- IAM policy inspected: approved SQS/S3 actions present and Worker DynamoDB actions absent.
- Dedicated queue/DLQ attributes recorded.
- Evidence destination created without secrets.

### Execution

1. Record the commit SHA, UTC start time, environment, Job ID, queue, bucket, and participants.
2. Have the Backend submit one approved deterministic dev Job. Do not bypass Backend ownership unless a dedicated harness procedure is separately approved.
3. Observe sanitized Worker journald events for that Job ID.
4. Have the Backend observer record GET-visible states; the Worker itself must not issue GET.
5. Have the Mobile observer record user-visible progress/final status.
6. After SUCCESS, read S3 object metadata and record SQS deletion/queue evidence.
7. Download the APK only to the approved evidence host, calculate SHA-256, and optionally inspect it with Android tooling.

Sanitized Worker observation:

```bash
mkdir -p test-results/integration
sudo journalctl \
  -u prompton-worker \
  --since "$TEST_START_UTC" \
  --no-pager \
  | grep -F "$JOB_ID" \
  > "test-results/integration/${JOB_ID}-worker.log"
```

Before sharing, inspect the captured file for raw requirements, keys, credentials, signed URLs, response bodies, and internal secrets.

Artifact metadata after observed SUCCESS:

```bash
aws s3api head-object \
  --bucket "$S3_BUCKET_NAME" \
  --key "jobs/${JOB_ID}/artifact/app-debug.apk" \
  --query '{ContentLength:ContentLength,ETag:ETag,LastModified:LastModified}'
```

Expected lifecycle:

1. Worker PATCHes ANALYZING (25).
2. Worker PATCHes GENERATING_CODE (50).
3. Worker PATCHes BUILDING (75).
4. Worker uploads and verifies the APK.
5. Worker PATCHes SUCCESS (100 plus exact artifact key).
6. Status API returns 2xx.
7. Worker calls SQS DeleteMessage.
8. Backend GET and Mobile show SUCCESS with the same artifact result.

Intermediate state observation may miss a short-lived state due to polling timing. The evidence must still establish PATCH acceptance through sanitized Worker/Backend records without exposing response bodies.

## 5. Controlled Failure Scenarios

Execute only if each fault injection is approved and reversible.

### 5.1 Intermediate Status API failure

Use a Backend-owned test stub or routing mechanism; do not change production DNS/firewalls. Cause one intermediate status command to end in final failure.

Expected:

- Warning event includes Job ID, status, failure class, and attempts.
- AI/build flow continues.
- No key, payload, body, or raw exception text appears.

### 5.2 SUCCESS final failure

Cause SUCCESS reporting to fail only in the dedicated environment.

Expected:

- Verified artifact may exist.
- Worker classifies completion as `INTERNAL_ERROR` and attempts best-effort FAILED.
- SQS message is not deleted.
- Redelivery performs the full pipeline again.

### 5.3 Delete failure after accepted SUCCESS

Cause only DeleteMessage to fail after Backend accepted SUCCESS.

Expected:

- SUCCESS remains authoritative.
- Worker emits a sanitized acknowledgment warning.
- Worker sends no contradictory FAILED.
- Message can redeliver and the full pipeline can repeat.

### 5.4 Processing failure

Use a deterministic approved build/generation failure.

Expected:

- FAILED contains the original safe message and approved error code.
- FAILED omits progress and artifact key.
- Message is retained and eventually follows the dedicated queue redrive policy.

## 6. Evidence and Cleanup

Required sanitized evidence:

- Commit SHA and UTC timestamps.
- Job ID and approved environment identifiers.
- Worker status-attempt outcomes without response bodies.
- Backend GET state observations supplied by Backend.
- Mobile observations supplied by Mobile.
- S3 key, ContentLength, and downloaded APK SHA-256.
- SQS deletion or queue-state/redrive evidence.
- Queue VisibilityTimeout and RedrivePolicy.
- Environment owner/group/mode, IAM review, and TLS handshake result.

Cleanup must be performed by the resource owner using the unique Job ID and dedicated prefixes. Never purge a shared queue, delete unrelated objects, rotate shared credentials, or weaken IAM/firewall/TLS settings. If a failed test message remains, coordinate receipt-handle deletion or allow the dedicated DLQ policy to retain it for diagnosis.

## 7. Exit Criteria

Local integration is complete when focused suites and the full 149-test gate pass. Joint integration is complete only when the approved evidence bundle proves:

- Backend accepts repeated state commands and same accepted SUCCESS on redelivery.
- Artifact verification precedes SUCCESS.
- SUCCESS 2xx precedes SQS deletion.
- Backend GET/Mobile final result matches the S3 artifact.
- Required security/readiness evidence is present.
- No sensitive value appears in evidence.
