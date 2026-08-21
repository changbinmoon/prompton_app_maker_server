# Dev E2E Approval Package - ai-worker Status API Migration

## 1. Package Status

| Item | Value |
|---|---|
| Preparation status | COMPLETE |
| Execution approval | NOT GRANTED |
| Readiness status | NOT READY |
| Package purpose | Obtain explicit approval for one controlled dev success-path Job and evidence collection |
| Live action performed while preparing | None |

This package does not authorize Job submission, service start/restart, Status API PATCH, SQS/S3 mutation, Hermes/Kiro use, Android build, deployment, IAM/network change, or cleanup.

Readiness evidence: `aidlc-docs/operations/status-api-readiness-evidence.md`.
Detailed procedure: `aidlc-docs/construction/build-and-test/e2e-test-instructions.md`.

## 2. Prefilled Dev Environment

| Field | Value |
|---|---|
| AWS region | `us-east-1` |
| Main queue | `https://sqs.us-east-1.amazonaws.com/440052841756/prompton-app-build-jobs-dev` |
| DLQ name | `prompton-app-build-jobs-dlq-dev` |
| Main queue VisibilityTimeout | `300` seconds (observed 2026-08-20) |
| Main queue maxReceiveCount | `3` (observed 2026-08-20) |
| S3 bucket | `prompton-app-builder-dev-changbin` |
| Status API base | `https://xb2z5ls8k0.execute-api.us-east-1.amazonaws.com` |
| Authentication mode | Must be confirmed; never place a key in this package |
| Worker install root | `/opt/prompton-ai-worker` |
| Protected env path | `/etc/prompton-worker/env` |
| systemd unit | `prompton-worker.service` |
| Work/cache paths | `/data/jobs`, `/data/hermes`, `/data/gradle` |

The current development machine is not the deployed Worker host. The actual dev host remains unidentified.

## 3. Required Test Identity and Window - Unfilled

| Required field | Approval value |
|---|---|
| Approved environment/account |  |
| Actual deployed Worker host/instance |  |
| Deployed commit SHA/revision |  |
| Unique non-customer Job ID |  |
| Test fixture name/version |  |
| UTC start time |  |
| UTC end time |  |
| Maximum authorized model/cost budget |  |
| Approved observation/stop conditions |  |
| Evidence storage/retention location |  |

All fields above are required before execution. The observation window coordinates owners; it must not be converted into an unapproved Worker end-to-end timeout.

## 4. Required Owners and Approvers - Unfilled

| Role | Name/team | Approval and UTC timestamp |
|---|---|---|
| Environment/account owner |  |  |
| Backend Job/GET owner |  |  |
| Worker operator |  |  |
| SQS/S3 resource owner |  |  |
| IAM/security reviewer |  |  |
| Hermes provider/cost approver |  |  |
| Kiro model/cost approver |  |  |
| Mobile observer |  |  |
| Cleanup owner |  |  |
| Final test conductor |  |  |

A single person may fill multiple roles only if organizational policy permits it. Approval must be explicit and limited to this package's Job/environment/window.

## 5. Readiness Findings That Block Approval

The following must be resolved or explicitly accepted by the responsible owner before execution:

- Worker effective IAM policy inventory is unavailable because IAM read actions were denied.
- Configured dev S3 bucket returned 403/AccessDenied for HeadBucket and zero-key `jobs/` prefix ListBucket checks.
- DLQ attributes/resource policy are unavailable to the current role.
- The actual deployed dev Worker host is not identified.
- Installed env owner/group/mode/static-key absence is unverified.
- Installed systemd unit, production `ExecStart`, hardening, writable paths, and service identity are unverified.
- Status API authentication mode is not confirmed for the target host.

Already passed and time-bound:

- Main queue VisibilityTimeout 300 and RedrivePolicy `maxReceiveCount=3`.
- Main queue had zero visible and zero in-flight messages at observation time.
- DNS, TCP 443, default certificate/hostname verification, and TLS 1.3 handshake succeeded without an HTTP request.

## 6. Scenario Scope - Selection Required

