# Components - Prompton AI Worker

## 컴포넌트 목록

### 1. sqs - SQS 메시지 관리
**책임:**
- SQS Queue에서 메시지 수신 (polling)
- 메시지 파싱 (jobId, requirements, assetsPrefix 추출)
- 메시지 삭제 (정상 완료 후)
- Visibility Timeout 연장 (장시간 처리 시)

**인터페이스:**
- 외부: AWS SQS (prompton-app-build-jobs-dev)
- 내부: worker (메인 오케스트레이터)에 메시지 전달

---

### 2. s3 - S3 파일 관리
**책임:**
- requirements.json 다운로드
- 사용자 에셋(이미지) 다운로드
- 생성 코드 업로드 (source/)
- APK 업로드 (artifact/)

**인터페이스:**
- 외부: AWS S3 (prompton-app-builder-dev-changbin)
- 내부: worker에 파일 경로/데이터 제공

---

### 3. dynamo - DynamoDB 상태 관리
**책임:**
- Job 상태 조회 (중복 처리 확인)
- Job 상태 업데이트 (status, progress, message)
- 로그 기록 (logs 필드 업데이트)
- artifactKey 저장 (성공 시)
- 에러 정보 기록 (실패 시)

**인터페이스:**
- 외부: AWS DynamoDB (prompton-jobs-dev, PK: jobId)
- 내부: worker에서 상태 전이 시 호출

---

### 4. ai - AI 코드 생성
**책임:**
- kiro-cli 프로세스 호출
- requirements.json 기반 앱 코드 생성 프롬프트 구성
- assets 참조 전달
- 생성 결과물(Android 프로젝트) 수집

**인터페이스:**
- 외부: kiro-cli (subprocess) + Opus5 모델
- 내부: worker에 생성된 프로젝트 경로 반환

---

### 5. build - APK 빌드
**책임:**
- Gradle Wrapper 생성 (gradlew)
- assembleDebug 태스크 실행
- 빌드 결과(APK 파일 경로) 반환
- 빌드 로그 수집

**인터페이스:**
- 외부: Android SDK, Gradle (EC2 사전 설치)
- 내부: worker에 APK 파일 경로 반환

---

### 6. worker - 메인 오케스트레이터
**책임:**
- 메인 루프 (SQS polling → 처리 → 완료)
- 처리 시퀀스 조율 (상태 전이 순서 보장)
- 중복 처리 방지 로직
- Visibility Timeout 연장 스케줄링
- Graceful Shutdown 처리 (SIGTERM → 현재 단계 완료 후 종료)

**인터페이스:**
- 내부: 모든 컴포넌트를 조율

---

### 7. config - 설정 관리
**책임:**
- 환경 변수 로드 및 검증
- 설정값 중앙 관리 (QUEUE_URL, TABLE_NAME, BUCKET_NAME 등)
- 기본값 제공

**인터페이스:**
- 내부: 모든 컴포넌트에서 설정값 참조
