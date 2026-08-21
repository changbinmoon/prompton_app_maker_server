# Prompton Worker Status API 전환 요구사항

## 문서 상태

- **상태**: 검토 대기
- **요청 유형**: 기존 기능의 통합 방식 변경 및 리팩터링
- **프로젝트 유형**: Brownfield
- **범위**: Worker 상태 관리, 설정, 배포, 테스트 및 운영 문서
- **복잡도**: Moderate
- **우선순위**: 이 문서는 기존 요구사항의 DynamoDB 직접 접근 관련 조항보다 우선한다.

## 1. 목적

EC2 AI Worker의 DynamoDB 직접 접근을 제거하고, 모든 Job 상태 변경을 Backend Status API를 통해 수행한다. Backend는 API Gateway와 Lambda를 통해 DynamoDB를 관리하며 Mobile App은 Backend 조회 API를 통해 상태를 확인한다.

Worker의 상태 관리 책임은 다음으로 제한한다.

1. Job 처리 단계에 맞는 PATCH payload 생성
2. Status API 호출 및 HTTP 응답 판정
3. 정해진 5xx 재시도 수행
4. 필수 SUCCESS 반영 후 SQS 메시지 삭제
5. API Key가 설정된 경우 인증 Header 추가

## 2. 확정 결정 요약

| 항목 | 확정 결정 |
|---|---|
| DynamoDB 직접 접근 | 완전 제거 |
| Worker의 GET 호출 | 호출하지 않음 |
| 중복 SQS 전달 | 매번 처음부터 전체 재처리 |
| 중간 상태 PATCH | best-effort |
| SUCCESS PATCH | 필수 |
| FAILED PATCH | best-effort |
| SUCCESS 실패 후 SQS 삭제 | 삭제하지 않음 |
| 5xx 재시도 | 최초 호출 포함 3회, 1초와 2초 대기 |
| 4xx 재시도 | 하지 않음 |
| 연결 오류와 timeout 재시도 | 하지 않음 |
| HTTP timeout | connect 3초, read 10초 |
| 성공 응답 | 본문과 관계없이 모든 2xx |
| FAILED progress | payload에서 생략 |
| 사용자 처리 로그 | DynamoDB 누적 제거, journald만 유지 |
| 현재 인증 | 인증 없음 |
| 향후 인증 | `PROMPTON_STATUS_API_KEY`를 `x-api-key`로 전송 |
| HTTP client | `requests==2.34.2` |

## 3. 시스템 경계

### 3.1 Worker가 수행하는 작업

- SQS Job 수신
- S3 requirements와 asset 다운로드
- Hermes prompt refinement
- Kiro Android 코드 생성
- Gradle APK 빌드
- S3 source와 APK 업로드
- Backend Status API PATCH 호출
- 정상 완료 후 SQS 메시지 삭제

### 3.2 Worker가 수행하지 않는 작업

- DynamoDB GetItem 또는 UpdateItem
- Job 상태 확인을 위한 GET API 호출
- DynamoDB `logs` 배열 갱신
- Mobile App 상태 조회
- Backend API Gateway, Lambda 또는 DynamoDB 구현

## 4. Status API 계약

### FR-SA-001: Endpoint

- **Method**: PATCH
- **Base URL 환경변수**: `PROMPTON_API_BASE_URL`
- **기본 배포값**: `https://xb2z5ls8k0.execute-api.us-east-1.amazonaws.com`
- **Path**: `/v1/jobs/{jobId}/status`
- **Content-Type**: `application/json`
- Base URL의 마지막 `/` 유무와 관계없이 URL에 중복 `/`가 생기지 않아야 한다.
- `jobId`는 기존 SQS parsing 단계에서 검증된 UUID를 사용한다.

### FR-SA-002: Header 확장성과 인증

기본 Header는 다음과 같다.

```json
{
  "Content-Type": "application/json"
}
```

`PROMPTON_STATUS_API_KEY`가 비어 있지 않으면 다음 Header를 추가한다.

```json
{
  "x-api-key": "<PROMPTON_STATUS_API_KEY>"
}
```

API Key 값은 소스, 예외 메시지, stdout, stderr, journald에 기록하지 않는다. 이후 다른 인증 방식이 추가될 수 있도록 Header 생성 로직은 Status API client 내부에 캡슐화한다.

### FR-SA-003: Status client 인터페이스

Status API 호출은 AI, S3, SQS 및 Build 로직과 분리된 client로 구현한다.

```python
update_job_status(
    job_id,
    status,
    progress=None,
    message=None,
    artifact_key=None,
    error_code=None,
)
```