| Scenario | Include? | Additional authorization |
|---|---|---|
| One success-path Job |  | Required baseline approval |
| Delete failure after accepted SUCCESS/redelivery |  | Separate duplicate model/build cost and reversible fault approval |
| Deterministic processing failure/FAILED |  | Separate failure fixture and DLQ/cleanup approval |
| Performance/resource observation |  | Separate target-host collection and stop-condition approval |
| Mobile APK install/smoke |  | Separate test device/application approval |

The minimum joint acceptance scope is one success-path Job. Optional fault/capacity scenarios must not be inferred from baseline approval.

## 7. Success-Path Acceptance Criteria

The approved run must produce sanitized evidence that:

1. Backend creates the Job, stores the approved raw requirements object, and enqueues its S3 pointer.
2. Worker emits ANALYZING, GENERATING_CODE, and BUILDING PATCH attempts with exact progress/messages.
3. Intermediate reporting failure, if naturally observed, does not stop processing.
4. Hermes refinement or safe raw fallback occurs before Kiro generation without raw-output disclosure.
5. Gradle produces a nonempty APK.
6. Worker uploads the APK and verifies HeadObject/ContentLength before SUCCESS.
7. SUCCESS contains progress 100, exact completion message, and `jobs/{jobId}/artifact/app-debug.apk`.
8. Status API returns 2xx before Worker deletes the SQS message.
9. Backend GET shows the stored final state and artifact; Worker itself performs no GET.
10. Mobile displays the same final SUCCESS/artifact outcome.
11. APK metadata and SHA-256 are recorded.
12. No API key, credential, raw Client JSON, Hermes output, signed URL, or sensitive Backend response body enters evidence.

## 8. Evidence Bundle Checklist

| Evidence | Owner | Collected/verified |
|---|---|---|
| Commit SHA and UTC timeline | Worker operator |  |
| Sanitized Worker journald events | Worker operator |  |
| PATCH status/attempt/HTTP-class outcomes without body/key | Worker/Backend |  |
| Main queue/DLQ attributes and deletion/redrive evidence | SQS owner |  |
| S3 artifact key, ContentLength, LastModified | S3 owner |  |
| Downloaded APK SHA-256 | Test conductor |  |
| Backend GET observations | Backend owner |  |
| Mobile final observation | Mobile observer |  |
| IAM/TLS/env/systemd readiness | Security/operator |  |
| Cleanup evidence | Cleanup owner |  |
| Sensitive-evidence review | Security reviewer |  |

## 9. Safety and Stop Conditions

Before the run, approvers must define environment-specific stop conditions for:

- Unexpected production/shared-resource identifiers.
- Missing/invalid owner approval.
- Credential or sensitive-data disclosure.
- Unapproved model/provider/cost use.
- S3/SQS access outside the unique Job prefix/message.
- Repeated service restart, OOM, disk pressure, or uncontrolled duplicate processing.
- TLS/certificate failure or authentication-mode mismatch.
- Cleanup uncertainty or risk to unrelated resources.

On a stop condition, cease new actions, preserve sanitized evidence, and coordinate recovery with resource owners. Do not purge a shared queue, recursively delete an unverified prefix, weaken IAM/TLS/firewalls, or add a Worker GET workaround.

## 10. Cleanup Approval - Unfilled

| Field | Approval value |
|---|---|
| Exact S3 Job prefix eligible for cleanup |  |
| Exact message/DLQ handling procedure |  |
| Backend record retention/deletion decision |  |
| Local Job workspace/evidence retention |  |
| Cleanup executor |  |
| Cleanup verification owner |  |
| Cleanup authorization and UTC timestamp |  |

Cleanup is part of the approved test window and is not implied by test-execution approval.

## 11. Final Authorization - Unfilled

| Decision | Value |
|---|---|
| All readiness blockers resolved/accepted by owners |  |
| All required identity/window/owner fields complete |  |
| Success-path scenario approved |  |
| Optional scenarios explicitly approved or excluded |  |
| Model/provider/cost authorization recorded |  |
| Cleanup authorization recorded |  |
| Final decision (`APPROVED` or `REJECTED`) |  |
| Final approver and UTC timestamp |  |

Until the final decision is explicitly `APPROVED`, no live E2E action is authorized.
