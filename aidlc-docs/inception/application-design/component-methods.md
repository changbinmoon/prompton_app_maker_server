# Component Methods - Prompton AI Worker

## 1. sqs 모듈

### receive_message() -> Optional[SQSMessage]
- **목적**: SQS Queue에서 메시지 1건 수신
- **입력**: None (Queue URL은 config에서 참조)
- **출력**: SQSMessage (jobId, requirements, assetsPrefix, receiptHandle) 또는 None
- **비고**: boto3 기본 polling 메커니즘 사용

### delete_message(receipt_handle: str) -> None
- **목적**: 처리 완료된 SQS 메시지 삭제
- **입력**: receipt_handle (수신 시 받은 핸들)
- **출력**: None
- **비고**: 전체 처리 성공 후에만 호출

### extend_visibility(receipt_handle: str, timeout_seconds: int) -> None
- **목적**: 메시지 Visibility Timeout 연장
- **입력**: receipt_handle, 연장할 초 단위
- **출력**: None
- **비고**: 장시간 처리 시 주기적 호출

---

## 2. s3 모듈

### download_requirements(bucket: str, key: str) -> dict
- **목적**: requirements.json 다운로드 및 파싱
- **입력**: S3 bucket명, object key
- **출력**: 파싱된 JSON dict
- **비고**: 실패 시 REQUIREMENTS_READ_FAILED 에러

### download_assets(bucket: str, prefix: str, local_dir: str) -> List[str]
- **목적**: 에셋 이미지 다운로드
- **입력**: bucket, assets prefix, 로컬 저장 경로
- **출력**: 다운로드된 파일 경로 리스트
- **비고**: 에셋 없으면 빈 리스트 반환

### upload_source(local_path: str, bucket: str, key: str) -> None
- **목적**: 생성된 코드/프로젝트 S3 업로드
- **입력**: 로컬 파일 경로, bucket, S3 key
- **출력**: None

### upload_artifact(local_path: str, bucket: str, key: str) -> str
- **목적**: APK 파일 S3 업로드
- **입력**: 로컬 APK 경로, bucket, S3 key
- **출력**: 업로드된 S3 key (artifactKey)
- **비고**: 업로드 성공 확인 후 반환. 실패 시 ARTIFACT_UPLOAD_FAILED

---

## 3. dynamo 모듈

### get_job_status(job_id: str) -> Optional[str]
- **목적**: Job 현재 상태 조회 (중복 처리 확인)
- **입력**: jobId
- **출력**: 현재 status 문자열 또는 None

### update_status(job_id: str, status: str, progress: int, message: str, **kwargs) -> None
- **목적**: Job 상태 업데이트
- **입력**: jobId, status, progress, message, 추가 필드(errorCode, artifactKey 등)
- **출력**: None
- **비고**: 원자적 업데이트 보장

### append_log(job_id: str, log_entry: str) -> None
- **목적**: 로그 항목 추가
- **입력**: jobId, 로그 메시지 문자열
- **출력**: None
- **비고**: logs 배열에 append

---

## 4. ai 모듈

### generate_code(requirements: dict, assets: List[str], work_dir: str) -> str
- **목적**: kiro-cli를 통해 AI 코드 생성
- **입력**: requirements dict, 에셋 파일 경로 리스트, 작업 디렉토리
- **출력**: 생성된 프로젝트 디렉토리 경로
- **비고**: subprocess로 kiro-cli 호출. 실패 시 AI_GENERATION_FAILED

---

## 5. build 모듈

### build_apk(project_dir: str) -> str
- **목적**: Android 프로젝트 APK 빌드
- **입력**: 프로젝트 디렉토리 경로
- **출력**: 생성된 APK 파일 경로
- **동작**:
  1. Gradle Wrapper 생성 (gradle wrapper)
  2. ./gradlew assembleDebug 실행
  3. app/build/outputs/apk/debug/app-debug.apk 경로 반환
- **비고**: 실패 시 BUILD_FAILED

---

## 6. worker 모듈

### run() -> None
- **목적**: Worker 메인 루프 실행
- **입력**: None
- **출력**: None (무한 루프, Graceful Shutdown 시 종료)

### process_job(message: SQSMessage) -> None
- **목적**: 단일 Job 전체 처리 시퀀스 실행
- **입력**: SQS 메시지 객체
- **출력**: None
- **동작**: 중복 확인 → 상태 전이 → 다운로드 → AI 생성 → 빌드 → 업로드 → 완료

### start_visibility_extender(receipt_handle: str) -> None
- **목적**: 백그라운드에서 Visibility Timeout 주기적 연장 시작
- **입력**: receipt_handle
- **출력**: None

### stop_visibility_extender() -> None
- **목적**: Visibility Timeout 연장 중지
- **입력**: None
- **출력**: None

### handle_shutdown(signum, frame) -> None
- **목적**: SIGTERM 시그널 핸들러 (Graceful Shutdown)
- **입력**: signal number, frame
- **출력**: None
- **동작**: 현재 처리 단계 완료 후 루프 종료

---

## 7. config 모듈

### load_config() -> Config
- **목적**: 환경 변수에서 설정값 로드 및 검증
- **입력**: None (os.environ에서 읽기)
- **출력**: Config 객체 (dataclass)
- **필수 환경 변수**:
  - AWS_REGION
  - SQS_QUEUE_URL
  - DYNAMODB_TABLE_NAME
  - S3_BUCKET_NAME
  - WORK_DIR (기본값: /data/jobs)
