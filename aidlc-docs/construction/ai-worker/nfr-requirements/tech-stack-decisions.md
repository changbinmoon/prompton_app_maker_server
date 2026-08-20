# Tech Stack Decisions - AI Worker

## 핵심 기술 스택

| 카테고리 | 선택 | 버전 | 근거 |
|----------|------|------|------|
| 언어 | Python | 3.12 | 최신 안정 버전, 성능 개선, boto3 호환 |
| 패키지 관리 | uv | latest | 속도 빠름, pyproject.toml 표준 지원, 현대적 도구 |
| AWS SDK | boto3 | latest | AWS 서비스 연동 표준 SDK |
| 프로세스 관리 | systemd | - | 리눅스 표준, 자동 재시작, 로그 통합 |
| AI 코드 생성 | kiro-cli + Opus5 | - | EC2에서 직접 실행 |
| APK 빌드 | Android SDK + Gradle | - | EC2 사전 설치, Gradle Wrapper |

---

## 런타임 환경

| 항목 | 설정 |
|------|------|
| OS | Amazon Linux 2023 (또는 Ubuntu 22.04) |
| 인스턴스 | t3.xlarge (4 vCPU, 16GB RAM) |
| 스토리지 | EBS gp3 (OS) + 전용 볼륨 /data (작업 디렉토리) |
| 인증 | IAM Instance Profile |
| Region | us-east-1 |

---

## Python 의존성

### 핵심 의존성

| 패키지 | 용도 |
|--------|------|
| boto3 | AWS SQS, S3, DynamoDB 연동 |
| botocore | boto3 의존성 (자동 설치) |

### 유틸리티 의존성

| 패키지 | 용도 |
|--------|------|
| python-dotenv | 로컬 개발 환경 .env 파일 로드 (선택적) |

### 개발 의존성

| 패키지 | 용도 |
|--------|------|
| pytest | 단위 테스트 |
| moto | AWS 서비스 모킹 (테스트용) |
| ruff | 린팅 + 포맷팅 |
| mypy | 타입 체크 |

---

## 프로젝트 설정 (pyproject.toml)

```toml
[project]
name = "prompton-ai-worker"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "boto3",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "moto[sqs,s3,dynamodb]",
    "ruff",
    "mypy",
    "boto3-stubs[sqs,s3,dynamodb]",
]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## systemd 서비스 설정

```ini
[Unit]
Description=Prompton AI Worker
After=network.target

[Service]
Type=simple
User=prompton
Group=prompton
WorkingDirectory=/opt/prompton-ai-worker
ExecStart=/opt/prompton-ai-worker/.venv/bin/python -m main
Restart=on-failure
RestartSec=5
EnvironmentFile=/etc/prompton-worker/env

# Graceful Shutdown
KillSignal=SIGTERM
TimeoutStopSec=300

# Security
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/data/jobs

[Install]
WantedBy=multi-user.target
```

---

## 환경 변수

| 변수 | 값 (dev) | 설명 |
|------|----------|------|
| AWS_REGION | us-east-1 | AWS Region |
| SQS_QUEUE_URL | https://sqs.us-east-1.amazonaws.com/440052841756/prompton-app-build-jobs-dev | SQS Queue URL |
| DYNAMODB_TABLE_NAME | prompton-jobs-dev | DynamoDB 테이블 |
| S3_BUCKET_NAME | prompton-app-builder-dev-changbin | S3 버킷 |
| WORK_DIR | /data/jobs | 작업 디렉토리 |
| LOG_LEVEL | INFO | 로그 레벨 |
| CLEANUP_HOURS | 24 | 작업 디렉토리 보존 시간 |

---

## 기술 결정 근거

### Python 3.12
- 성능 개선 (faster CPython 프로젝트 포함)
- 타입 힌트 개선 (TypedDict, dataclass 향상)
- boto3 완벽 호환
- 충분히 안정적인 릴리스 (2023년 10월 출시, 2년 이상 운영 실적)

### uv (패키지 관리)
- pip 대비 10~100배 빠른 의존성 해석 및 설치
- pyproject.toml 표준 지원
- venv 자동 관리
- lock 파일 지원 (재현 가능한 빌드)
- Rust로 작성되어 안정적

### t3.xlarge 선택 근거
- **16GB RAM**: Gradle 빌드 + AI 처리 동시 메모리 사용 고려
- **4 vCPU**: Gradle 병렬 빌드, kiro-cli 처리에 충분
- **네트워크**: Moderate (S3 대용량 전송에 적합)
- **Burstable**: 간헐적 작업에 적합 (대기 시간 동안 크레딧 축적)

### systemd 선택 근거
- 리눅스 표준 프로세스 관리자 (추가 설치 불필요)
- 자동 재시작 (Restart=on-failure)
- 로그 통합 (journalctl로 확인)
- 보안 강화 옵션 (NoNewPrivileges, ProtectSystem)
- SIGTERM 기반 Graceful Shutdown 지원
