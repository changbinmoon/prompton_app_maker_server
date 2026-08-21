# Gradle Wrapper Recovery Code Generation Plan

## Approval and scope

- **Approved at**: 2026-08-21T03:26:48.400Z
- **Approval input**: `진행해줘`
- **Unit**: `ai-worker`
- **Change type**: Brownfield targeted build-recovery bug fix
- **Trigger**: Local Job `5d5efe3d-56cb-4297-a1a4-421dc3fc8c76` generated a 31-byte ASCII `gradle-wrapper.jar` placeholder and failed with `GradleWrapperMain` ClassNotFoundException.

## Boundaries

- Modify existing application files in place; do not create duplicate modules.
- Do not stop or restart the running Worker during implementation.
- Do not submit another Backend Job, purge/delete SQS messages, change IAM, or alter the external Worker.
- Perform the real Gradle/APK smoke only on an isolated copy of the failed project.
- Keep Kiro tool trust restricted to `fs_read,fs_write`; do not grant shell execution.

## Files

- `build/builder.py`
- `tests/test_builder.py`
- `ai/generator.py`
- `tests/test_ai_generator.py`
- `aidlc-docs/operations/operational-test-plan.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/audit.md`

## Execution steps

### Step 1: Confirm failure contract and approval

- [x] Confirm the invalid wrapper payload, direct exception, and healthy Worker recovery evidence.
- [x] Record the user's explicit continuation approval in `audit.md`.
- [x] Define the no-AWS-mutation and isolated-copy test boundaries.

### Step 2: Implement wrapper integrity recovery

- [x] Validate that `gradlew` and `gradle/wrapper/gradle-wrapper.jar` both exist.
- [x] Validate the wrapper JAR as a readable ZIP containing `org/gradle/wrapper/GradleWrapperMain.class`.
- [x] Regenerate missing or invalid wrapper artifacts with the configured trusted Gradle executable.
- [x] Revalidate generated artifacts before executing `gradlew`.
- [x] Instruct Kiro not to create wrapper scripts or binary JAR placeholders.

### Step 3: Add and run automated tests

- [x] Update builder test fixtures to create a structurally valid wrapper JAR.
- [x] Cover invalid placeholder regeneration and post-generation integrity failure.
- [x] Assert the Kiro prompt delegates wrapper generation to the Worker.
- [x] Run targeted pytest, Ruff, and mypy checks.
- [x] Run the complete repository quality gates.

### Step 4: Run isolated real-project build smoke

- [x] Copy the failed generated project to a temporary isolated directory.
- [x] Invoke the updated builder under the service-account runtime without modifying the original Job directory.
- [x] Verify wrapper JAR integrity and APK ZIP/signature/package metadata.
- [x] Remove the temporary copied project and APK after recording safe evidence.

### Step 5: Record outcome

- [x] Update operational test status and blocker disposition.
- [x] Append implementation and verification evidence to `audit.md`.
- [x] Re-run Markdown, whitespace, and added-diff secret validation.

## Traceability and completion

This internal bug fix addresses FR-008 and BR-008/BR-015. No new user story, API, database entity, or infrastructure component is introduced. Completion requires all checkboxes above to be marked and both automated and isolated real-project build evidence to pass, or a precisely recorded remaining blocker if the generated Android source has an independent compile failure.
