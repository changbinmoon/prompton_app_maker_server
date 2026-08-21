# AI-DLC State Tracking

## Project Information
- **Project Type**: Brownfield (active Status API migration)
- **Original Project Type**: Greenfield
- **Start Date**: 2026-08-20T14:30:00Z
- **Current Stage**: WORKFLOW COMPLETE - Operations Placeholder Acknowledged
- **Prior Workflow Status**: COMPLETE at 2026-08-20T07:24:55Z
- **Active Change Request**: Replace Worker direct DynamoDB access with Backend Status API
- **Change Progress**: COMPLETE at 2026-08-20T13:09:41.571Z; no executable Operations stage exists

## Workspace State
- **Existing Code**: Yes (Python Worker; 132-test detection baseline, current suite 149 tests)
- **Reverse Engineering Needed**: No (current design and implementation artifacts loaded)
- **Workspace Root**: /home/ubuntu/prompton_app_maker_server

## Code Location Rules
- **Application Code**: Workspace root (NEVER in aidlc-docs/)
- **Documentation**: aidlc-docs/ only
- **Structure patterns**: See code-generation.md Critical Rules

## Extension Configuration
| Extension | Enabled | Decided At |
|-----------|---------|------------|
| Security Baseline | No | Requirements Analysis |
| Resiliency Baseline | No | Requirements Analysis |
| Property-Based Testing | No | Requirements Analysis |

## Active Status API Migration Execution Plan

- **Plan**: `aidlc-docs/inception/plans/execution-plan.md`
- **Risk Level**: High
- **Deployable Units**: 1 (`ai-worker`)
- **Stages to Execute After Approval**: Application Design, Functional Design, NFR Requirements, NFR Design, Code Generation, Build and Test
- **Stages to Skip**: Units Generation (single deployment/runtime unit), Infrastructure Design (no Worker-owned resource or IaC change)
- **Operational Checks Retained**: DynamoDB IAM removal, TCP 443 egress, TLS, env permissions, systemd validation, endpoint readiness, and joint Backend GET/Mobile E2E

## Active Change Stage Progress

### INCEPTION PHASE
- [x] Workspace Detection - COMPLETED / existing brownfield context resumed
- [x] Reverse Engineering - SKIP DECISION COMPLETE / current artifacts sufficient
- [x] Requirements Analysis - COMPLETED AND APPROVED
- [x] User Stories - COMPLETED AND APPROVED (7 stories)
- [x] Workflow Planning - COMPLETED AND APPROVED (2026-08-20T11:22:16.964Z)
- [x] Application Design - COMPLETED AND APPROVED (2026-08-20T11:35:53.834Z)
- [x] Units Generation - SKIP DECISION COMPLETE / one `ai-worker` unit

### CONSTRUCTION PHASE - ai-worker
- [x] Functional Design - COMPLETED AND APPROVED (2026-08-20T11:44:39.281Z)
- [x] NFR Requirements - COMPLETED AND APPROVED (2026-08-20T11:57:12.077Z)
- [x] NFR Design - COMPLETED AND APPROVED (2026-08-20T12:11:11.523Z)
- [x] Infrastructure Design - SKIP DECISION COMPLETE / no Worker-owned IaC
- [x] Code Generation - COMPLETED AND APPROVED (2026-08-20T12:49:40.634Z)
- [x] Build and Test - COMPLETED AND APPROVED (2026-08-20T13:08:18.475Z)

### OPERATIONS PHASE
- [x] Operations - PLACEHOLDER ACKNOWLEDGED / WORKFLOW COMPLETE (2026-08-20T13:09:41.571Z)

## Active Application Design Validation
- **Mandatory Artifacts**: 5/5 generated
- **Python Signature Blocks**: 17 parsed
- **Mermaid Diagrams**: 3/3 structurally validated with text alternatives
- **Requirement Traceability**: 25/25 Status API IDs covered
- **Lifecycle Invariants**: Verified artifact before mandatory SUCCESS; any 2xx before SQS deletion
- **Forbidden Paths**: No target Worker GET, direct DynamoDB call, or disabled TLS configuration
- **Independent Review**: APPROVED; no blocking findings

## Active Functional Design Validation
- **Mandatory Artifacts**: 3/3 generated; frontend N/A
- **Business Rules**: 28 target rules
- **Python Domain Blocks**: 12 parsed
- **Mermaid Diagrams**: 3/3 structurally validated with text alternatives
- **Requirement/Story Traceability**: 25/25 requirement IDs and 7/7 stories
- **Critical Invariants**: Exact payloads; full reprocessing; 5xx-only retry; verified artifact and SUCCESS before delete; original-error preservation
- **Delete Failure Rule**: Accepted SUCCESS remains authoritative; DeleteMessage failure logs and redelivers without contradictory FAILED
- **Forbidden Paths**: No target Worker GET, direct DynamoDB call, or persistent status-log path
- **Independent Review**: APPROVED; no blocking findings

## Active NFR Requirements Validation
- **Mandatory Artifacts**: 2/2 generated
- **NFR Set**: 49/49 unique IDs across 10 categories
- **Requirement/Story Traceability**: 25/25 requirement IDs and 7/7 stories
- **Embedded Content**: TOML and systemd INI parsed; Bash syntax passed
- **Technology Targets**: Python 3.12, requests 2.34.2, boto3 1.35.99, jsonschema 4.25.1, SQS/S3-only moto/stubs
- **Critical Controls**: Exact timeout/retry, fail-closed SUCCESS, IAM removal, TLS/TCP443, optional key, env/workdir/systemd hardening, log exclusions
- **Quality/E2E Gates**: pytest, Ruff, strict mypy, compileall, lock/frozen sync, source/deployment scans, joint Backend GET/Mobile evidence
- **Independent Review**: APPROVED; no blocking findings

