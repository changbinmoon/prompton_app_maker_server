# Business Rules - AI Worker

## 1. 메시지 처리 규칙

### BR-001: 중복 처리 방지
- **규칙**: SQS 메시지 수신 후, DynamoDB에서 jobId의 현재 상태를 반드시 확인한다
- **조건**: status가 `SUCCESS` 또는 `CANCELED`이면 처리를 건너뛴다
- **동작**: 중복 메시지는 즉시 삭제하고 다음 메시지를 수신한다
- **근거**: SQS Standard Queue는 at-least-once 전달을 보장하므로 중복이 발생할 수 있다

### BR-002: 메시지 삭제 시점
- **규칙**: SQS 메시지는 모든 처리가 정상 완료된 후에만 삭제한다
- **순서**: APK S3 업로드 성공 → DynamoDB SUCCESS 업데이트 → SQS 메시지 삭제
- **금지**: 메시지 수신 즉시 삭제 금지
- **근거**: 실패 시 메시지가 자동으로 재가시화되어 재시도가 가능해야 한다

### BR-003: 실패 시 메시지 유지
- **규칙**: 처리 실패 시 SQS 메시지를 삭제하지 않는다
- **동작**: Visibility Timeout 만료 후 메시지가 다시 보이게 되어 재처리된다
- **제한**: 최대 3회 실패 후 DLQ로 이동 (Queue 설정)

---

## 2. 상태 관리 규칙

### BR-004: 상태 전이 순서
- **규칙**: 상태는 반드시 QUEUED → ANALYZING → GENERATING_CODE → BUILDING → SUCCESS 순서를 따른다
- **금지**: 상태를 건너뛰거나 역행할 수 없다 (실패 시 FAILED로 전이는 어느 단계에서든 가능)
- **보장**: 각 상태 전이는 DynamoDB에 원자적으로 기록된다

### BR-005: 상태 업데이트 원자성
- **규칙**: status, progress, message는 단일 UpdateItem 호출로 동시에 업데이트한다
- **근거**: 앱이 조회 시 일관된 상태를 볼 수 있어야 한다

### BR-006: artifactKey 기록 시점
- **규칙**: artifactKey는 S3에 APK 업로드가 완전히 성공한 후에만 DynamoDB에 기록한다
- **순서**: S3 PutObject 성공 확인 → DynamoDB UpdateItem (status=SUCCESS, artifactKey=...)
- **근거**: 앱이 artifactKey로 다운로드 시도 시 실제 파일이 존재해야 한다

### BR-007: progress 값 규칙
- **규칙**: progress는 다음 고정값만 사용한다
  - ANALYZING: 25
  - GENERATING_CODE: 50
  - BUILDING: 75
  - SUCCESS: 100
- **실패 시**: 마지막 progress 값을 유지한다 (덮어쓰지 않음)

---

## 3. 에러 처리 규칙

### BR-008: 에러 코드 분류
- **규칙**: 모든 실패에는 적절한 errorCode를 할당한다
- **분류 기준**:

| 에러 상황 | errorCode |
|-----------|-----------|
| requirements.json 다운로드/파싱 실패 | REQUIREMENTS_READ_FAILED |
| requirements.json 형식 오류 | INVALID_REQUIREMENTS |
| Hermes 실행/출력 실패 | 오류 코드 없음; 최대 3회 후 Kiro raw fallback |
| kiro-cli 실행 실패 (exit code != 0) | AI_GENERATION_FAILED |
| kiro-cli 파일/경로 오류 | AI_GENERATION_FAILED |
| Gradle 빌드 실패 | BUILD_FAILED |
| APK S3 업로드 실패 | ARTIFACT_UPLOAD_FAILED |
| 위에 해당하지 않는 예외 | INTERNAL_ERROR |

### BR-009: 실패 상태 기록
- **규칙**: 실패 시 DynamoDB에 status=FAILED, message, errorCode를 기록한다
- **message**: 사용자에게 보여줄 수 있는 한국어 메시지
- **금지**: 스택 트레이스, 내부 경로 등 민감 정보를 message에 포함하지 않는다

---

## 4. Visibility Timeout 규칙

### BR-010: Visibility Timeout 연장 주기
- **규칙**: Queue Visibility Timeout의 50% 시점마다 연장을 수행한다
- **연장 값**: Queue의 원래 Visibility Timeout 값으로 연장 (리셋)
- **시작**: Job 처리 시작 시 (ANALYZING 전환 직전)
- **종료**: Job 처리 완료(성공/실패) 시

