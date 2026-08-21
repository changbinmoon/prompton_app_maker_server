# Performance and Capacity Test Instructions - ai-worker Status API Target

## 1. Applicability and Non-Goals

Performance/capacity evidence is applicable because a Job combines synchronous Status API calls, Hermes/Kiro model work, disk I/O, Gradle, S3, and SQS visibility management. However, no end-to-end Job deadline, throughput SLO, latency percentile, uptime percentage, RTO/RPO, autoscaling target, or numeric disk/memory alarm threshold was approved.

This document therefore defines:

- Deterministic checks for approved performance behavior.
- An observational target-host baseline for an approved dev Job.
- Sequential-capacity and visibility observations.
- Evidence fields for later capacity decisions.

It does not define a pass/fail throughput target or authorize live load/stress testing.

## 2. Approved Performance Requirements

| ID | Requirement |
|---|---|
| `NFR-PERF-001` | No application timeout around Hermes, Kiro, or Gradle; record phase timing for measurement. |
| `NFR-PERF-002` | One Worker process handles exactly one Job at a time. |
| `NFR-PERF-003` | SQS short polling returns immediately and waits 0.5 seconds after an empty response; maximum one message. |
| `NFR-PERF-004` | Every Status API attempt uses connect/read timeout `(3, 10)`. |
| `NFR-PERF-005` | Only 5xx retries; three total attempts and delays `[1.0, 2.0]`. |
| `NFR-PERF-006` | Any 2xx succeeds without response-body parsing; reporting remains synchronous. |
| `NFR-SCALE-001` | Current design is one Job per process on the existing t3.xlarge planning baseline. |
| `NFR-SCALE-002` | Approved dev evidence should record instance, memory, disk, and duration observations. |
| `NFR-SCALE-003` | No autoscaling or multi-instance coordination is implemented by this change. |

## 3. Deterministic Local Gate

Run the suites that prove performance-control behavior without real waits or external calls:

```bash
set -euo pipefail
uv sync --frozen --extra dev
uv run pytest -q \
  tests/test_status_api_client.py \
  tests/test_orchestrator.py \
  tests/test_sqs_client.py \
  tests/test_visibility_extender.py
```

Expected: 60 tests pass.

Evidence must show:

- Fake sleep recorder observes only 1.0 and 2.0 seconds after retryable 5xx.
- Every fake PATCH records `(3, 10)`.
- 4xx/network/timeout outcomes add no retry sleep.
- Orchestrator completes one Job before the next receive/process cycle.
- SQS receive uses `WaitTimeSeconds=0`, `MaxNumberOfMessages=1`, and an empty-response sleep recorder observes exactly 0.5 seconds.
- Visibility cadence remains 50% of the effective timeout, subject to the retained minimum.
- A slow processing test double is not canceled by a Worker end-to-end timeout.

## 4. Authorization Gate for Live Measurement

A live baseline mutates AWS/Backend state, consumes model capacity, and builds an Android project. Before execution, record:

- Approved dev environment and account.
- Unique Job ID and deterministic test fixture.
- Test window and named owners.
- Model/provider cost authorization.
- Queue/bucket/prefix isolation.
- Warm/cold cache choice.
- Environment-specific safety stop conditions for memory, disk, cost, time window, and duplicate processing.

Stop conditions must be approved for the test environment; this document does not invent numeric values.

## 5. Target-Host Baseline Metadata

Collect before the Job without printing secrets:

```bash
set -euo pipefail
EVIDENCE_DIR="test-results/performance/${JOB_ID}"
mkdir -p "$EVIDENCE_DIR"
date -u +%Y-%m-%dT%H:%M:%SZ > "$EVIDENCE_DIR/start-utc.txt"
uname -a > "$EVIDENCE_DIR/uname.txt"
lscpu > "$EVIDENCE_DIR/lscpu.txt"
free -b > "$EVIDENCE_DIR/memory-before.txt"
df -B1 /data/jobs /data/gradle > "$EVIDENCE_DIR/disk-before.txt"
java -version > "$EVIDENCE_DIR/java-version.txt" 2>&1
gradle --version > "$EVIDENCE_DIR/gradle-version.txt" 2>&1
kiro-cli --version > "$EVIDENCE_DIR/kiro-version.txt" 2>&1
hermes --version > "$EVIDENCE_DIR/hermes-version.txt" 2>&1
```

Also record through the approved infrastructure inventory process:

- EC2 instance type/AMI.
- EBS type/size/configured IOPS/throughput.
- Queue VisibilityTimeout/RedrivePolicy.
- Android SDK/build-tools versions.
- Worker commit SHA.
- Whether Gradle/Hermes caches are cold or warm.

Review command output before sharing; hostnames/user paths may require sanitization.

## 6. Optional Resource Sampling