## Active NFR Design Validation
- **Mandatory Artifacts**: 2/2 generated; stage plan created and all five question categories resolved
- **NFR Traceability**: 49/49 approved NFR IDs
- **Requirement/Story Traceability**: 25/25 Status API requirement IDs and 7/7 stories
- **Embedded Content**: 2/2 Mermaid diagrams structurally validated with text alternatives; 5 Python blocks parsed
- **Critical Patterns**: 5xx-only bounded retry; intermediate degradation; mandatory SUCCESS; verified artifact before SUCCESS; accepted SUCCESS before delete; no contradictory FAILED after delete failure
- **Security/Operations**: TLS defaults, optional-key confinement, DynamoDB IAM removal, TCP 443 readiness, protected environment, systemd hardening, journald allowlist, frozen dependencies
- **Validation Result**: Markdown fences, whitespace, resolved answers, exact controls, and stale positive DynamoDB/GET patterns passed
- **Independent Review**: APPROVED; no blocking or material findings

## Active Code Generation Part 1 Validation
- **Plan**: `aidlc-docs/construction/plans/ai-worker-code-generation-plan.md`
- **Execution Sequence**: 8 numbered implementation/validation steps
- **Traceability**: 25/25 Status API requirement IDs and 7/7 stories represented
- **File Impact**: Exact create/modify/delete paths; brownfield in-place edits; no duplicate modules
- **Baseline**: uv lock passed; 132 pytest passed with 98 warnings; Ruff passed; source-only strict mypy passed across 25 files; compileall passed
- **Known Gate Gap**: Repository-wide `mypy .` exposes 13 pre-existing test errors; Step 5 closes them without weakening strict mode
- **Safety Boundary**: Part 2 was approved at 2026-08-20T12:49:40.634Z; Build and Test instructions are authorized, but live AWS/API/model actions remain separately gated
- **External Boundary**: No Worker IAM/IaC file exists; live API/AWS/model/deployment actions require separate authorization
- **Plan Validation**: Markdown, embedded Python, paths, controls, step order, and approval boundary passed
- **Independent Review**: APPROVED; no blocking or material changes required

## Active Code Generation Part 2 Validation
- **Execution Plan**: All eight approved generation steps and all seven Worker story checkboxes complete
- **Implementation**: Status API PATCH client, lifecycle migration, DynamoDB adapter removal, configuration/dependency/deployment updates complete
- **Local Gates**: 149 tests passed with 70 warnings; Ruff, repository-wide strict mypy over 39 files, compileall, lock check, frozen sync, source/security/deployment scans passed
- **Traceability**: 25/25 Status API requirements, 49/49 NFRs, and 7/7 stories mapped in `code-summary.md`
- **Independent Review**: No blocking or material findings; one stale active tracking item corrected
- **External Boundary**: IAM, TCP 443, deployed env mode, queue/DLQ, and Backend GET/Mobile E2E remain Build and Test evidence
- **Approval**: Code Generation approved at 2026-08-20T12:49:40.634Z

## Active Build and Test Validation
- **Artifacts**: Eight instruction/summary files regenerated for the Status API target
- **Local Gates**: 149 tests passed with 70 warnings; Ruff, strict mypy over 39 files, compileall, lock check, and frozen sync passed
- **Content Validation**: 52 Bash blocks, nine Python heredocs, six JSON blocks, paths, links, secrets, stale guidance, 25 requirements, 49 NFRs, and seven stories passed
- **Independent Review**: No blocking or material findings; one cosmetic active state count corrected
- **External Boundary**: Live IAM, TCP443, deployed env/systemd, queue/DLQ, model, Backend GET, Mobile, and E2E evidence remain explicitly gated
- **Extensions**: Security Baseline, Resiliency Baseline, and Property-Based Testing disabled; N/A while project-specific controls remain enforced

## Active Change Current Status
- **Lifecycle Phase**: COMPLETE
- **Current Stage**: Operations placeholder acknowledged
- **Previous Step**: Build and Test approved at 2026-08-20T13:08:18.475Z
- **Current Step**: None; the current AI-DLC workflow ends after Build and Test
- **Status**: Active Status API migration workflow complete at 2026-08-20T13:09:41.571Z; deployment and live operations remain unauthorized

## Prior Baseline Stage Progress
- [x] Workspace Detection - COMPLETED (2026-08-20T14:30:00Z)
- [x] Requirements Analysis - COMPLETED (2026-08-20T14:32:00Z)
- [x] Workflow Planning - COMPLETED (2026-08-20T14:34:00Z)
- [ ] User Stories - SKIP (Worker는 사용자 직접 상호작용 없음)
- [x] Application Design - COMPLETED (2026-08-20T15:00:00Z)
- [ ] Units Generation - SKIP (단일 서비스)
- [x] Functional Design - COMPLETED (2026-08-20T15:07:00Z)
- [x] NFR Requirements - COMPLETED (2026-08-20T15:15:00Z)
- [x] NFR Design - COMPLETED (2026-08-20T15:18:00Z)
- [ ] Infrastructure Design - SKIP (기존 인프라 사용)
- [x] Code Generation - Part 1 (Planning) COMPLETED (2026-08-20T15:26:00Z)
- [x] Code Generation - Part 2 (Generation) COMPLETED (2026-08-20T15:45:00Z), APPROVED (2026-08-20T07:10:01Z)
- [x] Build and Test - COMPLETED (2026-08-20T07:21:10Z), APPROVED (2026-08-20T07:24:55Z)
- [x] Operations - PLACEHOLDER ACKNOWLEDGED (2026-08-20T07:24:55Z) - 현재 실행 단계 없음, AI-DLC 워크플로 종료