### BR-011: Visibility 연장 실패 처리
- **규칙**: Visibility Timeout 연장 호출이 실패해도 현재 Job 처리를 중단하지 않는다
- **동작**: 연장 실패 로그 기록 후 처리 계속 진행
- **위험**: 연장 실패 시 중복 처리 가능성 있으나, 멱등성으로 보호됨

---

## 5. 로그 규칙

### BR-012: 로그 기록 시점
- **규칙**: 주요 처리 단계 시작/완료 시 DynamoDB logs 필드에 추가한다
- **필수 로그 시점**:
  - 작업 시작
  - 요구조건 다운로드 완료
  - 에셋 다운로드 완료 (있을 경우)
  - Hermes 프롬프트 정제 시작
  - Hermes 프롬프트 정제 완료 또는 원본 JSON fallback
  - 코드 생성 시작/완료
  - APK 빌드 시작/완료
  - 작업 완료 또는 실패

### BR-013: 로그 보안
- **규칙**: 다음 정보를 로그에 절대 포함하지 않는다
  - AWS Access Key / Secret Key
  - Session Token
  - Presigned URL
  - API Key
  - 사용자 개인정보
- **검증**: 로그 메시지 생성 시 민감 패턴 필터링

---

## 6. 파일 처리 규칙

### BR-014: 에셋 처리
- **규칙**: 에셋이 없는 Job도 정상적인 Job이다
- **동작**: assetsPrefix 아래 객체가 없으면 빈 리스트로 처리하고 계속 진행한다
- **형식 제한**: image/png, image/jpeg만 지원
- **개수 제한**: 최대 5개

### BR-015: APK 저장 위치
- **규칙**: 빌드된 APK는 반드시 `jobs/{jobId}/artifact/app-debug.apk`에 저장한다
- **파일명**: MVP에서는 항상 `app-debug.apk`
- **근거**: Backend가 이 경로로 Presigned URL을 발급한다

### BR-016: 소스 코드 저장
- **규칙**: 생성된 코드를 `jobs/{jobId}/source/` 아래에 저장한다
- **형식**: project.zip (압축)
- **시점**: APK 빌드 성공 후 (빌드 실패 시에도 저장하여 디버깅에 활용 가능)

---

## 7. 작업 디렉토리 규칙

### BR-017: 디렉토리 생성
- **규칙**: Job 처리 시작 시 `/data/jobs/{jobId}/` 디렉토리를 생성한다
- **이미 존재 시**: 기존 디렉토리 삭제 후 재생성 (멱등성 보장)

### BR-018: 디렉토리 정리
- **규칙**: 생성 후 24시간이 경과한 작업 디렉토리를 삭제한다
- **정리 시점**: 메인 루프에서 새 메시지를 수신하기 전
- **정리 대상**: 성공/실패 모두 포함 (24시간 내 디버깅 가능)

---

## 8. 유효성 검증 규칙

### BR-019: SQS 메시지 유효성
- **필수 필드**: schemaVersion, jobId, requirements.bucket, requirements.key, assetsPrefix
- **jobId 형식**: UUID v4
- **schemaVersion**: "1.0" (현재 지원 버전)
- **실패 시**: INVALID_REQUIREMENTS 에러

### BR-020: requirements.json 유효성
- **입력**: Backend가 S3에 저장한 원본 Client JSON object
- **최대 크기**: 64 KiB (JSON 파싱 전에 검사)
- **인코딩**: UTF-8
- **구조 검증**: 유효한 JSON이며 최상위가 object
- **허용 범위**: 임의 root/nested 필드 허용; canonical schema는 runtime ingress에 적용하지 않음
- **실패 시**: INVALID_REQUIREMENTS 또는 REQUIREMENTS_READ_FAILED
- **보존**: Worker와 Hermes는 원본 JSON 필드를 변경하지 않음

### BR-021: Hermes prompt refinement와 Kiro fallback
- **순서**: raw JSON 다운로드 및 assets 처리 후 Hermes, 그 다음 Kiro
- **호출**: `--ignore-rules --toolsets context_engine --oneshot`
- **Android guardrail**: Kotlin, Jetpack Compose, API level 21-35 또는 26/35 기본값, valid applicationId 보존 또는 Job ID 기반 기본값
- **출력**: non-empty, NUL 없음, UTF-8 64 KiB 이하 text를 `refined-prompt.md`에 atomic 저장
- **재시도**: 최초 호출 포함 최대 3회, 실패 후 1초와 2초 대기
- **로그 보안**: raw JSON과 Hermes stdout/stderr를 로그에 기록하지 않음
- **fallback**: 모든 시도 실패 시 원본 JSON, assets, 동일 guardrail로 Kiro를 계속 실행
- **실패 분류**: Hermes exhaustion은 Job 실패가 아니며, 이후 Kiro 실패만 AI_GENERATION_FAILED
