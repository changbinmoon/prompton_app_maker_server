# NFR Design Patterns - ai-worker Status API Migration

## 1. Design Status and Scope

- **Unit**: `ai-worker`
- **Stage**: NFR Design
- **Deployment model**: One sequential Python 3.12 Worker process managed by systemd
- **Target change**: Replace Worker-owned DynamoDB status access with synchronous outbound Status API PATCH calls
- **Authoritative inputs**: Approved Status API requirements, Application Design, Functional Design, NFR Requirements, and technology decisions
- **Implementation boundary**: This document defines patterns and verification seams; Code Generation applies them to source, tests, manifests, and deployment files.

Security Baseline, Resiliency Baseline, and Property-Based Testing extensions are disabled. Their rule files are not enforced. The project-specific security, reliability, and deterministic-test controls below remain release-blocking.

## 2. Pattern Principles

1. Keep status transport mechanics in `StatusApiClient`; keep Job criticality and SQS acknowledgment policy in `WorkerOrchestrator`.
2. Bound only the operation with an approved bound. Status API calls have exact timeouts and retry limits; Hermes, Kiro, and Gradle keep their approved no-Worker-timeout behavior.
3. Degrade intermediate visibility without degrading completion integrity. Intermediate and FAILED reporting are best-effort; SUCCESS fails closed.
4. Treat verified artifact, accepted SUCCESS, and SQS deletion as an ordered completion barrier, not a distributed transaction.
5. Recover through SQS redelivery and clean full reprocessing. Do not introduce Worker GET, a status cache, an outbox, a circuit breaker, or a second persistence path.
6. Prevent sensitive data from entering log and exception objects rather than relying only on late text redaction.
7. Make every timing, failure, and ordering rule deterministic through constructor-injected collaborators and recorders.

## 3. Resilience and Availability Patterns

### PAT-RES-01: Selective Bounded Retry

**Applies to**: One Status API PATCH command.

**Design**:
- Use one synchronous request loop with attempt numbers 1 through 3.
- Pass `timeout=(3, 10)` on every request.
- Return immediately for any status code from 200 through 299 without parsing the body.
- For a 5xx response on attempt 1, emit a sanitized WARNING event, sleep 1 second, and retry.
- For a 5xx response on attempt 2, emit a sanitized WARNING event, sleep 2 seconds, and retry.
- For a 5xx response on attempt 3, raise one typed, sanitized final failure.
- A 4xx, other non-2xx/non-5xx response, `requests.ConnectionError`, or `requests.Timeout` is final on the current attempt. Do not sleep or send another request.
- If a retry sequence later receives a 4xx, connection error, or timeout, stop at that point. The final failure records the actual attempt count.

**Failure value**:
- `StatusApiFailure` carries only failure kind, optional numeric HTTP status, and attempt count.
- It carries no API key, headers, request payload, response body, raw exception text, credential, or signed URL.

**Rejected patterns**:
- Generic retry middleware, retrying network exceptions, unbounded exponential backoff, circuit breaker, and local status outbox are not approved.

**Verification**:
- A fake session supplies response/exception sequences.
- A sleep recorder proves `[]`, `[1]`, or `[1, 2]` exactly.
- Request records prove the timeout tuple on every attempt and no response-body access on 2xx.

### PAT-RES-02: Criticality Split at the Orchestrator Boundary

**Applies to**: Final `StatusApiFailure` after PAT-RES-01.

| Status | Boundary behavior | Local pipeline | SQS acknowledgment |
|---|---|---|---|
| ANALYZING | Catch and log sanitized WARNING | Continue | Not authorized |
| GENERATING_CODE | Catch and log sanitized WARNING | Continue | Not authorized |
| BUILDING | Catch and log sanitized WARNING | Continue | Not authorized |
| SUCCESS | Let failure enter Job failure classification | Fail as `INTERNAL_ERROR` | Prohibited |
| FAILED | Catch and log sanitized ERROR | Preserve original Job error | Prohibited |

The client does not know whether a command is best-effort or mandatory. This avoids coupling HTTP mechanics to queue lifecycle policy.

**Verification**:
- One orchestrator test injects final failure at each status.
- Intermediate failures must still reach the next processing collaborator.
- SUCCESS and FAILED failure branches must contain no SQS delete.

### PAT-RES-03: Ordered Completion Barrier

