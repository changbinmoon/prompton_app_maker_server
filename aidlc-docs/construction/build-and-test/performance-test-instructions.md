# Performance Test Instructions

## Applicability

Performance validation is applicable because each Job can run for 5 to 30 minutes or longer and combines model generation, disk I/O, Gradle compilation, and AWS calls. No maximum Job duration or throughput target was approved. Therefore this stage does not invent a latency SLA; it defines a reproducible baseline and validates the explicit sequential-processing and visibility-extension requirements.

## Performance Requirements

| Measure | Requirement or acceptance rule |
|---|---|
| Concurrent Jobs per Worker | Exactly 1 |
| SQS receive batch size | Exactly 1 |
| Long polling wait | 20 seconds |
| Visibility extension | Approximately every 50% of queue Visibility Timeout |
| Job duration | Measure and report; no fixed upper bound |
| Throughput | Measure Jobs per hour; no fixed minimum |
| Valid-Job error rate | 0% for the agreed representative sample |
| Process stability | No OOM kill, process crash, or unbounded disk growth |
| Queue handoff | Next Job begins after the prior Job reaches a terminal state |

## Test Environment

Use a dedicated queue, bucket prefix, DynamoDB test records, and EC2 instance matching the target t3.xlarge profile. Do not performance-test on shared production resources. Record:
- EC2 instance type and AMI
- EBS type, size, IOPS, and throughput
- Java, Gradle, Android SDK, kiro-cli, and model versions
- Queue Visibility Timeout
- Generated application complexity class
- Warm or cold Gradle cache state

## Baseline Test: One Representative Job

### Setup

1. Prepare one backend-approved deterministic requirements payload.
2. Clear only the dedicated test Job directory.
3. Decide whether the Gradle cache is cold or warm and record that choice.
4. Start resource collection:

```bash
mkdir -p test-results/performance
pidstat -durh 5 > test-results/performance/pidstat.log &
PIDSTAT_PID=$!
iostat -xz 5 > test-results/performance/iostat.log &
IOSTAT_PID=$!
```

`pidstat` and `iostat` are provided by the `sysstat` package. Install them in the test AMI before the test window.

### Execution

Submit one Job with the procedure in `integration-test-instructions.md`. Record UTC timestamps for:
- SQS send
- ANALYZING
- GENERATING_CODE
- BUILDING
- SUCCESS or FAILED

After the Job reaches a terminal state:

```bash
kill "$PIDSTAT_PID" "$IOSTAT_PID" 2>/dev/null || true
```

### Pass Criteria

- Only one Job is active.
- The Worker is not restarted or OOM-killed.
- Visibility extension continues for the full processing duration.
- The Job succeeds and produces a non-empty APK.
- CPU, memory, disk, and network measurements are present for analysis.

## Sequential Queue Test

Submit three representative Jobs to the dedicated queue within one minute. Use one Worker process.

Expected behavior:
- `MaxNumberOfMessages=1` is preserved.
- No two Job directories show active generation/build work at the same time.
- Job 2 starts only after Job 1 terminates; Job 3 starts only after Job 2 terminates.
- All valid Jobs succeed.
- Report total elapsed time and measured Jobs per hour.

Do not treat the three-Job sample as a scalability guarantee. It is a sequential-flow check.

## Long-Running Visibility Test

1. Use a Job expected to exceed one Visibility Timeout.
2. Record each successful and failed visibility-extension call.
3. Confirm extension intervals are approximately `VisibilityTimeout * 0.5`, subject to scheduler delay.
4. Confirm the message receive count does not increase while extension succeeds.
5. Confirm a transient extension failure does not crash the Job.

## Controlled Backlog Stress Test

This test is destructive and must use dedicated resources.

1. Queue 10 valid Jobs.
2. Keep one Worker active for the first run.
3. Observe queue depth, age of oldest message, CPU, memory, and disk.
4. Confirm strict single-Job processing and eventual backlog drain.
5. If a second Worker is evaluated later, repeat with two workers and verify cross-worker idempotency before changing production capacity.

Stop the test if any of the following occurs:
- Free disk falls below the test environment's safety threshold.
- The process is OOM-killed or repeatedly restarted.
- Valid-Job error rate becomes non-zero.
- Visibility extension repeatedly fails and duplicate processing is observed.

## Result Analysis

Record the following in `test-results/performance/results.md`:

| Metric | Baseline | Sequential 3-Job | Backlog 10-Job |
|---|---:|---:|---:|
| Total duration | | | |
| Mean Job duration | | | |
| p95 Job duration | N/A for one sample | | |
| Jobs per hour | | | |
| Peak RSS | | | |
| Peak CPU | | | |
| Peak disk use | | | |
| Visibility extensions | | | |
| Valid-Job failures | | | |

## Current Execution Status

Performance tests were not run in the local Build and Test session. Running them would create real AWS Jobs, consume Hermes and Opus 5 model capacity, and build generated Android projects. Execute them only after the raw Client JSON Backend path, service-user Hermes configuration, and test resource isolation are approved.
