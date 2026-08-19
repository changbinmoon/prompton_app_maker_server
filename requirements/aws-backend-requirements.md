# AI App Builder - AWS Backend 요구조건서

## 1. 프로젝트 개요

### 1.1 프로젝트명

AI App Builder Backend

### 1.2 프로젝트 목적

사용자가 Android 애플리케이션 요구조건서를 입력하면 AI가 요구사항을 분석하고 Android 애플리케이션을 설계 및 구현한 뒤 APK 파일을 자동으로 빌드하는 서비스를 개발한다.

완성된 APK는 AWS에 저장하고 사용자가 QR Code를 통해 다운로드할 수 있도록 한다.

본 문서는 이 시스템의 **AWS Backend 및 Infrastructure 구축**을 위한 요구조건을 정의한다.

---

# 2. 최종 사용자 경험

사용자는 다음 과정만 수행하면 앱을 생성할 수 있어야 한다.

```text
요구조건 입력
    ↓
[앱 생성 요청]
    ↓
AI 분석
    ↓
앱 설계
    ↓
Android 코드 생성
    ↓
APK 빌드
    ↓
빌드 검증
    ↓
APK 저장
    ↓
QR Code 제공
    ↓
Android 기기에서 다운로드
```

사용자는 AWS 내부 구조를 알 필요가 없어야 한다.

---

# 3. 전체 시스템 요구사항

AWS Backend는 다음 기능을 제공해야 한다.

1. 앱 생성 요청 접수
2. 요구조건 저장
3. Job 생성
4. 비동기 작업 처리
5. AI 모델 호출
6. Android 프로젝트 생성
7. APK 빌드
8. 빌드 오류 확인
9. 필요 시 코드 수정 및 재빌드
10. APK 저장
11. APK 다운로드 URL 생성
12. QR Code 생성 또는 QR 생성에 사용할 URL 제공
13. Job 진행 상태 조회
14. 시스템 로그 기록

---

# 4. 기본 Architecture

초기 Architecture는 다음 구조를 기준으로 설계한다.

```text
Client
   │
   │ HTTPS
   ▼
API Gateway
   │
   ▼
Lambda
   │
   ├── Job 생성
   ├── 요구사항 저장
   └── SQS Message 생성
   │
   ├──────────────→ DynamoDB
   │                  │
   │                Job Status
   │
   ▼
SQS
   │
   ▼
AI Agent / Worker
   │
   ├────────────→ Amazon Bedrock
   │
   │             AI Model
   │
   ├── Requirements Analysis
   ├── Application Design
   ├── Code Generation
   │
   ▼
CodeBuild
   │
   ├── Android SDK
   ├── JDK
   ├── Gradle
   │
   ▼
APK Build
   │
   ├── 실패 → Build Log → AI Agent → 수정 → 재빌드
   │
   └── 성공
          │
          ▼
          S3
          │
          ├── source
          ├── build log
          └── APK
               │
               ▼
         Presigned URL
               │
               ▼
            QR Code
               │
               ▼
             Client
```

AI Agent / Worker의 구체적인 AWS 실행 환경은 요구사항 분석 및 설계 단계에서 결정한다.

장시간 실행되는 AI Agent 작업을 단순 API Lambda 하나에 모두 구현하지 않는다.

---

# 5. AWS 서비스 요구사항

## 5.1 Amazon API Gateway

외부 Client가 Backend를 호출하기 위한 HTTP API를 제공한다.

최소 다음 API를 제공한다.

### 앱 생성

```text
POST /jobs
```

Request 예:

```json
{
  "requirements": "지렁이 게임 Android 앱을 만들어주세요..."
}
```

Response 예:

```json
{
  "jobId": "abc123",
  "status": "QUEUED"
}
```

### 작업 상태 조회

```text
GET /jobs/{jobId}
```

Response 예:

```json
{
  "jobId": "abc123",
  "status": "BUILDING"
}
```

완료된 경우:

```json
{
  "jobId": "abc123",
  "status": "SUCCESS",
  "downloadUrl": "...",
  "qrUrl": "..."
}
```

---

# 6. Lambda 요구사항

API Gateway에서 전달된 요청을 처리한다.

Lambda의 책임은 짧은 API 처리로 제한한다.

앱 생성 요청을 받으면:

1. 요청 검증
2. Job ID 생성
3. 요구사항 S3 저장
4. DynamoDB Job 생성
5. SQS에 작업 전달
6. Job ID 반환

