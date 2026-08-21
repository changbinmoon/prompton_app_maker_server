# User Stories - Status API Migration

## 문서 개요

- **Persona**: `P-01 Worker 운영자`
- **External beneficiary**: `B-01 Mobile App 사용자`
- **구성**: User journey + reliability/authentication/observability Hybrid
- **Story 수**: 7
- **Acceptance criteria**: 핵심 흐름은 Given/When/Then, 설정·보안·품질은 checklist
- **Traceability**: `story-traceability.md`

## US-SA-01: Status API 기반 Worker 배포 구성

**Persona**: P-01 Worker 운영자<br>
**External beneficiary outcome**: B-01이 Backend를 통해 상태를 받을 수 있는 Worker 경계가 준비된다.<br>
**Requirements**: FR-SA-001, FR-SA-003, FR-SA-015, FR-SA-017, FR-SA-018, NFR-SA-001

### User Story

As a Worker 운영자,<br>
I want Worker를 DynamoDB 직접 접근 없이 Backend Status API 설정으로 배포하고 싶다,<br>
So that 상태 저장소의 계정과 테이블 권한에 의존하지 않고 명확한 서비스 경계로 운영할 수 있다.

### Acceptance Criteria

- [ ] `PROMPTON_API_BASE_URL`은 필수 설정이며 빈 값이면 Worker가 fail-fast 한다.
- [ ] `SQS_QUEUE_URL`과 `S3_BUCKET_NAME`은 필수 설정으로 유지된다.
- [ ] `DYNAMODB_TABLE_NAME`은 Config, 배포 환경 예제 및 시작 로그에서 제거된다.
- [ ] Worker runtime에는 DynamoDB GetItem, UpdateItem 또는 Table resource 생성 경로가 없다.
- [ ] 상태 호출은 AI, Build, S3 및 SQS 로직과 분리된 Status API client를 통한다.
- [ ] `requests==2.34.2`가 직접 runtime dependency로 고정되고 frozen install이 가능하다.
- [ ] DynamoDB 전용 test extra와 stub은 다른 사용처가 없으면 제거되며 boto3 SQS/S3 지원은 유지된다.
- [ ] Worker IAM에서 DynamoDB 권한을 요구하지 않고 기존 SQS/S3 최소 권한만 유지한다.

### Verification

Config 단위 테스트, import/source scan, dependency lock 검사 및 배포 환경 검증으로 확인한다.

## US-SA-02: 처리 단계 상태 전달

**Persona**: P-01 Worker 운영자<br>
**External beneficiary outcome**: B-01이 분석, 코드 생성 및 빌드 진행 상태를 확인할 수 있다.<br>
**Requirements**: FR-SA-001, FR-SA-004, FR-SA-005, FR-SA-006, FR-SA-012

### User Story

As a Worker 운영자,<br>
I want 실제 Job 단계가 시작될 때 표준 상태와 progress를 Backend에 전달하고 싶다,<br>
So that 처리 중인 Job의 진행 상황을 운영 및 사용자 채널에서 일관된 의미로 해석할 수 있다.

### Acceptance Criteria

#### Scenario 1: 분석 시작

- **Given** Worker가 유효한 SQS Job 처리를 시작했고
- **When** requirements 분석 단계에 진입하면
- **Then** `ANALYZING`, progress `25`, message `요구조건을 분석하고 있습니다.`를 PATCH한다.

#### Scenario 2: 코드 생성 시작

- **Given** requirements와 선택적 assets 처리가 완료됐고
- **When** Hermes/Kiro 코드 생성 단계에 진입하면
- **Then** `GENERATING_CODE`, progress `50`, message `Android 코드를 생성하고 있습니다.`를 PATCH한다.

#### Scenario 3: APK 빌드 시작

- **Given** Android 프로젝트 코드 생성이 완료됐고
- **When** Gradle APK 빌드 단계에 진입하면
- **Then** `BUILDING`, progress `75`, message `APK를 빌드하고 있습니다.`를 PATCH한다.

#### Scenario 4: 중간 상태 API 실패

- **Given** ANALYZING, GENERATING_CODE 또는 BUILDING PATCH가 최종 실패했고
- **When** 해당 실패가 Status API client에서 반환되면
- **Then** Worker는 warning을 기록하고 현재 AI/Build 흐름을 계속한다.

- [ ] 모든 2xx는 응답 본문 유무와 관계없이 해당 상태 전달 성공으로 처리한다.
- [ ] 각 payload는 상태, progress 및 message를 하나의 JSON 요청에 포함한다.

### Verification

Orchestrator mock 테스트로 호출 순서, 정확한 payload 및 중간 상태 실패 후 처리 지속을 검증한다.

## US-SA-03: 검증된 완료와 SQS 메시지 삭제

**Persona**: P-01 Worker 운영자<br>
**External beneficiary outcome**: B-01이 SUCCESS를 볼 때 다운로드 가능한 APK가 존재한다.<br>
**Requirements**: FR-SA-007, FR-SA-012

### User Story

