# Logical Components - AI Worker

## 시스템 논리 구조

```
+-------------------------------------------------------------------+
|                        EC2 Instance (t3.xlarge)                     |
|                                                                    |
|  +-------------------------------------------------------------+  |
|  |                    systemd service layer                      |  |
|  |  (auto-restart, SIGTERM handling, journalctl logging)        |  |
|  +-------------------------------------------------------------+  |
|                              |                                     |
|  +-------------------------------------------------------------+  |
|  |                 Prompton AI Worker Process                    |  |
|  |                                                              |  |
|  |  +------------------+    +-----------------------------+     |  |
|  |  | Main Loop        |    | Visibility Extender Thread  |     |  |
|  |  | (sequential)     |    | (daemon, periodic)          |     |  |
|  |  +------------------+    +-----------------------------+     |  |
|  |           |                                                  |  |
|  |  +------------------+    +-----------------------------+     |  |
|  |  | Job Processor    |    | Cleanup Scheduler           |     |  |
|  |  | (orchestrator)   |    | (24h old dirs removal)      |     |  |
|  |  +------------------+    +-----------------------------+     |  |
|  |           |                                                  |  |
|  |  +-------+-------+-------+-------+-------+                  |  |
|  |  |  SQS  |  S3   | Dynamo|  AI   | Build |                  |  |
|  |  | Client| Client| Client| Module| Module|                  |  |
|  |  +-------+-------+-------+-------+-------+                  |  |
|  |                                                              |  |
|  +-------------------------------------------------------------+  |
|                                                                    |
|  +-------------------------------------------------------------+  |
|  |                    /data/jobs/ (EBS Volume)                   |  |
|  |  +------------------+  +------------------+                  |  |
|  |  | /data/jobs/{id1} |  | /data/jobs/{id2} |  ...            |  |
|  |  +------------------+  +------------------+                  |  |
|  +-------------------------------------------------------------+  |
|                                                                    |
+-------------------------------------------------------------------+
         |              |              |
         v              v              v
   +----------+   +-----------+   +----------+
   | AWS SQS  |   | AWS S3    |   | AWS      |
   | (Queue)  |   | (Bucket)  |   | DynamoDB |
   +----------+   +-----------+   +----------+
```

---

## 컴포넌트 상세

### 1. systemd Service Layer
- **역할**: 프로세스 수명 관리
- **기능**:
  - 부팅 시 자동 시작
  - 비정상 종료 시 5초 후 재시작
  - SIGTERM 전달 (Graceful Shutdown)
  - stdout/stderr → journalctl 수집
  - 환경 변수 주입 (EnvironmentFile)
- **보안**: NoNewPrivileges, ProtectSystem=strict, ReadWritePaths=/data/jobs

### 2. Main Loop (Sequential Processor)
- **역할**: SQS polling + Job 처리 순차 실행
- **동작 방식**:
  - Long Polling (WaitTimeSeconds=20)
  - 메시지 수신 → process_job() 호출
  - shutdown_requested 플래그 확인
- **상태**: 항상 1개의 Job만 처리 (동시성 없음)

### 3. Visibility Extender Thread
- **역할**: 장시간 처리 중 SQS 메시지 보호
- **타입**: daemon thread (메인 프로세스 종료 시 함께 종료)
- **주기**: Visibility Timeout * 0.5
- **라이프사이클**: Job 처리 시작 시 start, 완료/실패 시 stop

### 4. Job Processor (Orchestrator)
- **역할**: 단일 Job의 전체 처리 시퀀스 조율
- **패턴**: Sequential Pipeline
- **Phase**: 중복 확인 → ANALYZING → GENERATING_CODE → BUILDING → SUCCESS
- **에러 핸들링**: 각 Phase에서 예외 발생 시 FAILED 처리

### 5. Cleanup Scheduler
- **역할**: 오래된 작업 디렉토리 자동 정리
- **트리거**: 메인 루프 반복 시 (새 메시지 수신 전)
- **조건**: 수정 시간 기준 24시간 초과
- **동작**: shutil.rmtree (재귀적 삭제)

