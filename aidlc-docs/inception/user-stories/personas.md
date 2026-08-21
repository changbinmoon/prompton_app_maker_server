# Personas - Status API Migration

## 문서 목적

Status API 전환 User Stories에서 사용할 사람 중심 관점과 시스템 경계를 정의한다. 승인된 Story Plan에 따라 정식 persona는 Worker 운영자 1개이며, Mobile App 사용자는 external beneficiary로만 표현한다.

## Persona P-01: Worker 운영자

### 역할

Prompton AI Worker의 배포, 설정, 실행 상태, Job 처리 결과 및 장애를 운영 환경에서 관리하는 담당자다. Backend 및 Mobile 팀과 함께 dev E2E 결과를 확인하지만, Backend API나 Mobile App 코드를 직접 구현하는 역할은 아니다.

### 목표

- Worker가 DynamoDB 권한 없이 Backend Status API로 상태를 전달하도록 운영한다.
- Job의 실제 처리 단계와 Backend/Mobile에 노출되는 상태가 계약대로 연결되는지 확인한다.
- APK가 S3에 검증된 후에만 SUCCESS가 반영되고 SQS 메시지가 삭제되는지 보장한다.
- Status API 장애가 AI/Build 처리 및 SQS 재시도 정책에 미치는 영향을 예측할 수 있어야 한다.
- API Key가 도입돼도 자격증명이 로그나 저장소에 노출되지 않도록 한다.
- journald와 자동 테스트 증적으로 실패 원인과 재시도 결과를 판단한다.

### 동기

- Cross-account DynamoDB 권한과 테이블 관리 의존성을 제거하고 운영 경계를 단순화한다.
- Mobile App 사용자가 보는 상태와 실제 Worker 처리 결과의 신뢰성을 유지한다.
- 반복 장애, orphan artifact 또는 메시지 조기 삭제로 인한 운영 사고를 방지한다.
- 변경 후에도 기존 AI 생성, Gradle 빌드, S3 및 SQS 처리에 회귀가 없음을 입증한다.

### 주요 작업

- `PROMPTON_API_BASE_URL`과 선택적 API Key를 안전하게 배포 설정에 반영한다.
- Worker 로그에서 상태 PATCH 성공, 실패, retry 및 최종 Job 결과를 확인한다.
- 4xx, 5xx, 연결 오류 및 timeout 시나리오가 승인된 정책대로 처리되는지 검증한다.
- SUCCESS 2xx와 SQS DeleteMessage 호출 순서를 확인한다.
- Worker mock/contract 테스트 결과와 승인된 dev Job E2E 증적을 수집한다.
- Backend GET 결과와 Mobile App 표시 상태를 Backend/Mobile 담당자와 공동 확인한다.
- Worker에서 DynamoDB 직접 접근과 관련 IAM 의존성이 제거됐는지 검사한다.

### Pain Points

- 중간 상태 PATCH가 best-effort이므로 실제 진행 단계와 사용자 표시 상태가 잠시 다를 수 있다.
- SUCCESS PATCH 실패 시 APK는 존재하지만 완료 상태가 반영되지 않는 상황을 진단해야 한다.
- SQS 재전달로 비용이 큰 Hermes, Kiro 및 Gradle 처리가 반복될 수 있다.
- Status API, S3, SQS, AI provider 및 Android build 결과가 여러 로그와 시스템에 분산돼 있다.
- 인증이 추후 추가되면 API Key 배포와 masking을 별도로 관리해야 한다.

### 성공 기준

- Worker 프로세스와 IAM 정책에 DynamoDB 직접 접근이 없다.
- 모든 상태 payload, HTTP timeout 및 retry 규칙이 자동 테스트로 증명된다.
- SUCCESS 2xx 전에 SQS 메시지가 삭제되지 않는다.
- 처리 실패 시 FAILED를 best-effort로 전달하고 메시지를 보존한다.
- API Key와 민감한 Backend 응답이 소스나 journald에 노출되지 않는다.
- 승인된 dev Job에서 Backend GET과 Mobile App이 Worker가 전송한 최종 상태 및 artifactKey를 동일하게 표시한다.
- 전체 회귀 품질 게이트와 공동 E2E acceptance가 통과한다.

### 기술 숙련도와 작업 환경

- Linux, systemd, journald, AWS CLI 및 Python 서비스 운영에 익숙하다.
- SQS Visibility Timeout, DLQ, S3 object key 및 API Gateway HTTP 응답을 이해한다.
- EC2 Worker 환경에서 dev/test 검증을 수행하며 production activation은 별도 승인을 따른다.

## External Beneficiary B-01: Mobile App 사용자

Mobile App 사용자는 이 변경의 결과를 받는 beneficiary지만 정식 story persona는 아니다.

### 기대 결과

- 앱 생성 단계가 Mobile App에 이해 가능한 상태와 progress로 표시된다.
- SUCCESS 상태에서 실제로 다운로드 가능한 artifact가 존재한다.
- 실패 시 안전한 사용자 메시지와 errorCode를 확인할 수 있다.

### Story 표현 방식

- 모든 story의 actor는 Worker 운영자다.
- Mobile App 사용자의 결과는 `External beneficiary outcome` 또는 공동 E2E acceptance로만 표현한다.
- Mobile App UI 또는 client 구현 task는 생성하지 않는다.

## 시스템 및 팀 경계

| 대상 | 분류 | 이번 Worker 변경의 책임 |
|---|---|---|
| EC2 AI Worker | 대상 시스템 | Status PATCH, AI/Build, S3/SQS lifecycle 구현 |
| Backend Status API | 외부 시스템 dependency | PATCH 수신, 상태 저장, 반복 요청 처리 |
| Backend GET API | E2E 검증 dependency | 저장된 Job 상태 조회 제공 |
| Mobile App | 외부 consumer | Backend 상태 표시; 구현은 범위 밖 |
| Backend/Mobile 담당자 | 공동 검증 참여자 | 승인된 dev Job의 GET 및 화면 결과 확인 |
| DynamoDB | Backend 내부 저장소 | Worker 직접 접근 금지 |

## Persona 사용 규칙

- User Stories는 `P-01 Worker 운영자`에 매핑한다.
- Mobile App 사용자는 persona 수에 포함하지 않는다.
- 외부 시스템을 사람 persona처럼 표현하지 않는다.
- Worker 범위 밖 작업은 dependency 또는 E2E acceptance로 구분한다.