**Applies to**: Finalization after APK build.

**Required order**:
1. Source upload is attempted with existing best-effort behavior.
2. APK upload completes.
3. S3 HeadObject and size comparison verify the artifact.
4. Mandatory SUCCESS is sent with the verified key.
5. Any 2xx returns normally from `StatusApiClient`.
6. Only then may `SQSClient.delete_message` run.

A call recorder shared by S3, status, and SQS fakes is the design-time transaction ledger. There is no rollback that deletes a verified artifact when SUCCESS fails.

**Special acknowledgment branch**:
- Once SUCCESS is accepted, a later DeleteMessage exception is an acknowledgment failure, not a Job-processing failure.
- Log a sanitized WARNING, do not send FAILED, and leave the message for redelivery.
- A redelivery performs the full pipeline and relies on Backend duplicate-SUCCESS acceptance.

### PAT-RES-04: Original-Error Preservation

**Applies to**: Requirements, AI, build, artifact, mandatory SUCCESS, and unexpected failures.

**Design**:
1. Capture the original exception.
2. Derive the approved `ErrorCode` and fixed safe Korean message before any FAILED call.
3. Send FAILED without `progress` or `artifactKey`.
4. If FAILED reporting fails, log only the original error code plus sanitized reporting metadata.
5. Retain the original classification and keep the SQS message.

Nested reporting failure never becomes the user-facing or queue-lifecycle error.

### PAT-RES-05: Queue-Managed Recovery and Full Reprocessing

**Applies to**: Worker crash, failed Job, SUCCESS failure, delete failure, or visibility expiry.

**Design**:
- Do not call Backend GET or DynamoDB GetItem.
- Do not skip terminal status or resume a local phase.
- Recreate `/data/jobs/{jobId}` for every valid delivery.
- Repeat inputs, Hermes, Kiro, Gradle, uploads, and status commands from ANALYZING.
- Preserve the message on every failure path; SQS visibility, redelivery, and DLQ policy own recovery.
- Record deployed queue/DLQ attributes before live acceptance. The planning target is `maxReceiveCount=3`, but the Worker does not implement the counter.
- Treat Backend repeated-state and duplicate-SUCCESS 2xx behavior as an external acceptance dependency.

### PAT-RES-06: Visibility Lease Pairing

**Applies to**: Every validated Job delivery.

**Design**:
- Start the existing visibility extender after clean workspace preparation and before ANALYZING.
- Derive extension cadence as 50 percent of the effective queue Visibility Timeout, subject to the existing minimum.
- Treat extension errors as warning-only.
- Stop the extender in `finally` after success, processing failure, HTTP failure, or delete attempt.

Tests use a fake extender with start/stop counters so every branch proves one paired lifecycle.

### PAT-RES-07: Process Supervision and Cooperative Shutdown

**Applies to**: Worker process lifecycle.

**Design**:
- systemd uses `Restart=on-failure` and `RestartSec=5`.
- SIGTERM sets the existing shutdown request so no new poll begins and the current Job can complete cooperatively.
- `TimeoutStopSec=300` is the supervisor ceiling. If exceeded, SQS redelivery is recovery.
- This remains a single-instance availability design. No uptime percentage, RTO, RPO, multi-instance HA, or automatic failover target is invented.

## 4. Performance and Scalability Patterns

### PAT-PERF-01: Synchronous Request Budget

A status command remains synchronous because the Worker processes one Job at a time. The maximum approved HTTP attempt count is fixed, but `(3, 10)` is a connect/read-inactivity tuple rather than a total wall-clock deadline. No derived total latency SLO is asserted.

No background status queue or thread is added. This keeps local phase ordering observable and makes SUCCESS a real blocking gate.

### PAT-PERF-02: Sequential Single-Lane Processing

- One process receives at most one message with `MaxNumberOfMessages=1` and processes it to return before the next Job begins.
- Long polling uses `WaitTimeSeconds=20`.
- Do not add async Job execution, multiprocessing, parallel message handling, or status-call parallelism.
- Existing Hermes, Kiro, and Gradle subprocesses receive no new Worker timeout.

SQS provides natural backlog buffering. The migration does not add a memory queue or overload admission controller.

### PAT-PERF-03: Capacity Observation, Not Invented Thresholds

