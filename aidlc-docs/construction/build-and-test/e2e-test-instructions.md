# End-to-End Test Instructions - ai-worker Status API Target

## 1. Purpose

Validate one complete approved dev Job across:

1. Backend Job creation, raw requirements upload, and SQS pointer production.
2. Worker SQS receipt and full processing.
3. Worker Status API PATCH commands.
4. Hermes refinement/fallback, Kiro generation, and Gradle APK build.
5. S3 source/artifact upload and artifact verification.
6. Mandatory SUCCESS acceptance before SQS deletion.
7. Backend GET and Mobile final-state/artifact agreement.

The Worker must not perform Backend GET.

## 2. High-Risk Safety Gate

This procedure mutates dev Backend/SQS/S3 state, can consume Hermes/Kiro model capacity, writes build data, and may trigger DLQ behavior. Before execution, obtain explicit approval identifying:

- Environment and account.
- Unique Job ID or authorization to create one.
- Test start/end window.
- Backend, Worker, Mobile, and cleanup owners.
- Queue/bucket/prefix and DLQ isolation.
- Allowed success/failure scenarios.
- Model/provider and cost authorization.

Do not run against production, purge a shared queue, weaken TLS/IAM/firewalls, print secrets, or reuse a customer Job.

## 3. Preconditions

### Code and deployment

- Exact commit SHA/revision recorded.
- Local 149-test, Ruff, strict mypy, compileall, lock, and frozen-sync gates passed.
- Approved revision deployed through the responsible process.
- systemd direct verification passes on the target host.
- Service identity owns/writes only approved paths.

### Backend and Status API

- Approved Status API base URL and authentication mode.
- Backend accepts repeated intermediate states and same accepted SUCCESS on redelivery.
- Backend observer can perform GET and record sanitized state results.
- Worker has no GET endpoint/client path.

### SQS/S3/IAM/network

- Dedicated dev queue/DLQ with sanitized VisibilityTimeout/RedrivePolicy evidence.
- Planning expectation `maxReceiveCount=3` confirmed or discrepancy approved.
- Dedicated S3 Job prefix.
- Worker Instance Profile has approved SQS/S3 actions and no DynamoDB actions.
- Outbound TCP 443 and certificate verification pass.

### Tool/runtime

- Hermes service-user configuration is ready without exposing provider credentials.
- Kiro CLI/model access is approved.
- Java, Android SDK, Gradle, and writable cache paths are ready.
- Capacity/disk observations can be collected without an invented threshold.

## 4. Evidence Workspace

Create a local evidence directory on the authorized observer host:

```bash
set -euo pipefail
: "${JOB_ID:?approved Job ID required}"
EVIDENCE_DIR="test-results/e2e/${JOB_ID}"
mkdir -p "$EVIDENCE_DIR"
git rev-parse HEAD > "$EVIDENCE_DIR/commit-sha.txt"
date -u +%Y-%m-%dT%H:%M:%SZ > "$EVIDENCE_DIR/start-utc.txt"
```

Do not copy API keys, environment dumps, raw Client JSON, Hermes output, signed URLs, or full Backend response bodies into this directory.

## 5. Success-Path Scenario

### 5.1 Submit through the Backend-owned path

The Backend participant creates one approved deterministic Job, stores the UTF-8 top-level requirements object (at most 64 KiB), optionally stores safe test assets, and enqueues the version 1.0 S3 pointer.

Record only:

- Job ID.
- Sanitized environment identifier.
- S3 bucket/key identifiers approved for evidence.
- Submission UTC timestamp.
- Backend request/correlation identifier if safe.

Do not manually inject a queue message unless the dedicated harness and payload are separately approved.

### 5.2 Observe Worker events

```bash
TEST_START_UTC="$(cat "$EVIDENCE_DIR/start-utc.txt")"
sudo journalctl \
  -u prompton-worker \
  --since "$TEST_START_UTC" \
  --no-pager \
  | grep -F "$JOB_ID" \
  > "$EVIDENCE_DIR/worker-events.log"
```

The Worker has no end-to-end timeout. Use the approved observation window for coordination, but do not classify a valid long-running Job as failed solely because it exceeds an invented duration.

Expected events/evidence:

- Job and each phase start/completion.
- Status name, attempt count, and success/failure class.
- 5xx retry/delay if encountered.
- Hermes completion or safe raw fallback.
- Artifact verification.
- Final Job success or approved error code.
- No raw request/response/credential content.

### 5.3 Backend and Mobile observation

Backend observer records GET-visible results for:

- ANALYZING, progress 25, exact message.
- GENERATING_CODE, progress 50, exact message.
- BUILDING, progress 75, exact message.
- SUCCESS, progress 100, exact message and artifact key.

Mobile observer records final SUCCESS and the same artifact result. Intermediate observations may be screenshots/timestamps if available, but polling timing must not cause an otherwise valid run to fail.

The Worker must not add or invoke GET to collect this evidence.

### 5.4 Verify S3 artifact