client는 JSON 직렬화, Header 구성, timeout, HTTP 호출, 재시도, 상태 코드 판정 및 안전한 로깅을 담당한다.

## 5. 상태별 요청

### FR-SA-004: ANALYZING

SQS Job의 실제 처리를 시작할 때 호출한다.

```json
{
  "status": "ANALYZING",
  "progress": 25,
  "message": "요구조건을 분석하고 있습니다."
}
```

### FR-SA-005: GENERATING_CODE

Hermes refinement와 Kiro 코드 생성 단계를 시작하기 전에 호출한다.

```json
{
  "status": "GENERATING_CODE",
  "progress": 50,
  "message": "Android 코드를 생성하고 있습니다."
}
```

### FR-SA-006: BUILDING

Gradle APK 빌드를 시작하기 전에 호출한다.

```json
{
  "status": "BUILDING",
  "progress": 75,
  "message": "APK를 빌드하고 있습니다."
}
```

### FR-SA-007: SUCCESS

APK 빌드, S3 업로드 및 업로드 검증이 모두 성공한 후 호출한다.

```json
{
  "status": "SUCCESS",
  "progress": 100,
  "message": "앱 생성이 완료되었습니다.",
  "artifactKey": "jobs/{jobId}/artifact/app-debug.apk"
}
```

처리 순서는 반드시 다음을 따른다.

1. APK 빌드 성공
2. S3 artifact 업로드
3. S3 `HeadObject`와 크기 비교를 통한 업로드 성공 검증
4. SUCCESS PATCH 호출
5. SUCCESS PATCH 2xx 확인
6. SQS 메시지 삭제

SUCCESS PATCH가 최종 실패하면 SQS 메시지를 삭제하지 않는다.

### FR-SA-008: FAILED

복구할 수 없는 처리 오류가 발생하면 best-effort로 호출한다.

```json
{
  "status": "FAILED",
  "message": "APK 빌드에 실패했습니다.",
  "errorCode": "BUILD_FAILED"
}
```

- `progress`는 전송하지 않으며 Backend가 마지막 값을 유지한다.
- FAILED PATCH 실패는 원래 처리 오류를 대체하거나 숨기지 않는다.
- FAILED PATCH 성공 여부와 관계없이 처리에 실패한 SQS 메시지는 삭제하지 않는다.
- errorCode는 다음 값만 사용한다.
  - `REQUIREMENTS_READ_FAILED`
  - `INVALID_REQUIREMENTS`
  - `AI_GENERATION_FAILED`
  - `BUILD_FAILED`
  - `ARTIFACT_UPLOAD_FAILED`
  - `INTERNAL_ERROR`
- SUCCESS PATCH 자체의 최종 실패는 Worker 내부에서 `INTERNAL_ERROR`로 분류하여 FAILED 보고를 시도한다.

## 6. HTTP 처리 정책

### FR-SA-009: 응답 판정

| 결과 | 처리 |
|---|---|
| 모든 2xx | 성공, 응답 본문은 필수가 아님 |
| 모든 4xx | 재시도 없이 실패 처리 |
| 모든 5xx | 제한된 재시도 수행 |
| 연결 오류 | 재시도 없이 실패 처리 |
| connect/read timeout | 재시도 없이 실패 처리 |

응답 본문은 성공 판정에 사용하지 않는다. 오류 로깅이 필요하면 길이를 제한하고 민감정보 필터링을 적용하며 API Key나 전체 Backend 응답을 그대로 기록하지 않는다.

### FR-SA-010: 5xx 재시도

- 최초 호출을 포함해 최대 3회 시도한다.
- 첫 번째 실패 후 1초 대기한다.
- 두 번째 실패 후 2초 대기한다.
- 세 번째 실패 후 최종 실패로 반환한다.
- 4xx, 연결 오류 및 timeout에는 이 재시도를 적용하지 않는다.

### FR-SA-011: Timeout

`requests` 호출은 다음 timeout을 사용한다.

- connect timeout: 3초
- read timeout: 10초

### FR-SA-012: 단계별 치명도

| 상태 | 최종 API 실패 시 Worker 동작 |
|---|---|
| ANALYZING | warning 기록 후 AI/Build 처리 계속 |
| GENERATING_CODE | warning 기록 후 AI/Build 처리 계속 |
| BUILDING | warning 기록 후 Build 처리 계속 |
| FAILED | error 기록 후 원래 실패 흐름 유지, SQS 삭제 안 함 |
| SUCCESS | Job 완료 실패로 처리, SQS 삭제 안 함 |