을 수행한다.

AI 코드 생성과 Android 빌드 전체를 API Lambda 내부에서 수행하지 않는다.

---

# 7. S3 요구사항

S3는 프로젝트 산출물을 저장하는 Artifact Storage 역할을 한다.

Job별로 데이터를 분리한다.

예:

```text
jobs/
└── {jobId}/
    ├── requirements/
    │   └── requirements.md
    │
    ├── design/
    │   └── design.md
    │
    ├── source/
    │   └── source.zip
    │
    ├── logs/
    │   └── build.log
    │
    └── output/
        └── app.apk
```

S3 Bucket은 기본적으로 Public으로 공개하지 않는다.

APK 다운로드는 제한된 시간 동안 사용할 수 있는 Presigned URL 방식으로 제공한다.

---

# 8. DynamoDB 요구사항

DynamoDB는 Job의 상태와 메타데이터를 관리한다.

Primary Key:

```text
jobId
```

최소 데이터:

```json
{
  "jobId": "abc123",
  "status": "BUILDING",
  "createdAt": "...",
  "updatedAt": "...",
  "buildAttempts": 1
}
```

Job 상태는 최소 다음 값을 지원한다.

```text
QUEUED

ANALYZING

DESIGNING

GENERATING_CODE

BUILDING

FIXING

SUCCESS

FAILED
```

---

# 9. SQS 요구사항

앱 생성 요청은 비동기로 처리한다.

API 요청과 실제 앱 생성 작업을 분리한다.

```text
API
 ↓
Lambda
 ↓
SQS
 ↓
Worker
```

Worker가 일시적으로 처리할 수 없는 상황에서도 Job이 유실되지 않도록 설계한다.

실패한 작업 처리를 위한 Dead Letter Queue 사용을 고려한다.

---

# 10. Amazon Bedrock 요구사항

AI 모델은 Amazon Bedrock을 통해 호출한다.

AI는 최소 다음 작업을 수행해야 한다.

### Requirements Analysis

사용자가 제공한 요구사항을 분석한다.

### Application Design

Android 앱 구조를 설계한다.

### Code Generation

Android 프로젝트 코드를 생성한다.

### Error Analysis

Android 빌드가 실패하면 build log를 분석한다.

### Code Fix

빌드 오류를 해결하기 위한 코드 수정을 수행한다.

모델은 특정 모델에 지나치게 결합되지 않도록 추상화한다.

Model ID 또는 inference configuration을 환경 설정으로 변경할 수 있도록 한다.

---

# 11. AI Agent 요구사항

AI Agent는 단일 Prompt → Response 구조가 아닌 workflow 형태로 동작해야 한다.

기본 Workflow:

```text
Requirements
      ↓
Analysis
      ↓
Design
      ↓
Code Generation
      ↓
Build
      ↓
   Success?
   ↙      ↘
 NO        YES
 ↓          ↓
Analyze    APK
Error
 ↓
Fix Code
 ↓
Build Again
```

무한 반복을 방지하기 위해 최대 Build/Fix 횟수를 설정한다.

초기 기본값:

```text
MAX_BUILD_ATTEMPTS = 3
```

최대 횟수 이후에도 실패하면 Job 상태를 `FAILED`로 변경한다.

---

# 12. Android Code Generation 요구사항

초기 MVP에서는 생성 가능한 Android 앱의 범위를 제한한다.

기본 기술 Stack:

```text
Kotlin
Android SDK
Jetpack Compose
Gradle
```

AI가 생성하는 프로젝트는 일반적인 Gradle 기반 Android 프로젝트 구조를 따라야 한다.

최소 다음 명령으로 Debug APK를 생성할 수 있어야 한다.

```bash
./gradlew assembleDebug
```

MVP에서는 복잡한 외부 서비스 연동보다 standalone Android 앱 생성을 우선한다.

---

# 13. CodeBuild 요구사항

AI가 생성한 코드는 격리된 빌드 환경에서 실행한다.

CodeBuild 환경에는 최소 다음 도구가 존재해야 한다.

```text
JDK
Android SDK
Android Build Tools
Gradle 또는 Gradle Wrapper 실행 환경
```

빌드 명령:

```bash
./gradlew assembleDebug
```

빌드 성공 시 APK를 S3에 업로드한다.

빌드 실패 시 build log를 AI Agent가 분석할 수 있도록 저장한다.

---

# 14. APK 요구사항

MVP의 최종 산출물은 다음 파일이다.