- Retain the t3.xlarge planning baseline of 4 vCPU and 16 GiB RAM.
- Record instance type, Job duration, available/peak memory, and disk availability during approved dev E2E where tooling permits.
- Do not turn those observations into pass/fail limits in this migration.
- Future horizontal scaling remains possible through SQS, but requires Backend idempotency evidence and a separately approved rollout design.

### PAT-PERF-04: Workspace Lifecycle

- Recreate a Job-specific workspace for each attempt and apply mode 0700 where POSIX permissions are supported.
- Remove directories older than `CLEANUP_HOURS`, default 24, before polling.
- Cleanup failure is warning-only.
- Record disk availability and writable-path readiness, but do not invent a free-space alert threshold.

## 5. Security Patterns

### PAT-SEC-01: TLS Secure by Construction

- Construct a normal production `requests.Session` and do not set `verify=False`, suppress certificate warnings, install an unapproved CA bypass, or expose a TLS-disable configuration flag.
- Do not pass a certificate-disabling argument on PATCH.
- Permit a proxy only when the environment retains hostname and certificate verification.
- Deployment readiness separately proves outbound TCP 443 reachability to the configured API Gateway host.

Tests inspect request arguments and source/config scans for certificate-disable patterns.

### PAT-SEC-02: Optional API Key Confinement

- `load_config` trims the optional key only to determine whether it is absent; missing, empty, or whitespace-only input becomes `None`.
- Only `StatusApiClient._build_headers` receives the normalized value.
- Add `x-api-key` only for a non-empty configured key.
- Do not expose a key getter, include it in `Config.__repr__` output, startup logs, exceptions, request records printed by tests, snapshots, or evidence bundles.
- Inject production secrets through `/etc/prompton-worker/env` or an explicitly approved mechanism with mode 0640 or stricter and restricted ownership.
- Do not store AWS access, secret, or session keys in the environment file; boto3 continues to use the EC2 Instance Profile.

Sentinel-key tests assert zero appearances across caplog, exception strings, stdout/stderr captures, and generated evidence.

### PAT-SEC-03: Least-Privilege Service Boundaries

Worker IAM permits only the approved SQS and S3 actions/resources needed by the data plane. DynamoDB GetItem, UpdateItem, table resources, and other Worker DynamoDB actions are removed. The ordinary HTTPS Status API currently adds no AWS IAM action.

Source, deployment, and policy scans enforce the negative boundary. Backend API Gateway, Lambda, and DynamoDB remain external and Backend-owned.

### PAT-SEC-04: Safe Event Schema

Logs are created from an allowlist of safe fields rather than serializing arbitrary objects.

**Allowed examples**:
- validated Job ID
- phase or status enum
- attempt count
- coarse result/failure kind
- numeric HTTP status when available
- approved error code
- configured non-secret environment identity where needed
- elapsed phase duration

**Never accepted as event fields**:
- headers or API key
- request payload or raw Client JSON
- response body
- Hermes stdout/stderr
- AWS credential/session token
- signed URL
- arbitrary exception text

A final sanitizer remains defense in depth for existing logs, but safe event construction is the primary control.

### PAT-SEC-05: systemd and Workspace Confinement