## Code Generation Results (ai-worker)
- **생성 파일**: 33개 (소스 21, 테스트 11, 배포 2, 설정 3)
- **단위 테스트**: 105 passed
- **린트 (ruff)**: All checks passed
- **타입 체크 (mypy strict)**: Success, 23 files
- **코드 요약**: aidlc-docs/construction/ai-worker/code/code-summary.md
- **계획 파일**: Historical 14-step baseline plan superseded; `aidlc-docs/construction/plans/ai-worker-code-generation-plan.md` now contains the active Status API migration plan

## Build and Test Results
- **완료 시각**: 2026-08-20T07:21:10Z
- **빌드**: uv frozen sync, lock check, Python compile 모두 성공
- **단위/로컬 컴포넌트 테스트**: 105 passed, 0 failed (82 botocore/moto deprecation warnings)
- **린트**: Ruff All checks passed
- **타입 체크**: mypy strict Success (23 source files)
- **콘텐츠 검증**: Markdown 8개, Bash block 37개, JSON block 1개 구문 검증 통과
- **수정 사항**: 미지원 `kiro-cli generate` 호출을 2.18.1 호환 `chat --no-interactive --model claude-sonnet-4.5` 호출로 수정
- **산출물**: `aidlc-docs/construction/build-and-test/` 내 필수 5개 및 추가 3개 지침 파일
- **미실행**: 실제 AWS/Claude Sonnet 4.5/Android 전체 E2E 및 성능 테스트 (격리 리소스 승인과 확정 requirements 스키마 필요)
- **요약**: `aidlc-docs/construction/build-and-test/build-and-test-summary.md`

## Workflow Completion
- **Completed At**: 2026-08-20T07:24:55Z
- **CONSTRUCTION**: Build and Test까지 완료 및 사용자 승인됨
- **OPERATIONS**: 현재 placeholder이며 배포·모니터링 실행 절차는 정의되지 않음
- **Workflow Status**: COMPLETE
- **Production Activation**: 별도 승인 필요. 확정된 `requirements.json` 계약, 실제 AWS/Claude Sonnet 4.5/Android E2E, 대상 EC2 성능 기준선, 보안 검사를 먼저 완료해야 함

## Delivery and Operational Test Preparation
- **Requested At**: 2026-08-20T07:27:18Z
- **Delivery Branch**: `feature/ai-worker-operational-readiness`
- **Runbook**: `aidlc-docs/operations/operational-test-plan.md`
- **Operational Test Status**: PARTIALLY EXECUTED - NO-GO (2026-08-21T03:15:07Z)
- **Reason**: 공식 Backend 성공 경로는 외부 Worker 기준 검증됐고 local Kiro generation도 성공했지만, 공유 Queue 처리 주체 비결정성과 invalid generated Gradle wrapper로 local full E2E가 실패함
- **Primary Blockers**: External/local duplicate consumers, generated wrapper JAR integrity gap, service-user Hermes provider/credential absence, remaining isolated DLQ/visibility/performance/security gates
- **Remote Push Status**: PUSHED (verified 2026-08-20T07:40:54Z)
- **Remote Branch**: `origin/feature/ai-worker-operational-readiness`
- **Verified Delivery Base Commit**: `6ce19f9247304094f0d1e7f4c65ec99b43196181`

## Requirements Contract Decision Status
- **Reviewed At**: 2026-08-20T08:11:17Z
- **Original Answers**: Complete (6/6)
- **Clarification Answers**: Complete (5/5)
- **Implementation Answers**: Superseded by approved raw Client JSON flow and Worker-owned guardrails
- **Schema Status**: RETAINED AS OPTIONAL REFERENCE - `contracts/requirements.schema.json`
- **Fixture Status**: RETAINED AS OPTIONAL REFERENCE - 2 valid, 7 invalid
- **Worker Validation Status**: IMPLEMENTED - 64 KiB, UTF-8 JSON, top-level raw object
- **Backend Producer Status**: PENDING IN EXTERNAL REPOSITORY - raw object S3 upload and SQS pointer only
- **Hermes Status**: IMPLEMENTED LOCALLY - v0.20.4 one-shot, 3 attempts, output validation, Kiro raw fallback
- **Contract README**: `contracts/README.md`
- **Decision Files**: `aidlc-docs/operations/requirements-contract-questions.md`, `requirements-contract-clarification-questions.md`, `requirements-contract-implementation-questions.md`

## Requirements Contract Implementation Results
- **Completed At**: 2026-08-20T08:11:17Z
- **Schema**: Draft 2020-12 v1, canonical root and strict Android/assets fields
- **Fixtures**: 2 valid, 7 invalid
- **Worker Enforcement**: 64 KiB limit, schema validation, minSdk<=targetSdk
- **Dependency**: `jsonschema==4.25.1`
- **Validation**: 118 passed, Ruff passed, mypy strict passed (24 source files)
- **Consumer Status**: SUPERSEDED AT RUNTIME - canonical validator remains optional reference only
- **Producer Status**: Raw object upload/SQS wiring pending in absent Backend repository
- **Hermes Status**: Worker implementation complete; live service-user provider/model validation pending
- **Implementation Commit**: `3b2779e6bf1c3dd7b1c66d5c7cced806218c8ff0`
- **Remote Delivery**: PUSHED and SHA verified on `origin/feature/ai-worker-operational-readiness`