```bash
ARTIFACT_KEY="jobs/${JOB_ID}/artifact/app-debug.apk"
aws s3api head-object \
  --bucket "$S3_BUCKET_NAME" \
  --key "$ARTIFACT_KEY" \
  --query '{ContentLength:ContentLength,ETag:ETag,LastModified:LastModified}' \
  > "$EVIDENCE_DIR/artifact-metadata.json"
aws s3 cp \
  "s3://${S3_BUCKET_NAME}/${ARTIFACT_KEY}" \
  "$EVIDENCE_DIR/app-debug.apk"
test -s "$EVIDENCE_DIR/app-debug.apk"
sha256sum "$EVIDENCE_DIR/app-debug.apk" \
  > "$EVIDENCE_DIR/app-debug.apk.sha256"
```

The metadata ContentLength must match the downloaded nonempty file size. The artifact key must exactly match Backend/Mobile evidence.

Optional Android inspection when approved tools are present:

```bash
apkanalyzer manifest application-id "$EVIDENCE_DIR/app-debug.apk"
apkanalyzer apk summary "$EVIDENCE_DIR/app-debug.apk"
```

Device/emulator installation is a separate Mobile/QA action and requires a dedicated test device and approved application ID.

### 5.5 Verify SQS completion

Use queue/CloudTrail/Backend-owned evidence to prove DeleteMessage occurs only after accepted SUCCESS. Do not infer deletion merely from a temporarily empty receive. Record the message identifier/correlation and timestamps without storing the full body if it contains sensitive data.

## 6. Redelivery and Idempotency Scenario

Execute only with explicit additional approval because it intentionally causes duplicate processing/model/build cost.

1. Cause DeleteMessage to fail after Backend accepts SUCCESS, using a dedicated reversible fault mechanism.
2. Prove no contradictory FAILED is sent.
3. Allow the same message to redeliver.
4. Prove the Worker recreates the workspace and reruns the full pipeline from ANALYZING.
5. Prove Backend accepts repeated states and the same SUCCESS with 2xx.
6. Prove final artifact key remains correct and eventual deletion succeeds.

Do not simulate this by weakening shared IAM or firewall rules.

## 7. Failure-Path Scenario

Use a separate approved Job and dedicated queue.

- Inject one deterministic requirements, generation, build, or artifact failure.
- Verify FAILED uses one approved error code and safe message.
- Verify progress/artifact fields are omitted from the FAILED command.
- Verify the SQS message is not deleted.
- Verify redelivery and DLQ behavior match the recorded policy.
- Verify the original failure remains authoritative if FAILED reporting also fails.

Failure-path Mobile display is optional unless specifically included in the approved test window.

## 8. Sensitive-Evidence Review

Before sharing evidence, scan text files for obvious secret shapes:

```bash
uv run python - "$EVIDENCE_DIR" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
patterns = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"(?i)x-api-key\s*[:=]\s*\S+"),
    re.compile(r"(?i)aws_(?:secret_access_key|session_token)\s*[:=]\s*\S+"),
    re.compile(r"X-Amz-Signature=", re.IGNORECASE),
)
for path in root.rglob("*"):
    if not path.is_file() or path.suffix == ".apk":
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for pattern in patterns:
        assert not pattern.search(text), f"sensitive evidence requires review: {path}"
print("evidence secret-shape scan passed")
PY
```

A pass does not replace human review. Remove response bodies/raw payloads rather than attempting to redact unknown schemas automatically.

## 9. Cleanup

Cleanup is owned by the named Backend/AWS test owners and uses only the unique Job ID/prefix. Before deletion, preserve the approved evidence bundle.

- Stop only temporary observer processes.
- Remove the dedicated test Job/prefix/message through owner-approved procedures.
- Preserve DLQ evidence until failure triage is complete.
- Never purge a shared queue or recursively delete an unverified bucket prefix.
- Do not delete Backend records needed for Mobile/Backend acceptance before sign-off.
- Remove local APK/evidence only according to retention policy.

## 10. Acceptance Checklist

- [ ] Approved environment, Job ID, window, participants, and model cost authorization recorded.
- [ ] Commit SHA and UTC timestamps recorded.
- [ ] Worker PATCH attempts prove ANALYZING, GENERATING_CODE, BUILDING, SUCCESS.
- [ ] S3 upload plus size verification precedes SUCCESS.
- [ ] SUCCESS 2xx precedes SQS deletion.
- [ ] Backend GET shows exact final state/artifact.
- [ ] Mobile shows matching final state/artifact.
- [ ] APK metadata and SHA-256 recorded.
- [ ] Queue/DLQ and deployed readiness evidence recorded.
- [ ] No key, credential, raw Client JSON, Hermes output, signed URL, or sensitive response body appears.
- [ ] Cleanup completed by resource owners.

## 11. Current Status

Worker-owned local automation passed. This joint E2E was not executed during instruction generation and remains pending an explicitly approved dev Job and test window.
