# Code Summary - ai-worker Status API Migration

## 1. Summary

The `ai-worker` now reports Job lifecycle changes through the outbound Backend Status API instead of reading or writing Worker-owned DynamoDB state. It remains a single sequential Python 3.12 process and preserves existing SQS, S3, Hermes, Kiro, Gradle, visibility-extension, workspace, and cleanup behavior.

This document supersedes the historical DynamoDB implementation clauses previously recorded here. Build and Test instruction files are intentionally not rewritten during Code Generation; the mandatory Build and Test stage will regenerate them after explicit Code Generation approval.

| Item | Result |
|---|---|
| Unit | `ai-worker` |
| Project type | Brownfield Python Worker |
| Application code | `/home/ubuntu/prompton_app_maker_server` |
| Documentation | `aidlc-docs/construction/ai-worker/code/` |
| Status transport | `PATCH /v1/jobs/{jobId}/status` |
| Worker status reads | None; no Backend GET or DynamoDB GetItem path |
| Full local suite | 149 passed, 70 botocore deprecation warnings |
| Static gates | Ruff, repository-wide strict mypy (39 files), compileall passed |
| Dependency gates | Lock check and frozen dev sync passed |
| Live external actions | Not executed; deferred to Build and Test and an approved test window |

## 2. File Delta

### 2.1 Created

| Path | Purpose |
|---|---|
| `status_api/__init__.py` | Exports the outbound Status API adapter. |
| `status_api/client.py` | Implements PATCH URL/header/payload construction, timeout, 5xx-only retry, typed sanitized failure, and allowlisted logging. |
| `tests/test_status_api_client.py` | Provides 19 deterministic fake-session/sleep tests for the HTTP and security contract. |
| `tests/test_main.py` | Verifies safe startup logging, configuration failure, API-key exclusion, and removal of table output. |

### 2.2 Modified in Place

| Path | Change |
|---|---|
| `pyproject.toml` | Added direct `requests==2.34.2`; reduced moto and boto3-stubs extras to SQS/S3. |
| `uv.lock` | Regenerated the exact dependency graph; removed DynamoDB-only stub resolution. |
| `models/entities.py` | Replaced the table field with normalized API base URL and an optional `repr=False` API key. |
| `models/enums.py` | Corrected the GENERATING_CODE message and removed the terminal-status skip constant. |
| `models/exceptions.py` | Added typed, sanitized Status API failures and removed obsolete persistence wording. |
| `models/__init__.py` | Exported the Status API failure types. |
| `config/settings.py` | Requires a nonblank API base URL, strips trailing slashes, normalizes a blank key to `None`, and removes the table variable. |
| `worker/orchestrator.py` | Replaced persistence/status reads with lifecycle PATCH commands, criticality handling, and the SUCCESS/delete barrier. |
| `main.py` | Logs only the non-secret API base at startup; no table or key output. |
| `s3/client.py` | Updated stale persistence wording; data-plane behavior is unchanged. |
| `sqs/client.py` | Updated stale design references; behavior is unchanged. |
| `worker/visibility_extender.py` | Updated stale references; cadence/error handling are unchanged. |
| `utils/cleanup.py` | Replaced terminal-skip wording with full-redelivery semantics; behavior is unchanged. |
| `tests/conftest.py` | Migrated the shared Config fixture to API base/key fields. |
| `tests/test_config.py` | Covers URL handling/normalization, optional-key protection, defaults, and table removal. |
| `tests/test_orchestrator.py` | Replaced DynamoDB tests with 24 lifecycle, ordering, degradation, redelivery, failure, logging, and shutdown tests. |
| `tests/test_requirements_contract.py` | Added one narrow typing suppression for untyped `jsonschema`; behavior is unchanged. |
| `tests/test_s3_client.py` | Added strict moto fixture typing and formatting; behavior is unchanged. |
| `deploy/env.example` | Added required `PROMPTON_API_BASE_URL`, empty optional `PROMPTON_STATUS_API_KEY`, and removed `DYNAMODB_TABLE_NAME`; retained 0640/secret guidance. |
| `deploy/prompton-worker.service` | Preserved supervision/hardening and added `/data/gradle` to `ReadWritePaths`. |

### 2.3 Deleted

| Path | Reason |
|---|---|
| `dynamo/client.py` | Direct Worker DynamoDB state/log persistence is prohibited. |
| `dynamo/__init__.py` | The obsolete adapter package has no remaining responsibility. |
| `tests/test_dynamo_client.py` | Replaced by outbound Status API contract tests. |

No `*_new.py`, `*_modified.py`, `*_copy.py`, alternate status package, or DynamoDB fallback was created. Application code remains in the workspace root; this documentation directory contains Markdown only.