## Pending Backend and Hermes Integration Follow-up
- **Requested At**: 2026-08-20T08:42:43Z
- **Backend Repository Discovery**: BLOCKED - this workspace contains Worker code only
- **Hermes Discovery**: `/home/ubuntu/.local/bin/hermes`, Hermes Agent v0.20.4
- **Verified Hermes Interface**: `--oneshot` prompt input and final text stdout
- **Decision File**: `aidlc-docs/operations/pending-integrations-questions.md`
- **Status**: WAITING FOR USER ANSWERS - Backend target, model/provider isolation, retry, and fallback
- **Hermes Policy Answers**: VALID - host default model/provider, 3 total attempts with 1s/2s backoff, raw Client JSON fallback
- **Backend Producer Answer**: CLARIFICATION REQUIRED - user requested definition instead of selecting scope
- **Clarification File**: `aidlc-docs/operations/pending-integrations-clarification-questions.md`

## Raw Client JSON to Hermes Flow Revision
- **Requested At**: 2026-08-20T08:54:22Z
- **Target Ingress**: Raw Client JSON object stored in S3 and fetched by Worker
- **Current Decision**: Worker owns deterministic Android guardrails; canonical schema is not runtime ingress
- **Implemented Runtime**: raw object validation, Hermes prompt refinement, `refined-prompt.md`, Kiro raw fallback
- **Clarification File**: `aidlc-docs/operations/raw-client-hermes-flow-clarification.md` (Answer A)
- **Status**: APPROVED AND LOCALLY IMPLEMENTED
- **Code Generation Plan**: `aidlc-docs/construction/plans/raw-client-hermes-integration-plan.md` (5 steps, 24 checkboxes)
- **Code Generation Part 1**: COMPLETE - plan validated
- **Code Generation Part 2**: WAITING FOR EXPLICIT PLAN APPROVAL
- **Plan Approval**: APPROVED at 2026-08-20T09:03:12Z (`진행`)
- **Code Generation Part 2**: IN PROGRESS - Step 1 Raw S3 ingress
- **Step 1 Raw S3 Ingress**: COMPLETE - 26 targeted tests passed, Ruff passed
- **Current Plan Step**: Step 2 Hermes prompt refiner
- **Step 2 Hermes Refiner**: COMPLETE - 9 tests passed, Ruff and strict mypy passed
- **Current Plan Step**: Step 3 Worker and Kiro integration
- **Step 3 Worker/Kiro Integration**: COMPLETE - 55 targeted tests passed, Ruff and strict mypy passed
- **Current Plan Step**: Step 4 Deployment and contract documentation
- **Step 4 Deployment/Contract Docs**: COMPLETE - 12 Markdown files and embedded Bash/JSON blocks validated
- **Current Plan Step**: Step 5 Validation and delivery
- **Step 5 Validation**: 132 passed, 98 warnings; Ruff passed; strict mypy passed (25 source files); compile and lock checks passed
- **Content/Deployment Validation**: 20 changed/new Markdown files, 10 contract JSON files, Bash/JSON fences, diff whitespace, and systemd syntax passed
- **Independent Review**: APPROVED - no blocking or material changes required
- **Current Plan Step**: Step 5 explicit commit and remote delivery
- **Raw/Hermes Implementation Commit**: `2dbeff31aa11b123d5d65d60991f9e61543f9515`
- **Remote Delivery**: PUSHED and SHA verified on `origin/feature/ai-worker-operational-readiness`
- **Code Generation Part 2**: COMPLETE - all 17 execution checkboxes complete

## 2026-08-21 Operational Recovery Verification
- **Authorization**: Kiro service-account auth, non-interactive smoke, Hermes diagnosis, Worker restart, and one official Backend Job were explicitly approved.
- **Kiro Runtime**: PASS - Kiro CLI 2.18.1 service-account auth and companion runtime restored under `HOME=/data/hermes`.
- **Kiro Model**: `claude-sonnet-4.5`; unsupported `claude-opus-5` references were corrected in source, tests, and active docs.
- **Kiro Smoke**: PASS - exit 0, exact `SERVICE_ACCOUNT_KIRO_OK` content, SHA-256 `287aae1d95c06cf3f69fafdaa7ae7cd17aa49b081e7b12db7b41db4cbd871e11`.
- **Hermes**: DEGRADED - v0.20.4 is installed, but service-user provider/model and usable credential are absent; three attempts fail and raw requirements fallback works.
- **Worker Restart**: PASS - `prompton-worker.service` PID 44641, active/running/enabled, NRestarts=0; no forced termination occurred.
- **Official Backend Job**: `58c76a31-8715-4804-8cd7-84ac25e5a409` reached SUCCESS 100 with a 10,624,278-byte debug APK, but no matching local journal entry exists, so the processing actor was the external Worker.
- **APK Verification**: PASS - SHA-256 `36bc02994ac1ed73772c3aca97f7d9852f6c71a9f38ab2099491a8e5e7f9e88b`; ZIP and apksigner checks passed; aapt2 parsed package `com.prompton.generated.app58c76a318715` and launchable `MainActivity`.
- **Local Worker Job**: `5d5efe3d-56cb-4297-a1a4-421dc3fc8c76` completed Kiro generation with 37 files and 58,992 bytes, then entered BUILDING.
- **Local Build**: FAIL - generated `gradle-wrapper.jar` is 31-byte ASCII placeholder text, causing `org.gradle.wrapper.GradleWrapperMain` ClassNotFoundException.
- **Backend Status for Local Job**: Stale terminal Job rejected intermediate PATCH with 409 and FAILED with 400; this is separate from local Kiro success and build failure.
- **Worker Recovery After Failure**: PASS - PID 44641 remained active/running with NRestarts=0 and TasksCurrent=1, indicating polling resumed.
- **Overall Operational Decision**: NO-GO - Backend artifact E2E passed only through the external Worker; local full E2E remains blocked by duplicate consumers and wrapper integrity failure.
- **Safety**: No SQS purge, manual message deletion, DynamoDB IAM change, embedded Friendli key copy, presigned URL persistence, or forced Worker/Kiro termination occurred.
- **Extensions**: Security Baseline, Resiliency Baseline, and Property-Based Testing remain disabled and are N/A; project-specific safety controls remained enforced.

