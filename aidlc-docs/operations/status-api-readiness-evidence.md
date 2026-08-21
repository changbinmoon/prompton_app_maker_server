# Status API Migration - Read-Only Readiness Evidence

## 1. Evidence Metadata

| Item | Value |
|---|---|
| Collected at | 2026-08-20T13:22:54.386Z |
| AWS profile | Current default profile |
| AWS region | `us-east-1` |
| Resource source | Non-secret dev identifiers from `deploy/env.example` |
| Host scope | Current machine, read-only inspection |
| Network scope | DNS, TCP 443, and default-certificate TLS handshake only |
| HTTP request/PATCH | None |
| Mutation/model/deployment | None |

No API key, AWS secret, session token, environment-file content, raw Job data, signed URL, or Backend response body was collected.

## 2. Overall Readiness

**Status: NOT READY for a live Job or deployment.**

The public Status API TLS path and main queue attributes are reachable, but target-host deployment artifacts are absent and IAM/S3/DLQ policy evidence is incomplete or denied. This report is evidence only and does not authorize remediation or deployment.

## 3. AWS Principal Evidence

| Check | Result | Evidence |
|---|---|---|
| Caller identity | PASS | Default profile resolves to an assumed `prompton-ai-worker-role` session. |
| Account alignment | REVIEW | Caller account differs from the configured cross-account queue owner. Cross-account policies are therefore material. |
| IAM role metadata | BLOCKED | `iam:GetRole` denied. |
| Managed policy inventory | BLOCKED | `iam:ListAttachedRolePolicies` denied. |
| Inline policy inventory | BLOCKED | `iam:ListRolePolicies` denied. |

Required follow-up: an authorized IAM/infrastructure owner must supply read-only effective policy evidence showing approved SQS/S3 actions, no Worker DynamoDB actions, no administrator wildcard, and correct cross-account resource policies.

## 4. SQS and DLQ Evidence

Configured main queue: `prompton-app-build-jobs-dev`.

| Check | Result | Evidence |
|---|---|---|
| Main queue GetQueueAttributes | PASS | Cross-account read succeeded. |
| VisibilityTimeout | PASS | `300` seconds. |
| RedrivePolicy | PASS | DLQ target is configured with `maxReceiveCount=3`. |
| Approximate visible messages | OBSERVED | `0` at collection time. |
| Approximate in-flight messages | OBSERVED | `0` at collection time. |
| Main queue Policy/RedriveAllowPolicy | BLOCKED | Policy attributes are owner-only for this caller. |
| DLQ URL resolution | BLOCKED | Queue is absent to this caller or caller lacks access. |
| Direct DLQ GetQueueAttributes | BLOCKED | Cross-account resource policy does not allow this role. |

Queue-depth values are point-in-time observations, not proof that the queue remains empty. Required follow-up: the queue owner must provide sanitized main/DLQ resource policy, DLQ retention/depth, and redrive-allow evidence or grant a reviewed read-only path.

## 5. S3 Evidence

Configured bucket: `prompton-app-builder-dev-changbin`.

| Check | Result | Evidence |
|---|---|---|
| HeadBucket | FAIL | HTTP 403 Forbidden. |
| ListBucket authorization with `jobs/` prefix and zero returned keys | FAIL | AccessDenied. No object key was returned. |
| GetObject/PutObject/artifact metadata | NOT TESTED | No approved Job ID/object key and mutations are prohibited. |

The failures may reflect identity policy, bucket policy, account ownership, or an intentionally narrower object-only grant; this session did not infer or change the cause. Required follow-up: the infrastructure/S3 owner must verify effective cross-account permissions for the exact requirements/assets/source/artifact prefixes before E2E approval.

## 6. Current-Host Deployment Evidence

| Check | Result | Evidence |
|---|---|---|
| `prompton` service user | ABSENT | No local passwd entry. |
| `/etc/prompton-worker/env` | ABSENT | No deployed environment file to inspect. |
| `prompton-worker.service` installed unit | ABSENT | systemd reports `LoadState=not-found`, `ActiveState=inactive`. |
| Installed restart/timeout/hardening | NOT TESTABLE | No installed unit. Values returned by systemd are manager defaults, not Worker evidence. |
| `/data/jobs` | ABSENT | Path not present. |
| `/data/hermes` | ABSENT | Path not present. |
| `/data/gradle` | ABSENT | Path not present. |

The current machine is a development host, not a deployed Worker host. Repository templates and host-compatible unit syntax passed local validation, but installed env ownership/mode, service identity, direct production `ExecStart`, sandbox, writable paths, and service status remain target-host checks.

## 7. DNS, TCP 443, and TLS Evidence

Configured hostname: `xb2z5ls8k0.execute-api.us-east-1.amazonaws.com`.

| Check | Result | Evidence |
|---|---|---|
| DNS resolution | PASS | Resolved to two public IPv4 addresses at collection time. |
| TCP 443 | PASS | Connection established within the 3-second probe timeout. |
| Default certificate verification | PASS | Python default trust store and hostname verification succeeded. |
| TLS protocol | PASS | TLS 1.3. |
| Cipher | OBSERVED | `TLS_AES_128_GCM_SHA256`. |
| Certificate expiry | OBSERVED | 2026-11-05 23:59:59 GMT. |
| Certificate SHA-256 | OBSERVED | `c620774acb1db3a7da2802b64325e5e536f1b4b01e0a52cd794110072d4dd3e0`. |
| HTTP request/API key | NOT SENT | The probe ended after the TLS handshake. |

DNS addresses and certificates can rotate; repeat the handshake in the approved E2E window and treat the current fingerprint as time-bound evidence, not a pin.

## 8. Release-Readiness Findings

### Blocking before an approved dev E2E

1. Supply effective Worker IAM evidence; current role cannot inspect its policies.
2. Resolve or explain S3 403/AccessDenied for the configured dev bucket and exact Job prefixes.
3. Supply DLQ attributes/resource-policy evidence from the queue owner.
4. Identify the actual deployed dev Worker host; the current machine has no installed service/env/data paths.
5. On that host, verify env mode/ownership/static-key absence, direct systemd unit syntax/security, writable paths, and service identity.

### Passed evidence to retain

1. Default-profile assumed Worker role identity established.
2. Main queue VisibilityTimeout is 300 seconds.
3. Main queue RedrivePolicy targets a DLQ with `maxReceiveCount=3`.
4. Main queue depth was zero visible and zero in-flight at collection time.
5. DNS, TCP 443, TLS 1.3, certificate chain, and hostname verification succeeded without an HTTP request.

## 9. Safety Record

This collection performed read-only identity, queue, bucket-authorization, host metadata, and TLS-handshake checks. It did not:

- Send Status API HTTP traffic or an API key.
- Enqueue, receive, delete, or change visibility for a message.
- Read or write an S3 object.
- Modify IAM, queue, bucket, network, systemd, or environment configuration.
- Start/restart a service.
- Invoke Hermes, Kiro, Gradle, or an Android build.
