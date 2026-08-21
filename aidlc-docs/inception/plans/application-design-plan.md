# Application Design Plan - Status API Migration

## Plan Status

- **Stage**: INCEPTION - Application Design
- **Status**: IN PROGRESS
- **Unit boundary**: Single deployable `ai-worker`
- **Authoritative requirements**: `status-api-requirements.md`
- **Approved stories**: `US-SA-01` through `US-SA-07`
- **Scope**: Component boundaries, public interfaces, service orchestration, dependency direction, and communication patterns
- **Out of scope**: Detailed retry algorithms and business-rule pseudocode (Functional/NFR Design), application code changes (Code Generation), and Backend/Mobile implementation

## Step 1 - Context and Impact Analysis

- [x] Load approved Status API requirements, stories, persona, and execution plan.
- [x] Inspect all existing Application Design artifacts.
- [x] Inspect current Worker, DynamoDB, config, S3, SQS, AI, build, visibility, status, and exception interfaces.
- [x] Identify obsolete design paths: Worker-side GET, terminal skip/delete, DynamoDB UpdateItem, DynamoDB logs, table configuration, and DynamoDB IAM dependency.
- [x] Confirm one-unit boundary and constructor-injection seam.

## Step 2 - Resolved Design Questions

All answers below are inherited from approved requirements and stories. They introduce no new product decision and contain no unresolved `[Answer]:` tag.

### Question 1 - Status integration component boundary

How should outbound Job status updates be isolated from orchestration and AWS clients?

A) Add HTTP calls directly to `WorkerOrchestrator`

B) Create a dedicated `status_api` client with one public status-update interface

C) Extend `DynamoClient` to support HTTP as a second transport

X) Other

[Answer]: B - FR-SA-003 requires a separate Status API client; direct DynamoDB access and the Dynamo component are removed.

### Question 2 - Client outcome contract

How should the client communicate a final non-success result to the orchestrator?

A) Return `bool` and require callers to infer the cause from logs

B) Return `None` on any 2xx and raise a sanitized typed Status API exception on final failure

C) Swallow every failure inside the client

X) Other

[Answer]: B - This keeps HTTP policy in the client while allowing the orchestrator to apply best-effort or mandatory criticality without exposing response bodies or credentials.

### Question 3 - Status criticality ownership

Where should intermediate, SUCCESS, and FAILED criticality be selected?

A) Inside the HTTP client based on status values

B) In explicit orchestrator reporting methods that call a transport-neutral client

C) In the Backend response body

X) Other

[Answer]: B - The orchestrator owns Job lifecycle semantics; the client owns transport behavior. Intermediate/FAILED paths catch typed failures, while SUCCESS lets the failure enter normal Job failure handling.

### Question 4 - HTTP dependency injection

How should HTTP calls be made testable without coupling orchestrator tests to requests internals?

A) Patch the module-level `requests.patch` function in every test

B) Inject a `requests.Session` and sleep callable into `StatusApiClient`, with secure production defaults

C) Introduce a second network microservice

X) Other

[Answer]: B - Session and sleep injection provide deterministic contract tests while preserving a small in-process component boundary.

### Question 5 - User and operational logs

What replaces DynamoDB `logs` persistence?

A) Sanitized Python logging to journald only; Backend receives only the approved latest status message

B) Add an unapproved Backend log endpoint

C) Store logs in S3 from the Worker

X) Other

[Answer]: A - FR-SA-015 and FR-SA-016 remove persistent user log writes and retain sanitized operational logging.

### Answer Analysis

- [x] All five answers are specific and map directly to approved requirement IDs.
- [x] No combined, conditional, vague, or contradictory answer exists.
- [x] No follow-up design question is required.

## Step 3 - Mandatory Design Artifacts

- [x] Update `components.md` with target component definitions, responsibilities, and interfaces.
- [x] Update `component-methods.md` with target method signatures, inputs, outputs, and high-level failure contracts.
- [x] Update `services.md` with lifecycle orchestration and service interaction boundaries.
- [x] Update `component-dependency.md` with dependency matrix, external systems, and validated Mermaid/data-flow alternatives.
- [x] Update consolidated `application-design.md` with architecture decisions and end-to-end component view.

## Step 4 - Design Validation

- [x] Verify no target design path directly accesses DynamoDB or calls Worker-side GET.
- [x] Verify intermediate and FAILED reporting are best-effort while SUCCESS is mandatory.
- [x] Verify artifact upload/HeadObject-size validation precedes SUCCESS and SUCCESS 2xx precedes SQS deletion.
- [x] Verify Status API URL, optional API key, timeout/retry ownership, TLS, and safe logging boundaries are represented.
- [x] Verify all Mermaid diagrams, text alternatives, Markdown fences, links, and whitespace.
- [x] Verify cross-artifact component and method names are consistent.
- [x] Verify traceability to FR-SA-001 through FR-SA-018 and NFR-SA-001 through NFR-SA-003 at Application Design depth.

## Step 5 - Completion and Approval

- [x] Update `aidlc-state.md` to the Application Design approval gate.
- [x] Log artifact completion, disabled-extension handling, validation evidence, and the complete approval prompt in `audit.md`.
- [x] Present explicit `Request Changes`, `Add Units Generation`, and `Approve & Continue` choices.
- [x] Wait for explicit user approval before entering Functional Design.