## 2026-08-21 Gradle Wrapper Recovery Implementation
- **Approval**: User input `진행해줘` at 2026-08-21T03:26:48.400Z.
- **Plan**: `aidlc-docs/construction/plans/gradle-wrapper-recovery-plan.md`.
- **Builder Change**: Wrapper script, trusted official distribution properties, ZIP/JAR integrity, and `GradleWrapperMain.class` are validated before execution.
- **Recovery Change**: Missing or invalid Wrapper artifacts are generated in an isolated minimal Gradle project and copied into the Android project, then revalidated.
- **Generator Change**: Kiro is prohibited from creating `gradlew`, `gradlew.bat`, or binary `gradle-wrapper.jar`; it creates only official compatible wrapper properties.
- **Automated Validation**: 19 targeted tests passed; complete suite 152 passed with 70 warnings; Ruff lint, changed-file format, strict mypy over 39 files, compileall, lock, and diff checks passed.
- **Wrapper Smoke**: PASS - 31-byte placeholder became a 47,505-byte valid JAR with `GradleWrapperMain.class`; SHA-256 `7a9ce74cff467ca1bf60a4fcd9f05185acceda4d0f382434d393e17864262c5d`.
- **Original Job Integrity**: PASS - original 31-byte JAR and SHA-256 `4cc6031f1d351eb332f07cc6cb17ae5ae4a055ed85801ce67020a9045c9a4fb9` remained unchanged.
- **Host SDK Finding**: Android Platform 35 is absent from `/opt/android-sdk`, which is read-only to the service account; an isolated writable SDK overlay was required for the smoke.
- **Generated Source Finding**: Three Material3 progress lambda calls and one missing Pager experimental opt-in independently prevented compilation; four minimal changes were applied to the temporary copy only.
- **APK Smoke**: PASS after isolated SDK/source corrections - 7,214,177 bytes, SHA-256 `20076c994eb6c3a6862258b5e442df36ce9edc130d213c79c4ecc481d477f799`, ZIP/signature/aapt2 passed, package `com.appmaker.generated.app1945`, targetSdk 35, launchable `MainActivity`.
- **Cleanup**: Temporary project, SDK overlay, APK, and logs removed; original Job directory preserved.
- **Deployment**: PENDING - source changes are not installed under `/opt/prompton-ai-worker` and the service was not restarted.
- **Current Decision**: Wrapper defect is resolved and verified in source, but production/local no-edit E2E remains NO-GO until deployment, Platform 35 availability, generated source compatibility, and duplicate-consumer isolation are resolved.

## 2026-08-21 SDK 36 and Kiro Plan Decision
- **Approval**: User requested SDK 36 only, Compose compatibility work to proceed, deployment to be skipped, duplicate consumers to be ignored, and Kiro Opus 5 plus account plan to be checked.
- **SDK Policy**: Source guardrails now ignore Client API levels and require `minSdk=26`, `compileSdk=36`, `targetSdk=36`, and Build Tools 36.0.0.
- **Fixed Toolchain**: AGP 8.10.1, Gradle 8.11.1, JDK 17, Kotlin 1.9.24, Compose compiler 1.5.14, and Compose BOM 2024.06.00.
- **Compose Compatibility**: Source guardrails require Java/Kotlin JVM 17, `Float` progress values for Material 3 `LinearProgressIndicator`, and explicit opt-in for experimental APIs including `ExperimentalFoundationApi` pager APIs.
- **Host SDK**: Platform 36 and Build Tools 36.0.0 are installed; Platform 35 is no longer required by the new source policy.
- **Kiro Identity Type**: BuilderId; raw account identifiers were not recorded.
- **Kiro Plan**: `KIRO FREE`, 4.81 of 50 covered credits used (9%), reset 2026-09-01.
- **Kiro Model Catalog**: Nine models available; no Opus model and no exact `claude-opus-5`.
- **Model Decision**: Keep supported `claude-sonnet-4.5`; setting Opus 5 would intentionally restore a known runtime failure.
- **Targeted Validation**: Refiner, generator, and builder suite passed 29 tests; changed-file Ruff format/lint and strict mypy passed.
- **Deployment**: SKIPPED per user decision; `/opt/prompton-ai-worker` and systemd remain unchanged.
- **Duplicate Consumer**: ACCEPTED RISK per user decision; no Queue or external Worker change.
- **Current Status**: Source policy updated, but a new SDK36 no-edit local E2E remains pending and production activation remains NO-GO.