Retain:
- dedicated `prompton` user/group
- `NoNewPrivileges=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- `PrivateTmp=true`
- explicit `ReadWritePaths` for Worker/tool paths
- environment-file injection

The Job workspace is owner-only where supported. Deployment tests assert every required writable path is declared without broadening the filesystem to global write access.

## 6. Observability Patterns

### PAT-OBS-01: Correlated Lifecycle Events

Use stable, human-readable key/value logging through Python `logging`; JSON formatting is optional rather than required. Job-scoped events include validated `jobId` where available.

| Event family | Level | Required safe fields |
|---|---|---|
| Job/phase start and completion | INFO | jobId, phase, event, optional elapsed duration |
| Status accepted | INFO | jobId, status, attempt, result class |
| 5xx retry | WARNING | jobId, status, attempt, next delay, failure kind |
| Intermediate report failure | WARNING | jobId, status, attempt, failure kind |
| Hermes fallback, visibility, source upload | WARNING | jobId, event, safe category |
| Artifact verified | INFO | jobId, artifact key, safe size metadata |
| Final Job failure | ERROR | jobId, approved errorCode |
| FAILED reporting failure | ERROR | jobId, original errorCode, reporting kind/attempt |
| Post-SUCCESS delete failure | WARNING | jobId, acknowledgment category |

Backend response content is never a log input. Success/failure classification is body-independent.

### PAT-OBS-02: journald as the Only Required Worker Log Sink

- Python stdout/stderr is collected by systemd with `SyslogIdentifier=prompton-worker`.
- Remove DynamoDB log appends and do not add a Backend log API.
- Journald retention and centralized export remain operator settings; no new metric, dashboard, alarm, or retention resource is designed in this repository.

### PAT-OBS-03: Evidence Separation

Automated test output and E2E evidence use the same allowlisted fields. Evidence may contain a commit SHA, UTC time, numeric HTTP status, S3 bucket/key and ContentLength, APK SHA-256, and sanitized queue attributes. It must not include credentials, API key, raw Client JSON, signed URL, or sensitive response body.

## 7. Operations and Reproducibility Patterns

### PAT-OPS-01: Fail-Fast Immutable Configuration

`load_config` builds one frozen configuration object before polling.

Required non-empty values:
- `SQS_QUEUE_URL`
- `S3_BUCKET_NAME`
- `PROMPTON_API_BASE_URL`

Optional status secret:
- `PROMPTON_STATUS_API_KEY`, normalized to absent when blank

`DYNAMODB_TABLE_NAME` has no target field, startup requirement, or log entry. The API base URL may be normalized by removing trailing slashes and may be logged only as a non-secret environment endpoint.

### PAT-OPS-02: Reproducible Dependency Boundary

- Python is 3.12.
- `requests==2.34.2`, `boto3==1.35.99`, and `jsonschema==4.25.1` remain exact direct decisions.
- Dev dependencies remain exact.
- moto and boto3 stubs retain SQS/S3 extras only after source/test scans prove no DynamoDB use.
- `uv lock --check` and `uv sync --frozen --extra dev` are release gates.

No package upgrade is inferred from this design.

### PAT-OPS-03: Deployment Readiness Before Live Mutation

Before an approved live Job:
1. Validate required environment values without printing the optional key.
2. Verify environment owner/group/mode and absence of static AWS key names.
3. Verify the systemd unit and hardening directives.
4. Verify writable paths and available disk.
5. Verify HTTPS reachability over TCP 443 while retaining TLS checks.
6. Record queue/DLQ redrive attributes.
7. Confirm approved Job ID, environment, participants, and test window.

A connectivity probe is not proof of the PATCH schema. Contract tests and joint E2E provide that evidence.

### PAT-OPS-04: Forward-Fix Recovery

The old direct DynamoDB runtime is not a viable rollback without separately restoring IAM and storage access. Keep changes isolated until local gates pass, then prefer forward-fix plus SQS redelivery. Design or code approval alone does not authorize production activation.

## 8. Maintainability and Verification Patterns

### PAT-TEST-01: Dependency Injection Without a Framework

- `StatusApiClient` accepts an injectable session and sleep callable.
- `WorkerOrchestrator` accepts status, S3, SQS, AI, build, and visibility collaborators.
- Fakes expose ordered records and configured exceptions.
- Production defaults construct real collaborators; tests do not use the network.

This preserves the existing simple Python architecture while making all failure matrices deterministic.

### PAT-TEST-02: Complete Decision-Table Tests

Status client tables cover:
- representative 2xx with empty, malformed, and non-JSON bodies
- 4xx immediate failure
- 5xx success/failure sequences and exact sleeps
- 5xx followed by 4xx, connection error, or timeout
- connection and timeout on the first attempt
- exact URL, payload omission, headers, and timeout
- configured/absent API key and secret/body log exclusion

Orchestrator tables cover:
- every intermediate failure continues
- no GET and complete repeated processing
- artifact verification before SUCCESS
- SUCCESS 2xx before delete
- SUCCESS failure to INTERNAL_ERROR/FAILED without delete
- FAILED nested failure preserving the original error
- accepted SUCCESS followed by DeleteMessage failure with no contradictory FAILED
- visibility start/stop on every branch

### PAT-TEST-03: Layered Release Gates

Run and require zero errors from:
- full pytest
- Ruff
- strict mypy
- Python compileall
- uv lock check and frozen dev sync
- systemd unit verification
- environment/template checks
- secret/log sentinel scans
- source/import scans for DynamoDB, Worker GET, and stale table configuration
- dependency-extra scans

No coverage percentage or property-based target is introduced.

### PAT-TEST-04: Documentation and External Acceptance

Status API design, implementation summaries, deployment, build/test, and operational guidance use the target boundary and clearly mark historical DynamoDB guidance as superseded.

The Worker repository owns deterministic client/orchestrator contract tests. Backend GET persistence and Mobile display are joint external acceptance evidence and never become Worker production GET code.

## 9. Joint E2E Pattern

An explicitly approved dev Job provides the final cross-system evidence:
1. Worker logs sanitized attempts for ANALYZING, GENERATING_CODE, BUILDING, and SUCCESS.
2. Backend GET, invoked by the responsible external harness/team rather than Worker code, observes stored states.
3. S3 evidence proves the artifact key, ContentLength, and APK SHA-256.
4. Mobile shows final SUCCESS and the same artifact result.
5. Queue evidence proves deletion occurs after accepted SUCCESS.
6. A repeated-state/duplicate-SUCCESS scenario proves Backend idempotency before horizontal scaling or relying on delete-failure redelivery.

Live AWS/API/S3 mutation and model usage require separate test approval. Readiness documentation can complete before the live window; production activation cannot.

## 10. NFR Traceability

| NFR ID | Design realization |
|---|---|
| NFR-PERF-001 | PAT-PERF-02 preserves no Worker timeout for Hermes, Kiro, and Gradle; PAT-OBS-01 records phase timing. |
| NFR-PERF-002 | PAT-PERF-02 keeps one sequential Job per process. |
| NFR-PERF-003 | PAT-PERF-02 fixes long polling at 20 seconds and one message. |
| NFR-PERF-004 | PAT-RES-01 and PAT-PERF-01 apply `(3, 10)` on every PATCH. |
| NFR-PERF-005 | PAT-RES-01 applies 5xx-only attempts and `[1, 2]` delays. |
| NFR-PERF-006 | PAT-RES-01 returns on any 2xx without body processing. |
| NFR-REL-001 | PAT-RES-05 enforces no GET and full clean redelivery processing. |
| NFR-REL-002 | PAT-RES-02 contains intermediate reporting failure. |
| NFR-REL-003 | PAT-RES-03 provides the artifact/SUCCESS/delete barrier. |
| NFR-REL-004 | PAT-RES-04 preserves original failure and omits FAILED progress/artifact. |
| NFR-REL-005 | PAT-RES-03 separates post-SUCCESS acknowledgment failure and prohibits FAILED. |
| NFR-REL-006 | PAT-RES-06 pairs the visibility lease on all branches. |
| NFR-REL-007 | PAT-RES-07 defines restart and shutdown behavior. |
| NFR-REL-008 | PAT-RES-05 and PAT-OPS-03 require queue/DLQ evidence. |
| NFR-REL-009 | PAT-RES-05 and the joint E2E pattern verify Backend idempotency externally. |
| NFR-AVAIL-001 | PAT-RES-07 states the single-process availability boundary without invented targets. |
| NFR-SEC-001 | PAT-SEC-03 removes Worker DynamoDB IAM while retaining scoped SQS/S3. |
| NFR-SEC-002 | PAT-SEC-01 keeps certificate verification enabled. |
| NFR-SEC-003 | PAT-SEC-01 and PAT-OPS-03 require TCP 443 reachability. |
| NFR-SEC-004 | PAT-SEC-02 confines the optional API key and proves zero disclosure. |
| NFR-SEC-005 | PAT-SEC-02 protects the environment file and retains Instance Profile credentials. |
| NFR-SEC-006 | PAT-PERF-04 and PAT-SEC-05 protect workspace and writable paths. |
| NFR-SEC-007 | PAT-SEC-04 and PAT-OBS-03 exclude sensitive data. |
| NFR-SEC-008 | PAT-SEC-05 retains required systemd hardening. |
| NFR-OBS-001 | PAT-OBS-01 defines required event coverage. |
| NFR-OBS-002 | PAT-OBS-01 defines Job/status/attempt/errorCode correlation. |
| NFR-OBS-003 | PAT-OBS-02 removes persistent Worker status-log sinks other than journald. |
| NFR-OBS-004 | PAT-OBS-01 defines INFO/WARNING/ERROR/DEBUG use. |
| NFR-OBS-005 | PAT-RES-01 and PAT-SEC-04 exclude response-body dependence and logs. |
| NFR-OBS-006 | PAT-OBS-02 records the metrics/alerts boundary. |
| NFR-OPS-001 | PAT-OPS-01 validates required Status-era configuration before polling. |
| NFR-OPS-002 | PAT-RES-07, PAT-SEC-05, and PAT-OBS-02 realize systemd operation. |
| NFR-OPS-003 | PAT-OPS-02 fixes exact dependencies and frozen installation. |
| NFR-OPS-004 | PAT-PERF-04 defines cleanup and disk evidence without a threshold. |
| NFR-OPS-005 | PAT-OPS-03 verifies endpoint readiness without treating it as schema proof. |
| NFR-OPS-006 | PAT-OPS-04 defines forward-fix recovery. |
| NFR-OPS-007 | PAT-OPS-03 and the E2E pattern require explicit live-test approval. |
| NFR-SCALE-001 | PAT-PERF-02 and PAT-PERF-03 retain one Job on the t3.xlarge baseline. |
| NFR-SCALE-002 | PAT-PERF-03 collects non-gating capacity evidence. |
| NFR-SCALE-003 | PAT-PERF-03 defers horizontal scaling pending idempotency evidence. |
| NFR-MAINT-001 | PAT-TEST-01 and PAT-TEST-02 define deterministic complete matrices. |
| NFR-MAINT-002 | PAT-TEST-03 requires pytest, Ruff, strict mypy, and compileall. |
| NFR-MAINT-003 | PAT-TEST-03 enforces source and dependency scans. |
| NFR-MAINT-004 | PAT-TEST-03 enforces service, environment, secret, and permission validation. |
| NFR-MAINT-005 | PAT-TEST-04 enforces target-document consistency. |
| NFR-USE-001 | Exact messages/progress remain Functional Design-owned; no Worker UI pattern is introduced. |
| NFR-E2E-001 | The joint E2E pattern verifies PATCH, external GET, artifact, Mobile, and delete order. |
| NFR-E2E-002 | PAT-OBS-03 and the joint E2E pattern define the sanitized evidence bundle. |
| NFR-E2E-003 | PAT-TEST-04 separates Worker automation from external Backend/Mobile evidence. |

## 11. Source and Story Traceability

| Source IDs | Design coverage |
|---|---|
| FR-SA-001, FR-SA-002, FR-SA-003 | PAT-OPS-01, PAT-SEC-01, PAT-SEC-02, PAT-TEST-01 |
| FR-SA-004, FR-SA-005, FR-SA-006 | PAT-RES-02, PAT-OBS-01 |
| FR-SA-007, FR-SA-008 | PAT-RES-03, PAT-RES-04 |
| FR-SA-009, FR-SA-010, FR-SA-011, FR-SA-012 | PAT-RES-01, PAT-RES-02, PAT-PERF-01 |
| FR-SA-013, FR-SA-014 | PAT-RES-05 |
| FR-SA-015, FR-SA-016 | PAT-SEC-04, PAT-OBS-01, PAT-OBS-02 |
| FR-SA-017, FR-SA-018 | PAT-OPS-01, PAT-OPS-02 |
| NFR-SA-001, NFR-SA-002, NFR-SA-003 | PAT-SEC-01 through PAT-SEC-05 |
| TR-SA-001, TR-SA-002, TR-SA-003, TR-SA-004 | PAT-TEST-01 through PAT-TEST-04 and the joint E2E pattern |
| US-SA-01, US-SA-02, US-SA-03, US-SA-04, US-SA-05, US-SA-06, US-SA-07 | Deployment boundary, phase visibility, completion integrity, safe failure, predictable HTTP, protected observability, and joint acceptance patterns above |

## 12. Explicit Non-Patterns

The following are intentionally absent because they are unapproved, violate requirements, or belong to external systems:
- Worker Job-status GET or terminal-state precheck
- direct Worker DynamoDB access or DynamoDB log persistence
- local durable status outbox, cache, Redis, or secondary database
- circuit breaker or retry of 4xx/network/timeout failures
- concurrent Job execution or autoscaling resource design
- response-body parsing for success
- TLS-disable switch or secret-bearing diagnostics
- new CloudWatch dashboard/alarm resources
- Backend API, persistence, or Mobile implementation
- production deployment or live mutation without separate approval
