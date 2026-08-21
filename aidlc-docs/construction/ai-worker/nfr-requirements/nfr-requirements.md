# NFR Requirements - ai-worker Status API Migration

## 1. Scope and Requirement Semantics

These NFRs apply to the single sequential EC2 `ai-worker` unit after replacing direct DynamoDB status access with Backend Status API PATCH calls.

Requirement terms:
- **MUST**: release-blocking and verified by the named evidence.
- **MUST NOT**: release-blocking prohibition.
- **External dependency**: required for joint acceptance but implemented outside this repository.
- **Not specified**: no numeric target was approved; the design must not invent one.

The Security Baseline, Resiliency Baseline, and Property-Based Testing extensions remain disabled. Project-specific security, reliability, and test requirements below are still mandatory.

## 2. Performance Requirements

### NFR-PERF-001: End-to-End Job Duration

- The Worker has no end-to-end Job completion deadline for Hermes, Kiro, or Gradle.
- It MUST NOT introduce an application timeout around those existing subprocesses.
- Phase start/completion timestamps or elapsed duration MUST be available in sanitized journald events for later measurement.
- **Pass condition**: no Worker subprocess timeout is present; a slow test double can outlive the Status API timeout without being canceled by the Worker.

### NFR-PERF-002: Processing Concurrency

- One Worker process MUST handle exactly one SQS Job at a time.
- It MUST NOT add multiprocessing, async concurrent Job execution, or parallel SQS message handling in this migration.
- **Pass condition**: orchestrator tests show the next receive/process cycle begins only after the current `process_job` returns.

### NFR-PERF-003: SQS Polling

- Short polling MUST use `WaitTimeSeconds=0` and `MaxNumberOfMessages=1`.
- After an empty response, the orchestrator MUST wait 0.5 seconds before the next receive unless shutdown is already requested.
- **Pass condition**: SQS client and orchestrator tests record the exact receive parameters and 0.5-second empty cadence.

### NFR-PERF-004: Per-Attempt Status API Timeout

- Each PATCH MUST use connect timeout 3 seconds and read-inactivity timeout 10 seconds as the tuple `(3, 10)`.
- This tuple is not a total wall-clock deadline; no separate global request deadline is specified.
- **Pass condition**: deterministic client test records the exact timeout argument for every attempt.

### NFR-PERF-005: Status API Retry Budget

- Only 5xx responses consume retry budget.
- Maximum is three total attempts with sleep sequence `[1, 2]` seconds.
- A 4xx, connection error, connect timeout, read timeout, or other final non-5xx response MUST stop without an additional request or sleep.
- **Pass condition**: fake-session and sleep-recorder tests assert attempt count and exact sleep sequence for each outcome.

### NFR-PERF-006: Response Processing

- Every 2xx MUST complete without JSON parsing or body validation.
- Status calls remain synchronous; no additional queue/thread is introduced for HTTP reporting.
- **Pass condition**: empty, non-JSON, and malformed bodies on representative 2xx responses all pass.

## 3. Reliability and Availability Requirements

### NFR-REL-001: Full Redelivery Processing

- Every validated SQS delivery MUST recreate the Job workspace and execute inputs, Hermes, Kiro, Gradle, and output flow from the beginning.
- The Worker MUST NOT call Backend GET, DynamoDB GetItem, or terminal-state skip logic.
- **Pass condition**: the same message processed twice produces two complete phase sequences and no read-status call.

### NFR-REL-002: Intermediate Degradation

- Final ANALYZING, GENERATING_CODE, or BUILDING reporting failure MUST be contained as a warning and MUST NOT stop the current AI/build pipeline.
- **Pass condition**: each injected reporting failure still reaches the next processing component.

### NFR-REL-003: Mandatory Completion Gate

- Artifact upload plus HeadObject/size verification MUST complete before SUCCESS.
- SQS DeleteMessage MUST occur only after SUCCESS returns any 2xx.
- SUCCESS final failure MUST preserve the message and enter INTERNAL_ERROR/FAILED handling.
- **Pass condition**: call-recorder tests prove strict ordering and prohibited calls in each failure branch.