## 7. SQS 재전달과 멱등성

### FR-SA-013: GET 미사용

Worker는 `GET /v1/jobs/{jobId}`를 호출하지 않는다. 기존 DynamoDB 상태 조회와 terminal status skip 로직을 제거한다.

### FR-SA-014: 전체 재처리

동일 SQS 메시지가 재전달되거나 Worker가 재시작하면 Job을 처음부터 다시 처리한다.

- 기존 `/data/jobs/{jobId}` 디렉터리를 삭제하고 재생성한다.
- requirements와 assets를 다시 다운로드한다.
- Hermes, Kiro 및 Gradle을 다시 실행한다.
- source와 artifact를 같은 S3 key에 다시 업로드할 수 있다.
- 각 상태 PATCH가 반복될 수 있다.

Backend는 다음을 보장해야 한다.

- 동일 상태 PATCH가 반복되어도 안전해야 한다.
- 재처리로 `ANALYZING`부터 상태 PATCH가 다시 전송될 수 있음을 허용해야 한다.
- 이미 반영된 SUCCESS에 동일한 SUCCESS payload가 다시 전달되면 2xx를 반환해야 한다.

Worker가 GET을 사용하지 않으므로 SUCCESS 반영 후 SQS 삭제만 실패한 경우에도 전체 AI 생성과 빌드가 다시 수행될 수 있다. 이 비용과 지연은 확정된 정책에 따른 수용된 위험이다.

## 8. 로그와 관측성

### FR-SA-015: DynamoDB 로그 제거

기존 `DynamoClient.append_log()`와 DynamoDB `logs` 배열 갱신을 제거한다. 별도의 Backend log API는 이번 범위에 포함하지 않는다.

### FR-SA-016: journald 로그

다음 이벤트는 Python logging을 통해 journald에 남긴다.

- 상태 PATCH 성공 또는 실패
- HTTP status class와 시도 횟수
- 5xx 재시도
- 단계 시작과 완료
- 최종 Job 성공 또는 오류 코드

로그에는 API Key, Client raw JSON, Hermes stdout/stderr, AWS 자격증명, signed URL 및 Backend 민감 응답을 포함하지 않는다.

## 9. 설정 및 dependency

### FR-SA-017: 환경변수

필수 환경변수:

- `SQS_QUEUE_URL`
- `S3_BUCKET_NAME`
- `PROMPTON_API_BASE_URL`

선택 환경변수:

- `PROMPTON_STATUS_API_KEY`
- 기존 `AWS_REGION`, `WORK_DIR`, `VISIBILITY_TIMEOUT`, `CLEANUP_HOURS`, `LOG_LEVEL`, tool path 변수

`DYNAMODB_TABLE_NAME`은 제거한다.

### FR-SA-018: HTTP dependency

- `requests==2.34.2`를 직접 runtime dependency로 선언한다.
- lock file을 갱신하고 frozen install 검증을 수행한다.
- DynamoDB 전용 boto3 stub과 moto dependency feature는 다른 사용처가 없으면 제거한다.
- boto3는 SQS와 S3 때문에 유지한다.

## 10. IAM 및 네트워크

### NFR-SA-001: IAM 최소 권한

Worker IAM 정책에서 DynamoDB `GetItem`과 `UpdateItem` 권한을 제거한다. SQS와 S3 최소 권한은 유지한다.

Status API가 현재 인증 없는 HTTPS endpoint이므로 추가 AWS IAM API 권한은 요구하지 않는다.

### NFR-SA-002: TLS와 egress

- HTTPS 인증서 검증을 비활성화하지 않는다.
- EC2에서 API Gateway endpoint로 TCP 443 outbound 통신이 가능해야 한다.
- proxy 또는 방화벽이 있다면 endpoint 접근을 허용해야 한다.

### NFR-SA-003: Secret 관리

- API Key가 도입되면 `/etc/prompton-worker/env` 또는 승인된 secret injection 방식으로 제공한다.
- 환경 파일 권한은 0640 이하를 유지한다.
- API Key를 소스 저장소에 저장하지 않는다.

## 11. 코드 변경 범위

