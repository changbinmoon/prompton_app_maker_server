# Kiro Opus 5 Quick Activation Plan

## Approval and evidence

- **Approved at**: 2026-08-21T04:21:08.620Z
- **User input**: `opus 5 지원 가능하면 다시 opus5를 사용하도록 퀵하게 수정`
- **Verified catalog**: The organization profile exposes exact `claude-opus-5`.
- **Verified smoke**: Exact Opus 5 completed a non-interactive one-file generation smoke.
- **Scope**: Change the source model constant and assertion, apply a model-only active deployment hotfix, validate, and restart the Worker.

## Step 1: Source and active documentation

- [x] Change `KIRO_CLI_MODEL` from `claude-sonnet-4.5` to `claude-opus-5`.
- [x] Update the focused generator test assertion.
- [x] Update current requirements and operational state without rewriting historical evidence.

## Step 2: Source validation

- [x] Run focused generator tests.
- [x] Run Ruff lint/format and strict mypy for changed Python files.
- [x] Run compile and whitespace checks.

## Step 3: Model-only active hotfix

- [x] Confirm the Worker is idle and stop it gracefully.
- [x] Resolve and back up the active deployed generator file.
- [x] Change only the deployed model reference to `claude-opus-5` and verify no unrelated deployed diff.

## Step 4: Runtime verification and restore

- [x] Verify active deployed syntax and exact model constant.
- [x] Run an isolated service-account Opus 5 non-interactive smoke.
- [x] Restart the Worker and verify stable systemd state.
- [x] Update audit and active operational documentation.
- [x] Run final Markdown, secret, backup, and deployment-scope checks.

## Safety boundary

Do not deploy the current source tree wholesale. SDK 36, Compose, Gradle Wrapper, or other uncommitted source changes remain undeployed. Do not mutate Queue, IAM, DynamoDB, or the external Worker. Do not record authentication URLs, codes, tokens, account identifiers, or organization identifiers. Preserve a model-hotfix rollback copy before modifying the active deployed file.
