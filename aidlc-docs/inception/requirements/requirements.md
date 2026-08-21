# Prompton AI Worker 요구사항 사양서

## Status API 전환 우선 적용 공지

DynamoDB 직접 접근, 상태 조회, 상태 갱신, 사용자 로그 저장 및 관련 IAM 조항은 `status-api-requirements.md`가 이 문서보다 우선한다. 기존 DynamoDB 조항은 구현 기준으로 사용하지 않는다.

## Intent Analysis

| 항목 | 내용 |
|------|------|
| **사용자 요청** | aws-backend-requirements.md의 AI Worker 동작에 대한 요구사항 사양서 작성 |
| **요청 유형** | New Project - AI Worker 서비스 신규 구현 |
| **범위** | Multiple Components - SQS, S3, DynamoDB, AI 처리, APK 빌드 연동 |
| **복잡도** | Complex - 메시지 큐 기반 비동기 처리, AI 코드 생성, 빌드 파이프라인 |

---

## 1. 시스템 개요

### 1.1 목적
Prompton AI Worker는 SQS 큐에서 앱 생성 Job을 수신하여, AI 기반 코드 생성 및 APK 빌드를 수행하는 백엔드 워커 서비스이다.

### 1.2 담당 영역
AI Worker의 책임은 SQS에 등록된 Job을 가져오는 시점부터 시작하며, APK를 S3에 업로드하고 DynamoDB 상태를 SUCCESS로 변경한 뒤 SQS 메시지를 삭제하는 시점에 끝난다.

### 1.3 시스템 경계

```
[Mobile App] → [API Gateway] → [Lambda] → [SQS]
                                              │
════════════════════════════════════════════════╪════ AI Worker 담당 영역 시작
                                              │
                                              v
                                         [AI Worker]
                                              │
                                              ├── SQS Job 수신
                                              ├── S3 입력 다운로드
                                              ├── AI 처리 (kiro-cli + Opus5)
                                              ├── 코드 생성
                                              ├── APK 빌드 (Gradle Wrapper)
                                              ├── S3 결과 업로드
                                              └── DynamoDB 상태 업데이트
```

---

## 2. 기술 스택

| 항목 | 선정 |
|------|------|
| **프로그래밍 언어** | Python (권장 - boto3, 풍부한 AI/ML 생태계) |
| **배포 환경** | EC2 인스턴스 (IAM Role / Instance Profile) |
| **AI 코드 생성** | kiro-cli + Opus5 (EC2 서버에서 실행) |
| **APK 빌드** | EC2에 Android SDK/Gradle 사전 설치, 프로젝트별 Gradle Wrapper 생성 |
| **동시 처리** | 1개 (단일 Job 순차 처리) |
| **AWS Region** | us-east-1 |

---

## 3. 기능적 요구사항

### FR-001: SQS 메시지 수신
- **설명**: Worker는 SQS Queue를 polling하여 Job 메시지를 수신한다
- **Queue**: `prompton-app-build-jobs-dev` (Standard Queue)
- **ARN**: `arn:aws:sqs:us-east-1:440052841756:prompton-app-build-jobs-dev`
- **URL**: `https://sqs.us-east-1.amazonaws.com/440052841756/prompton-app-build-jobs-dev`
- **메시지 스키마**:
```json
{
  "schemaVersion": "1.0",
  "jobId": "UUID",
  "requirements": {
    "bucket": "prompton-app-builder-dev-changbin",
    "key": "jobs/{jobId}/requirements/requirements.json"
  },
  "assetsPrefix": "jobs/{jobId}/assets/"
}
```
- **수락 기준**: 
  - Queue를 주기적으로 polling하여 메시지를 수신할 수 있다
  - Message Body에서 jobId, requirements, assetsPrefix를 파싱할 수 있다

### FR-002: 중복 처리 방지
- **설명**: 메시지 수신 후 DynamoDB에서 현재 Job 상태를 확인하여 중복 처리를 방지한다
- **동작**:
  - `DynamoDB GetItem(jobId)` 수행
  - status가 `SUCCESS` 또는 `CANCELED`이면 메시지를 삭제하고 처리를 건너뛴다
- **수락 기준**:
  - 이미 완료/취소된 Job은 재처리하지 않는다
  - Worker 로직은 멱등하게 동작한다

### FR-003: 상태 전이 관리
- **설명**: Worker는 처리 진행에 따라 DynamoDB 상태를 순차적으로 업데이트한다
- **상태 흐름**: `QUEUED` → `ANALYZING` → `GENERATING_CODE` → `BUILDING` → `SUCCESS`
- **DynamoDB Table**: `prompton-jobs-dev` (PK: `jobId`)
- **업데이트 필드**: status, progress, message
- **진행률 매핑**:

| 상태 | progress | message |
|------|----------|---------|
| ANALYZING | 25 | 요구조건을 분석하고 있습니다. |
| GENERATING_CODE | 50 | 앱 코드를 생성하고 있습니다. |
| BUILDING | 75 | APK를 빌드하고 있습니다. |
| SUCCESS | 100 | 앱 생성이 완료되었습니다. |

- **수락 기준**:
  - 각 단계 시작 시 DynamoDB 상태가 즉시 갱신된다
  - 앱에서 GET /v1/jobs/{jobId} 호출 시 최신 상태를 확인할 수 있다

### FR-004: S3 입력 다운로드
- **설명**: SQS 메시지의 bucket/key 정보를 사용하여 요구조건 JSON을 다운로드한다
- **Bucket**: `prompton-app-builder-dev-changbin`
- **경로**: `jobs/{jobId}/requirements/requirements.json`
- **수락 기준**:
  - requirements.json을 정상적으로 다운로드하고 파싱할 수 있다
  - S3 접근 실패 시 적절한 에러를 처리한다

### FR-005: Asset 다운로드 (선택적)
- **설명**: 사용자가 첨부한 이미지 에셋을 다운로드한다
- **경로**: `jobs/{jobId}/assets/` 아래 객체 목록 조회
- **지원 형식**: image/png, image/jpeg
- **최대 개수**: 5개
- **수락 기준**:
  - assetsPrefix 아래 객체를 목록 조회하고 다운로드할 수 있다
  - 이미지가 없는 Job도 정상 처리된다

### FR-006: AI 요구조건 분석 및 코드 생성
- **설명**: kiro-cli + Opus5를 사용하여 requirements.json 기반으로 앱 코드를 생성한다
- **입력**: requirements.json, assets (있을 경우)
- **출력**: Android 프로젝트 코드
- **수락 기준**:
  - kiro-cli를 subprocess로 호출하여 코드를 생성할 수 있다
  - 생성된 코드가 빌드 가능한 Android 프로젝트 구조를 가진다

### FR-007: 생성 코드 저장
- **설명**: AI가 생성한 코드/프로젝트를 S3에 저장한다
- **경로**: `jobs/{jobId}/source/` (예: `jobs/{jobId}/source/project.zip`)
- **수락 기준**:
  - 생성된 코드를 S3 source/ 경로에 업로드할 수 있다

### FR-008: APK 빌드
- **설명**: 생성된 Android 프로젝트에 Gradle Wrapper를 생성하고 APK를 빌드한다
- **환경**: EC2에 사전 설치된 Android SDK + Gradle
- **빌드 방식**: 프로젝트별 Gradle Wrapper 생성 후 `./gradlew assembleDebug` 실행
- **출력**: `app-debug.apk`
- **수락 기준**:
  - Gradle Wrapper를 생성할 수 있다
  - assembleDebug 태스크를 실행하여 APK를 빌드할 수 있다
  - 빌드 실패 시 적절한 에러를 반환한다

### FR-009: APK 업로드
- **설명**: 빌드된 APK를 S3 artifact 경로에 업로드한다
- **경로**: `jobs/{jobId}/artifact/app-debug.apk`
- **순서 보장**: APK 업로드 성공 확인 후에만 DynamoDB를 SUCCESS로 변경
- **수락 기준**:
  - APK를 정해진 S3 Key에 업로드할 수 있다
  - 업로드 성공 확인 후 DynamoDB SUCCESS 상태 변경이 수행된다
  - DynamoDB 업데이트 시 `artifactKey` 필드가 포함된다

### FR-010: SQS 메시지 삭제
- **설명**: 모든 작업 정상 완료 후 SQS 메시지를 삭제한다
- **삭제 시점**: DynamoDB SUCCESS 업데이트 완료 후
- **절대 금지**: 메시지 수신 즉시 삭제
- **수락 기준**:
  - 전체 처리 완료 후에만 메시지가 삭제된다
  - 실패 시 메시지를 삭제하지 않는다 (Visibility Timeout 만료 후 재처리 가능)

### FR-011: 실패 처리
- **설명**: 처리 중 오류 발생 시 DynamoDB를 FAILED 상태로 업데이트한다
- **업데이트 필드**: status, message, errorCode
- **ErrorCode 목록**:

| errorCode | 설명 |
|-----------|------|
| REQUIREMENTS_READ_FAILED | requirements.json 읽기 실패 |
| INVALID_REQUIREMENTS | 요구조건 형식 오류 |
| AI_GENERATION_FAILED | AI 코드 생성 실패 |
| BUILD_FAILED | APK 빌드 실패 |
| ARTIFACT_UPLOAD_FAILED | APK S3 업로드 실패 |
| INTERNAL_ERROR | 내부 오류 |

- **수락 기준**:
  - 실패 시 DynamoDB에 FAILED 상태와 적절한 errorCode가 기록된다
  - 실패 시 SQS 메시지를 삭제하지 않는다 (재시도 가능)
  - progress는 마지막 값을 유지한다

### FR-012: Visibility Timeout 연장
- **설명**: AI 생성 + APK 빌드가 Visibility Timeout보다 오래 걸릴 수 있으므로, 장시간 작업 시 ChangeMessageVisibility를 호출하여 타임아웃을 연장한다
- **수락 기준**:
  - 처리 시간이 길어질 경우 주기적으로 Visibility Timeout을 연장한다
  - 동일 Job이 다른 Worker에 의해 중복 처리되지 않는다

### FR-013: 로그 기록
- **설명**: 사용자에게 보여줄 처리 로그를 DynamoDB logs 필드에 업데이트한다
- **형식**: 문자열 배열
- **예시**:
```json
{
  "logs": [
    "[worker] 작업을 시작했습니다.",
    "[llm] 요구조건 분석 완료",
    "[llm] 코드 생성 완료",
    "[gradle] APK 빌드 시작"
  ]
}
```
- **금지 정보**: AWS Access Key, Secret Key, Session Token, Presigned URL, API Key, 사용자 비밀정보
- **수락 기준**:
  - 주요 처리 단계마다 로그가 추가된다
  - 민감 정보가 로그에 포함되지 않는다

---

## 4. 비기능적 요구사항

### NFR-001: 멱등성
- Worker 로직은 동일 Job을 여러 번 수신해도 안전하게 처리할 수 있어야 한다
- jobId 기준으로 DynamoDB 상태를 확인하여 이미 처리된 Job을 건너뛴다

### NFR-002: 장애 복구
- Worker 장애 시 SQS 메시지를 삭제하지 않아 Visibility Timeout 만료 후 재처리가 가능하다
- 최대 3회 실패 시 DLQ(`prompton-app-build-jobs-dlq-dev`)로 이동한다

### NFR-003: IAM 최소 권한
- Access Key를 코드에 저장하지 않는다
- EC2 IAM Role / Instance Profile을 사용한다
- 필요 권한:
  - SQS: ReceiveMessage, DeleteMessage, ChangeMessageVisibility, GetQueueAttributes
  - S3: GetObject (`jobs/*/requirements/*`, `jobs/*/assets/*`), PutObject (`jobs/*/source/*`, `jobs/*/artifact/*`)
  - DynamoDB: GetItem, UpdateItem
  - 기타: kiro-cli 실행에 필요한 권한
- AdministratorAccess를 부여하지 않는다

### NFR-004: 순차 처리
- 동시에 1개의 Job만 처리한다 (단일 프로세스, 순차 처리)

### NFR-005: DLQ 연동
- Main Queue: `prompton-app-build-jobs-dev`
- DLQ: `prompton-app-build-jobs-dlq-dev`
- 최대 수신 횟수: 3 (3회 실패 시 DLQ로 이동)

### NFR-006: 로그 보안
- 로그에 민감 정보(AWS Key, Token, Presigned URL, API Key)를 포함하지 않는다

---

## 5. 처리 시퀀스 (정상 흐름)

```
[1] SQS ReceiveMessage
         |
[2] Message JSON 파싱 → jobId 확보
         |
[3] DynamoDB GetItem(jobId) → 중복 확인
         |
[4] DynamoDB UpdateItem → status = ANALYZING, progress = 25
         |
[5] S3 GetObject → requirements.json 다운로드
         |
[6] S3 ListObjects + GetObject → assets 다운로드 (있을 경우)
         |
[7] kiro-cli + Opus5 → 요구조건 분석
         |
[8] DynamoDB UpdateItem → status = GENERATING_CODE, progress = 50
         |
[9] kiro-cli + Opus5 → 코드 생성
         |
[10] S3 PutObject → 생성 코드 저장 (source/)
         |
[11] DynamoDB UpdateItem → status = BUILDING, progress = 75
         |
[12] Gradle Wrapper 생성 + assembleDebug → APK 빌드
         |
[13] S3 PutObject → APK 업로드 (artifact/app-debug.apk)
         |
[14] S3 업로드 성공 확인
         |
[15] DynamoDB UpdateItem → status = SUCCESS, progress = 100, artifactKey
         |
[16] SQS DeleteMessage
```

