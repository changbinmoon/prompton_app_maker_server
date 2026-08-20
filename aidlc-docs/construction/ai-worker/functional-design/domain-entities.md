# Domain Entities - AI Worker

## 1. Core Entities

### SQSMessage
Worker가 SQS Queue에서 수신하는 메시지 구조

```python
@dataclass
class SQSMessage:
    job_id: str                    # UUID - Job 고유 식별자
    requirements_bucket: str       # S3 bucket 이름
    requirements_key: str          # S3 object key (requirements.json)
    assets_prefix: str             # S3 prefix (assets 경로)
    receipt_handle: str            # SQS 메시지 핸들 (삭제/연장 시 필요)
    schema_version: str            # 메시지 스키마 버전 ("1.0")
```

### JobStatus (Enum)
Job의 상태를 나타내는 열거형

```python
class JobStatus(str, Enum):
    UPLOAD_PENDING = "UPLOAD_PENDING"
    QUEUED = "QUEUED"
    ANALYZING = "ANALYZING"
    GENERATING_CODE = "GENERATING_CODE"
    BUILDING = "BUILDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
```

### ErrorCode (Enum)
실패 원인을 분류하는 열거형

```python
class ErrorCode(str, Enum):
    REQUIREMENTS_READ_FAILED = "REQUIREMENTS_READ_FAILED"
    INVALID_REQUIREMENTS = "INVALID_REQUIREMENTS"
    AI_GENERATION_FAILED = "AI_GENERATION_FAILED"
    BUILD_FAILED = "BUILD_FAILED"
    ARTIFACT_UPLOAD_FAILED = "ARTIFACT_UPLOAD_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
```

### JobProgress
상태별 고정 진행률 매핑

```python
JOB_PROGRESS: dict[JobStatus, int] = {
    JobStatus.UPLOAD_PENDING: 3,
    JobStatus.QUEUED: 10,
    JobStatus.ANALYZING: 25,
    JobStatus.GENERATING_CODE: 50,
    JobStatus.BUILDING: 75,
    JobStatus.SUCCESS: 100,
}
```

### StatusMessage
상태별 사용자 표시 메시지

```python
STATUS_MESSAGES: dict[JobStatus, str] = {
    JobStatus.ANALYZING: "요구조건을 분석하고 있습니다.",
    JobStatus.GENERATING_CODE: "앱 코드를 생성하고 있습니다.",
    JobStatus.BUILDING: "APK를 빌드하고 있습니다.",
    JobStatus.SUCCESS: "앱 생성이 완료되었습니다.",
}
```

---

## 2. Configuration Entities

### Config
환경 변수 기반 설정 객체

```python
@dataclass
class Config:
    aws_region: str                # AWS Region (us-east-1)
    sqs_queue_url: str             # SQS Queue URL
    dynamodb_table_name: str       # DynamoDB 테이블명
    s3_bucket_name: str            # S3 버킷명
    work_dir: str                  # 작업 디렉토리 기본 경로 (/data/jobs)
    visibility_timeout: int        # Queue Visibility Timeout (초)
    cleanup_hours: int             # 작업 디렉토리 보존 시간 (24)
```

---

## 3. Value Objects

### JobWorkDir
Job별 작업 디렉토리 경로 구조

```python
@dataclass
class JobWorkDir:
    base_path: str                 # /data/jobs/{jobId}
    requirements_path: str         # /data/jobs/{jobId}/requirements.json
    assets_dir: str                # /data/jobs/{jobId}/assets/
    project_dir: str               # /data/jobs/{jobId}/project/
    output_dir: str                # /data/jobs/{jobId}/output/
    apk_path: str                  # /data/jobs/{jobId}/output/app-debug.apk
```

### S3Paths
Job별 S3 경로 구조

```python
@dataclass
class S3Paths:
    requirements_key: str          # jobs/{jobId}/requirements/requirements.json
    assets_prefix: str             # jobs/{jobId}/assets/
    source_key: str                # jobs/{jobId}/source/project.zip
    artifact_key: str              # jobs/{jobId}/artifact/app-debug.apk
```

---

## 4. DynamoDB Record Structure

### Job Record (읽기/쓰기)

| 필드 | 타입 | Worker 읽기 | Worker 쓰기 | 설명 |
|------|------|:-----------:|:-----------:|------|
| jobId | String (PK) | O | X | Job 고유 ID |
| status | String | O | O | 현재 상태 |
| progress | Number | X | O | 진행률 (0-100) |
| message | String | X | O | 사용자 표시 메시지 |
| errorCode | String | X | O | 에러 코드 (실패 시) |
| artifactKey | String | X | O | APK S3 경로 (성공 시) |
| logs | List[String] | X | O | 처리 로그 배열 |

---

## 5. Exception Hierarchy

```python
class WorkerError(Exception):
    """Worker 기본 예외"""
    error_code: ErrorCode

class RequirementsReadError(WorkerError):
    """S3에서 requirements.json 읽기 실패"""
    error_code = ErrorCode.REQUIREMENTS_READ_FAILED

class InvalidRequirementsError(WorkerError):
    """requirements.json 형식 오류"""
    error_code = ErrorCode.INVALID_REQUIREMENTS

class AIGenerationError(WorkerError):
    """kiro-cli 코드 생성 실패"""
    error_code = ErrorCode.AI_GENERATION_FAILED

class BuildError(WorkerError):
    """Gradle APK 빌드 실패"""
    error_code = ErrorCode.BUILD_FAILED

class ArtifactUploadError(WorkerError):
    """APK S3 업로드 실패"""
    error_code = ErrorCode.ARTIFACT_UPLOAD_FAILED
```

---

## 6. Entity Relationships

```
Config ─────────────────────────────────┐
                                        │ (참조)
SQSMessage ──► Worker Orchestrator ◄────┘
                     │
                     ├── JobWorkDir (생성/관리)
                     ├── S3Paths (계산)
                     │
                     ├── JobStatus (상태 전이)
                     ├── JobProgress (진행률 매핑)
                     ├── StatusMessage (메시지 매핑)
                     │
                     └── WorkerError (예외 처리)
                              │
                              ├── RequirementsReadError
                              ├── InvalidRequirementsError
                              ├── AIGenerationError
                              ├── BuildError
                              └── ArtifactUploadError
```
