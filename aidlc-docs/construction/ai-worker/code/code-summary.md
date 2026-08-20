# Code Summary - AI Worker

## 개요

| 항목 | 값 |
|------|-----|
| Unit | ai-worker (단일 유닛) |
| 언어 | Python 3.12 |
| 패키지 관리 | uv (비패키지 애플리케이션 모드) |
| 애플리케이션 코드 위치 | Workspace root |
| Follow-up 추가 | `ai/refiner.py`, `tests/test_prompt_refiner.py`; raw/Hermes 통합을 위한 기존 코드·배포·문서 수정 |

---

## 1. 생성된 파일 목록

### 1.1 엔트리포인트 및 설정

| 파일 | 역할 |
|------|------|
| `main.py` | 프로세스 엔트리포인트, 로깅 초기화, Config 로드, Orchestrator 실행 |
| `pyproject.toml` | 의존성, ruff/mypy/pytest 설정 |
| `.python-version` | Python 3.12 고정 |

### 1.2 도메인 모델 (`models/`)

| 파일 | 주요 정의 |
|------|-----------|
| `models/enums.py` | `JobStatus`, `ErrorCode`, `JOB_PROGRESS`, `STATUS_MESSAGES`, `TERMINAL_STATUSES`, `ERROR_MESSAGES` |
| `models/entities.py` | `Config`(+Hermes path), `SQSMessage`(+`from_raw` 검증), `JobWorkDir`(+`requirements.json`, `refined-prompt.md`), `S3Paths`(+`for_job`) |
| `models/requirements.py` | Runtime ingress와 분리된 optional canonical reference schema validator |
| `models/exceptions.py` | `WorkerError` 계층 5종, `classify_error()`, `user_message_for()` |

### 1.3 설정 (`config/`)

| 파일 | 역할 |
|------|------|
| `config/settings.py` | 환경 변수 로드/검증(`load_config`, `HERMES_CLI_PATH`), boto3 재시도 설정(`build_boto_config`) |

### 1.4 AWS 클라이언트

| 파일 | 공개 메서드 |
|------|-------------|
| `sqs/client.py` | `receive_message`, `delete_message`, `extend_visibility`, `get_visibility_timeout` |
| `s3/client.py` | `download_requirements`, `download_assets`, `upload_source`, `upload_artifact` |
| `dynamo/client.py` | `get_job_status`, `update_status`, `append_log` |

### 1.5 처리 모듈

| 파일 | 역할 |
|------|------|
| `ai/refiner.py` | `PromptRefiner.refine()` - raw JSON guardrail prompt, Hermes one-shot, 3회 retry, atomic output, raw fallback |
| `ai/generator.py` | `AIGenerator.generate_code()` - refined prompt 또는 raw fallback으로 kiro-cli 호출 + 결과 검증 |
| `build/builder.py` | `ApkBuilder.build_apk()` - Gradle Wrapper 확보 → assembleDebug → APK 복사 |
| `worker/visibility_extender.py` | `VisibilityExtender` - daemon thread, 컨텍스트 매니저 지원 |
| `worker/orchestrator.py` | `WorkerOrchestrator` - 메인 루프, `process_job`, Graceful Shutdown |

### 1.6 유틸리티 (`utils/`)

| 파일 | 역할 |
|------|------|
| `utils/log_sanitizer.py` | `sanitize_log()` - AWS Key/Token/Presigned URL/자격증명 마스킹 |
| `utils/cleanup.py` | `prepare_workdir()`, `cleanup_old_workdirs()` |

### 1.7 배포 (`deploy/`)

| 파일 | 역할 |
|------|------|
| `deploy/prompton-worker.service` | systemd unit (자동 재시작, SIGTERM 300초 대기, 보안 강화) |
| `deploy/env.example` | 환경 변수 템플릿 (AWS 자격증명 미포함) |

### 1.8 테스트 (`tests/`)

