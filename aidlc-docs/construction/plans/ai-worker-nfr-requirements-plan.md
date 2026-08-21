# NFR Requirements Plan - ai-worker Status API Migration

## Plan Status

- **Stage**: CONSTRUCTION - NFR Requirements
- **Unit**: `ai-worker`
- **Status**: COMPLETE AND APPROVED
- **Depth**: Standard, targeted to the new HTTPS dependency and operational boundary
- **Inputs**: Approved Status API requirements, Application Design, Functional Design, current dependency manifest/lock, systemd unit, and environment template
- **Scope**: Performance, reliability, availability, security, observability, operations, scalability, maintainability, quality gates, and technology choices
- **Out of scope**: Concrete implementation patterns (NFR Design), source changes (Code Generation), infrastructure resource creation, Backend/Mobile implementation

## Step 1 - NFR Context Analysis

- [x] Load NFR Requirements rule and existing NFR artifacts.
- [x] Load approved functional/application design and authoritative requirements.
- [x] Inspect current Python, dependency, lock, systemd, environment, IAM, logging, workspace, and E2E constraints.
- [x] Identify stale NFR assumptions: DynamoDB idempotency/permissions/logs, unpinned “latest” dependencies, and direct table configuration.
- [x] Confirm retained baseline: Python 3.12, uv, single sequential Worker, t3.xlarge planning baseline, systemd, SQS/S3 boto3, 24-hour cleanup, and strict quality gates.

## Step 2 - Resolved NFR Questions

All answers are inherited from approved decisions or current verified project constraints. No unresolved `[Answer]:` tag remains.

### Question 1 - Status API latency limits

What measurable timeout applies to each Status API attempt?

A) One 30-second total request timeout

B) Connect timeout 3 seconds and read-inactivity timeout 10 seconds, with no separate global request deadline

C) No timeout

X) Other

[Answer]: B - FR-SA-011 specifies the requests timeout tuple; it is not an end-to-end Job deadline.

### Question 2 - Retry availability policy

Which failures consume retry/backoff budget?

A) Every exception

B) Only HTTP 5xx, for three total attempts with 1-second and 2-second delays

C) Network errors and timeouts only

X) Other

[Answer]: B - FR-SA-009 and FR-SA-010 make 4xx, connection errors, and timeouts immediately final.

### Question 3 - Completion availability boundary

How should Status API unavailability affect the Worker?

A) Every status outage aborts the Job

B) Intermediate/FAILED reporting degrades, but SUCCESS fails closed and preserves SQS

C) All status failures are ignored

X) Other

[Answer]: B - The approved criticality matrix protects expensive processing while preventing unrecorded completion.

### Question 4 - Secret and transport controls

How is optional API authentication secured?

A) Store the key in source and disable TLS checks in dev

B) Inject the optional key through the protected environment file, send only as `x-api-key`, keep TLS verification enabled, and redact it everywhere

C) Log the key hash for debugging

X) Other

[Answer]: B - NFR-SA-002 and NFR-SA-003 require TLS, TCP 443 egress, repository exclusion, and environment mode 0640 or stricter.

### Question 5 - Observability destination

Where are Worker operational events retained?

A) DynamoDB `logs`

B) Sanitized Python logging to stdout/stderr collected by journald; no user log persistence endpoint

C) Raw HTTP request/response archives

X) Other

[Answer]: B - FR-SA-015 and FR-SA-016 remove DynamoDB logs and prohibit sensitive bodies.

### Question 6 - Technology and dependency policy

What stack/version policy applies?

A) Unpinned latest packages

B) Python 3.12 with uv lock/frozen sync, exact runtime pins including `requests==2.34.2`, and SQS/S3-only Dynamo-related test/stub cleanup

C) Replace Python with another runtime

X) Other

[Answer]: B - Existing manifests and FR-SA-018 require reproducible exact versions.

### Question 7 - Capacity and scaling target

What capacity model applies to this migration?

A) Concurrent multi-Job processing in one process

B) One Job at a time on the existing t3.xlarge planning baseline; no new throughput SLO or autoscaling resource in scope

C) Serverless conversion

X) Other

[Answer]: B - Existing approved operation is sequential, and the migration changes status transport rather than compute capacity.

### Question 8 - Quality and acceptance evidence

What evidence is required before operational acceptance?

A) Manual inspection only

B) Full automated quality gates plus deterministic HTTP/orchestrator tests and an approved dev Job observed through Backend GET and Mobile

C) Production smoke test without local tests

X) Other

[Answer]: B - TR-SA-001 through TR-SA-004 define local, contract, deployment, and joint E2E evidence.

### Answer Analysis

- [x] Eight of eight answers are numeric, bounded, versioned, or linked to explicit acceptance evidence.
- [x] No vague “standard”, “typical”, “latest”, combined, or contradictory answer remains.
- [x] Usability/accessibility is N/A for the headless Worker; user-visible status semantics are covered by exact payload and joint Mobile acceptance.
- [x] No clarification file or additional question round is required.

## Step 3 - Mandatory NFR Artifacts

- [x] Update `nfr-requirements.md` with measurable performance, reliability, security, observability, operations, scalability, maintainability, and E2E criteria.
- [x] Update `tech-stack-decisions.md` with exact runtime/dev dependency targets, configuration, systemd, HTTP, AWS, and toolchain decisions.

## Step 4 - NFR Validation

- [x] Verify every NFR uses a measurable value, explicit pass/fail condition, or deliberate “not specified/in scope” boundary.
- [x] Verify connect/read timeout, 5xx attempt/backoff, any-2xx, and no-retry outcomes are exact.
- [x] Verify TLS, TCP 443, API key, environment mode, IAM removal, workdir mode, and log exclusions.
- [x] Verify intermediate degradation, mandatory SUCCESS, SQS preservation, redelivery, systemd restart, visibility, and cleanup requirements.
- [x] Verify exact dependency pins, lock/frozen sync, DynamoDB-extra removal, and retained SQS/S3 boto3 support.
- [x] Verify pytest, Ruff, strict mypy, compileall, systemd/env, source scan, contract, and E2E evidence gates.
- [x] Verify all 25 Status API requirement IDs and seven stories map to NFR or explicit functional/deferred ownership.
- [x] Verify Markdown, embedded TOML/INI/Bash syntax, links, tables, and whitespace.
- [x] Obtain independent review with no blocking finding.

## Step 5 - Completion and Standard Approval Gate

- [x] Update `aidlc-state.md` to the NFR Requirements approval gate.
- [x] Log validation, disabled-extension handling, and the complete standardized approval prompt in `audit.md`.
- [x] Present only `Request Changes` and `Continue to Next Stage` options.
- [x] Explicit approval received at 2026-08-20T11:57:12.077Z; proceed to NFR Design.
