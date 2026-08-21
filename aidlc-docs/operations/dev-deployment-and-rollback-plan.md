# Dev Deployment and Rollback Plan - ai-worker Status API Migration

## 1. Plan Status and Authorization Boundary

| Item | Value |
|---|---|
| Target | Dev Worker environment only |
| Planning status | COMPLETE |
| Deployment authorization | NOT GRANTED |
| Readiness | BLOCKED / NOT READY |
| Production promotion | Out of scope |
| Live E2E authorization | Separate package; currently NOT GRANTED |

This is a plan only. Do not run its service, filesystem, dependency, AWS, IAM, network, Status API, SQS, S3, Hermes, Kiro, Gradle, or cleanup steps until the named owners approve the exact revision, host, window, commands, and rollback target.

Readiness evidence: `aidlc-docs/operations/status-api-readiness-evidence.md`.
E2E approval package: `aidlc-docs/operations/dev-e2e-approval-package.md`.
Build/test summary: `aidlc-docs/construction/build-and-test/build-and-test-summary.md`.

## 2. Deployment Objective

Deploy one approved Status API-compatible `ai-worker` revision to the dev host so that:

- Worker status writes use PATCH `/v1/jobs/{jobId}/status` only.
- Worker performs no status GET or direct DynamoDB operation.
- Intermediate status failures degrade safely.
- Verified APK upload precedes mandatory SUCCESS.
- SUCCESS 2xx precedes SQS DeleteMessage.
- The existing SQS, S3, Hermes, Kiro, Gradle, visibility, workspace, and cleanup contracts remain intact.

Deployment completion does not imply production readiness. Joint dev E2E evidence remains separately gated.

## 3. Fixed Dev Paths and Inputs

| Item | Target value |
|---|---|
| Install root / WorkingDirectory | `/opt/prompton-ai-worker` |
| Runtime executable | `/opt/prompton-ai-worker/.venv/bin/python -m main` |
| Protected environment | `/etc/prompton-worker/env` |
| systemd unit | `/etc/systemd/system/prompton-worker.service` |
| Service identity | `prompton:prompton` |
| Job work root | `/data/jobs` |
| Hermes home | `/data/hermes` |
| Gradle cache | `/data/gradle` |
| Region | `us-east-1` |
| Main queue | `prompton-app-build-jobs-dev` |
| S3 bucket | `prompton-app-builder-dev-changbin` |
| Status API host | `xb2z5ls8k0.execute-api.us-east-1.amazonaws.com` |

Required release inputs:

- Approved immutable source revision and checksum.
- Matching `pyproject.toml` and `uv.lock`.
- `deploy/prompton-worker.service` from that revision.
- Protected environment values supplied through the approved secret/config channel.
- A previously deployed Status API-compatible rollback revision, or an approved forward-fix decision.

Do not copy a development `.venv`, cache, local evidence, API key, or AWS credential into the release artifact.

## 4. Roles and Approval Record - Unfilled

| Role | Name/team | Approval and UTC timestamp |
|---|---|---|
| Change owner |  |  |
| Dev environment owner |  |  |
| Worker operator |  |  |
| IAM/SQS/S3 owner |  |  |
| Backend/Status API owner |  |  |
| Security reviewer |  |  |
| Rollback decision owner |  |  |
| E2E test conductor |  |  |
| Final deployment approver |  |  |

Required change fields:

| Field | Approved value |
|---|---|
| Target host/instance |  |
| Release commit SHA |  |
| Release artifact/checksum |  |
| Deployment UTC window |  |
| Expected service interruption |  |
| Queue handling/drain decision |  |
| Previous Status API-compatible revision |  |
| Rollback artifact/checksum |  |
| Evidence location/retention |  |
| Final authorization (`APPROVED` or `REJECTED`) |  |

No command below is authorized while these fields or blocking readiness findings remain unresolved.

## 5. Blocking Preconditions

Before deployment approval, responsible owners must:

1. Identify the actual dev Worker host; the current development machine is not deployed.
2. Supply effective Worker IAM evidence with approved SQS/S3 actions and no DynamoDB actions.
3. Resolve or explain the configured S3 bucket 403/AccessDenied and prove exact-prefix access.
4. Supply main queue/DLQ resource-policy and DLQ attribute evidence.
5. Confirm Status API authentication mode and protected secret injection.
6. Create/verify the `prompton` user/group and approved `/data` paths.
7. Verify `/etc/prompton-worker/env` owner/group/mode 0640 or stricter and absence of static AWS keys.
8. Verify direct target-host systemd syntax/security with the production executable present.
9. Confirm DNS/TCP443/default TLS from the actual dev host.
10. Identify a rollback revision that already uses the Status API, or explicitly approve forward-fix-only recovery.
11. Pass local build, 149 tests, Ruff, strict mypy, compileall, lock, frozen sync, and source/deployment scans for the exact release revision.

