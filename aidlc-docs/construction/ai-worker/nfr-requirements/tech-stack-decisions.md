# Tech Stack Decisions - ai-worker Status API Migration

## 1. Decision Summary

| Category | Target decision | Version or constraint | Evidence/rationale |
|---|---|---|---|
| Runtime language | Python | 3.12 (`.python-version`), project `>=3.12` | Existing strict-typed Worker runtime |
| Dependency manager | uv | Lockfile + frozen sync; CLI version recorded in evidence | Existing non-package application workflow |
| HTTP client | requests | `2.34.2` exact direct runtime pin | Approved Status API contract; installed distribution provides inline typing |
| AWS SDK | boto3 | `1.35.99` exact | Retained for SQS and S3 only |
| JSON library | stdlib `json` | Python 3.12 | Status payload and raw ingress serialization |
| Schema reference | jsonschema | `4.25.1` exact, retained pending separate cleanup | Existing optional contract/reference tooling |
| Process manager | systemd | Host-provided | Restart, shutdown, hardening, journald integration |
| HTTP transport security | requests default TLS verification | Certificate checks enabled | NFR-SA-002 |
| AI refinement | Hermes CLI | Existing host v0.20.4 baseline; capture live version | Existing one-shot/fallback flow |
| AI generation | Kiro CLI | 2.18.1 verified host baseline; capture live model | Existing Android generator flow |
| APK build | Gradle Wrapper + Android SDK + Java | Project/host controlled; capture versions | Existing build flow |
| Compute baseline | EC2 t3.xlarge | 4 vCPU, 16 GiB planning baseline | Existing approved capacity, not an SLO |
| Deployment unit | One Linux systemd service | Sequential one-Job process | No architecture migration |

The target remains a non-package Python application started with `python -m main`. No web framework, async framework, database client, or new service is introduced.

## 2. Target Python Dependency Manifest

```toml
[project]
requires-python = ">=3.12"
dependencies = [
    "boto3==1.35.99",
    "jsonschema==4.25.1",
    "requests==2.34.2",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.4",
    "moto[sqs,s3]==5.0.28",
    "ruff==0.9.4",
    "mypy==1.14.1",
    "boto3-stubs[sqs,s3]==1.35.99",
]

[tool.uv]
package = false
```

### Dependency Decisions

| Package | Decision | Reason |
|---|---|---|
| `requests==2.34.2` | Add as direct runtime dependency | PATCH, timeout tuple, Session injection, TLS defaults; already resolved in lock but must become direct |
| `boto3==1.35.99` | Retain | SQS and S3 data plane |
| `jsonschema==4.25.1` | Retain in this migration | Not part of Status API change; removal needs separate source/contract decision |
| `moto[sqs,s3,dynamodb]` | Change to `moto[sqs,s3]` after target scan | Dynamo tests/package are removed |
| `boto3-stubs[sqs,s3,dynamodb]` | Change to `boto3-stubs[sqs,s3]` | Strict typing remains for retained AWS services |
| `pytest==8.3.4` | Retain exact | Existing test runner |
| `ruff==0.9.4` | Retain exact | Existing lint gate |
| `mypy==1.14.1` | Retain exact strict checker | Existing static gate |
| `botocore` | Transitive through boto3 | No duplicate direct declaration |
| `types-requests` | Not required for requests 2.34.2 | Project frozen environment confirms the pinned distribution contains `py.typed` |

All target dependencies use exact pins. “latest” is not an acceptable manifest value.

## 3. HTTP Client Decision

### Selected Pattern

- One in-process `StatusApiClient` using an injectable `requests.Session`.
- Injectable sleep callable for deterministic retry tests.
- Synchronous PATCH because the Worker processes one Job sequentially.
- Endpoint: normalized base URL plus `/v1/jobs/{jobId}/status`.
- Timeout: `(3, 10)` for connect/read inactivity.
- Any 2xx succeeds without response parsing.
- Only 5xx retries; three total attempts and delays `[1, 2]`.
- Default TLS certificate verification remains enabled.