| 영역 | 변경 |
|---|---|
| Status client | 신규 HTTP client 모듈과 예외 추가 |
| Orchestrator | DynamoClient 의존성을 StatusApiClient로 교체 |
| 중복 방지 | GET/DynamoDB terminal check 제거 |
| 상태 갱신 | PATCH payload와 단계별 치명도 적용 |
| 로그 | DynamoDB append 제거, journald로 전환 |
| Config | API URL/key 추가, DynamoDB table 제거 |
| Main | Table 로그 제거, API base 정보 추가 |
| Dependencies | requests 직접 pin, DynamoDB test extras 정리 |
| Deployment | env.example과 운영 지침 갱신 |
| Tests | DynamoDB tests 제거, Status API client와 orchestrator HTTP 정책 테스트 추가 |

## 12. 테스트 요구사항

### TR-SA-001: Status client 단위 테스트

다음을 검증한다.

- URL 결합과 JSON payload
- API Key 미설정/설정 Header
- 모든 2xx 성공
- 4xx 무재시도
- 5xx 최대 3회와 1초/2초 backoff
- 연결 오류와 timeout 무재시도
- connect/read timeout 전달
- API Key와 민감 응답 로그 비노출

### TR-SA-002: Orchestrator 단위 테스트

다음을 검증한다.

- GET을 호출하지 않음
- 모든 수신 메시지를 처음부터 처리
- 중간 PATCH 실패에도 처리 계속
- S3 artifact 검증 전에 SUCCESS를 호출하지 않음
- SUCCESS 2xx 후에만 SQS 삭제
- SUCCESS 실패 시 SQS 미삭제
- 처리 실패 시 FAILED best-effort 및 SQS 미삭제
- FAILED payload에 progress가 없음
- 정확한 상태, progress, message, artifactKey, errorCode

### TR-SA-003: 회귀 품질 게이트

- 전체 pytest 통과
- Ruff 통과
- mypy strict 통과
- compileall 통과
- uv lock check 및 frozen sync 통과
- systemd unit 검증

### TR-SA-004: 실제 API 계약 테스트

승인된 dev Job을 사용하여 다음을 외부 테스트 harness 또는 Backend/Mobile에서 검증한다. Worker 자체는 GET을 호출하지 않는다.

1. Worker의 ANALYZING PATCH 후 GET에서 ANALYZING 확인
2. GENERATING_CODE PATCH 후 GET에서 GENERATING_CODE 확인
3. BUILDING PATCH 후 GET에서 BUILDING 확인
4. APK S3 업로드 및 검증
5. SUCCESS PATCH와 artifactKey 반영
6. GET과 Mobile App에서 SUCCESS 및 동일 artifactKey 확인
7. SUCCESS 반영 후 SQS 메시지 삭제 확인

## 13. 완료 조건

- Worker source와 runtime 경로에 DynamoDB 직접 접근이 없다.
- `DYNAMODB_TABLE_NAME`이 필수 설정에서 제거된다.
- 상태 변경은 지정된 PATCH endpoint만 사용한다.
- 중간 상태는 best-effort로 처리된다.
- SUCCESS는 필수이며 2xx 전에는 SQS 메시지를 삭제하지 않는다.
- FAILED에서 progress를 생략한다.
- 모든 5xx 재시도와 timeout 정책이 테스트로 검증된다.
- API Key가 설정된 경우에만 `x-api-key`가 추가되고 로그에 노출되지 않는다.
- 기존 AI, S3, Build, Visibility 및 SQS retry 동작에 회귀가 없다.
- 실제 dev Job에서 Backend GET과 Mobile App이 동일 상태를 조회한다.

## 14. 수용된 위험과 제약

- GET 미사용으로 terminal Job과 canceled Job을 Worker가 사전에 식별하지 못한다.
- SQS 중복 전달 시 Hermes, Kiro, Gradle 및 S3 업로드가 반복될 수 있다.
- 중간 PATCH 실패 시 Mobile App이 실제 처리 단계보다 오래된 상태를 볼 수 있다.
- 연결 오류와 timeout은 재시도하지 않으므로 일시적 네트워크 오류가 상태 누락 또는 SUCCESS 실패로 이어질 수 있다.
- SUCCESS PATCH 실패 후 artifact가 S3에 존재하지만 Job 상태는 SUCCESS가 아닌 orphan 상태가 될 수 있다. SQS 재전달로 전체 처리를 다시 시도한다.
- Backend가 반복 상태와 SUCCESS idempotency를 지원하지 않으면 전체 재처리 정책이 정상 동작하지 않는다.

## 15. Extension 설정

| Extension | 상태 | 근거 |
|---|---|---|
| Security Baseline | Disabled | 현재는 적용하지 않고 향후 재검토 |
| Resiliency Baseline | Disabled | 사용자 선택 |
| Property-Based Testing | Disabled | 사용자 선택 |