## 6. Pre-Deployment Read-Only Capture

After approval and before changing files/services, capture sanitized evidence:

```bash
set -euo pipefail
date -u +%Y-%m-%dT%H:%M:%SZ
git -C /opt/prompton-ai-worker rev-parse HEAD
sudo systemctl status prompton-worker.service --no-pager
sudo systemctl show prompton-worker.service \
  --property=LoadState,ActiveState,SubState,MainPID,ExecMainStartTimestamp,FragmentPath
sudo stat -c '%U %G %a %n' /etc/prompton-worker/env
sudo stat -c '%U %G %a %n' /data/jobs /data/hermes /data/gradle
```

Do not print the environment file, systemd Environment values, raw Job data, API key, credentials, or signed URLs.

Record main queue depth/redrive attributes through the approved owner. Determine whether a Job is active from sanitized journald/service evidence. Never purge the queue to create a deployment window.

## 7. Release Artifact Preparation

Perform on an approved build host for the exact revision:

```bash
set -euo pipefail
uv lock --check
uv sync --frozen --extra dev
uv run pytest -q
uv run ruff check .
uv run mypy .
uv run python -m compileall -q .
git diff --check -- . ':(exclude)aidlc-docs/audit.md'
git rev-parse HEAD
```

Create the immutable release artifact through the organization's approved artifact process. Exclude:

- `.venv`, caches, bytecode, test results, and local workspaces.
- `/etc` or `/data` content.
- Secrets, environment files, credentials, evidence bundles, and untracked developer files.

Record the artifact checksum and source commit. Do not deploy directly from an uncommitted working tree.

## 8. Deployment Sequence - Requires Final Approval

### 8.1 Coordinate processing boundary

- Stop accepting new deployment actions if a Job is active.
- Prefer completing the current Job under visibility extension before service stop.
- If the approved window requires interruption, use SIGTERM/systemd cooperative stop and honor `TimeoutStopSec=300`.
- Record message/visibility/redelivery impact; do not delete or purge messages as a deployment shortcut.

### 8.2 Capture rollback material

- Preserve the current source revision/artifact and checksum.
- Preserve the installed systemd unit.
- Preserve the protected environment through an approved root-only backup mechanism; do not copy it into general evidence.
- Record current ownership/modes and tool/runtime versions.
- Confirm the preserved revision is Status API-compatible before calling it a rollback candidate.

### 8.3 Stop the service

High-risk command; run only in the approved window after confirming Job handling:

```bash
sudo systemctl stop prompton-worker.service
sudo systemctl is-active prompton-worker.service || true
```

Expected state is inactive. If stop exceeds the approved boundary or message visibility becomes unsafe, invoke the rollback/incident decision owner rather than forcing queue cleanup.

### 8.4 Install approved source

- Verify the release checksum before extraction/copy.
- Install into `/opt/prompton-ai-worker` using the organization's reviewed atomic/backup procedure.
- Preserve ownership required by the dedicated service identity.
- Do not copy local `.venv`, untracked files, credentials, or evidence.
- Confirm `status_api/` exists and `dynamo/` does not exist.

The exact file-transfer/atomic-switch command must be supplied and reviewed for the target host; this plan intentionally does not invent a destructive `rm`, `rsync --delete`, or symlink-switch strategy.

### 8.5 Create the production virtual environment from the lock

Confirm the target `uv` executable path, then run as the approved service/build identity:

```bash
cd /opt/prompton-ai-worker
uv lock --check
uv sync --frozen
/opt/prompton-ai-worker/.venv/bin/python -m compileall -q .
```

Production sync omits dev extras unless the deployment owner explicitly requires them. Do not relax `--frozen` or regenerate the lock on the host.

### 8.6 Install protected environment and unit

- Populate `/etc/prompton-worker/env` through the approved secret/config mechanism.
- Require `SQS_QUEUE_URL`, `S3_BUCKET_NAME`, and `PROMPTON_API_BASE_URL`.
- Treat `PROMPTON_STATUS_API_KEY` as optional secret; never print it.
- Do not include `DYNAMODB_TABLE_NAME` or static AWS keys.
- Set root/service-group ownership and mode 0640 or stricter.
- Install the reviewed unit at `/etc/systemd/system/prompton-worker.service`.

Verify without printing values:

```bash
sudo stat -c '%U %G %a %n' /etc/prompton-worker/env
sudo systemd-analyze verify /etc/systemd/system/prompton-worker.service
sudo systemctl daemon-reload
sudo systemctl cat prompton-worker.service
```

Confirm exact `ExecStart`, hardening, restart policy, timeout, and writable paths before start.

### 8.7 Pre-Start smoke checks

```bash
sudo -u prompton test -x /opt/prompton-ai-worker/.venv/bin/python
sudo -u prompton test -r /etc/prompton-worker/env
sudo -u prompton test -w /data/jobs
sudo -u prompton test -w /data/hermes
sudo -u prompton test -w /data/gradle
```

