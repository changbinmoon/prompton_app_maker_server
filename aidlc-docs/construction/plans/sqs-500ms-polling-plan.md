# SQS 500ms Polling Quick Change Plan

## Approval and interpretation

- **Approved at**: 2026-08-21T05:15:03.108Z
- **User input**: `폴링 간격 500ms로 퀵하게 수정해줘`
- **Interpretation**: AWS SQS `WaitTimeSeconds` accepts integer seconds only. Use `WaitTimeSeconds=0` and sleep 0.5 seconds only after an empty receive response.
- **Sequential behavior**: Continue processing at most one Job. No polling occurs while a Job is active.
- **Cost warning**: Idle receive requests can increase from about 4,320/day to about 172,800/day, approximately 40x.

## Step 1: Source and tests

- [x] Replace 20-second long polling with zero-second short polling.
- [x] Add a 0.5-second delay after empty responses, skipped once shutdown is requested.
- [x] Update SQS and orchestrator tests for exact parameters and cadence.
- [x] Update active NFR, design, contract, test, and operational documentation.

## Step 2: Validation

- [x] Run targeted SQS/orchestrator tests.
- [x] Run complete pytest, Ruff, strict mypy, compileall, lock, and diff gates.
- [x] Verify no Queue, visibility, deletion, IAM, or concurrency contract changed.

## Step 3: Active hotfix

- [x] Wait for the active Job to finish and confirm the Worker is idle.
- [x] Gracefully stop the Worker and create a root-only backup of the two deployed files.
- [x] Atomically install only `sqs/client.py` and `worker/orchestrator.py`.
- [x] Verify deployed hashes, exact 0.5-second cadence, and unchanged release inventory outside the two files.

## Step 4: Restart and closeout

- [x] Restart the Worker and verify stable systemd state and organization authentication.
- [x] Observe empty polling without manually receiving, deleting, purging, or changing message visibility.
- [x] Update audit and operational state with request-rate risk and rollback evidence.
- [x] Run final backup, source/deployed, Markdown, secret, and Worker stability checks.

## Rollback

If deployed compile, cadence, startup, or stability validation fails, stop the Worker, atomically restore the two backed-up files with recorded ownership/modes, compile, restart, and verify the prior 20-second long-poll state. Do not purge or manually delete SQS messages.

## Safety boundary

Do not modify Queue attributes, IAM, DynamoDB, external Worker, concurrency, visibility extension, message deletion gates, credentials, dependencies, environment, or systemd unit. Do not interrupt an active Job. No commit or push is included.
