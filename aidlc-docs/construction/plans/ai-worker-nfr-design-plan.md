# NFR Design Plan - ai-worker Status API Migration

## Plan Status

- **Stage**: CONSTRUCTION - NFR Design
- **Unit**: `ai-worker`
- **Status**: COMPLETE AND APPROVED
- **Depth**: Standard, targeted to the outbound HTTPS status boundary and lifecycle integrity
- **Inputs**: Approved Status API requirements, user stories, Application Design, Functional Design, NFR Requirements, and technology decisions
- **Scope**: Concrete NFR patterns, logical components, failure/degradation boundaries, protected observability, deterministic test seams, and operational verification
- **Out of scope**: Application source changes, infrastructure resource creation, Backend/Mobile implementation, and production activation

## Step 1 - NFR Context Analysis

- [x] Load the NFR Design rule and mandatory common rules.
- [x] Load approved requirements, stories, Application Design, Functional Design, NFR Requirements, and technology decisions.
- [x] Confirm the execution plan requires NFR Design for the single `ai-worker` unit.
- [x] Confirm Security Baseline, Resiliency Baseline, and Property-Based Testing extensions remain disabled.
- [x] Identify the critical NFR boundaries: intermediate degradation, mandatory SUCCESS, bounded 5xx retry, no GET, protected credentials/logs, sequential capacity, reproducible deployment, and joint E2E evidence.

## Step 2 - Resolved NFR Design Questions

All mandatory NFR Design categories were evaluated. The answers below are inherited from explicitly approved requirements and designs; no unresolved `[Answer]:` tag remains.

### Question 1 - Resilience Pattern

Which fault-tolerance pattern must the status boundary use?

A) Retry every HTTP and network failure, then continue all statuses best-effort

B) Retry only HTTP 5xx for three total attempts with 1-second and 2-second delays; contain intermediate/FAILED reporting failure, but fail closed on SUCCESS and preserve SQS

C) Add a circuit breaker and local status outbox

D) Other (please describe after the `[Answer]:` tag below)

[Answer]: B - Approved FR-SA-009 through FR-SA-012 and NFR-REL-002 through NFR-REL-005 define this exact split.

### Question 2 - Scalability Pattern

Which scaling mechanism and load boundary apply to this migration?

A) Add concurrent async Job execution inside one process

B) Keep one sequential Job per Worker process on the current t3.xlarge planning baseline; collect capacity evidence and defer horizontal scaling

C) Provision autoscaling and distributed coordination now

D) Other (please describe after the `[Answer]:` tag below)

[Answer]: B - NFR-PERF-002 and NFR-SCALE-001 through NFR-SCALE-003 prohibit a new concurrency or autoscaling design.

### Question 3 - Performance Pattern

How must Status API latency and request work be bounded?

A) Use an unbounded client timeout and background queue

B) Use synchronous PATCH with timeout `(3, 10)`, any-2xx body-independent success, and an exact three-attempt 5xx budget; do not add subprocess deadlines

C) Use a 30-second end-to-end Job deadline

D) Other (please describe after the `[Answer]:` tag below)

[Answer]: B - NFR-PERF-001 and NFR-PERF-004 through NFR-PERF-006 provide exact measurable constraints.

### Question 4 - Security Pattern

Which transport, credential, and logging controls must the design apply?

A) Disable certificate validation in development and log response bodies

B) Keep default TLS verification, inject an optional key only through protected configuration, add only `x-api-key`, use least-privilege SQS/S3 IAM, and structurally exclude secrets and response bodies from logs/exceptions

C) Add static AWS keys to the environment file

D) Other (please describe after the `[Answer]:` tag below)

[Answer]: B - NFR-SEC-001 through NFR-SEC-008 and the approved Status API contract make these controls release-blocking.

### Question 5 - Logical Components and Integration

Which component pattern should realize the NFRs?

A) Put HTTP, retry, status criticality, and message deletion in one orchestrator method

B) Use a dedicated synchronous `StatusApiClient`, typed sanitized failures, orchestrator-owned criticality, injected session/sleep and adapter fakes, journald logging, existing SQS visibility, and external Backend/Mobile E2E observers

C) Add Redis, a local durable outbox, and a separate status service

D) Other (please describe after the `[Answer]:` tag below)

[Answer]: B - Approved Application/Functional Design and NFR-MAINT-001 define these boundaries without adding infrastructure.

### Answer Analysis

- [x] Resilience, scalability, performance, security, and logical-component categories were explicitly evaluated.
- [x] Every answer maps to approved numeric, behavioral, or ownership constraints.
- [x] No answer is vague, contradictory, or dependent on an unapproved threshold.
- [x] No clarification round is required before artifact generation.

## Step 3 - Required NFR Design Artifacts

- [x] Generate `nfr-design-patterns.md` with concrete resilience, performance, scalability, security, observability, operations, maintainability, and acceptance patterns.
- [x] Generate `logical-components.md` with responsibilities, interactions, state/failure flow, configuration, test seams, and external boundaries.

## Step 4 - Validation

- [x] Verify every one of the 49 approved NFR IDs maps to a pattern or explicit external/operational boundary.
- [x] Verify all 25 Status API requirement IDs and all seven stories remain covered.
- [x] Verify exact timeout, retry, any-2xx, no-GET, SUCCESS-before-delete, FAILED preservation, and post-SUCCESS delete-failure behavior.
- [x] Verify TLS, optional key, IAM removal, TCP 443, environment protection, systemd hardening, workspace, and log-exclusion controls.
- [x] Verify deterministic tests, source/dependency scans, quality gates, deployment checks, and joint E2E evidence ownership.
- [x] Validate Markdown, tables, code blocks, Mermaid syntax, text alternatives, links, and whitespace.
- [x] Obtain independent review with no blocking finding.

## Step 5 - Completion and Approval Gate

- [x] Update `aidlc-state.md` and the execution plan to the NFR Design approval gate.
- [x] Append validation, disabled-extension handling, and the standardized approval prompt to `audit.md`.
- [x] Present only `Request Changes` and `Continue to Next Stage` options.
- [x] Explicit approval received at 2026-08-20T12:11:11.523Z; proceed to Code Generation Part 1 - Planning.