### NFR-REL-004: FAILED Error Preservation

- FAILED reporting MUST omit progress and artifact key.
- Reporting failure MUST NOT replace the original errorCode or safe message.
- Both FAILED success and failure MUST preserve the SQS message.
- **Pass condition**: nested-failure tests retain all original classification values and issue no delete.

### NFR-REL-005: Post-SUCCESS Delete Failure

- If SUCCESS is accepted and DeleteMessage fails, accepted SUCCESS remains authoritative.
- The Worker MUST log a sanitized acknowledgment error, MUST NOT send contradictory FAILED, and MUST leave the message for SQS redelivery.
- **Pass condition**: an injected delete exception records SUCCESS before delete, records no FAILED, and does not issue another delete in that attempt.

### NFR-REL-006: Visibility Lease

- Visibility extension interval MUST remain 50% of the effective queue Visibility Timeout, subject to the existing minimum interval.
- Extension failure MUST be warning-only.
- The extender MUST stop on every success, processing failure, HTTP failure, and delete-attempt path.
- **Pass condition**: deterministic lifecycle tests show start/stop pairing and non-fatal extension error.

### NFR-REL-007: Process Recovery

- systemd MUST use `Restart=on-failure` and `RestartSec=5`.
- SIGTERM MUST stop new polling and allow cooperative current-Job completion until `TimeoutStopSec=300`.
- If systemd enforces the 300-second limit, SQS visibility/redelivery remains the recovery mechanism.
- **Pass condition**: `systemd-analyze verify` succeeds and service content assertions match these values.

### NFR-REL-008: Queue Redrive

- The deployed queue/DLQ configuration MUST be recorded and verified before live acceptance.
- The existing planning target is `maxReceiveCount=3`; the Worker does not implement this counter.
- **Pass condition**: E2E evidence includes sanitized queue redrive attributes.

### NFR-REL-009: Backend Idempotency Dependency

The external Backend MUST:
- Accept repeated intermediate commands, including ANALYZING after an earlier terminal status.
- Return 2xx for the same accepted SUCCESS payload on redelivery.
- Preserve safe behavior for repeated FAILED commands.

**Pass condition**: approved contract/E2E evidence demonstrates repeated status and SUCCESS acceptance. This is an external acceptance dependency, not Worker implementation.

### NFR-AVAIL-001: Service Availability Boundary

- No uptime percentage, multi-instance HA target, RTO, or RPO is approved for this migration.
- Worker availability is provided by one EC2 process, systemd restart, SQS redelivery, and DLQ behavior.
- Intermediate API outage degrades visibility; SUCCESS API outage fails completion closed.

## 4. Security Requirements

### NFR-SEC-001: Worker IAM Least Privilege

The Worker role MUST retain only required actions for this flow:
- SQS: ReceiveMessage, DeleteMessage, ChangeMessageVisibility, GetQueueAttributes.
- S3: GetObject for requirements/assets and artifact HeadObject semantics, PutObject for source/artifact, and constrained ListBucket for asset prefixes.
- DynamoDB GetItem/UpdateItem and any other Worker DynamoDB action MUST be absent.
- No additional AWS permission is required for the current unauthenticated HTTPS Status API.

**Pass condition**: policy inspection and source scan show no Worker DynamoDB action/resource; approved SQS/S3 actions remain.

### NFR-SEC-002: TLS Certificate Verification

- Every Status API request MUST use requests default certificate verification.
- No code, test default, environment flag, or deployment instruction may disable certificate checks.
- **Pass condition**: source/config scan and HTTP fake assertions show no override disabling TLS checks.

### NFR-SEC-003: Network Egress

- The target EC2 environment MUST reach the configured API Gateway hostname over outbound TCP 443.
- Proxy/firewall rules, if present, MUST allow this destination without bypassing certificate validation.
- **Pass condition**: deployment readiness evidence includes a sanitized HTTPS reachability result.