Also require IAM/S3/SQS/TLS readiness evidence from the actual host. Do not send PATCH or enqueue a smoke Job at this step.

### 8.8 Start and observe the service

High-risk command; run only after all pre-start gates pass:

```bash
sudo systemctl start prompton-worker.service
sudo systemctl is-active prompton-worker.service
sudo journalctl -u prompton-worker --since '5 minutes ago' --no-pager
```

Pass conditions before E2E:

- Service remains active without restart loop.
- Startup logs show the non-secret Status API base and no key/table value.
- No config/import/permission/tool-path error.
- Worker polls only the approved queue.
- No message is submitted solely by service-start verification.

## 9. Post-Deployment Verification

### Local/host checks

- Installed revision/checksum matches approval.
- Protected env and unit permissions/values match the plan.
- No obsolete adapter/config path exists.
- journald contains no key, credentials, payload, Hermes output, signed URL, or response body.
- systemd restart/hardening/writable paths are effective.

### Joint dev E2E

Execute only after `dev-e2e-approval-package.md` has final decision `APPROVED`. Use its unique Job, owners, window, cost, evidence, and cleanup boundaries. Deployment approval alone does not authorize E2E.

## 10. Rollback Strategy

### 10.1 Critical limitation

**Do not roll back to the old direct-DynamoDB Worker unless a separate cross-system plan explicitly restores and validates IAM, configuration, persistence semantics, tests, and Backend/Mobile compatibility.** The old runtime is not a viable routine rollback target.

Preferred recovery order:

1. Stop unsafe rollout progression.
2. If a prior validated Status API-compatible release exists, roll back to it.
3. Otherwise keep the message safe through SQS visibility/redelivery and perform a forward fix.
4. Coordinate Backend state/artifact reconciliation; do not send contradictory terminal states.

### 10.2 Rollback triggers

The rollback decision owner evaluates:

- Service cannot start or enters a restart loop.
- Required config/import/permission/tool checks fail.
- Status API transport violates TLS/auth/contract expectations.
- SQS/S3 permission regression prevents safe processing.
- Artifact/SUCCESS/delete ordering cannot be trusted.
- Sensitive data appears in logs/evidence.
- Unexpected duplicate processing or message-loss risk occurs.

A failed optional intermediate status update alone is not necessarily a rollback trigger; the approved design intentionally degrades that signal.

### 10.3 Rollback execution - Status API-compatible target only

After the rollback owner approves the exact artifact:

```bash
sudo systemctl stop prompton-worker.service
```

Then:

- Restore the approved prior Status API-compatible source artifact/checksum.
- Restore its matching `pyproject.toml`, `uv.lock`, unit, and protected environment contract.
- Recreate/sync the virtual environment with `uv lock --check` and `uv sync --frozen`.
- Verify direct production systemd syntax and pre-start path/permission checks.
- Start the service only after readiness passes.
- Record SQS message visibility/redelivery and Backend/artifact state before any E2E retry.

Illustrative final service steps, still requiring approval:

```bash
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/prompton-worker.service
sudo systemctl start prompton-worker.service
sudo systemctl is-active prompton-worker.service
```

### 10.4 Forward-fix conditions

Use forward-fix rather than rollback when:

- No prior Status API-compatible artifact exists.
- Reverting would restore forbidden direct persistence/status-read behavior.
- Backend has already accepted SUCCESS and reverting could emit contradictory state.
- S3 artifact/Backend state requires reconciliation.
- The defect is isolated and messages remain recoverable through SQS redelivery/DLQ.

No database migration rollback is required because this Worker owns no database migration. Backend-owned persistence changes, if any, require the Backend's own plan.

## 11. Rollback Verification

- Service runs the approved rollback/forward-fix revision.
- Config and unit match that revision without secret disclosure.
- Status API PATCH-only/no-GET/no-direct-persistence boundaries remain.
- Queue messages are neither purged nor manually discarded.
- Existing verified artifacts and accepted SUCCESS records are not contradicted.
- Any E2E retry uses a renewed approval package if Job/window/cost/cleanup scope changes.

## 12. Evidence and Closeout

Deployment/rollback evidence must include:

- Approvals, target, revision/artifact checksums, UTC timeline.
- Pre/post service status and sanitized journald.
- Env/unit owner/group/mode without values.
- IAM/SQS/S3/TLS readiness evidence.
- Rollback target compatibility decision.
- E2E package decision and result if separately executed.
- Cleanup and outstanding-risk ownership.

Never include API keys, AWS credentials, environment contents, raw Client JSON, Hermes output, signed URLs, or sensitive Backend bodies.

## 13. Current Decision

**BLOCKED / DO NOT DEPLOY.**

Readiness findings remain unresolved, approval fields are blank, no target host is identified, and no final authorization exists. This plan is complete as documentation only.