## 2026-08-21 Kiro Organization Profile Transition
- **Approval**: The user selected option B in `aidlc-docs/operations/kiro-organization-profile-transition-questions.md`, explicitly authorizing a local organization OAuth credential DB transfer between the ubuntu and `prompton` operating-system accounts.
- **Worker Coordination**: PASS - Worker idle and zero Kiro child processes were confirmed before a graceful stop; it restarted only after all authentication gates passed.
- **Rollback and Source Backups**: PASS - the original Builder ID rollback backup remains preserved, and a second root-only backup contains a consistent ubuntu source snapshot plus the pre-copy service DB and CLI settings; all backup files are mode `0600`.
- **Installed Credential DB**: PASS - SQLite online backup and atomic replacement completed; installed integrity is `ok`, owner is `prompton:prompton`, and mode is `0600`.
- **Kiro Identity Type**: `IamIdentityCenter`; provider and account identifiers were not recorded.
- **Profile Access**: PASS - the TTY-only profile fetch and current-profile confirmation exited successfully without unavailable, terminal, or other errors.
- **Kiro Plan**: `KIRO PRO+`, 1603.14 of 2000 covered credits used (80%), reset 2026-09-01.
- **Kiro Model Catalog**: 19 models available, including exact `claude-opus-5` and `claude-sonnet-4.5`; the active selected model is now Opus 5.
- **Organization Smoke**: PASS - exact `claude-opus-5` non-interactive generation exited 0, created exactly one expected file with exact content, and removed the temporary directory.
- **Worker Restore**: PASS - PID 49141, active/running, NRestarts=0, TasksCurrent=1, no startup error marker, and no idle Kiro child process.
- **Opus 5 Activation**: COMPLETE - source and focused test target exact `claude-opus-5`; the active deployed generator received a two-line model-only hotfix after a root-only backup. Deployed syntax/AST and isolated service-account smoke passed, and Worker PID 49405 is active/running with NRestarts=0, TasksCurrent=1, and zero startup error markers. All other uncommitted source changes remain undeployed.
- **Safety**: No authentication URL, device code, token, email, account ID, provider identifier, presigned URL, Queue/IAM/DynamoDB mutation, external Worker change, source deployment, commit, or push occurred.

## 2026-08-21 Current Source Worker Deployment
- **Approval**: User input `Worker 배포` explicitly superseded the prior full-source deployment skip for the current dev Worker.
- **Fixed Scope**: Source and active release inventories each contained 27 files; only `ai/generator.py`, `ai/refiner.py`, and `build/builder.py` differed. `pyproject.toml`, `uv.lock`, and the systemd unit already matched.
- **Predeploy Gate**: PASS - frozen lock/sync, full pytest 152 passed with 70 known warnings, Ruff lint/format, strict mypy over 39 files, compileall, diff, and Status API/no-DynamoDB boundary checks passed.
- **Host Gate**: PASS - protected env owner/mode and required/forbidden key checks, writable data paths, Android Platform 36, Build Tools 36.0.0, Worker `JAVA_HOME` JDK 17, disk, and idle state passed.
- **Rollback Backup**: `/var/backups/prompton-worker/current-source-deploy-20260821T043218Z`; three prior active files and the checksum/mode manifest are root-owned mode `0600` under a root-only directory.
- **Install**: PASS - the Worker was gracefully stopped and the three source files were installed with per-file fsync and atomic replacement while preserving active owner/mode. Installed hashes match source and the complete 27-file source/active inventory has zero differences.
- **Deployed Validation**: PASS - deployed compile, exact `claude-opus-5`, fixed SDK36/Compose guardrails, Wrapper recovery symbols, pinned dependency versions, Status API/no-DynamoDB boundary, and systemd verification passed.
- **Authentication**: PASS - pre/post-start service account type is `IamIdentityCenter`, and exact Opus 5 remains in the organization catalog.
- **Worker Restore**: PASS - PID 49807, active/running, Result=success, NRestarts=0, TasksCurrent=1, startup error markers=0, and idle Kiro child count=0.
- **Operational Boundary**: No Job was submitted. Queue, IAM, DynamoDB, external Worker, environment, systemd unit, virtual environment, organization authentication, commit, and push were not changed.
- **Current Deployment Status**: SDK36/Compose generation guardrails, trusted Gradle Wrapper recovery, and Opus 5 are active in the local systemd Worker. A post-deployment no-edit Job/APK E2E remains pending.

## 2026-08-21 Active SQS Polling Diagnosis
- **Report**: User observed a queued message and suspected that the local Worker was not polling it.
- **Finding**: NOT A POLLING FAILURE - the local Worker received one message at 04:42:40 UTC and began processing it immediately.
- **Current Phase**: Exact Opus 5 code generation started at 04:42:53 UTC and remains active with two Kiro descendants; code generation has not yet completed or entered BUILDING.
- **Sequential Contract**: `MAX_MESSAGES_PER_RECEIVE=1`, and `WorkerOrchestrator.run()` calls `process_job()` synchronously. It cannot poll the next visible message until the current Job returns.
- **Queue Evidence**: Read-only attributes first reported visible 0/in-flight 3 and later visible 2/in-flight 1; these values are approximate and may include new or external-consumer activity.
- **Errors**: No `sqs_receive_failed` event occurred. Intermediate Status API updates returned HTTP 409 but are explicitly handled with `action=continue` and did not stop processing.
- **Decision**: No restart or configuration change. Interrupting the active Job would increase visibility/redelivery risk. No manual receive, delete, visibility change, or purge was performed.
- **Current Risk**: Additional visible messages wait while this intentionally single-threaded Worker completes the current Job; the previously accepted external-consumer risk remains.