### NFR-SEC-004: Optional API Key

- Missing, empty, or whitespace-only `PROMPTON_STATUS_API_KEY` MUST result in no `x-api-key` header.
- A non-empty key MUST be sent only in `x-api-key`.
- The key MUST NOT appear in source, exceptions, stdout/stderr, journald, test snapshots, or evidence bundles.
- **Pass condition**: header tests and secret/log scans cover absent and configured modes.

### NFR-SEC-005: Environment File Protection

- Secret injection uses `/etc/prompton-worker/env` or another explicitly approved mechanism.
- File mode MUST be 0640 or stricter and ownership MUST limit access to the service identity/administrator.
- AWS access/secret/session keys MUST NOT be stored there; AWS SDK authentication remains the EC2 Instance Profile.
- **Pass condition**: deployment evidence records sanitized owner/group/mode and absence of AWS static key names.

### NFR-SEC-006: Workspace Protection

- Each Job workspace SHOULD be mode 0700 where the filesystem supports POSIX permissions.
- The systemd service MUST write only to declared Worker/tool paths.
- **Pass condition**: unit test or deployment inspection verifies workspace mode and `ReadWritePaths` coverage.

### NFR-SEC-007: Sensitive Log Exclusion

Zero occurrences are permitted for:
- API keys and authentication header values.
- Raw Client JSON and Hermes stdout/stderr.
- AWS credentials/session tokens.
- Signed URLs.
- Backend response-body content.

**Pass condition**: caplog tests and pattern scans use sentinel secrets and assert none appear.

### NFR-SEC-008: systemd Hardening

