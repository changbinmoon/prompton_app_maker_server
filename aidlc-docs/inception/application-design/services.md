# Services - Prompton AI Worker

## 서비스 계층 개요

AI Worker는 단일 서비스(Worker Orchestrator)가 기능별 모듈을 조율하는 구조이다.
별도의 마이크로서비스 분리 없이, 단일 프로세스 내에서 모듈 간 직접 호출로 동작한다.

---

## 1. Worker Orchestrator Service (worker 모듈)

### 역할
전체 Job 처리 라이프사이클을 관리하는 메인 오케스트레이터

### 오케스트레이션 패턴

```
[Main Loop]
     │
     ├── SQS Polling (sqs.receive_message)
     │
     ├── 중복 확인 (dynamo.get_job_status)
     │
     ├── Visibility Extender 시작 (background thread)
     │
     ├── 상태: ANALYZING
     │   ├── dynamo.update_status
     │   ├── s3.download_requirements
     │   └── s3.download_assets
     │
     ├── 상태: GENERATING_CODE
     │   ├── dynamo.update_status
     │   └── ai.generate_code
     │
     ├── 상태: BUILDING
     │   ├── dynamo.update_status
     │   ├── build.build_apk
     │   └── s3.upload_source
     │
     ├── 완료 처리
     │   ├── s3.upload_artifact
     │   ├── dynamo.update_status (SUCCESS)
     │   └── sqs.delete_message
     │
     └── Visibility Extender 중지
```

### 서비스 경계
- **입력**: SQS 메시지
- **출력**: DynamoDB 상태 업데이트, S3 결과물
- **에러 시**: DynamoDB FAILED 상태 기록, SQS 메시지 유지

---

## 2. Visibility Timeout Extension Service (worker 내부)

### 역할
장시간 처리 중 SQS 메시지가 다른 Worker에게 노출되지 않도록 Timeout 연장

### 동작 방식
- 별도 스레드(또는 asyncio task)로 동작
- 일정 주기(예: Visibility Timeout의 50% 지점)마다 연장 호출
- Job 처리 완료 또는 실패 시 중지

---

## 3. 외부 서비스 연동

| 외부 서비스 | 연동 방식 | 재시도 전략 |
|-------------|-----------|-------------|
| AWS SQS | boto3 client | Exponential backoff (boto3 내장) |
| AWS S3 | boto3 client | Exponential backoff (boto3 내장) |
| AWS DynamoDB | boto3 client | Exponential backoff (boto3 내장) |
| kiro-cli | subprocess | 재시도 없음 (1회 실패 시 FAILED) |
| Gradle | subprocess | 재시도 없음 (1회 실패 시 FAILED) |

---

## 4. 에러 처리 서비스 흐름

```
[예외 발생]
     │
     ├── AWS 서비스 에러 (S3, DynamoDB, SQS)
     │   └── boto3 내장 재시도 (exponential backoff)
     │       ├── 성공 → 계속 진행
     │       └── 최종 실패 → FAILED 상태 기록
     │
     ├── kiro-cli 에러
     │   └── 즉시 FAILED (AI_GENERATION_FAILED)
     │
     ├── Gradle 빌드 에러
     │   └── 즉시 FAILED (BUILD_FAILED)
     │
     └── 예상치 못한 에러
         └── FAILED (INTERNAL_ERROR)
```