## 2026-08-21 Hermes Refinement Failure Diagnosis
- **Runtime**: PASS - Hermes Agent v0.20.4 exists, is executable, and runs under `HOME=/data/hermes`.
- **Invocation**: PASS - the Worker uses restricted one-shot mode with `--ignore-rules --toolsets context_engine --oneshot`; input preparation and output paths are valid.
- **Observed Failure**: Three attempts per Job returned exit code 1 with 1-second and 2-second retry delays; the Worker then used raw requirements fallback as designed.
- **Root Cause**: Hermes has no configured inference backend. Resolved status reports Model `(not set)` and Provider `Auto`; all inference authentication and API-key providers are not logged in or not configured.
- **Credential Evidence**: The service environment has no Anthropic/OpenAI/Friendli/static AWS credential keys. Hermes `.env` has no active provider/model/API-key/endpoint assignment, `active_provider` is null, and the Hermes inference auth file is absent.
- **Non-Causes**: The executable, HOME, `context_engine` toolset, requirements input, output write path, Kiro organization authentication, and SQLite WAL warning are not the cause.
- **Logging Behavior**: `PromptRefiner` intentionally rejects nonzero exit and logs only `exitCode=1`; it does not log untrusted stdout/stderr, so the journal does not contain the provider error text.
- **Current Behavior**: DEGRADED but safe - refinement is skipped after three failures and exact Opus 5 generation continues from raw requirements.

## 2026-08-21 Service Hermes Inference Configuration
- **Approval**: User requested that the `prompton` Hermes configuration use the ubuntu user's working inference setup, explicitly authorizing local credential transfer.
- **Source Discovery**: Ubuntu Hermes had a configured custom provider/model. The required inference API credential is stored as a literal secret in the active provider entry of `config.yaml`.
- **Minimization**: Only the `model` section and one active provider definition were extracted. Ubuntu `.env` had no inference-relevant setting, and ubuntu `auth.json` contained an unrelated credential pool; neither was copied.
- **Isolated Validation**: A temporary `prompton` HOME resolved the extracted model and custom provider successfully before service mutation.
- **Rollback Backup**: `/var/backups/prompton-worker/hermes-ubuntu-config-20260821T050303Z`; incoming minimal config and manifest are root-owned mode `0600`. The service config target previously did not exist.
- **Installed Config**: `/data/hermes/.hermes/config.yaml`, owner `prompton:prompton`, mode `0600`; parent directory mode `0700`. Installed hash matches the root-only incoming snapshot.
- **Status Validation**: Service `hermes status --all` exits 0 with a configured model and custom provider.
- **Inference Smoke**: Restricted one-shot exited 0 and returned exact `HERMES_SERVICE_OK` output. No project or user data was sent.
- **Worker Integration Smoke**: Deployed `PromptRefiner` produced a nonempty, valid output within 64 KiB from synthetic requirements and cleaned its temporary directory.
- **Worker Coordination**: The active Job had already passed the Hermes phase and no Hermes child existed, so atomic config installation required no Worker stop/restart. Worker remained active with PID 49807 and NRestarts=0.
- **Current Behavior**: Future Jobs can use Hermes refinement before exact Opus 5 generation. Existing Jobs that already fell back are unchanged.
- **Safety**: No ubuntu Kiro credential, unrelated Hermes auth pool, full `.env`, account identifier, provider URL, token value, Queue/IAM/DynamoDB/external Worker state, commit, or push was copied or recorded.

## 2026-08-21 SQS 500ms Polling Change
- **Approval**: User requested a quick 500ms polling interval.
- **API Constraint**: SQS `WaitTimeSeconds` accepts integer seconds, so exact 500ms behavior uses `WaitTimeSeconds=0` and a 0.5-second orchestrator delay after empty responses.
- **Shutdown Behavior**: The delay is skipped when shutdown is already requested.
- **Unchanged Contracts**: Maximum one message, sequential Job processing, visibility extension, success/delete gates, Queue configuration, and external consumers are unchanged.
- **Cost Risk**: Idle receive requests can rise from about 4,320/day to about 172,800/day, approximately 40x, with increased SQS cost/API load and short-poll false-empty behavior.
- **Deployment Status**: ACTIVE - the current Job was allowed to return after a graceful shutdown request, then the Worker exited without forced termination. `sqs/client.py` and `worker/orchestrator.py` were atomically deployed.
- **Rollback Backup**: `/var/backups/prompton-worker/sqs-500ms-polling-20260821T053253Z`; prior files and checksum/mode manifest are root-owned mode `0600`.
- **Deployed Verification**: Source/active release inventory has 27 files with zero differences. Deployed compile and execution recorder confirm `WaitTimeSeconds=0`, `MaxNumberOfMessages=1`, and exact 0.5-second empty delay.
- **Worker Restore**: PID 53329, active/running, NRestarts=0, TasksCurrent=1, startup/observation error markers=0, and organization authentication remains `IamIdentityCenter`.
- **Idle Observation**: No local message receive occurred during the observation window. Queue visible depth was 0; one approximate in-flight message may belong to another consumer.
- **Accepted Cost Risk**: The approximately 40x idle receive request increase and observed short-poll CPU/API overhead are explicitly accepted by this quick change.

