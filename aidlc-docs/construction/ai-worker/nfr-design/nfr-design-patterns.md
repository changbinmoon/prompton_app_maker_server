# NFR Design Patterns - AI Worker

## 1. Resilience Patterns

### Pattern 1: Automatic Retry with Exponential Backoff
- **적용 대상**: AWS 서비스 호출 (SQS, S3, DynamoDB)
- **구현**: boto3 내장 재시도 메커니즘 (botocore retry config)
- **설정**:
  - max_attempts: 3
  - mode: "adaptive" (AWS 권장)
- **코드 적용**:

```python
import boto3
from botocore.config import Config

retry_config = Config(
    retries={
        "max_attempts": 3,
        "mode": "adaptive"
    }
)

sqs_client = boto3.client("sqs", config=retry_config)
s3_client = boto3.client("s3", config=retry_config)
dynamodb_client = boto3.resource("dynamodb", config=retry_config)
```

### Pattern 2: Message Visibility Management (Lease Extension)
- **적용 대상**: SQS 메시지 처리 중 중복 방지
- **구현**: 별도 daemon thread에서 주기적 ChangeMessageVisibility 호출
- **전략**:
  - 연장 주기: Visibility Timeout * 0.5
  - 연장 값: 원래 Visibility Timeout (리셋)
  - 실패 시: 로그 기록 후 처리 계속 (멱등성으로 보호)
- **코드 패턴**:

```python
import threading

class VisibilityExtender:
    def __init__(self, sqs_client, queue_url, receipt_handle, timeout):
        self._stop_event = threading.Event()
        self._interval = timeout * 0.5
        self._timeout = timeout
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _run(self):
        while not self._stop_event.wait(self._interval):
            try:
                sqs_client.change_message_visibility(...)
            except Exception:
                logger.warning("Visibility 연장 실패")
```

### Pattern 3: Idempotent Consumer
- **적용 대상**: 전체 Job 처리 로직
- **구현**: DynamoDB에서 jobId 상태를 확인하여 이미 처리된 Job은 skip
- **전략**:
  - 처리 시작 전 GetItem(jobId) 호출
  - SUCCESS/CANCELED 상태면 메시지 삭제 후 skip
  - 작업 디렉토리 존재 시 삭제 후 재생성 (깨끗한 시작 보장)

### Pattern 4: Graceful Degradation (Fail-Fast for External Processes)
- **적용 대상**: kiro-cli, Gradle subprocess 호출
- **구현**: 외부 프로세스 실패 시 재시도 없이 즉시 FAILED 처리
- **근거**:
  - AI 코드 생성은 비결정적 → 재시도로 해결 불가
  - Gradle 빌드 실패는 코드 오류 → 재시도 무의미
  - SQS 재전달로 전체 Job 레벨 재시도 가능 (최대 3회)

### Pattern 5: Dead Letter Queue (Poison Message Handling)
- **적용 대상**: 반복 실패 메시지
- **구현**: AWS SQS 설정 (maxReceiveCount=3 → DLQ 이동)
- **Worker 역할**: DLQ 설정은 인프라 수준, Worker는 실패 시 메시지 유지만 담당

---

## 2. Availability Patterns

### Pattern 6: Process Supervisor (systemd)
- **적용 대상**: Worker 프로세스 자체의 가용성
- **구현**: systemd Restart=on-failure
- **동작**:
  - 비정상 종료 (exit code != 0) → 5초 후 자동 재시작
  - OOM Kill → 자동 재시작
  - SIGTERM → Graceful Shutdown (재시작 안 함)
- **제한**: 단일 인스턴스 (HA 구성 아님)

### Pattern 7: Graceful Shutdown (Cooperative Cancellation)
- **적용 대상**: 서비스 중지/배포 시 진행 중인 작업 보호
- **구현**: SIGTERM 시그널 핸들러 + shutdown flag
- **동작**:
  1. SIGTERM 수신 → shutdown_requested = True
  2. 현재 처리 단계 완료 대기 (새 Job 수신 중지)
  3. Visibility Extender 중지
  4. 프로세스 종료
- **systemd TimeoutStopSec**: 300초 (최대 대기 시간)

