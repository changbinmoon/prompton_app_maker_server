# Functional Design Plan - ai-worker Status API Migration

## Plan Status

- **Stage**: CONSTRUCTION - Functional Design
- **Unit**: `ai-worker`
- **Status**: IN PROGRESS
- **Detail level**: Comprehensive and targeted to status lifecycle invariants
- **Unit source**: Approved execution plan and Application Design; Units Generation was explicitly skipped because this is one deployable/runtime unit.
- **Scope**: Detailed business logic, domain entities/value objects, validation rules, data flow, integration outcomes, and failure scenarios
- **Out of scope**: Concrete HTTP library code and infrastructure patterns (NFR Design), source changes (Code Generation), Backend/Mobile implementation

## Step 1 - Unit Context Analysis

- [x] Load the Functional Design rule and existing `ai-worker` artifacts.
- [x] Load approved Status API requirements and Application Design contracts.
- [x] Inspect existing SQS, workspace, S3, Hermes, Kiro, Gradle, visibility, status, and error models.
- [x] Identify superseded functional paths: status GET, terminal skip/delete, DynamoDB writes/logs, strict persisted-state progression, and table record model.
- [x] Confirm preserved behavior: one-Job processing, clean workspace, raw JSON ingress, optional assets, Hermes fallback, Kiro/Gradle execution, verified artifact, visibility extension, and 24-hour cleanup.

## Step 2 - Resolved Functional Questions

All answers are inherited from approved requirements and Application Design. No unresolved `[Answer]:` tag remains.

### Question 1 - Repeated SQS delivery

How does the Worker handle a redelivered valid Job message?

A) Read terminal state and skip completed Jobs

B) Recreate the workspace and execute the entire Job from ANALYZING

C) Resume from the most recently observed local phase

X) Other

[Answer]: B - FR-SA-013 and FR-SA-014 explicitly prohibit GET and require full reprocessing.

### Question 2 - Status update criticality

Which layer decides whether a final Status API failure stops processing?

A) The Status API client swallows every failure

B) The orchestrator applies best-effort to ANALYZING/GENERATING_CODE/BUILDING/FAILED and mandatory semantics to SUCCESS

C) The Backend response body decides

X) Other

[Answer]: B - FR-SA-012 and the approved component boundary place lifecycle criticality in the orchestrator.

### Question 3 - HTTP outcome algorithm

What result and retry rule governs one status update command?

A) Parse JSON and retry any exception

B) Accept any 2xx, retry only 5xx for three total attempts with 1-second/2-second delays, and do not retry 4xx, connection errors, timeouts, or other non-2xx classes

C) Retry until SQS visibility expires

X) Other

[Answer]: B - FR-SA-009 through FR-SA-011 define the complete decision table; success never depends on a response body.

### Question 4 - Mandatory SUCCESS failure

What happens after verified artifact upload if SUCCESS cannot be recorded?

A) Delete the SQS message because the artifact exists

B) Classify completion as INTERNAL_ERROR, attempt FAILED best-effort, and preserve the SQS message

C) Ignore the error and return success locally

X) Other

[Answer]: B - FR-SA-007, FR-SA-008, and FR-SA-012 require fail-closed completion.

### Question 5 - FAILED reporting failure

How is a second failure while reporting FAILED handled?

A) Replace the original error with the reporting error

B) Log sanitized reporting metadata, preserve the original errorCode/message, and keep the SQS message

C) Delete the message to avoid duplicate work

X) Other

[Answer]: B - The original Job failure remains authoritative and FAILED is best-effort.

### Question 6 - Domain representation of outbound status

How should optional payload fields be modeled before serialization?

A) A status-update value object with optional typed fields; serialization omits `None`

B) Free-form dictionaries assembled in every phase

C) A DynamoDB record object reused for HTTP

X) Other

[Answer]: A - A typed value object preserves exact field names and FAILED progress omission while keeping transport serialization centralized.

### Answer Analysis

- [x] Six of six answers are precise and directly traceable to approved requirements.
- [x] No vague, combined, conditional, contradictory, or frontend-specific decision exists.
- [x] No clarification file or additional question round is required.

## Step 3 - Mandatory Functional Design Artifacts

- [x] Update `business-rules.md` with full-reprocessing, payload, criticality, HTTP outcome, deletion, error-preservation, logging, and preserved pipeline rules.
- [x] Update `domain-entities.md` with Status API command/failure value objects, exact status mappings, target Config, existing Job/S3/workspace entities, and removed persistence model.
- [x] Update `business-logic-model.md` with deterministic Job orchestration, status-client decision algorithm, success/failure flows, and scenario matrix.
- [x] Confirm no frontend/UI artifact is applicable to the `ai-worker` unit.

## Step 4 - Functional Validation

- [x] Verify exact ANALYZING, GENERATING_CODE, BUILDING, SUCCESS, and FAILED payloads and omission rules.
- [x] Verify status invocation points and per-delivery sequence.
- [x] Verify upload plus HeadObject/size validation precedes SUCCESS and any 2xx precedes SQS deletion.
- [x] Verify SUCCESS final failure becomes INTERNAL_ERROR and FAILED reporting cannot mask the original error.
- [x] Verify only 5xx retries, with three total attempts and 1-second/2-second delays; all other final failures have no client retry.
- [x] Verify no Worker-side GET, DynamoDB access, table/log entity, or terminal skip remains in target behavior.
- [x] Verify existing input, AI/build, S3/SQS, visibility, workspace, and cleanup behavior remains represented.
- [x] Verify requirement/story traceability, Mermaid/text alternatives, pseudocode, Markdown, and whitespace.
- [x] Obtain independent review with no blocking finding.

## Step 5 - Completion and Standard Approval Gate

- [x] Update `aidlc-state.md` to the Functional Design approval gate.
- [x] Log validation, disabled-extension handling, and the complete standardized approval prompt in `audit.md`.
- [x] Present only `Request Changes` and `Continue to Next Stage` options.
- [x] Wait for explicit approval before NFR Requirements.