## 3. Implemented Contracts

### 3.1 Status API Client

`StatusApiClient.update_job_status()`:

- Composes `{normalizedBase}/v1/jobs/{jobId}/status`, issues PATCH only, and exposes no GET method.
- Always sends `Content-Type: application/json`; sends `x-api-key` only for a configured nonblank key.
- Uses exact JSON field names and omits every `None`: `status`, `progress`, `message`, `artifactKey`, `errorCode`.
- Passes `timeout=(3, 10)` on every attempt and uses requests' default TLS certificate verification.
- Treats every 2xx as success without parsing or reading the response body.
- Retries HTTP 5xx only, up to three total attempts, with delays `[1.0, 2.0]`.
- Does not retry 4xx, connection errors, connect/read timeouts, or other non-2xx/non-5xx results.
- Raises typed, sanitized `StatusApiFailure` data after final failure.
- Logs allowlisted metadata only; it excludes headers, keys, payloads, raw external exceptions, and response bodies.

### 3.2 Orchestrator Lifecycle

Every valid SQS delivery recreates the workspace and reprocesses the Job. There is no status GET or terminal-state skip.

1. Start visibility extension.
2. Best-effort PATCH `ANALYZING`, progress 25, `요구조건을 분석하고 있습니다.`.
3. Re-download inputs and run retained analysis/refinement behavior.
4. Best-effort PATCH `GENERATING_CODE`, progress 50, `Android 코드를 생성하고 있습니다.`.
5. Run retained Hermes fallback and Kiro generation behavior.
6. Best-effort PATCH `BUILDING`, progress 75, `APK를 빌드하고 있습니다.`.
7. Build the APK and retain source upload behavior.
8. Upload the artifact and complete S3 HeadObject/size verification.
9. Mandatorily PATCH `SUCCESS`, progress 100, `앱 생성이 완료되었습니다.`, and `jobs/{jobId}/artifact/app-debug.apk`.
10. Delete the SQS message only after SUCCESS returns 2xx.
11. Stop visibility extension on every exit path.

Intermediate reporting failures are warnings and do not stop processing. A processing failure sends best-effort `FAILED` with a safe message/error code, omitting progress and artifact; reporting failure cannot replace the original classification. Final SUCCESS reporting failure becomes `INTERNAL_ERROR`, triggers best-effort FAILED, and preserves the SQS message. DeleteMessage failure after accepted SUCCESS logs a sanitized warning, sends no contradictory FAILED, and leaves the message for redelivery.

### 3.3 Configuration, Dependencies, and Deployment

- Required: `SQS_QUEUE_URL`, `S3_BUCKET_NAME`, `PROMPTON_API_BASE_URL`.
- Optional secret: `PROMPTON_STATUS_API_KEY`; blank values become `None`, and the key is excluded from Config repr.
- Removed: `DYNAMODB_TABLE_NAME`.
- Direct runtime dependency: `requests==2.34.2`.
- Retained exact dependencies include `boto3==1.35.99` and `jsonschema==4.25.1`.
- Dev extras: `moto[sqs,s3]==5.0.28`, `boto3-stubs[sqs,s3]==1.35.99`; no DynamoDB-only stub remains resolved.
- systemd retains `Restart=on-failure`, `RestartSec=5`, `TimeoutStopSec=300`, dedicated identity, journald output, and hardening. Writable paths include `/data/jobs` and `/data/gradle` plus retained tool paths.
- Production `ExecStart` remains `/opt/prompton-ai-worker/.venv/bin/python -m main`; it was not changed for the development host.
- No Worker IAM/IaC policy file exists in this repository; deployed DynamoDB permission removal is external readiness evidence.

## 4. Validation Evidence

| Gate | Evidence |
|---|---|
| Configuration/model target | 18 tests passed; Ruff, strict mypy, compileall, lock/manifest assertions passed. |
| Status API client target | 19 tests passed; Ruff, strict mypy, compileall passed. |
| Orchestrator/components | 82 tests passed; Ruff, strict mypy, compileall passed. |
| Runtime/deployment target | 69 tests passed; Ruff, strict source mypy over 25 files, compileall/deployment assertions passed. |
| Full regression | 149 tests passed with 70 botocore deprecation warnings. |
| Repository lint | `uv run ruff check .` passed. |
| Repository typing | `uv run mypy .` passed for 39 files without weakening strictness. |
| Compilation | `uv run python -m compileall -q .` passed. |
| Lock/install | `uv lock --check` and `uv sync --frozen --extra dev` passed. |
| Source/security scan | 25 runtime files scanned; zero prohibited DynamoDB, status GET, terminal precheck, append-log, TLS-disable, response-body logging, credential-shaped production literal, or duplicate fallback paths. |
| Diff hygiene | `git diff --check -- . ':(exclude)aidlc-docs/audit.md'` passed. The append-only audit is excluded because raw history and Markdown hard breaks remain exact. |
| systemd | Direct local verify is blocked only because the deployed `/opt` executable is absent. A temporary host-compatible substitution passed syntax verification; exact production values were separately asserted. |