```text
app-debug.apk
```

추후 Release Signing 기능을 추가할 수 있도록 설계한다.

MVP에서는 Debug APK 생성 성공을 우선한다.

---

# 15. QR Code 요구사항

빌드 성공 후 APK 다운로드 URL을 생성한다.

```text
S3 APK
   ↓
Presigned URL
   ↓
QR Code
```

QR Code를 스마트폰으로 스캔하면 APK 다운로드가 가능해야 한다.

QR에 S3 내부 주소나 AWS credential 등의 민감한 정보가 포함되어서는 안 된다.

---

# 16. CloudWatch 요구사항

다음 작업에 대한 로그를 확인할 수 있어야 한다.

```text
API 요청

Lambda 실행

AI Agent 실행

Bedrock 호출

CodeBuild 실행

Build 실패

Build 성공
```

각 로그는 가능하면 `jobId`를 포함하여 특정 앱 생성 작업을 추적할 수 있도록 한다.

---

# 17. IAM 및 보안 요구사항

AWS 권한은 Least Privilege 원칙을 따른다.

서비스별 IAM Role을 분리한다.

예:

```text
Lambda Role
 ├── 필요한 S3 접근
 ├── 필요한 DynamoDB 접근
 └── 필요한 SQS 접근

AI Worker Role
 ├── 필요한 S3 접근
 ├── 필요한 DynamoDB 접근
 ├── 필요한 SQS 접근
 └── 필요한 Bedrock 호출

CodeBuild Role
 ├── 필요한 S3 접근
 └── 필요한 Build Artifact 접근
```

모든 서비스에 AdministratorAccess를 부여하는 방식은 사용하지 않는다.

AWS Access Key, Secret Access Key 등의 credential을 source code에 저장하지 않는다.

---

# 18. 생성 코드 실행 보안

사용자의 요구사항을 기반으로 AI가 생성한 코드는 신뢰할 수 없는 코드로 취급한다.

AI가 생성한 Android 코드를 Backend API 서버에서 직접 실행하지 않는다.

빌드 작업은 격리된 build environment에서 수행한다.

Build environment에 불필요한 AWS 권한을 부여하지 않는다.

생성된 코드가 AWS Account 내부의 다른 리소스에 임의로 접근할 수 없도록 설계한다.

---

# 19. Infrastructure as Code

AWS Infrastructure는 수동 Console 설정에만 의존하지 않는다.

Infrastructure as Code 방식으로 관리한다.

AWS 환경에 적합한 다음 기술 중 하나를 설계 단계에서 선정한다.

```text
AWS CDK
AWS SAM
CloudFormation
```

특별한 이유가 없다면 AWS CDK 사용을 우선 검토한다.

Infrastructure Code에는 최소 다음 리소스가 포함되어야 한다.

```text
API Gateway
Lambda
S3
DynamoDB
SQS
Dead Letter Queue
IAM Roles
CloudWatch 관련 설정
CodeBuild
```

Bedrock 사용을 위한 IAM 권한도 Infrastructure Code에서 관리한다.

---

# 20. 환경 분리

환경별 설정을 코드에 직접 하드코딩하지 않는다.

최소 다음 환경을 고려한다.

```text
dev
prod
```

MVP에서는 `dev` 환경부터 구축한다.

Region, Bucket Name, Model ID 등의 값은 환경 설정으로 관리한다.

---

# 21. 비용 관리

본 프로젝트는 초기 PoC/MVP 단계이므로 비용 최소화를 우선한다.

가능하면 요청이 없을 때 지속적으로 서버 비용이 발생하는 구조를 피한다.

초기에는 EC2를 상시 실행하지 않는다.

다음 서비스의 비용을 특히 모니터링한다.

```text
Amazon Bedrock
CodeBuild
S3
CloudWatch
```

AI Agent의 최대 반복 횟수를 제한하여 불필요한 Bedrock 및 CodeBuild 비용 발생을 방지한다.

---

# 22. MVP 범위

1차 MVP의 목표는 다음 흐름을 완성하는 것이다.

```text
Android 요구사항 입력
        ↓
AWS API
        ↓
AI 코드 생성
        ↓
Android Build
        ↓
APK 생성
        ↓
S3 저장
        ↓
Download URL
```

다음 기능은 MVP 이후로 미룰 수 있다.

```text
Google Play Store 배포

Release APK/AAB Signing 자동화

iOS 앱 생성

사용자 로그인

결제

여러 AI 모델 자동 선택

복잡한 Android Native 기능

대규모 동시 사용자 처리
```