As a Worker 운영자,<br>
I want 검증된 APK artifact와 Backend SUCCESS 반영이 모두 완료된 뒤에만 SQS 메시지를 삭제하고 싶다,<br>
So that 완료 상태가 실제 산출물과 일치하고 Job 메시지가 조기에 유실되지 않는다.

### Acceptance Criteria

#### Scenario 1: 정상 완료

- **Given** APK 빌드가 성공했고
- **When** Worker가 APK를 `jobs/{jobId}/artifact/app-debug.apk`에 업로드한 뒤 HeadObject와 파일 크기로 검증하면
- **Then** `SUCCESS`, progress `100`, message `앱 생성이 완료되었습니다.`, 해당 `artifactKey`를 PATCH한다.
- **And** SUCCESS PATCH가 2xx를 반환한 뒤에만 SQS DeleteMessage를 호출한다.

#### Scenario 2: artifact 업로드 또는 검증 실패

- **Given** APK 빌드는 성공했지만
- **When** S3 업로드 또는 업로드 후 검증이 실패하면
- **Then** SUCCESS PATCH와 SQS DeleteMessage를 호출하지 않는다.

#### Scenario 3: SUCCESS 반영 실패

- **Given** S3 artifact 검증이 성공했고
- **When** SUCCESS PATCH가 허용된 처리 후에도 성공하지 못하면
- **Then** Job 완료를 실패로 처리하고 SQS 메시지를 삭제하지 않는다.

- [ ] source 업로드 결과는 APK artifact 검증 및 SUCCESS 순서를 변경하지 않는다.
- [ ] 자동 테스트는 SUCCESS 호출과 SQS 삭제의 선후 관계를 검증한다.

### Verification

호출 기록 fake를 사용한 orchestrator 테스트와 실제 dev Job의 S3 metadata, Backend GET 및 SQS 상태 증적으로 확인한다.

## US-SA-04: 안전한 실패 상태 보고

**Persona**: P-01 Worker 운영자<br>
**External beneficiary outcome**: B-01이 내부 상세정보 없이 이해 가능한 실패 상태를 확인할 수 있다.<br>
**Requirements**: FR-SA-008, FR-SA-012

### User Story

As a Worker 운영자,<br>
I want 복구할 수 없는 Job 오류를 표준 message와 errorCode로 best-effort 보고하고 싶다,<br>
So that 실패 원인을 안전하게 전달하면서 SQS의 재시도와 DLQ 동작을 보존할 수 있다.

### Acceptance Criteria

#### Scenario 1: 처리 단계 실패

- **Given** requirements, AI 생성, Gradle 빌드 또는 artifact 업로드 중 복구 불가능한 오류가 발생했고
- **When** Worker가 예외를 분류하면
- **Then** `FAILED`, 안전한 사용자 message 및 해당 errorCode를 PATCH한다.
- **And** FAILED payload에는 `progress`를 포함하지 않는다.
- **And** SQS 메시지를 삭제하지 않는다.

#### Scenario 2: FAILED 보고 실패

- **Given** 원래 Job 처리가 실패했고
- **When** FAILED PATCH도 성공하지 못하면
- **Then** Worker는 FAILED 보고 오류를 기록하되 원래 예외와 errorCode를 보존한다.
- **And** SQS 메시지를 삭제하지 않는다.

#### Scenario 3: SUCCESS PATCH 최종 실패

- **Given** artifact는 검증됐지만 SUCCESS PATCH가 최종 실패했고
- **When** Worker가 완료 실패를 처리하면
- **Then** `INTERNAL_ERROR`로 FAILED 보고를 best-effort 시도한다.

- [ ] errorCode는 승인된 6개 값 중 하나다.
- [ ] message에는 stack trace, 내부 경로, credential, token 또는 사용자 비밀정보가 없다.

### Verification

오류 유형별 orchestrator 단위 테스트로 payload, progress 부재, 원래 오류 보존 및 SQS 미삭제를 검증한다.

## US-SA-05: 예측 가능한 HTTP 오류 처리

**Persona**: P-01 Worker 운영자<br>
**External beneficiary outcome**: 상태 전달 장애가 일관된 정책으로 처리돼 사용자 결과의 원인을 설명할 수 있다.<br>
**Requirements**: FR-SA-003, FR-SA-009, FR-SA-010, FR-SA-011, TR-SA-001

### User Story

As a Worker 운영자,<br>
I want Status API의 HTTP 결과와 timeout을 고정된 정책으로 처리하고 싶다,<br>
So that 일시적 Backend 장애와 요청 오류의 시도 횟수 및 처리 시간을 예측할 수 있다.

### Acceptance Criteria

#### Scenario 1: 5xx 응답

- **Given** Status API가 5xx를 반환하고
- **When** client가 요청을 처리하면
- **Then** 최초 요청을 포함해 최대 3회 시도한다.
- **And** 첫 실패 후 1초, 두 번째 실패 후 2초 대기한다.

#### Scenario 2: 4xx 응답

- **Given** Status API가 4xx를 반환하고
- **When** client가 응답을 판정하면
- **Then** 추가 요청 없이 즉시 실패를 반환한다.