No test called the live Status API, enqueued a Job, consumed Hermes/Kiro capacity, deployed code, or changed AWS/IAM/network resources.

## 5. Requirement Traceability - 25 IDs

| ID | Implementation/evidence |
|---|---|
| `FR-SA-001` | Config URL normalization and PATCH-only path construction; URL/header tests. |
| `FR-SA-002` | Conditional encapsulated `x-api-key`; header and secret-exclusion tests. |
| `FR-SA-003` | Dedicated injectable `StatusApiClient.update_job_status()`; client/orchestrator tests. |
| `FR-SA-004` | Exact ANALYZING command; payload/sequence tests. |
| `FR-SA-005` | Exact GENERATING_CODE command/message; payload/sequence tests. |
| `FR-SA-006` | Exact BUILDING command; payload/sequence tests. |
| `FR-SA-007` | Artifact verification → SUCCESS 2xx → DeleteMessage; strict order/failure tests. |
| `FR-SA-008` | Safe FAILED payload, six classifications, omission/original-error/SUCCESS-failure tests. |
| `FR-SA-009` | Any-2xx body-independent success and immediate nonretry outcomes; response matrix. |
| `FR-SA-010` | 5xx-only three attempts and `[1.0, 2.0]`; fake session/sleep tests. |
| `FR-SA-011` | Exact `(3, 10)` per attempt; recorded-call tests. |
| `FR-SA-012` | Best-effort intermediate/FAILED versus mandatory SUCCESS; failure matrix. |
| `FR-SA-013` | No GET, DynamoDB read, or terminal skip; source scan/no-GET tests. |
| `FR-SA-014` | Redelivery recreates workspace and runs full pipeline; repeated-delivery tests. Backend idempotency is external. |
| `FR-SA-015` | Deleted append-log/Dynamo adapter; zero-path scan. |
| `FR-SA-016` | Allowlisted journald events; correlation/sensitive-data caplog tests. |
| `FR-SA-017` | Required API URL, optional protected key, removed table variable; config/main/env tests/scans. |
| `FR-SA-018` | Exact requests pin, frozen lock, SQS/S3-only extras, no DynamoDB stub; manifest/lock gates. |
| `NFR-SA-001` | Runtime needs no DynamoDB actions; deployed IAM inspection is external Build and Test evidence. |
| `NFR-SA-002` | TLS default/zero disable path local; deployed TCP 443 reachability is external evidence. |
| `NFR-SA-003` | Empty key template, protected repr/logging, 0640 guidance; deployed file inspection is external. |
| `TR-SA-001` | 19 deterministic Status client contract/security tests passed. |
| `TR-SA-002` | 24 target orchestrator tests plus retained component regression passed. |
| `TR-SA-003` | 149 tests, Ruff, strict mypy, compileall, lock/frozen sync, deployment validation passed. |
| `TR-SA-004` | Worker mock/contract readiness complete; approved dev Job, Backend GET, S3/SQS, and Mobile evidence remain external. |

## 6. NFR Traceability - 49 IDs by Category

