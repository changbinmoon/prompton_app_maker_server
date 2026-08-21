# SDK 36 and Compose Compatibility Code Generation Plan

## Approval and decisions

- **Approved at**: 2026-08-21T03:46:02.979Z
- **User input**: `1. 일단 SDK36만 사용하게 2. 진행 3. 패스 4.무시 5. kiro-cli가 opus5 사용하도록 다시 변경 및 kiro-cli의 계정 플랜 확인`
- **Unit**: `ai-worker`
- **Change type**: Brownfield generation-policy compatibility fix
- **SDK interpretation**: Always generate with `compileSdk=36`, `targetSdk=36`, and `minSdk=26`.
- **Deployment**: Skip; do not modify `/opt/prompton-ai-worker` or restart systemd.
- **Duplicate consumer**: Keep the acknowledged shared-Queue risk; do not alter Queue or external Worker.

## Kiro model and plan evidence

- [x] Query service-account Kiro identity type without recording identifiers.
- [x] Query `/usage` without recording account URL or credentials.
- [x] Query the Kiro CLI 2.18.1 model list.
- [x] Record `KIRO FREE`, 4.81 of 50 covered credits used, 9%, reset 2026-09-01.
- [x] Confirm that no Opus model and no exact `claude-opus-5` model are supported.
- [x] Keep `claude-sonnet-4.5` to avoid deploying a known-invalid model argument.

## Files

- `ai/refiner.py`
- `ai/generator.py`
- `tests/test_prompt_refiner.py`
- `tests/test_ai_generator.py`
- `contracts/README.md`
- `aidlc-docs/operations/operational-test-plan.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/audit.md`

## Step 1: Update deterministic Android generation guardrails

- [x] Ignore Client-supplied Android API levels for compile/target selection.
- [x] Require `compileSdk=36`, `targetSdk=36`, and `minSdk=26`.
- [x] Require a mutually compatible fixed AGP, Gradle, Kotlin, Compose compiler, and Compose BOM stack.
- [x] Require Java 17 bytecode settings.
- [x] Require dependency-version-compatible Compose API calls.
- [x] Require explicit `@OptIn` annotations for experimental Compose APIs.
- [x] Retain official wrapper properties and Worker-owned wrapper binary generation.

## Step 2: Add and update tests

- [x] Assert SDK 36-only values in Hermes and raw-Kiro prompt paths.
- [x] Assert the fixed Android/Compose toolchain compatibility guidance.
- [x] Assert progress indicator and experimental API compatibility guidance.
- [x] Run targeted refiner, generator, and builder tests.

## Step 3: Update active contracts and operational state

- [x] Update the active raw Client Android guardrail contract to SDK 36.
- [x] Mark Platform 35 absence as superseded by the SDK 36 policy, pending deployment.
- [x] Record that Opus 5 remains blocked by the installed Kiro model catalog.
- [x] Preserve historical targetSdk 35 smoke evidence as historical evidence.

## Step 4: Validate and close

- [x] Run the complete pytest, Ruff, mypy, compileall, and lock gates.
- [x] Run Markdown, whitespace, plan checkbox, and added-diff secret checks.
- [x] Verify the running Worker remains unchanged and healthy.
- [x] Record final evidence in `audit.md`.

## Safety boundary

No Kiro login mutation, model invocation, AWS resource change, Queue purge/delete, IAM change, service deployment/restart, or external Worker change is authorized by this plan. The source model remains `claude-sonnet-4.5` because the requested `claude-opus-5` is not available in the installed Kiro CLI catalog.
