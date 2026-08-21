# Kiro Organization Profile Transition Questions

## Current verified state

- The `prompton` service account originally used a Builder ID session.
- The Worker was idle, then gracefully stopped before credential mutation.
- A root-only rollback backup was created and passed SQLite integrity validation.
- The existing ubuntu Kiro session is an IAM Identity Center organization session with a `KIRO PRO+` plan.
- The same organization provider rejects new Pro Device Flow registration with `This account is currently not available`.
- The Builder ID backup was atomically restored and verified.
- The Worker is active and polling again; no organization credential was copied.
- Authentication URLs, device codes, tokens, emails, and account identifiers were not recorded.

## Question 1

How should the blocked organization-profile transition proceed?

A) Ask the organization administrator to enable or restore Kiro Pro device registration and entitlement, then retry a clean service-account Device Flow. This is the recommended option because organization OAuth credentials are not copied between operating-system accounts.

B) Explicitly authorize copying the existing ubuntu user's Kiro organization credential database into the `prompton` service home. This transfers organization OAuth credential material between operating-system accounts. The Worker will be stopped, both states will be backed up, file ownership will be restricted, organization identity/model/plan and a non-interactive smoke will be verified, and rollback will occur on any failure.

C) Use a different organization IAM Identity Center provider that has an active Kiro entitlement. Provide its Start URL and region through a secure channel; they will not be written to audit or source files.

D) Keep the restored Builder ID profile and stop the organization-profile transition.

E) Other (please describe after the `[Answer]:` tag below).

[Answer]: B

## Execution outcome

- **Status**: Complete
- The “Current verified state” section above records the pre-decision rollback state and is superseded by this outcome.
- The Worker was stopped only after confirming it was idle and had no Kiro child process.
- Consistent source and pre-copy service snapshots were stored in a new root-only backup directory with mode `0600` files.
- The ubuntu organization credential database snapshot was atomically installed for `prompton`; source, backup, and installed SQLite integrity checks returned `ok`.
- Service-account `whoami` now reports `IamIdentityCenter`, and the TTY-only profile command fetched and confirmed the current profile successfully.
- The organization catalog exposes 19 models, including exact `claude-opus-5`.
- `/usage` reports `KIRO PRO+`, 1603.14 of 2000 covered credits used (80%), resetting on 2026-09-01.
- A `claude-opus-5` non-interactive smoke created exactly one file with exact expected content and then cleaned up the temporary directory.
- The Worker restarted successfully and is active/running with no restart or startup error marker.
- No authentication URL, device code, token, email, account identifier, or organization identifier was recorded.
- Queue, IAM, DynamoDB, the external Worker, deployed application code, and the configured source model were not changed.