| 파일 | 테스트 수 |
|------|-----------|
| `tests/conftest.py` | 공용 fixture (`config`, `job_id`) |
| `tests/test_config.py` | 11 |
| `tests/test_sqs_client.py` | 11 |
| `tests/test_s3_client.py` | 15 (moto) |
| `tests/test_dynamo_client.py` | 10 (moto) |
| `tests/test_orchestrator.py` | 25 |
| `tests/test_visibility_extender.py` | 6 |
| `tests/test_prompt_refiner.py` | 10 |
| `tests/test_ai_generator.py` | 9 |
| `tests/test_requirements_contract.py` | 11 (optional reference) |
| `tests/test_builder.py` | 7 |
| `tests/test_cleanup.py` | 17 (cleanup + log_sanitizer) |
| **합계** | **132** |

---

## 2. 비즈니스 규칙 구현 매핑

| 규칙 | 구현 위치 | 검증 테스트 |
|------|-----------|-------------|
| BR-001 중복 처리 방지 | `orchestrator._skip_if_already_done` | `test_process_job_skips_terminal_status` |
| BR-002 메시지 삭제 시점 | `orchestrator._phase_finalize` (마지막 단계) | `test_process_job_happy_path` |
| BR-003 실패 시 메시지 유지 | `orchestrator.process_job` except 블록 | `test_process_job_ai_failure` |
| BR-004 상태 전이 순서 | `_phase_analyzing` → `_generating_code` → `_building` → `_finalize` | `test_process_job_happy_path` |
| BR-005 상태 갱신 원자성 | `DynamoClient.update_status` (단일 UpdateItem) | `test_update_status_writes_atomically` |
| BR-006 artifactKey 기록 시점 | `S3Client.upload_artifact` head_object 검증 후 전달 | `test_process_job_artifact_upload_failure` |
| BR-007 progress 고정값/유지 | `JOB_PROGRESS`, 실패 시 `progress=None` | `test_failure_does_not_overwrite_progress` |
| BR-008 에러 코드 분류 | `models.exceptions.classify_error` | `test_process_job_ai_failure` (parametrize) |
| BR-009 실패 메시지 보안 | `user_message_for` (사전 정의 메시지만) | `test_failure_message_has_no_internal_detail` |
| BR-010 VT 50% 연장 | `EXTEND_INTERVAL_RATIO = 0.5` | `test_interval_is_half_of_visibility_timeout` |
| BR-011 연장 실패 무시 | `VisibilityExtender._run` except | `test_extend_failure_does_not_raise` |
| BR-012 로그 기록 시점 | 각 phase의 `append_log` 호출 | `test_process_job_writes_required_logs` |
| BR-013 로그 보안 | `sanitize_log` (update_status/append_log에서 적용) | `test_sanitize_masks_*` 7건 |
| BR-014 에셋 선택적 처리 | `download_assets` 빈 리스트 반환, 확장자/개수 제한 | `test_download_assets_*` 3건 |
| BR-015 APK 저장 위치 | `S3Paths.for_job` → `jobs/{jobId}/artifact/app-debug.apk` | `test_process_job_happy_path` |
| BR-016 소스 저장 | `upload_source` (빌드 성공 후, 실패 허용) | `test_upload_source_creates_zip` |
| BR-017 디렉토리 멱등 생성 | `prepare_workdir` (삭제 후 재생성) | `test_process_job_recreates_workdir` |
| BR-018 24시간 정리 | `cleanup_old_workdirs`, 루프 최상단 호출 | `test_run_performs_cleanup_before_receive` |
| BR-019 SQS 메시지 검증 | `SQSMessage.from_raw` | `test_receive_message_rejects_*` 4건 |
| BR-020 raw requirements.json 검증 | `S3Client.download_requirements` (64 KiB, UTF-8, JSON object) | raw/empty/invalid UTF-8/non-object/oversize S3 tests |
| BR-021 Hermes refinement/fallback | `PromptRefiner.refine`, `orchestrator._phase_generating_code`, `AIGenerator.generate_code` | `tests/test_prompt_refiner.py`, refined/raw orchestrator and generator tests |

---

## 3. NFR 설계 패턴 구현 매핑