| Category and IDs | Implementation/test or external boundary |
|---|---|
| Performance: `NFR-PERF-001`, `NFR-PERF-002`, `NFR-PERF-003`, `NFR-PERF-004`, `NFR-PERF-005`, `NFR-PERF-006` | No subprocess timeout/concurrency added; retained one-message long polling; exact HTTP timeout/retry/body behavior tested. |
| Reliability local: `NFR-REL-001`, `NFR-REL-002`, `NFR-REL-003`, `NFR-REL-004`, `NFR-REL-005`, `NFR-REL-006`, `NFR-REL-007` | Full redelivery, degradation, completion barrier, error preservation, post-SUCCESS delete, visibility, shutdown/service recovery implemented/tested. |
| Reliability external: `NFR-REL-008`, `NFR-REL-009` | Queue/DLQ attributes and Backend repeated-status/SUCCESS idempotency require approved deployment/contract evidence. |
| Availability: `NFR-AVAIL-001` | Preserved one process, systemd restart, SQS redelivery/DLQ; no unapproved HA/RTO/RPO target. |
| Security local: `NFR-SEC-001`, `NFR-SEC-002`, `NFR-SEC-004`, `NFR-SEC-006`, `NFR-SEC-007`, `NFR-SEC-008` | No DynamoDB path; TLS default; protected key; workspace/writable paths; sentinel log exclusion; systemd hardening. |
| Security external: `NFR-SEC-003`, `NFR-SEC-005` | TCP 443 and deployed env owner/group/mode/static-credential inspection require target-host evidence. |
| Observability: `NFR-OBS-001`, `NFR-OBS-002`, `NFR-OBS-003`, `NFR-OBS-004`, `NFR-OBS-005`, `NFR-OBS-006` | Correlated allowlisted events/levels; no DB/backend log persistence or response body; metrics/alarms out of scope. |
| Operations local: `NFR-OPS-001`, `NFR-OPS-002`, `NFR-OPS-003`, `NFR-OPS-006`, `NFR-OPS-007` | Fail-fast config, service values, reproducible dependencies, forward-fix and live-test authorization boundaries checked. |
| Operations external: `NFR-OPS-004`, `NFR-OPS-005` | Cleanup/writable paths local; target disk, endpoint, TCP 443, auth readiness require target-host evidence. |
| Scalability local: `NFR-SCALE-001`, `NFR-SCALE-003` | One Job/process retained; no autoscaling/concurrency. Backend idempotency precedes horizontal rollout. |
| Scalability external: `NFR-SCALE-002` | Instance, memory, disk, duration observations belong in approved dev E2E evidence. |
| Maintainability local: `NFR-MAINT-001`, `NFR-MAINT-002`, `NFR-MAINT-003`, `NFR-MAINT-004` | Deterministic fakes/order tests, all local gates/scans, env/service assertions, compatible unit verification passed. |
| Maintainability staged: `NFR-MAINT-005` | Active artifacts use Status API authority; historical Build and Test instructions are superseded and regenerate next stage. |
| Usability: `NFR-USE-001` | Exact Korean messages/progress/safe errors tested; interactive accessibility is N/A for a headless Worker. |
| E2E external: `NFR-E2E-001`, `NFR-E2E-002` | Defined evidence requires approved dev Job and Backend/Mobile participants; no live action occurred. |
| E2E ownership: `NFR-E2E-003` | Worker Status/orchestrator automation complete; Backend GET/Mobile display remain external. |

## 7. Story Traceability - 7 Stories

| Story | Completed Worker implementation and automated evidence | External boundary |
|---|---|---|
| `US-SA-01` | API config/client boundary, DynamoDB code/config removal, exact lock/frozen sync, startup/deployment/source scans. | Deployed IAM policy inspection. |
| `US-SA-02` | Exact intermediate commands/payloads/sequence, any-2xx, and degradation tests. | Backend/Mobile E2E observation. |
| `US-SA-03` | S3 verification before SUCCESS, SUCCESS before delete, and failure/order tests. | Live S3, Backend GET, SQS evidence. |
| `US-SA-04` | Safe classifications, omission, error preservation, no-delete, INTERNAL_ERROR tests. | Optional live failure display. |
| `US-SA-05` | Timeout, 2xx, 5xx retry/backoff, 4xx/network/timeout tests. | Live endpoint joint acceptance. |
| `US-SA-06` | Conditional key, TLS, protected config/logs, events, removed DB logs, env/service scans. | TCP 443 and deployed env permissions. |
| `US-SA-07` | Full automated gates, mock contracts, service/env checks, external evidence checklist ready. | Approved dev Job, evidence bundle, Backend GET, Mobile, queue/DLQ, target host. |

All seven story checkboxes may be completed for assigned Worker implementation and automated evidence. Per the approved plan, deferred live Backend/Mobile acceptance remains mandatory Build and Test evidence and does not reopen Worker Code Generation.

## 8. Accepted External Boundaries

Not executed during Code Generation:

1. Inspect/change deployed Worker IAM to prove DynamoDB actions absent.
2. Verify outbound TCP 443 from target EC2.
3. Inspect deployed env ownership/mode (0640 or stricter).
4. Record queue/DLQ attributes, including planned `maxReceiveCount=3`.
5. Run an approved dev Job through live Status API/S3/SQS.
6. Confirm states/artifact through Backend GET and Mobile App.
7. Collect target capacity, APK hash, commit SHA, and sanitized live evidence.

These require explicit authorization and belong to Build and Test/an approved test window. No commit, push, deployment, AWS/IAM/network mutation, live API call, queue action, or model consumption occurred.

## 9. Local Reproduction

```bash
uv lock --check
uv sync --frozen --extra dev
uv run pytest -q
uv run ruff check .
uv run mypy .
uv run python -m compileall -q .
git diff --check -- . ':(exclude)aidlc-docs/audit.md'
```

The Security Baseline, Resiliency Baseline, and Property-Based Testing extensions remain disabled as approved. Project-specific security, reliability, and deterministic test requirements above were enforced.