### Rejected Alternatives

| Alternative | Reason rejected |
|---|---|
| boto3 DynamoDB client/resource | Violates target boundary and IAM objective |
| Worker-side Backend GET | Violates approved full-redelivery policy |
| async HTTP client | Adds concurrency/runtime complexity without throughput benefit |
| urllib low-level client | More manual error/timeout/test handling than approved requests client |
| Generic retry library | Policy is small, explicit, fixed, and testable without another dependency |
| Circuit breaker | Resiliency extension disabled; mandatory SUCCESS must fail closed rather than hide outage |

## 4. AWS and IAM Decision

### Retained AWS Components

- SQS client: receive, delete, visibility change, queue attributes.
- S3 client: download requirements/assets, list constrained asset prefix, upload source/artifact, HeadObject verification.
- EC2 Instance Profile: supplies AWS SDK credentials.

### Removed AWS Components

- DynamoDB boto3 resource/Table construction.
- DynamoDB GetItem and UpdateItem actions.
- DynamoDB table environment variable and startup log.
- DynamoDB moto/stub feature extras.

The Status API is ordinary HTTPS and currently needs no new AWS IAM API action. Network egress to its API Gateway hostname on TCP 443 is an operational prerequisite.

## 5. Configuration Decision

| Variable | Required | Secret | Target handling |
|---|:---:|:---:|---|
| `SQS_QUEUE_URL` | Yes | No | Existing SQS client value |
| `S3_BUCKET_NAME` | Yes | No | Existing S3 client value |
| `PROMPTON_API_BASE_URL` | Yes | No | Strip trailing slash for endpoint joining; safe to identify environment |
| `PROMPTON_STATUS_API_KEY` | No | Yes | Normalize empty to absent; send only as `x-api-key`; never log |
| `AWS_REGION` | No | No | Existing default `us-east-1` |
| `WORK_DIR` | No | No | Existing default `/data/jobs` |
| `VISIBILITY_TIMEOUT` | No | No | Existing positive integer fallback |
| `CLEANUP_HOURS` | No | No | Existing default 24 |
| `LOG_LEVEL` | No | No | Existing validated logging level |
| Tool/home variables | No | Some host-sensitive | Existing Hermes/Kiro/Gradle/Android paths |
| `DYNAMODB_TABLE_NAME` | Removed | N/A | Must not be loaded, documented as required, or logged |

The deployment example uses the approved dev base URL but contains no real API key. `/etc/prompton-worker/env` remains mode 0640 or stricter.

## 6. systemd Decision

The existing service model is retained. Required target service properties include:

```ini
[Service]
EnvironmentFile=/etc/prompton-worker/env
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=300
StandardOutput=journal
StandardError=journal
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/data/jobs /data/hermes
```

Operational constraints:
- Add every actually used writable Gradle/Android cache path to `ReadWritePaths`; do not broaden write access globally.
- `After=network-online.target` and `Wants=network-online.target` remain because Status API, SQS, and S3 require network readiness.
- The service user remains `prompton`.
- The 300-second stop limit is an operational ceiling; interrupted Jobs recover through SQS redelivery.

## 7. Logging and Observability Technology

| Concern | Decision |
|---|---|
| Application logging | Python standard `logging` |
| Process output | stdout/stderr |
| Collection | systemd journal (`SyslogIdentifier=prompton-worker`) |
| User-visible persistence | Backend stores latest status/message; Worker has no log API |
| Correlation | Validated Job ID, status, attempt, result class, safe errorCode |
| Secret filtering | Existing sanitizer plus structured safe arguments; caplog sentinel tests |
| Response bodies | Never included in logs |
| Metrics/dashboard | No new resource in this repository |

JSON logging is not required; stable human-readable key/value fields are sufficient for current journald acceptance.

## 8. Development and Test Stack