| 패턴 | 구현 위치 |
|------|-----------|
| P1 Automatic Retry | `config.settings.build_boto_config` (adaptive, max 3) |
| P2 Visibility 연장 | `worker/visibility_extender.py` |
| P3 Idempotent Consumer | `_skip_if_already_done` + `prepare_workdir` |
| P4 External Process Policy | Hermes는 bounded retry 후 fallback; AIGenerator/ApkBuilder는 fail-fast |
| P5 DLQ | 인프라 설정 (Worker는 실패 시 메시지 유지만 담당) |
| P6 Process Supervisor | `deploy/prompton-worker.service` `Restart=on-failure` |
| P7 Graceful Shutdown | `_install_signal_handlers`, `_handle_shutdown`, `TimeoutStopSec=300` |
| P8 최소 권한 IAM | 인프라 설정 (코드에서 권한 요구사항 준수) |
| P9 Credential-Free 인증 | boto3 기본 자격증명 체인, `env.example`에 Key 미포함 |
| P10 Log Sanitization | `utils/log_sanitizer.py` |
| P11 Long Polling | `sqs.client.LONG_POLL_WAIT_SECONDS = 20` |
| P12 Workspace Isolation | `JobWorkDir.for_job` (`/data/jobs/{jobId}`), 권한 700 |
| P13 Structured Logging | `main.setup_logging` (stdout → journald) |
| P14 Periodic Cleanup | `cleanup_old_workdirs` 루프 호출 |

---

## 4. 검증 결과

| 검사 | 명령 | 결과 |
|------|------|------|
| 단위 테스트 | `pytest` | 132 passed, 98 warnings |
| 린트 | `ruff check .` | All checks passed |
| 타입 체크 (strict) | `mypy main.py config models sqs s3 dynamo ai build utils worker` | Success, no issues (25 files) |

---

## 5. 계획 대비 변경 사항

| 항목 | 계획 | 실제 | 근거 |
|------|------|------|------|
| `tests/conftest.py` | 미포함 | 추가 | 공용 fixture(`config`, `job_id`) 중복 제거 |
| `build_boto_config()` | 위치 미지정 | `config/settings.py` | 3개 클라이언트가 공유하는 설정이므로 config에 배치 |
| `models/entities.py`의 `Config` | domain-entities.md 초기 필드 | `log_level`, `hermes_cli_path`, `kiro_cli_path`, `gradle_path` 추가 | 외부 실행 파일 경로와 운영 로그 설정 주입 필요 |
| `sqs` 모듈 | `get_queue_attributes` | `get_visibility_timeout(fallback)` | BR-010의 실제 용도(VT 조회)에 맞춘 구체적 인터페이스 |
| log_sanitizer 40자 패턴 | `[A-Za-z0-9/+=]{40}` | 독립 토큰 + 대소문자 혼재 조건 추가 | 원 패턴은 git SHA 등 정상 문자열까지 마스킹하여 로그 유용성 저하. BR-013 보호 범위는 유지 |
| `upload_source` 실패 처리 | 미지정 | 예외 대신 경고 로그 후 계속 | APK가 핵심 산출물이며 소스는 디버깅 보조자료 (BR-016) |

---

## 6. 미결정 사항 및 후속 조치 필요 항목

| 항목 | 현재 구현 | 확정 시 수정 위치 |
|------|-----------|-------------------|
| kiro-cli CLI 인터페이스 | `chat --no-interactive --model claude-opus-5 --trust-tools=fs_read,fs_write <prompt>` (2.18.1 검증) | kiro-cli 버전 변경 시 `chat --help`와 모델 목록 호환성 재검증 |
| S3 Client 요청 계약 | 임의 UTF-8 JSON object, 최대 64 KiB; canonical schema는 optional reference | 실제 Backend 저장소에서 raw object upload/SQS pointer 연결 |
| Hermes | v0.20.4 `--ignore-rules --toolsets context_engine --oneshot`, host 기본 provider/model | 배포 서비스 사용자의 `HERMES_HOME` 설정·인증과 live 호출 검증 |
| Android SDK/Gradle 경로 | 환경 변수로 주입 (`env.example` 참고) | `deploy/env.example`, systemd `ReadWritePaths` |

---

## 7. 실행 방법 (로컬 검증)

```bash
# 의존성 설치
uv sync --extra dev

# 단위 테스트
uv run pytest

# 린트 + 타입 체크
uv run ruff check .
uv run mypy main.py config models sqs s3 dynamo ai build utils worker
```

배포 및 통합 테스트 절차는 Build and Test 단계에서 정의한다.