---

## 3. Security Patterns

### Pattern 8: Principle of Least Privilege (IAM)
- **적용 대상**: EC2 Instance Profile 권한
- **구현**: 리소스 수준 제한 + 액션 수준 제한
- **IAM Policy 구조**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:us-east-1:440052841756:prompton-app-build-jobs-dev"
    },
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": [
        "arn:aws:s3:::prompton-app-builder-dev-changbin/jobs/*/requirements/*",
        "arn:aws:s3:::prompton-app-builder-dev-changbin/jobs/*/assets/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": [
        "arn:aws:s3:::prompton-app-builder-dev-changbin/jobs/*/source/*",
        "arn:aws:s3:::prompton-app-builder-dev-changbin/jobs/*/artifact/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::prompton-app-builder-dev-changbin",
      "Condition": {
        "StringLike": {
          "s3:prefix": "jobs/*/assets/*"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:440052841756:table/prompton-jobs-dev"
    }
  ]
}
```

### Pattern 9: Credential-Free Authentication
- **적용 대상**: AWS 서비스 인증
- **구현**: EC2 Instance Metadata Service (IMDS) + IAM Role
- **금지**: 하드코딩된 자격증명, .env 파일 내 AWS Key
- **boto3 동작**: 자동으로 Instance Profile 자격증명 사용

### Pattern 10: Log Sanitization
- **적용 대상**: DynamoDB logs 필드, 로컬 로그
- **구현**: 로그 메시지 생성 시 민감 패턴 필터링
- **필터 대상**: AWS Key 패턴, URL 내 토큰, API Key 형식
- **코드 패턴**:

```python
import re

SENSITIVE_PATTERNS = [
    re.compile(r'AKIA[0-9A-Z]{16}'),           # AWS Access Key
    re.compile(r'[A-Za-z0-9/+=]{40}'),          # AWS Secret Key (40자)
    re.compile(r'X-Amz-Security-Token=[^\s&]+'), # Session Token
    re.compile(r'https?://[^\s]*Signature=[^\s&]+'), # Presigned URL
]

def sanitize_log(message: str) -> str:
    for pattern in SENSITIVE_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    return message
```

---

## 4. Performance Patterns

### Pattern 11: Long Polling (Efficient Resource Usage)
- **적용 대상**: SQS 메시지 수신
- **구현**: WaitTimeSeconds=20
- **효과**: 빈 응답 감소, API 호출 비용 절감, 지연 최소화
- **코드 패턴**:

```python
response = sqs_client.receive_message(
    QueueUrl=queue_url,
    MaxNumberOfMessages=1,
    WaitTimeSeconds=20,
    MessageAttributeNames=["All"]
)
```

### Pattern 12: Workspace Isolation (Disk Performance)
- **적용 대상**: Job별 작업 디렉토리
- **구현**: /data/jobs/{jobId}/ (전용 EBS 볼륨)
- **효과**: OS 볼륨과 분리하여 I/O 경합 방지, 독립적 용량 관리

---

## 5. Maintainability Patterns

### Pattern 13: Structured Logging
- **적용 대상**: 전체 Worker 프로세스
- **구현**: Python logging 모듈 + JSON 포맷 (선택적)
- **레벨 전략**:
  - INFO: 상태 전이, 단계 시작/완료
  - WARNING: Visibility 연장 실패, 재시도
  - ERROR: Job 실패, 예외
  - DEBUG: 상세 처리 정보 (개발 환경)

### Pattern 14: Periodic Cleanup (Self-Healing Storage)
- **적용 대상**: 작업 디렉토리 (/data/jobs/)
- **구현**: 메인 루프에서 주기적으로 24시간 초과 디렉토리 삭제
- **효과**: 디스크 고갈 방지, 운영 개입 최소화
- **코드 패턴**:

```python
import shutil
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_old_workdirs(work_dir: str, max_age_hours: int = 24):
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    for job_dir in Path(work_dir).iterdir():
        if job_dir.is_dir():
            mtime = datetime.fromtimestamp(job_dir.stat().st_mtime)
            if mtime < cutoff:
                shutil.rmtree(job_dir, ignore_errors=True)
```