If `pidstat` and `iostat` are already installed in the approved image, start sampling before Job submission:

```bash
pidstat -durh 5 > "$EVIDENCE_DIR/pidstat.log" &
PIDSTAT_PID=$!
iostat -xz 5 > "$EVIDENCE_DIR/iostat.log" &
IOSTAT_PID=$!
printf '%s\n' "$PIDSTAT_PID" > "$EVIDENCE_DIR/pidstat.pid"
printf '%s\n' "$IOSTAT_PID" > "$EVIDENCE_DIR/iostat.pid"
```

Do not install packages during the test window without separate approval. If these tools are unavailable, record equivalent approved CloudWatch/OS observations.

Stop samplers after the scenario:

```bash
kill "$PIDSTAT_PID" "$IOSTAT_PID" 2>/dev/null || true
wait "$PIDSTAT_PID" "$IOSTAT_PID" 2>/dev/null || true
free -b > "$EVIDENCE_DIR/memory-after.txt"
df -B1 /data/jobs /data/gradle > "$EVIDENCE_DIR/disk-after.txt"
date -u +%Y-%m-%dT%H:%M:%SZ > "$EVIDENCE_DIR/end-utc.txt"
```

## 7. Single-Job Observational Baseline

Use the approved success-path procedure in `e2e-test-instructions.md`. Record UTC timestamps for:

- Backend submission/SQS enqueue.
- Worker Job start.
- ANALYZING report attempt/acceptance.
- GENERATING_CODE report attempt/acceptance.
- BUILDING report attempt/acceptance.
- Artifact upload and verification.
- SUCCESS attempt/acceptance.
- SQS deletion.
- Worker Job completion.

Record:

- Total observed duration and each phase duration.
- Peak/representative CPU and RSS.
- Disk use before/after and Gradle cache state.
- S3 artifact ContentLength.
- Status API attempts/retries and selected delay.
- Visibility-extension count/failures.
- systemd restart/OOM evidence.

Interpretation:

- A valid approved Job must preserve correctness and ordering.
- No restart/OOM/duplicate processing should occur in the observed run.
- Duration and resource values are measurements, not compliance thresholds.
- A long Job is not a failure solely because it exceeds an unapproved duration.

## 8. Sequential Capacity Observation

Only after a successful single-Job baseline, optionally submit an owner-approved small sequence of representative Jobs to a dedicated queue. The sample size and model budget must be approved before submission.

Observe:

- At most one active Job in the process.
- Next Job starts only after current `process_job` returns.
- No overlapping Job workspaces show active model/build execution in one process.
- Queue age/depth trends and total drain time.
- Per-Job duration/resource differences between cold/warm caches.
- Every valid Job's correctness result.

Report measured Jobs/hour only as an observation for that fixture/environment. Do not extrapolate a service SLO or horizontal-scaling guarantee.

## 9. Long-Running Visibility Observation

With one approved Job expected to exceed the queue VisibilityTimeout:

1. Record the configured timeout before submission.
2. Record each visibility-extension success/failure event.
3. Compare intervals with approximately 50% of the effective timeout, accounting for scheduler/log timestamp granularity.
4. Confirm receive count does not increase while extension succeeds.
5. Confirm an isolated extension failure is warning-only and does not cancel processing.
6. If redelivery occurs, confirm full reprocessing and Backend duplicate acceptance.

Do not alter a shared queue's VisibilityTimeout merely to force this scenario.

## 10. Status API Capacity Boundary

Do not run standalone PATCH load/stress traffic against the live Backend from this repository:

- Commands mutate Job state.
- No Backend rate/latency SLO or safe request volume was approved.
- Repeated commands require Backend idempotency and coordinated test data.

Client-side deterministic tests already prove the per-attempt timeout/retry budget. Any Backend load test requires a separate Backend-owned plan with quotas, fixtures, stop conditions, observability, cleanup, and approval.

## 11. Result Template

Write `test-results/performance/{jobId}/results.md`:

```text
Commit SHA:
Environment / instance type:
Job fixture and Job ID:
Test window (UTC):
Owners:
Cache state:
Queue VisibilityTimeout / RedrivePolicy:
Total Job duration:
Phase durations:
Status API attempts and retries:
Visibility extension count/failures:
Peak/representative CPU:
Peak RSS / memory before-after:
Disk before-after:
Artifact ContentLength / SHA-256:
Observed Jobs per hour (if sequential sample approved):
Restarts / OOM / duplicate processing:
Correctness result:
Deviations and follow-up:
```

## 12. Current Status

- Deterministic performance-control tests passed within the 149-test suite.
- No live performance, sequential-capacity, or long-running Job measurement was executed during instruction generation.
- No numeric performance threshold is claimed.
- Target-host observations remain pending an explicitly approved dev Job/window and cost/safety conditions.