---

## 6. 처리 시퀀스 (실패 흐름)

```
[1] ~ [N] 정상 처리 중 오류 발생
         |
[N+1] DynamoDB UpdateItem → status = FAILED, errorCode, message
         |
[N+2] SQS 메시지 삭제하지 않음
         |
[N+3] Visibility Timeout 만료 후 메시지 재가시화
         |
[N+4] 재시도 (최대 3회) 또는 DLQ 이동
```

---

## 7. AWS 리소스 목록

| 리소스 | 이름/ARN | 용도 |
|--------|----------|------|
| SQS Queue | prompton-app-build-jobs-dev | Job 메시지 수신 |
| | ARN: arn:aws:sqs:us-east-1:440052841756:prompton-app-build-jobs-dev | |
| | URL: https://sqs.us-east-1.amazonaws.com/440052841756/prompton-app-build-jobs-dev | |
| SQS DLQ | prompton-app-build-jobs-dlq-dev | 실패 메시지 격리 |
| S3 Bucket | prompton-app-builder-dev-changbin | 입출력 파일 저장 |
| DynamoDB Table | prompton-jobs-dev (PK: jobId) | Job 상태 관리 |

---

## 8. 데이터 모델

### 8.1 SQS Message Schema (입력)
```json
{
  "schemaVersion": "1.0",
  "jobId": "string (UUID)",
  "requirements": {
    "bucket": "string",
    "key": "string"
  },
  "assetsPrefix": "string"
}
```

### 8.2 DynamoDB Job Record (상태 관리)
```json
{
  "jobId": "string (PK)",
  "status": "UPLOAD_PENDING | QUEUED | ANALYZING | GENERATING_CODE | BUILDING | SUCCESS | FAILED | CANCELED",
  "progress": "number (0-100)",
  "message": "string",
  "errorCode": "string (실패 시)",
  "artifactKey": "string (성공 시, 예: jobs/{jobId}/artifact/app-debug.apk)",
  "logs": ["string array"]
}
```

### 8.3 S3 경로 구조
```
jobs/{jobId}/
├── requirements/
│   └── requirements.json        ← 입력 (읽기)
├── assets/
│   ├── 0-logo.png               ← 입력 (읽기, 선택적)
│   └── ...
├── source/
│   └── project.zip              ← 출력 (쓰기)
└── artifact/
    └── app-debug.apk            ← 출력 (쓰기)
```

---

## 9. 미결정 사항

| 항목 | 현재 상태 | 비고 |
|------|-----------|------|
| S3 Client 요청 계약 | 확정 및 Worker 구현 완료 | UTF-8 top-level JSON object, 최대 64 KiB, arbitrary fields 보존 |
| 로그 및 모니터링 수준 | 미정 | 1차 구현 후 결정 가능 |
| kiro-cli 호출 방식 상세 | 2.18.1 `chat --no-interactive` 검증 완료 | `claude-opus-5`, fs_read/fs_write 제한 |
| Hermes prompt refinement | Worker 구현 완료 | v0.20.4 one-shot, host provider/model, 3회 시도, raw Kiro fallback; live provider 검증 필요 |

---

## 10. Worker 완료 체크리스트

- [ ] SQS에서 메시지를 받을 수 있음
- [ ] Message Body에서 jobId를 읽을 수 있음
- [ ] S3에서 requirements.json을 읽을 수 있음
- [ ] assets가 있으면 읽을 수 있음
- [ ] DynamoDB 상태를 ANALYZING으로 변경할 수 있음
- [ ] AI 코드 생성이 가능함 (kiro-cli + Opus5)
- [ ] DynamoDB 상태를 GENERATING_CODE로 변경
- [ ] APK Build 가능 (Gradle Wrapper)
- [ ] DynamoDB 상태를 BUILDING으로 변경
- [ ] APK를 S3 artifact/에 저장
- [ ] DynamoDB 상태를 SUCCESS로 변경
- [ ] artifactKey 저장
- [ ] 정상 완료 후 SQS 메시지 삭제
- [ ] 실패 시 FAILED 상태 기록
- [ ] 실패 시 메시지를 즉시 삭제하지 않음
- [ ] 장시간 처리 시 Visibility Timeout 연장 가능
- [ ] 중복 수신 시 멱등 처리
