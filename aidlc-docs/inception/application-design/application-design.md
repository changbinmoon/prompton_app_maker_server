# Application Design - Prompton AI Worker (통합 문서)

## 1. 설계 개요

### 아키텍처 스타일
- **Modular by Feature**: 기능별 모듈 분리 (sqs/, s3/, dynamo/, ai/, build/)
- **Single Process Orchestrator**: worker 모듈이 전체 흐름을 조율
- **순차 처리**: 동시에 1개의 Job만 처리

### 프로젝트 구조
```
prompton_app_maker_server/
├── main.py                  # 엔트리포인트
├── worker/
│   ├── __init__.py
│   └── orchestrator.py      # 메인 루프 + Job 처리 시퀀스
├── sqs/
│   ├── __init__.py
│   └── client.py            # SQS 수신/삭제/Visibility 연장
├── s3/
│   ├── __init__.py
│   └── client.py            # S3 다운로드/업로드
├── dynamo/
│   ├── __init__.py
│   └── client.py            # DynamoDB 상태/로그 관리
├── ai/
│   ├── __init__.py
│   └── generator.py         # kiro-cli 호출
├── build/
│   ├── __init__.py
│   └── builder.py           # Gradle Wrapper + APK 빌드
├── config/
│   ├── __init__.py
│   └── settings.py          # 환경 변수 로드
└── requirements.txt         # Python 의존성
```

---

## 2. 컴포넌트 요약

| 컴포넌트 | 책임 | 외부 연동 |
|----------|------|-----------|
| worker | 메인 루프, Job 처리 조율, Graceful Shutdown | 없음 (내부 조율) |
| sqs | 메시지 수신/삭제/Visibility 연장 | AWS SQS |
| s3 | 파일 다운로드/업로드 | AWS S3 |
| dynamo | 상태 조회/업데이트, 로그 기록 | AWS DynamoDB |
| ai | AI 코드 생성 (kiro-cli) | kiro-cli subprocess |
| build | APK 빌드 (Gradle) | Android SDK/Gradle subprocess |
| config | 환경 변수 설정 관리 | 없음 |

---

## 3. 핵심 설계 결정

| 항목 | 결정 | 근거 |
|------|------|------|
| 프로젝트 구조 | Modular by Feature | 기능별 관심사 분리, 독립적 수정 가능 |
| Polling 방식 | boto3 기본 polling | SQS Long Polling 자동 활용, 단순성 |
| 작업 디렉토리 | /data/jobs/{jobId}/ | EC2 전용 볼륨, 디스크 공간 확보, 빌드 아티팩트 격리 |
| 에러 처리 | Exponential backoff | boto3 내장 재시도 활용, 외부 프로세스는 1회 실패 시 FAILED |
| 설정 관리 | 환경 변수 | EC2 IAM Role 자동 인증, 배포 간편 |
| Shutdown | 기본 수준 | 현재 처리 단계 완료 후 종료, SQS로 미완료 Job 자동 재처리 보장 |

---

## 4. 서비스 오케스트레이션

```
[Main Loop - worker.run()]
     │
     ├── sqs.receive_message() → 메시지 있으면 처리, 없으면 대기
     │
     └── worker.process_job(message)
              │
              ├── dynamo.get_job_status() → SUCCESS/CANCELED면 skip
              │
              ├── worker.start_visibility_extender()
              │
              ├── [ANALYZING]
              │   ├── dynamo.update_status(ANALYZING, 25)
              │   ├── s3.download_requirements()
              │   └── s3.download_assets()
              │
              ├── [GENERATING_CODE]
              │   ├── dynamo.update_status(GENERATING_CODE, 50)
              │   └── ai.generate_code()
              │
              ├── [BUILDING]
              │   ├── dynamo.update_status(BUILDING, 75)
              │   ├── build.build_apk()
              │   └── s3.upload_source()
              │
              ├── [SUCCESS]
              │   ├── s3.upload_artifact()
              │   ├── dynamo.update_status(SUCCESS, 100, artifactKey=...)
              │   └── sqs.delete_message()
              │
              ├── worker.stop_visibility_extender()
              │
              └── [FAILED - 예외 발생 시]
                  ├── dynamo.update_status(FAILED, errorCode=...)
                  └── worker.stop_visibility_extender()
```

---

## 5. 의존성 구조

```
                 +----------+
                 |  config  |
                 +----------+
                      ^
                      |
    +-----------------+------------------+
    |        |        |        |         |
+------+ +------+ +-------+ +----+ +-------+
|  sqs | |  s3  | | dynamo| | ai | | build |
+------+ +------+ +-------+ +----+ +-------+
    ^        ^        ^        ^       ^
    |        |        |        |       |
    +--------+--------+--------+-------+
                      |
                 +----------+
                 |  worker  |
                 +----------+
```

- **config**: 독립 (의존성 없음)
- **sqs, s3, dynamo, ai, build**: config만 의존
- **worker**: 모든 모듈에 의존 (오케스트레이터)

---

## 6. 외부 연동 재시도 전략

| 외부 서비스 | 재시도 방식 | 최대 재시도 | 비고 |
|-------------|-------------|-------------|------|
| AWS SQS | boto3 내장 exponential backoff | 3회 | 서비스 기본 설정 |
| AWS S3 | boto3 내장 exponential backoff | 3회 | 서비스 기본 설정 |
| AWS DynamoDB | boto3 내장 exponential backoff | 3회 | 서비스 기본 설정 |
| kiro-cli | 재시도 없음 | 0 | 실패 시 즉시 FAILED |
| Gradle | 재시도 없음 | 0 | 실패 시 즉시 FAILED |

---

## 7. Graceful Shutdown 동작

```
[SIGTERM 수신]
     │
     ├── shutdown_flag = True 설정
     │
     ├── 현재 처리 중인 단계 완료 대기
     │   (예: S3 업로드 중이면 업로드 완료까지)
     │
     ├── Visibility Extender 중지
     │
     └── 프로세스 종료
         (미완료 Job은 SQS Visibility Timeout 만료 후 자동 재가시화)
```
