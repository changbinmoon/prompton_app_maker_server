# Business Logic Model - AI Worker

## 1. 상태 머신 (Job Status State Machine)

### 상태 정의

| 상태 | 설명 | Worker 진입 조건 |
|------|------|-----------------|
| UPLOAD_PENDING | 사용자 파일 업로드 대기 | Worker 관여 없음 |
| QUEUED | SQS에 메시지 등록됨 | Worker 관여 없음 (Backend 설정) |
| ANALYZING | 요구조건 분석 중 | Worker가 Job 수신 후 처리 시작 |
| GENERATING_CODE | 코드 생성 중 | 요구조건 분석 완료 후 |
| BUILDING | APK 빌드 중 | 코드 생성 완료 후 |
| SUCCESS | 처리 완료 | APK S3 업로드 성공 후 |
| FAILED | 처리 실패 | 어느 단계에서든 예외 발생 시 |
| CANCELED | 취소됨 | Worker 관여 없음 (Backend 설정) |

### 상태 전이 규칙

```
QUEUED ──────────────────► ANALYZING
  │                            │
  │ (중복 확인: SUCCESS/       │ (requirements.json 다운로드,
  │  CANCELED이면 skip)        │  assets 다운로드, 분석)
  │                            │
  │                            ▼
  │                     GENERATING_CODE
  │                            │
  │                            │ (kiro-cli 코드 생성)
  │                            │
  │                            ▼
  │                        BUILDING
  │                            │
  │                            │ (Gradle APK 빌드)
  │                            │
  │                            ▼
  │                        SUCCESS
  │                            
  └─── (모든 단계에서) ──► FAILED
```

### 전이 조건

| 현재 상태 | 다음 상태 | 전이 조건 |
|-----------|-----------|-----------|
| QUEUED | ANALYZING | Worker가 메시지를 수신하고 중복이 아닌 경우 |
| ANALYZING | GENERATING_CODE | requirements.json 파싱 완료, assets 다운로드 완료 |
| GENERATING_CODE | BUILDING | kiro-cli 코드 생성 성공 |
| BUILDING | SUCCESS | APK 빌드 성공 + S3 업로드 성공 확인 |
| 모든 상태 | FAILED | 해당 단계에서 복구 불가능한 에러 발생 |

---

## 2. 메인 처리 시퀀스

### 2.1 Main Loop

```
while not shutdown_requested:
    1. message = sqs.receive_message()
    2. if message is None:
         continue (polling 대기)
    3. process_job(message)
    4. cleanup_old_workdirs()  # 24시간 초과 디렉토리 삭제
```

### 2.2 process_job(message) 상세 흐름

```
process_job(message):
    try:
        # Phase 0: 사전 검증
        job_id = message.job_id
        current_status = dynamo.get_job_status(job_id)
        if current_status in [SUCCESS, CANCELED]:
            sqs.delete_message(message.receipt_handle)
            return  # 중복 처리 방지

        # Visibility Extender 시작
        start_visibility_extender(message.receipt_handle)

        # Phase 1: ANALYZING
        dynamo.update_status(job_id, ANALYZING, 25, "요구조건을 분석하고 있습니다.")
        dynamo.append_log(job_id, "[worker] 작업을 시작했습니다.")

        requirements = s3.download_requirements(
            message.requirements.bucket,
            message.requirements.key
        )
        dynamo.append_log(job_id, "[worker] 요구조건 다운로드 완료")

        assets = s3.download_assets(
            message.requirements.bucket,
            message.assets_prefix,
            work_dir / "assets"
        )
        if assets:
            dynamo.append_log(job_id, f"[worker] 에셋 {len(assets)}개 다운로드 완료")

        # Phase 2: GENERATING_CODE
        dynamo.update_status(job_id, GENERATING_CODE, 50, "앱 코드를 생성하고 있습니다.")
        dynamo.append_log(job_id, "[llm] 코드 생성 시작")

        project_dir = ai.generate_code(
            requirements_path=work_dir / "requirements.json",
            assets_dir=work_dir / "assets",
            output_dir=work_dir / "project"
        )
        dynamo.append_log(job_id, "[llm] 코드 생성 완료")

        # Phase 3: BUILDING
        dynamo.update_status(job_id, BUILDING, 75, "APK를 빌드하고 있습니다.")
        dynamo.append_log(job_id, "[gradle] APK 빌드 시작")

        apk_path = build.build_apk(project_dir)
        dynamo.append_log(job_id, "[gradle] APK 빌드 완료")

        # Phase 4: 업로드 및 완료
        s3.upload_source(
            project_dir,
            bucket,
            f"jobs/{job_id}/source/project.zip"
        )

        artifact_key = s3.upload_artifact(
            apk_path,
            bucket,
            f"jobs/{job_id}/artifact/app-debug.apk"
        )

        # 순서 중요: S3 업로드 성공 확인 → DynamoDB SUCCESS → SQS 삭제
        dynamo.update_status(job_id, SUCCESS, 100,
            "앱 생성이 완료되었습니다.",
            artifactKey=artifact_key
        )
        dynamo.append_log(job_id, "[worker] 작업 완료")

        sqs.delete_message(message.receipt_handle)

    except Exception as e:
        # 실패 처리
        error_code = classify_error(e)
        dynamo.update_status(job_id, FAILED,
            message=str(e),
            errorCode=error_code
        )
        dynamo.append_log(job_id, f"[worker] 실패: {error_code}")
        # SQS 메시지 삭제하지 않음 (재시도 가능)

    finally:
        stop_visibility_extender()
```