| Tool | Exact target | Required use |
|---|---|---|
| pytest | 8.3.4 | Full suite and deterministic fakes |
| moto | 5.0.28 with SQS/S3 extras only | Retained AWS component tests |
| Ruff | 0.9.4 | Lint/import/modernization gate |
| mypy | 1.14.1 strict | All source modules including Status client |
| boto3-stubs | 1.35.99 with SQS/S3 extras only | Retained AWS typing |
| Python compileall | Python 3.12 stdlib | Import/syntax gate |
| systemd-analyze | Host-provided | Service-unit verification |
| fake HTTP session | Test utility in repository | Response/exception sequence and request recording |
| sleep recorder | Test utility in repository | Exact 1-second/2-second backoff assertions |

Property-based testing is not added because that extension is disabled. Deterministic table-driven tests cover the complete HTTP/lifecycle matrix.

## 9. Quality Gate Commands

```bash
uv lock --check
uv sync --frozen --extra dev
uv run pytest
uv run ruff check .
uv run mypy .
uv run python -m compileall -q .
systemd-analyze verify deploy/prompton-worker.service
```

Additional release checks:
- Source/import scan for DynamoDB client/resource and Worker GET status paths.
- Config/env scan for removed table variable and optional API key safety.
- caplog secret/body exclusion tests.
- Lock graph scan for unused DynamoDB moto/stub features.
- Contract/E2E evidence readiness checklist.

## 10. External Toolchain Decisions

| Tool | Existing decision | Required evidence |
|---|---|---|
| Hermes | Host-configured provider/model, one-shot interface, v0.20.4 baseline | Version, sanitized attempt/fallback logs |
| Kiro CLI | 2.18.1 verified baseline with existing non-interactive command/model | CLI version/model identifier, successful generated project markers |
| Java | Existing Java 17 deployment setting | `java -version` in build evidence |
| Android SDK | Existing API/toolchain installation | Installed SDK/build-tools versions |
| Gradle | Project wrapper, host Gradle only for wrapper creation | Wrapper and Gradle versions |
| EC2 | t3.xlarge planning baseline | Instance type, CPU/memory/disk observations |

No external tool is upgraded by this migration unless Code Generation validation proves compatibility requires a separately documented change.

## 11. Migration Delta

| Current baseline | Target |
|---|---|
| `DynamoClient` and table access | `StatusApiClient` PATCH-only adapter |
| boto3 SQS/S3/DynamoDB use | boto3 SQS/S3 only plus requests HTTPS |
| `DYNAMODB_TABLE_NAME` | `PROMPTON_API_BASE_URL` plus optional key |
| DynamoDB moto/stubs | SQS/S3 moto/stubs only |
| DynamoDB user logs | Python logging to journald |
| Terminal status precheck | Full processing for every delivery |
| DynamoDB SUCCESS then delete | Verified artifact, Status API SUCCESS 2xx, then delete |
| Unpinned “latest” documentation | Exact manifest versions or explicit host-provided boundary |

## 12. Traceability

| Decision | Source |
|---|---|
| requests 2.34.2, Session, timeout/retry | FR-SA-003, FR-SA-009, FR-SA-010, FR-SA-011, TR-SA-001 |
| Optional key and TLS | FR-SA-002, NFR-SA-002, NFR-SA-003, US-SA-06 |
| boto3 SQS/S3 retention and DynamoDB removal | FR-SA-015, FR-SA-017, FR-SA-018, NFR-SA-001, US-SA-01 |
| Python 3.12, uv, strict tools | Existing approved baseline and TR-SA-003 |
| systemd/journald | FR-SA-016, existing approved operation, US-SA-06 |
| Deterministic fake session/sleep | TR-SA-001, TR-SA-002, US-SA-05 |
| External E2E/tool evidence | TR-SA-004, US-SA-07 |

## 13. Deferred Implementation

NFR Design will specify concrete retry, safe logging, degradation, configuration, and verification patterns. Code Generation will edit manifests/lock/source/tests/deployment files. This artifact selects the target stack but does not modify runtime code or installed infrastructure.