## 2026-08-21 Post-Configuration Hermes Refinement Diagnosis
- **Prior Failure**: RESOLVED - the earlier missing provider/model/credential diagnosis was corrected by the minimal ubuntu-to-service Hermes configuration transfer and successful restricted smokes.
- **Latest Observation**: A post-configuration Job started Hermes once and received exit code 1 on all three configured attempts before raw fallback; Opus 5 generation then started as designed.
- **Backend State**: PASS - service Hermes resolves one configured custom provider/model with credential and endpoint present, and status exits 0.
- **Controlled Reproduction**: PASS - the same service HOME, provider/model, flags, current Job working directory, and a synthetic 3,327-byte prompt returned exact expected output without stderr.
- **Input Validation**: PASS - actual requirements are valid UTF-8 top-level JSON; the 3,327-byte refinement prompt is far below ARG_MAX and has no control/surrogate or common prompt-override, tool, jailbreak, or credential markers.
- **Persisted Evidence**: The state DB contains only three successful synthetic user/assistant pairs. Failed actual attempts produced no session or error metadata; the unrelated SQLite WAL-reset warning is not causal.
- **Final Classification**: The failure is request-specific within Hermes/provider/agent handling or transient during those calls, not a global configuration, executable, HOME, CWD, size, toolset, or provider-reachability failure.
- **Diagnostic Limit**: The exact historical provider error is unrecoverable because `PromptRefiner` intentionally discards stdout/stderr for nonzero exits. Replaying real Client data externally requires explicit authorization and was not performed.
- **Runtime Impact**: Safe degradation only - raw requirements fallback to exact `claude-opus-5` is working; no Worker restart is required.
- **Safety**: No Queue, IAM, DynamoDB, external Worker, service, configuration, message, or credential mutation occurred during this diagnosis.

## 2026-08-21 Actual-Request Hermes Replay
- **Authorization**: The user explicitly authorized retransmitting the actual received Client requirements to Hermes for refinement.
- **Isolation**: The only post-configuration Job was terminal. Its 1,796-byte requirements were copied into a service-owned mode `0700` directory; the running Worker and Job lifecycle were not touched.
- **Exact Input Construction**: Deployed `build_refinement_prompt`, the real Job ID, service HOME/provider/model, and exact `--ignore-rules --toolsets context_engine --oneshot` flags produced the same 3,327-byte prompt shape.
- **Result**: PASS on attempt 1 - exit 0, 1,255 stdout bytes, zero stderr; no retry was required.
- **Output Validation**: PASS - 1,254 trimmed bytes, nonempty, no NUL, below 64 KiB, no Markdown fence or Client wrapper echo, no credential-like value, all 16 Android guardrail checks satisfied, and the valid original package candidate was preserved.
- **Hermes State**: The latest persisted assistant message has `finish_reason=stop` and content length consistent with the UTF-8 output.
- **Artifact**: Preserved atomically as `refined-prompt-replay.md` in the terminal Job directory, service-account owned and mode `0600`; byte hash matches the validated output. Canonical `refined-prompt.md` remains absent to avoid implying that the historical Job used this replay.
- **Cleanup**: The isolated requirements/output working directory was removed after preservation.
- **Revised Diagnosis**: The exact actual prompt now succeeds, excluding deterministic input-content rejection. The original three failures were transient/intermittent within Hermes/provider invocation; their lower-level message remains unrecoverable because historical stderr was discarded.
- **Worker Safety**: PID 53329 remains active/running with `NRestarts=0`, `TasksCurrent=1`, and no Kiro or Hermes child. No Queue, IAM, DynamoDB, external Worker, message, or service mutation occurred.

## 2026-08-21 Worker-Only Hermes Rejection Root Cause
- **Observed Pattern**: Two post-configuration Worker Jobs each exhausted three Hermes attempts with exit 1 and used raw Opus 5 fallback, while direct service-account replay succeeded.
- **Root Cause**: The systemd Worker inherits both `HOME=/data/hermes` and `HERMES_HOME=/data/hermes`. Hermes treats `HERMES_HOME` as the exact config/state directory, not the operating-system HOME.
- **Path Resolution**: With `HERMES_HOME` unset, Hermes resolves `/data/hermes/.hermes`; under the Worker value it resolves `/data/hermes`; with `HERMES_HOME=/data/hermes/.hermes` it resolves the installed config directory correctly.
- **Configuration Location**: The validated custom provider/model config is `/data/hermes/.hermes/config.yaml`; the Worker therefore bypasses it when using the current environment value.
- **Variable-Only Reproduction**: Manual-style environment returned exact synthetic output with exit 0. Worker-style `HERMES_HOME=/data/hermes` reported Provider Auto and returned exit 1 with a 190-byte stderr classified as provider-not-configured/auth-missing. Corrected `HERMES_HOME=/data/hermes/.hermes` returned exact output with exit 0 and no stderr.
- **Non-Causes**: Network isolation, seccomp, executable/config/Job CWD permissions, prompt size/content, provider availability, and Kiro authentication are excluded. `PrivateNetwork=no`, network namespace matches the host, `Seccomp=0`, and required paths are accessible inside the Worker mount namespace.
- **Prior Replay Clarification**: The actual-request replay succeeded because it set `HOME=/data/hermes` without inheriting the Worker's incorrect `HERMES_HOME`; it did not reproduce the Worker environment. The prior transient-failure classification is superseded.
- **Source Finding**: `deploy/env.example` contains the same incorrect `HERMES_HOME=/data/hermes` value and must be corrected with the active protected environment to prevent recurrence.
- **Required Remediation**: Set `HERMES_HOME=/data/hermes/.hermes` (or remove it and rely on `HOME=/data/hermes`), then gracefully restart only after the active Job drains and run a Worker-path smoke/new Job verification.
- **Current Safety**: The latest Job is already in Kiro fallback generation. No Worker restart, environment mutation, Queue/IAM/DynamoDB/external Worker change, or active-Job interruption occurred during diagnosis.