### 6. AWS Client Modules

| 모듈 | boto3 서비스 | 재시도 설정 |
|------|-------------|------------|
| SQS Client | sqs | adaptive, max 3 |
| S3 Client | s3 | adaptive, max 3 |
| DynamoDB Client | dynamodb | adaptive, max 3 |

### 7. AI Module
- **역할**: kiro-cli subprocess 관리
- **입력**: requirements.json 경로, assets 경로, 출력 경로
- **출력**: 생성된 프로젝트 디렉토리
- **프로세스**: subprocess.run(kiro-cli ..., check=True)
- **타임아웃**: 없음 (완료까지 대기)

### 8. Build Module
- **역할**: Gradle 빌드 subprocess 관리
- **전제**: EC2에 Android SDK, Gradle 사전 설치
- **동작**:
  1. gradle wrapper 생성
  2. ./gradlew assembleDebug 실행
  3. APK 경로 반환
- **타임아웃**: 없음 (완료까지 대기)

### 9. /data/jobs/ (EBS Volume)
- **역할**: Job별 격리된 작업 공간
- **볼륨 타입**: EBS gp3 (OS와 분리)
- **구조**: /data/jobs/{jobId}/ (각 Job별 디렉토리)
- **권한**: 700 (Worker 프로세스 사용자만 접근)
- **수명**: 최대 24시간 후 자동 삭제

---

## 외부 연동 흐름

```
                    Prompton AI Worker
                          |
          +---------------+---------------+
          |               |               |
          v               v               v
    +-----------+   +-----------+   +------------+
    | AWS SQS   |   | AWS S3    |   | DynamoDB   |
    +-----------+   +-----------+   +------------+
    | - Receive |   | - Get     |   | - GetItem  |
    | - Delete  |   |   reqs    |   | - Update   |
    | - Change  |   | - Get     |   |   status   |
    |   Vis.    |   |   assets  |   | - Update   |
    | - Get     |   | - Put     |   |   logs     |
    |   Attrs   |   |   source  |   +------------+
    +-----------+   | - Put     |
                    |   artifact|
                    +-----------+
```

---

## 스레드 모델

```
[Main Thread]                    [Visibility Extender Thread (daemon)]
     |                                      |
     |--- sqs.receive_message() ----+       |
     |                              |       |
     |--- process_job() starts -----+--- extender.start() --->|
     |       |                      |                          |
     |       |--- ANALYZING         |                    sleep(interval)
     |       |--- GENERATING_CODE   |                          |
     |       |--- BUILDING          |                    extend_visibility()
     |       |--- SUCCESS           |                          |
     |       |                      |                    sleep(interval)
     |--- process_job() ends -------+--- extender.stop() ---->|
     |                                                         |
     |--- cleanup_old_workdirs()                          [thread ends]
     |
     |--- (loop continues)
```

---

## 장애 시나리오 및 복구

| 장애 시나리오 | 감지 방법 | 복구 방법 |
|---------------|-----------|-----------|
| Worker 프로세스 crash | systemd 감지 | 자동 재시작 (5초 후) |
| kiro-cli 실패 | exit code != 0 | FAILED 기록, SQS 재처리 |
| Gradle 빌드 실패 | exit code != 0 | FAILED 기록, SQS 재처리 |
| S3 접근 실패 | boto3 예외 (재시도 후) | FAILED 기록, SQS 재처리 |
| DynamoDB 접근 실패 | boto3 예외 (재시도 후) | 로그 기록, 프로세스 계속 |
| Visibility 연장 실패 | 예외 catch | 로그 기록, 처리 계속 |
| 디스크 공간 부족 | IOError | FAILED 기록, 24시간 정리 대기 |
| 네트워크 단절 | boto3 연결 타임아웃 | 재시도 후 FAILED |
| OOM Kill | systemd 감지 | 자동 재시작 |