---

## 3. Visibility Timeout 연장 로직

### 연장 전략
- **주기**: Queue Visibility Timeout의 50%
- **예시**: Visibility Timeout = 300초 → 150초마다 연장
- **동작**: 별도 스레드에서 주기적으로 ChangeMessageVisibility 호출
- **종료 조건**: Job 처리 완료(성공/실패) 시 스레드 중지

### 구현 흐름

```
visibility_extender_thread:
    interval = queue_visibility_timeout * 0.5
    while not stopped:
        sleep(interval)
        if not stopped:
            sqs.extend_visibility(receipt_handle, queue_visibility_timeout)
```

---

## 4. 작업 디렉토리 관리

### 디렉토리 구조
```
/data/jobs/{jobId}/
├── requirements.json    # S3에서 다운로드
├── assets/              # 에셋 이미지
│   ├── 0-logo.png
│   └── ...
├── project/             # kiro-cli 생성 코드
│   ├── app/
│   ├── build.gradle
│   ├── gradlew
│   └── ...
└── output/
    └── app-debug.apk    # 빌드 결과
```

### 정리 정책
- **보존 기간**: 24시간
- **정리 시점**: 메인 루프 반복 시 오래된 디렉토리 확인
- **정리 대상**: 생성 시간이 24시간을 초과한 작업 디렉토리
- **실패한 Job**: 동일 정책 (24시간 보존 → 디버깅 가능)

---

## 5. Graceful Shutdown 로직

```
handle_shutdown(signum, frame):
    shutdown_requested = True
    # 현재 처리 중인 단계가 있으면 해당 단계 완료까지 대기
    # (sqs.receive_message 대기 중이면 즉시 종료)

Main Loop 동작:
    while not shutdown_requested:
        message = sqs.receive_message()
        if message:
            process_job(message)  # 이 Job은 완료/실패까지 처리
        # 루프 시작점에서 shutdown_requested 확인 → 다음 Job은 받지 않음
```

---

## 6. kiro-cli 연동 모델

### 호출 방식
- kiro-cli가 직접 requirements.json 파일 경로를 받아 처리
- 타임아웃 없음 (완료까지 대기)
- subprocess로 실행, stdout/stderr 수집

### 입력
- requirements.json 파일 경로
- assets 디렉토리 경로 (있을 경우)
- 출력 디렉토리 경로

### 출력
- 생성된 Android 프로젝트 (출력 디렉토리에 작성)
- exit code 0: 성공, 그 외: 실패

### 에러 처리
- exit code != 0 → AI_GENERATION_FAILED
- subprocess 예외(파일 없음 등) → AI_GENERATION_FAILED