The service MUST retain:
- `NoNewPrivileges=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- `PrivateTmp=true`
- Explicit `ReadWritePaths`

**Pass condition**: service-file assertions and `systemd-analyze verify` pass.

## 5. Observability Requirements

### NFR-OBS-001: Required Event Coverage

Sanitized Python logging to stdout/stderr and journald MUST cover:
- Job and phase start/completion.
- Status being reported, success/failure class, and attempt count.
- Each 5xx retry and selected delay.
- Hermes fallback, visibility error, source upload warning, and artifact verification.
- Final Job success, original errorCode, or post-SUCCESS delete acknowledgment failure.

### NFR-OBS-002: Correlation

- Job-scoped events MUST include validated `jobId` where available.
- HTTP events MUST include status name and attempt count.
- Final failures MUST include approved errorCode, not raw exception content.
- **Pass condition**: caplog assertions verify the required fields for success and every failure class.

### NFR-OBS-003: Log Destination

- DynamoDB `logs` updates and Backend log APIs MUST be absent.
- journald is the only required persistence destination for Worker operational logs.
- journald retention duration/central export is not specified by this migration and remains an operator setting.

### NFR-OBS-004: Log Levels

- INFO: phase and successful status/Job milestones.
- WARNING: best-effort intermediate failure, retry, Hermes fallback, visibility/source warning, and delete acknowledgment failure.
- ERROR: final Job failure and FAILED-reporting failure.
- DEBUG: non-sensitive development details only.

### NFR-OBS-005: Response Body Handling

- Success/failure determination MUST NOT depend on response content.
- Backend response-body content MUST NOT be logged.
- **Pass condition**: sentinel response content is absent from captured logs at all levels.

### NFR-OBS-006: Metrics and Alerts Boundary

No new CloudWatch metric, dashboard, or alarm resource is required in this repository. Joint E2E uses journald, HTTP results, S3 metadata, and SQS evidence. Alerting infrastructure remains outside the approved Worker code scope.

## 6. Operations Requirements

### NFR-OPS-001: Fail-Fast Configuration

Worker startup MUST fail before polling if any required value is missing/empty:
- `SQS_QUEUE_URL`
- `S3_BUCKET_NAME`
- `PROMPTON_API_BASE_URL`

`PROMPTON_STATUS_API_KEY` remains optional and secret. `DYNAMODB_TABLE_NAME` MUST NOT be required or logged.

### NFR-OPS-002: Process Management

- Execute as the dedicated `prompton` user/group through systemd.
- Use `/opt/prompton-ai-worker/.venv/bin/python -m main` and `/etc/prompton-worker/env`.
- Send stdout/stderr to journald with `SyslogIdentifier=prompton-worker`.

### NFR-OPS-003: Dependency Reproducibility

- `requests==2.34.2` MUST be a direct runtime dependency.
- boto3 remains exactly `1.35.99`; jsonschema remains exactly `4.25.1` unless a separately approved cleanup removes it.
- DynamoDB-only moto/stub extras MUST be removed when target source/tests have no use.
- `uv lock --check` and frozen sync with dev extras MUST succeed.

### NFR-OPS-004: Disk Lifecycle

- Work root remains `/data/jobs` unless configured otherwise.
- Directories older than `CLEANUP_HOURS` (default 24) are removed before polling.
- Cleanup failure is warning-only.
- Deployment readiness MUST record available disk and writable-path configuration; no numeric free-space alarm threshold is approved.

### NFR-OPS-005: Endpoint Readiness

Before live Job execution, operators MUST verify:
- Normalized API base URL points to the approved environment.
- HTTPS TCP 443 reachability succeeds.
- Authentication mode matches optional key configuration.
- A non-mutating reachability probe does not establish the success schema; contract tests/E2E do.

### NFR-OPS-006: Release Rollback

- Changes remain isolated on the feature branch until local gates pass.
- Because direct DynamoDB access is unavailable, rollback to the old runtime is not a viable operational recovery without separate IAM/storage restoration.
- Forward-fix plus SQS redelivery is the planned recovery for this migration.

### NFR-OPS-007: Live-Test Safety

- Actual dev SQS/API/S3 execution and Hermes/Kiro usage require an approved Job ID, environment, and test window.
- Production activation is not authorized by design/code approval alone.

## 7. Scalability and Capacity Requirements

### NFR-SCALE-001: Current Capacity

- One process handles one Job at a time on the existing t3.xlarge planning baseline (4 vCPU, 16 GiB RAM).
- No per-hour throughput SLO is specified because Hermes/Kiro/Gradle duration is variable and no new benchmark was approved.

### NFR-SCALE-002: Vertical Capacity Evidence

- The dev E2E evidence SHOULD record instance type, peak/available memory, disk availability, and Job duration.
- These observations inform later capacity decisions and are not pass/fail thresholds in this migration.

### NFR-SCALE-003: Future Horizontal Scaling

SQS can distribute Jobs across future instances, but this change does not provision autoscaling or multi-instance coordination. Backend idempotency and full redelivery behavior are prerequisites before any horizontal rollout.

## 8. Maintainability and Quality Requirements

### NFR-MAINT-001: Deterministic Tests

- HTTP tests inject a fake session and sleep recorder; no external network is used.
- Orchestrator tests inject Status API/S3/SQS fakes with ordered call records.
- Tests MUST cover mixed retry outcomes such as 5xx followed by 4xx/timeout and the accepted-SUCCESS/DeleteMessage-failure branch.

### NFR-MAINT-002: Static Quality

Release gates MUST pass with zero errors:
- Full pytest suite.
- Ruff check.
- mypy strict over all source modules.
- Python compileall.

No coverage percentage or property-based test target is introduced.

### NFR-MAINT-003: Source and Dependency Scans

Automated checks MUST establish:
- No runtime import/use of `DynamoClient`, DynamoDB resource/Table, GetItem, UpdateItem, or append-log path.
- No Worker GET status endpoint.
- No `DYNAMODB_TABLE_NAME` requirement/startup output.
- Direct requests pin and no unused DynamoDB test/stub extras.

### NFR-MAINT-004: Deployment Validation

- `systemd-analyze verify deploy/prompton-worker.service` MUST pass in a compatible Linux environment.
- Environment template MUST contain the three required status-era values and no real secret.
- Secret pattern and file-permission checks MUST pass.

### NFR-MAINT-005: Documentation Consistency

Application, Functional, NFR, build/test, deployment, and operational artifacts MUST use the Status API target as authoritative and MUST mark historical DynamoDB clauses as superseded rather than executable guidance.

## 9. Usability and External Acceptance

### NFR-USE-001: Headless Worker Boundary

Accessibility and interactive UI requirements are N/A for the Worker. User-visible semantics are the exact Korean status messages, progress values, safe errorCode/message, and artifact availability defined in Functional Design.

### NFR-E2E-001: Joint Dev Acceptance

An approved dev Job MUST demonstrate externally:
1. Worker PATCH attempts for ANALYZING, GENERATING_CODE, BUILDING, and SUCCESS.
2. Backend GET observes the corresponding stored states; Worker itself performs no GET.
3. S3 artifact exists with matching key and verified size.
4. Mobile App shows final SUCCESS and the same artifact result.
5. SQS deletion occurs only after accepted SUCCESS.

### NFR-E2E-002: Evidence Bundle

Evidence MUST include:
- Commit SHA and UTC timestamps.
- Sanitized journald excerpts and HTTP status results.
- S3 bucket/key, ContentLength, and APK SHA-256.
- SQS message/deletion or queue-state evidence.
- Backend GET result and Mobile observation supplied by the responsible teams.
- No API key, credential, raw Client JSON, signed URL, or full sensitive response body.

### NFR-E2E-003: Automated Contract Ownership

The Worker repository owns mock/contract automation for the Status client and orchestrator. Backend GET persistence behavior and Mobile display are joint external acceptance, not Worker production code.

## 10. Traceability

| Source | NFR ownership |
|---|---|
| FR-SA-001, FR-SA-002, FR-SA-003 | NFR-PERF-004, NFR-SEC-002 through NFR-SEC-004, NFR-OPS-001 |
| FR-SA-004, FR-SA-005, FR-SA-006, FR-SA-007 | NFR-REL-002, NFR-REL-003, NFR-OBS-001 |
| FR-SA-008 | NFR-REL-004, NFR-OBS-002 |
| FR-SA-009, FR-SA-010, FR-SA-011, FR-SA-012 | NFR-PERF-004 through NFR-PERF-006, NFR-REL-002 through NFR-REL-004 |
| FR-SA-013, FR-SA-014 | NFR-REL-001, NFR-REL-009 |
| FR-SA-015, FR-SA-016 | NFR-SEC-007, NFR-OBS-001 through NFR-OBS-005 |
| FR-SA-017, FR-SA-018 | NFR-OPS-001, NFR-OPS-003, NFR-MAINT-003 |
| NFR-SA-001 | NFR-SEC-001 |
| NFR-SA-002 | NFR-SEC-002, NFR-SEC-003 |
| NFR-SA-003 | NFR-SEC-004, NFR-SEC-005 |
| TR-SA-001 | NFR-PERF-004 through NFR-PERF-006, NFR-MAINT-001 |
| TR-SA-002 | NFR-REL-001 through NFR-REL-006, NFR-MAINT-001 |
| TR-SA-003 | NFR-MAINT-002 through NFR-MAINT-004 |
| TR-SA-004 | NFR-E2E-001 through NFR-E2E-003 |
| US-SA-01, US-SA-02, US-SA-03, US-SA-04, US-SA-05, US-SA-06, US-SA-07 | Configuration, status visibility, completion integrity, safe failure, HTTP predictability, protected observability, and joint acceptance NFRs above |

## 11. Release-Blocking NFR Gate

The NFR gate passes only when:
- Exact timeout/retry/response tests pass.
- Lifecycle, error-preservation, and delete-order tests pass.
- TLS/key/log/IAM/source scans pass.
- Full pytest, Ruff, strict mypy, compileall, lock/frozen sync, and deployment checks pass.
- Live E2E readiness is documented; actual external acceptance is completed in an approved test window before production activation.
