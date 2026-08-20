# Code Generation Plan - AI Worker

## Unit Context
- **Unit**: ai-worker (단일 유닛)
- **언어**: Python 3.12
- **패키지 관리**: uv + pyproject.toml
- **배포**: EC2 + systemd
- **Workspace Root**: d:\Practice\prompthon\prompton_app_maker_server

## Code Location
- **Application Code**: Workspace root (d:\Practice\prompthon\prompton_app_maker_server)
- **Documentation**: aidlc-docs/construction/ai-worker/code/

## Project Structure (Target)
```
prompton_app_maker_server/
├── main.py                       # 엔트리포인트
├── pyproject.toml                # 프로젝트 설정 및 의존성
├── .python-version               # Python 버전 지정
├── config/
│   ├── __init__.py
│   └── settings.py              # 환경 변수 로드, Config dataclass
├── worker/
│   ├── __init__.py
│   ├── orchestrator.py          # 메인 루프, Job 처리 시퀀스
│   └── visibility_extender.py   # Visibility Timeout 연장 스레드
├── sqs/
│   ├── __init__.py
│   └── client.py               # SQS 수신/삭제/Visibility 연장
├── s3/
│   ├── __init__.py
│   └── client.py               # S3 다운로드/업로드
├── dynamo/
│   ├── __init__.py
│   └── client.py               # DynamoDB 상태/로그 관리
├── ai/
│   ├── __init__.py
│   └── generator.py            # kiro-cli subprocess 호출
├── build/
│   ├── __init__.py
│   └── builder.py              # Gradle Wrapper + APK 빌드
├── models/
│   ├── __init__.py
│   ├── enums.py                # JobStatus, ErrorCode 열거형
│   ├── entities.py             # SQSMessage, JobWorkDir, S3Paths
│   └── exceptions.py           # 커스텀 예외 계층
├── utils/
│   ├── __init__.py
│   ├── log_sanitizer.py        # 로그 민감정보 필터링
│   └── cleanup.py              # 작업 디렉토리 정리
├── deploy/
│   ├── prompton-worker.service  # systemd 서비스 파일
│   └── env.example              # 환경 변수 예시
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_sqs_client.py
    ├── test_s3_client.py
    ├── test_dynamo_client.py
    ├── test_orchestrator.py
    ├── test_visibility_extender.py
    ├── test_ai_generator.py
    ├── test_builder.py
    └── test_cleanup.py
```

---

## Generation Steps

### Step 1: Project Structure Setup
- [x] pyproject.toml 생성 (프로젝트 메타데이터, 의존성, 도구 설정)
- [x] .python-version 생성
- [x] main.py 생성 (엔트리포인트)

### Step 2: Models Layer
- [x] models/__init__.py
- [x] models/enums.py (JobStatus, ErrorCode, JOB_PROGRESS, STATUS_MESSAGES)
- [x] models/entities.py (Config, SQSMessage, JobWorkDir, S3Paths)
- [x] models/exceptions.py (WorkerError 및 하위 예외)

### Step 3: Config Module
- [x] config/__init__.py
- [x] config/settings.py (환경 변수 로드, 검증, Config dataclass 반환)

### Step 4: SQS Client Module
- [x] sqs/__init__.py
- [x] sqs/client.py (receive_message, delete_message, extend_visibility, get_queue_attributes)

### Step 5: S3 Client Module
- [x] s3/__init__.py
- [x] s3/client.py (download_requirements, download_assets, upload_source, upload_artifact)

### Step 6: DynamoDB Client Module
- [x] dynamo/__init__.py
- [x] dynamo/client.py (get_job_status, update_status, append_log)

### Step 7: AI Generator Module
- [x] ai/__init__.py
- [x] ai/generator.py (generate_code - kiro-cli subprocess 호출)

### Step 8: Build Module
- [x] build/__init__.py
- [x] build/builder.py (build_apk - Gradle Wrapper 생성 + assembleDebug)

### Step 9: Utilities
- [x] utils/__init__.py
- [x] utils/log_sanitizer.py (sanitize_log - 민감정보 필터링)
- [x] utils/cleanup.py (cleanup_old_workdirs - 24시간 초과 디렉토리 삭제)

### Step 10: Visibility Extender
- [x] worker/visibility_extender.py (VisibilityExtender 클래스 - daemon thread)

### Step 11: Worker Orchestrator
- [x] worker/__init__.py
- [x] worker/orchestrator.py (WorkerOrchestrator - 메인 루프, process_job, Graceful Shutdown)

### Step 12: Deployment Artifacts
- [x] deploy/prompton-worker.service (systemd 서비스 파일)
- [x] deploy/env.example (환경 변수 예시)

### Step 13: Unit Tests
- [x] tests/__init__.py
- [x] tests/conftest.py (공용 fixture - 계획 외 추가)
- [x] tests/test_config.py
- [x] tests/test_sqs_client.py
- [x] tests/test_s3_client.py
- [x] tests/test_dynamo_client.py
- [x] tests/test_orchestrator.py
- [x] tests/test_visibility_extender.py
- [x] tests/test_ai_generator.py
- [x] tests/test_builder.py
- [x] tests/test_cleanup.py (cleanup + log_sanitizer 커버)

### Step 14: Documentation
- [x] aidlc-docs/construction/ai-worker/code/code-summary.md (생성된 코드 요약)

---

## Completion Criteria
- [x] 모든 모듈 생성 완료 (14/14 steps)
- [x] 단위 테스트 코드 작성 완료 (105 tests passed)
- [x] systemd 배포 설정 완료
- [x] 코드가 타입 안전하고 비즈니스 규칙을 반영 (mypy strict 통과, ruff 통과, BR-001~BR-020 전건 매핑)

## Verification Results
| 검사 | 명령 | 결과 |
|------|------|------|
| 단위 테스트 | `pytest` | 105 passed |
| 린트 | `ruff check .` | All checks passed |
| 타입 체크 (strict) | `mypy main.py config models sqs s3 dynamo ai build utils worker` | Success (23 files) |
