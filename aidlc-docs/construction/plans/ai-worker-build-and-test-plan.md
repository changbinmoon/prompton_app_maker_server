# Build and Test Plan - ai-worker Status API Migration

## Plan Status

- **Stage**: CONSTRUCTION - Build and Test
- **Unit**: `ai-worker`
- **Project type**: Brownfield Python 3.12 Worker
- **Status**: COMPLETE AND APPROVED
- **Prerequisite**: Code Generation approved at 2026-08-20T12:49:40.634Z
- **Purpose**: Regenerate the complete Build and Test instruction set for the Status API target, validate it, and stop at the explicit Operations approval gate.
- **Safety boundary**: Local deterministic checks are allowed. Live Status API, SQS, S3 mutation, Hermes/Kiro model use, Backend GET, Mobile observation, IAM/network changes, deployment, commit, and push are not authorized by this plan.

## Baseline Evidence

- 149 tests passed with 70 botocore deprecation warnings.
- Ruff passed.
- Repository-wide strict mypy passed for 39 files.
- Compileall, `uv lock --check`, and frozen dev sync passed.
- Source/security/dependency/deployment scans passed.
- Direct production-path systemd verification is blocked only because `/opt/prompton-ai-worker/.venv/bin/python` is absent on the development host; host-compatible syntax verification and exact production assertions passed.
- Historical Build and Test files contain DynamoDB and 132-test guidance and must be replaced in place.

## Execution Steps

### Step 1 - Analyze Scope and Existing Artifacts
- [x] Load mandatory Build and Test, content-validation, and continuity rules.
- [x] Confirm Code Generation approval and current state.
- [x] Inspect all eight existing instruction files and identify stale DynamoDB, terminal-skip, 132-test, and old dependency guidance.
- [x] Load the approved code summary, requirements/NFR/story boundaries, manifest, environment template, and systemd unit.

### Step 2 - Regenerate Build Instructions
- [x] Replace `build-instructions.md` with frozen sync, lock, compile, quality, source-scan, config, and deployment validation commands.
- [x] Document exact required/optional Status API environment values and the production-path systemd limitation.
- [x] Exclude live deployment and model execution from the local build gate.

### Step 3 - Regenerate Unit Test Instructions
- [x] Replace `unit-test-instructions.md` with all 149 tests and focused suite commands.
- [x] Document Status client, orchestrator ordering, configuration, startup logging, retained component behavior, warnings, and failure triage.
- [x] Preserve behavior-based quality gates without inventing a coverage threshold.

### Step 4 - Regenerate Integration and Additional Test Instructions
- [x] Replace `integration-test-instructions.md` with local component integration and separately authorized live interaction procedures.
- [x] Replace `contract-test-instructions.md` with the outbound Status API PATCH, SQS/S3, Hermes/Kiro, and Backend idempotency contracts.
- [x] Replace `security-test-instructions.md` with project NFR security checks and external IAM/TCP443/env/systemd evidence.
- [x] Replace `e2e-test-instructions.md` with the approved Worker-Backend-S3-SQS-Mobile evidence flow and safety/cleanup controls.

### Step 5 - Regenerate Performance Instructions
- [x] Replace `performance-test-instructions.md` with observational duration/resource/capacity procedures.
- [x] Preserve one Job per process and visibility requirements; do not invent latency, throughput, or availability targets.
- [x] Gate every model/AWS/backlog scenario behind an approved dev Job and test window.

### Step 6 - Regenerate Summary and Traceability
- [x] Replace `build-and-test-summary.md` with current local results and generated-file inventory.
- [x] Map 25 Status API requirements, 49 NFRs by category, and seven stories to instruction/evidence ownership.
- [x] Distinguish completed local gates, instruction readiness, and pending external/live acceptance.
- [x] Record disabled extension status as N/A while retaining project-specific controls.

### Step 7 - Validate and Independently Review
- [x] Validate Markdown fences, Bash/JSON/Python syntax, paths, commands, links, secrets, Status API terminology, and zero executable DynamoDB guidance.
- [x] Confirm all eight required instruction files exist and historical test counts/paths are removed.
- [x] Obtain independent review; no blocking or material findings, and the stale active workspace count minor was corrected.

### Step 8 - Complete Stage Tracking and Approval Gate
- [x] Update state/execution tracking to Build and Test complete / approval pending.
- [x] Append validation evidence and the standardized completion prompt to `audit.md`.
- [x] Present the mandatory Build and Test two-option completion message.
- [x] Explicit user approval received at 2026-08-20T13:08:18.475Z; Operations placeholder acknowledged.

## Deliverables

- `aidlc-docs/construction/build-and-test/build-instructions.md`
- `aidlc-docs/construction/build-and-test/unit-test-instructions.md`
- `aidlc-docs/construction/build-and-test/integration-test-instructions.md`
- `aidlc-docs/construction/build-and-test/performance-test-instructions.md`
- `aidlc-docs/construction/build-and-test/contract-test-instructions.md`
- `aidlc-docs/construction/build-and-test/security-test-instructions.md`
- `aidlc-docs/construction/build-and-test/e2e-test-instructions.md`
- `aidlc-docs/construction/build-and-test/build-and-test-summary.md`

## Extension Configuration

| Extension | Enabled | Disposition |
|---|---|---|
| Security Baseline | No | N/A; project-specific security requirements remain mandatory. |
| Resiliency Baseline | No | N/A; approved project-specific reliability requirements remain mandatory. |
| Property-Based Testing | No | N/A; deterministic tests remain mandatory. |