#### Scenario 3: 연결 오류 또는 timeout

- **Given** 연결 오류, connect timeout 또는 read timeout이 발생하고
- **When** client가 예외를 처리하면
- **Then** 재시도 없이 실패를 반환한다.

- [ ] requests timeout은 connect `3`초, read `10`초 tuple로 전달된다.
- [ ] 모든 2xx는 성공이고 응답 JSON parsing은 성공 조건이 아니다.
- [ ] 단위 테스트는 시도 횟수, sleep sequence 및 무재시도 조건을 검증한다.

### Verification

HTTP session fake와 sleep recorder를 사용한 결정적 단위 테스트로 확인한다.

## US-SA-06: 인증과 관측성 보호

**Persona**: P-01 Worker 운영자<br>
**External beneficiary outcome**: 상태 전달 인증이 추가돼도 B-01의 상태 흐름이 credential 노출 없이 유지된다.<br>
**Requirements**: FR-SA-002, FR-SA-015, FR-SA-016, FR-SA-017, NFR-SA-002, NFR-SA-003, TR-SA-001

### User Story

As a Worker 운영자,<br>
I want 선택적 API 인증과 Status API 로그를 안전하게 운영하고 싶다,<br>
So that credential을 노출하지 않고 상태 전달 장애를 진단할 수 있다.

### Acceptance Criteria

- [ ] `PROMPTON_STATUS_API_KEY`가 없거나 비어 있으면 `x-api-key` Header를 보내지 않는다.
- [ ] API Key가 설정되면 해당 값을 `x-api-key` Header에만 추가한다.
- [ ] API Key는 소스, 예외, stdout, stderr 및 journald에 기록되지 않는다.
- [ ] HTTPS 인증서 검증을 비활성화하지 않는다.
- [ ] EC2 환경은 API Gateway endpoint에 TCP 443 outbound 통신이 가능하다.
- [ ] 환경 파일은 0640 이하이며 API Key를 저장소에 포함하지 않는다.
- [ ] journald에는 PATCH 상태, 성공/실패, 시도 횟수, 5xx retry 및 최종 Job errorCode를 기록한다.
- [ ] raw Client JSON, Hermes stdout/stderr, AWS credential, signed URL 및 전체 Backend 민감 응답을 로그에 남기지 않는다.
- [ ] DynamoDB `logs` 배열 갱신 경로가 제거되고 사용자에게는 Status API의 최신 message만 전달된다.

### Verification

Header 생성, log capture, TLS 기본값, 환경 예제 및 secret pattern scan으로 검증한다.

## US-SA-07: 자동 계약 및 공동 E2E 검증

**Persona**: P-01 Worker 운영자<br>
**External beneficiary outcome**: B-01이 Mobile App에서 Worker가 전달한 최종 상태와 artifact를 동일하게 확인한다.<br>
**Requirements**: TR-SA-003, TR-SA-004

### User Story

As a Worker 운영자,<br>
I want Worker 자동 테스트와 승인된 dev Job의 공동 E2E 증적을 확보하고 싶다,<br>
So that Status API migration이 Worker, Backend 및 Mobile 상태 흐름을 깨뜨리지 않았음을 입증할 수 있다.

### Acceptance Criteria

#### Scenario 1: Worker 자동 검증

- **Given** Status API migration 변경이 준비됐고
- **When** Worker 품질 게이트를 실행하면
- **Then** 전체 pytest, Ruff, mypy strict, compileall, lock check 및 frozen sync가 통과한다.
- **And** systemd unit과 필수 환경 설정 검증이 통과한다.

#### Scenario 2: 공동 dev E2E

- **Given** 승인된 dev Job과 Backend/Mobile 검증 참여자가 준비됐고
- **When** Worker가 실제 Job을 처리하면
- **Then** Backend GET에서 ANALYZING, GENERATING_CODE, BUILDING 및 SUCCESS 결과를 확인한다.
- **And** SUCCESS의 artifactKey가 S3의 검증된 APK와 일치한다.
- **And** Mobile App에서 최종 상태와 artifact 결과를 동일하게 확인한다.
- **And** SUCCESS 반영 후 SQS 메시지 삭제를 확인한다.

- [ ] Worker 저장소는 Status client 및 orchestrator mock/contract 자동 테스트 증적을 제공한다.
- [ ] Backend GET 검증과 Mobile 화면 확인은 공동 E2E acceptance로 기록한다.
- [ ] Mobile App 또는 Backend 구현 코드는 Worker story 범위에 포함하지 않는다.
- [ ] 테스트 증적에는 commit SHA, UTC 시각, sanitized 로그, HTTP 결과, S3 metadata 및 APK SHA-256이 포함된다.

### Verification

자동 품질 게이트 보고서와 승인된 dev E2E 증적 묶음으로 확인한다.

## Story 범위 참고

승인된 requirements 중 story 본문에 반복하지 않도록 선택된 항목은 `story-traceability.md`의 Requirements-Only References를 따른다.