---

# 23. 개발 단계

전체 시스템을 한 번에 구현하지 않는다.

## Phase 1 — AWS Connection

목표:

```text
Local Development Environment
        ↓
AWS CLI
        ↓
AWS Account
```

완료 조건:

```bash
aws sts get-caller-identity
```

성공.

---

## Phase 2 — S3 PoC

로컬에서 파일을 S3에 업로드하고 다시 다운로드한다.

완료 조건:

```text
requirements.md
      ↓
     S3
      ↓
download 성공
```

---

## Phase 3 — Bedrock PoC

로컬 프로그램에서 Bedrock 모델을 호출한다.

완료 조건:

```text
Requirements
     ↓
Bedrock
     ↓
AI Response
```

---

## Phase 4 — API PoC

구성:

```text
Client
 ↓
API Gateway
 ↓
Lambda
 ↓
Bedrock
```

완료 조건:

HTTP API를 통해 요구사항을 전달하고 AI 응답을 받을 수 있다.

---

## Phase 5 — Android Build PoC

AI 생성 기능과 분리하여 미리 준비된 Android 프로젝트를 CodeBuild에서 빌드한다.

```text
Android Project
      ↓
CodeBuild
      ↓
APK
      ↓
S3
```

완료 조건:

S3에 `app-debug.apk`가 생성된다.

---

## Phase 6 — AI Code Generation

```text
Requirements
     ↓
Bedrock
     ↓
Android Project
```

완료 조건:

생성된 Android 프로젝트가 로컬 또는 격리된 테스트 환경에서 정상적인 Gradle 프로젝트로 인식된다.

---

## Phase 7 — End-to-End Integration

```text
Requirements
     ↓
AI
     ↓
Code
     ↓
CodeBuild
     ↓
APK
     ↓
S3
```

완료 조건:

하나의 요구사항으로 APK까지 자동 생성된다.

---

## Phase 8 — Async Job Architecture

SQS와 DynamoDB를 추가한다.

```text
POST /jobs
    ↓
Job ID
    ↓
SQS
    ↓
Worker
    ↓
DynamoDB Status
```

완료 조건:

앱 생성 작업이 API 요청과 독립적으로 수행된다.

---

## Phase 9 — QR Delivery

```text
APK
 ↓
Presigned URL
 ↓
QR
 ↓
Android Download
```

완료 조건:

Android 스마트폰으로 QR을 스캔하여 생성된 APK를 다운로드할 수 있다.

---

# 24. Kiro / AI-DLC 개발 지침

본 프로젝트는 AI-DLC workflow를 따른다.

Kiro는 본 요구사항을 받은 즉시 전체 AWS Infrastructure를 생성하거나 배포하지 않는다.

다음 순서를 따른다.

```text
Requirements Analysis
        ↓
Architecture Design
        ↓
사용자 검토
        ↓
Detailed Design
        ↓
사용자 검토
        ↓
Implementation Plan
        ↓
Phase별 Implementation
        ↓
Test
        ↓
Deployment
```

특히 AWS 리소스를 실제 생성하거나 삭제하는 작업은 설계 결과를 먼저 사용자에게 설명하고 검토 후 진행한다.

불명확한 AWS 서비스 선택이나 Architecture 결정은 임의로 확정하지 않고 대안과 Trade-off를 제시한다.

각 Phase가 완료되면 다음 Phase로 넘어가기 전에 완료 조건을 검증한다.

---

# 25. 최종 완료 조건

다음 시나리오가 End-to-End로 성공하면 Backend MVP가 완료된 것으로 판단한다.

```text
1. 사용자가 Android 앱 요구사항 입력

2. POST /jobs

3. Job ID 반환

4. 요구사항 S3 저장

5. AI Agent 작업 시작

6. Bedrock을 이용하여 요구사항 분석

7. Android Architecture 생성

8. Android 코드 생성

9. CodeBuild 실행

10. Gradle Build

11. 빌드 실패 시 제한된 횟수 내에서 수정 시도

12. APK Build 성공

13. APK S3 저장

14. Job Status = SUCCESS

15. Presigned Download URL 생성

16. QR Code 제공

17. Android 스마트폰에서 APK 다운로드
```

이 전체 과정에서 AWS credential이 source code 또는 사용자에게 노출되어서는 안 된다.

모든 주요 작업은 `jobId`를 기준으로 추적할 수 있어야 한다.
