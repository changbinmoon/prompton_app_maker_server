# Raw Client JSON and Hermes Integration Code Generation Plan

## Plan Status

- **Unit**: ai-worker
- **Workflow**: Raw Client JSON object in S3 -> Worker validation -> Hermes refinement -> Kiro generation
- **Plan role**: This file is the single source of truth for this follow-up code generation.
- **Approval status**: Approved by user on 2026-08-20T09:03:12Z

## Confirmed Decisions

- [x] Backend stores the original Client JSON object in S3 without a canonical envelope requirement.
- [x] Worker ingress validates only 64 KiB maximum size, UTF-8 JSON, and top-level object shape.
- [x] Worker injects deterministic Android guardrails while preserving the original JSON.
- [x] Hermes uses the host-configured provider/model with `--ignore-rules --toolsets context_engine --oneshot`.
- [x] Hermes is attempted at most three times with 1-second and 2-second backoff delays.
- [x] Valid Hermes stdout is non-empty and no larger than 64 KiB and is stored as `refined-prompt.md`.
- [x] After final Hermes failure, Kiro continues with the original JSON, assets, and the same Android guardrails.

## Unit Context and Boundaries

- **Input boundary**: SQS points to an S3 object containing an arbitrary Client JSON object.
- **Worker responsibility**: Safe raw JSON validation, prompt guardrail construction, Hermes invocation, output validation, retry, fallback, Kiro invocation, and operational logging.
- **Backend dependency**: The actual API Gateway/Lambda repository is not present. This repository will document the raw-object producer contract but cannot wire the S3 upload endpoint.
- **External dependencies**: Hermes Agent v0.20.4 and kiro-cli 2.18.1 installed on the Worker host.
- **Data preservation**: Client JSON is not rewritten or replaced by Hermes output.
- **Canonical schema compatibility**: Existing canonical schema and fixtures remain reference artifacts but are no longer enforced on Worker S3 ingress.

## Execution Steps

### Step 1 - Raw S3 ingress contract

- [x] Change `s3/client.py` to accept any top-level JSON object within the existing 64 KiB limit without canonical schema validation.
- [x] Update `tests/test_s3_client.py` to prove arbitrary raw Client objects are accepted while malformed, non-object, and oversized documents remain rejected.
- [x] Keep canonical schema tests isolated as reference contract tests and remove claims that the Worker enforces that schema at ingress.

### Step 2 - Hermes prompt refiner

- [x] Add `ai/refiner.py` with one-shot command construction, deterministic Android guardrails, untrusted JSON delimiters, output size checks, atomic `refined-prompt.md` writing, and sanitized logs.
- [x] Implement at most three attempts with 1-second and 2-second delays and return `None` after final failure so Kiro fallback can continue.
- [x] Add `tests/test_prompt_refiner.py` for success, exact command, guardrails, retries, empty/oversized output, missing executable, non-zero exit, and no untrusted-value logging.

### Step 3 - Worker and Kiro integration

- [x] Add Hermes executable and refined prompt paths to `Config` and `JobWorkDir` through `models/entities.py` and `config/settings.py`.
- [x] Inject the prompt refiner into `worker/orchestrator.py`, run it before Kiro, and record success/fallback DynamoDB logs without failing the Job on Hermes exhaustion.
- [x] Extend `ai/generator.py` so Kiro reads `refined-prompt.md` when present and otherwise receives the identical deterministic Android fallback guardrails with the raw JSON and assets.
- [x] Update orchestrator, generator, config, and shared fixtures/tests for the new interfaces.

### Step 4 - Deployment and contract documentation

- [x] Add `HERMES_CLI_PATH` to `deploy/env.example` and ensure the systemd sandbox permits the configured Hermes runtime/home access required by the chosen host-default provider/model policy.
- [x] Update `contracts/README.md`, `aidlc-docs/construction/ai-worker/functional-design/business-rules.md`, `aidlc-docs/construction/ai-worker/code/code-summary.md`, affected files under `aidlc-docs/construction/build-and-test/`, `aidlc-docs/operations/operational-test-plan.md`, and `aidlc-docs/aidlc-state.md` to describe raw ingress, Hermes retry, and Kiro fallback accurately.
- [x] Mark the earlier Backend canonical producer question as superseded by the user-approved raw-object producer boundary.

### Step 5 - Validation and delivery

- [x] Run targeted tests for S3 ingress, prompt refiner, generator, config, and orchestrator.
- [x] Run the full pytest suite, Ruff, strict mypy, compile, lock, JSON/Markdown syntax, and `git diff --check` validations.
- [x] Obtain an independent code review and resolve blocking findings.
- [ ] Stage only intended files, commit to `feature/ai-worker-operational-readiness`, push, and verify local/remote SHA equality and a clean worktree.

## Traceability

- **Raw Client preservation**: Steps 1 and 2
- **Hermes before Kiro**: Steps 2 and 3
- **Android API level and applicationId guardrails**: Steps 2 and 3
- **Hermes retry and fallback**: Steps 2 and 3
- **Operational reproducibility**: Steps 4 and 5
- **Backend limitation disclosure**: Step 4
