# Status API 전환 요구사항 확인 질문

## 검토 요약

요구사항의 방향은 타당하며 DynamoDB 교차 계정 권한 문제를 제거한다. 현재 Worker에는 DynamoDB 기반 상태 갱신 외에도 상태 조회를 통한 중복 방지와 사용자용 처리 로그 누적 기능이 있으므로, 단순히 `UpdateItem`을 `PATCH`로 바꾸는 것만으로는 기존 동작을 보존할 수 없다.

확인된 주요 변경 범위:

- `DynamoClient`를 별도 `StatusApiClient`로 대체
- `DYNAMODB_TABLE_NAME` 설정과 DynamoDB 직접 접근 제거
- 상태 조회 기반 중복 처리 방식을 `GET /v1/jobs/{jobId}` 계약으로 전환
- 상태 갱신, 실패 보고, 재시도와 HTTP timeout 정책 추가
- DynamoDB `logs` 누적 기능의 대체 방식 결정
- Status API 단위 테스트와 실제 API 계약 테스트 추가
- 설계 문서, 운영 runbook, IAM 요구사항 갱신

아래 질문에 각 `[Answer]:` 뒤에 선택지를 기입해 주세요.

## Question 1
`GET /v1/jobs/{jobId}`는 Worker에서 언제 호출해야 합니까?

A) SQS 메시지 처리 시작 전 중복 방지 목적으로만 호출하고, PATCH 후 GET 확인은 E2E 테스트 또는 Mobile/Backend가 수행한다. (권장)

B) 처리 시작 전 호출하고 모든 PATCH 직후에도 GET을 호출하여 상태를 read-after-write 검증한다.

C) Worker에서는 GET을 전혀 호출하지 않고 PATCH만 수행한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 2
`GET /v1/jobs/{jobId}` 성공 응답의 JSON 구조는 무엇입니까?

A) Job 필드가 최상위에 있다. 예: `jobId`, `status`, `progress`, `message`, `artifactKey`, `errorCode`

B) `data` 객체 아래에 Job 필드가 있다.

C) 기존 Backend API 계약이 별도로 있으며 실제 성공 응답 예시를 답변에 제공한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: D = GET 안 함

## Question 3
SQS 재전달 또는 Worker 재시작 시 이미 `ANALYZING`, `GENERATING_CODE`, `BUILDING`, `FAILED`인 Job을 어떻게 처리해야 합니까?

A) `SUCCESS`와 `CANCELED`만 삭제 후 건너뛰고, 그 외 상태는 처음부터 재처리한다. Backend는 동일 상태 반복 PATCH와 기존 진행 상태에서 `ANALYZING`으로 재시작하는 전이를 허용한다. (권장)

B) Worker가 GET 결과에 따라 마지막 단계부터 재개한다.

C) `QUEUED` 상태만 처리하고 그 외 모든 상태는 메시지를 삭제하지 않은 채 중단한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
Status API 갱신이 최종적으로 실패했을 때 현재 Job 처리는 어떻게 해야 합니까?

A) 모든 상태 PATCH는 필수다. 허용된 재시도 후에도 실패하면 Job 처리를 중단하고 SQS 메시지를 삭제하지 않는다. FAILED 보고 자체의 실패는 로컬 로그에 기록한다. (권장)

B) Status API는 best-effort다. 실패해도 AI 생성과 빌드를 계속한다.

C) ANALYZING과 SUCCESS PATCH만 필수이고 GENERATING_CODE와 BUILDING은 best-effort다.

D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 5
어떤 오류를 어떤 정책으로 재시도해야 합니까?

A) 연결 오류, timeout, HTTP 408, 429, 5xx를 최초 호출 포함 최대 3회 시도하고 1초, 2초 exponential backoff를 적용한다. `Retry-After`가 있으면 이를 우선한다. (권장)

B) 요구사항 원문대로 5xx만 최초 호출 포함 최대 3회 시도하고 1초, 2초 대기한다.

C) 연결 오류, timeout, 5xx만 재시도하고 모든 4xx는 즉시 실패한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 6
Status API HTTP timeout 값은 무엇으로 설정해야 합니까?

A) 연결 3초, 응답 읽기 10초 (권장)

B) 연결 5초, 응답 읽기 15초

C) 단일 전체 timeout 30초

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
`FAILED` PATCH의 `progress`는 어떻게 정해야 합니까?

A) 마지막으로 Status API에 성공 반영된 progress를 전송하며, ANALYZING도 반영되지 않은 경우 0을 전송한다.

B) FAILED 요청에서는 progress를 생략하고 Backend가 기존 값을 유지한다. (기존 Worker 동작과 동일, 권장)

C) 실패가 발생한 로컬 처리 단계에 따라 25, 50, 75 중 하나를 항상 전송한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 8
현재 DynamoDB `logs` 배열에 기록하던 단계별 사용자 로그는 어떻게 처리해야 합니까?

A) DynamoDB 로그 누적을 제거하고 Worker journald 로그만 유지하며, 사용자에게는 최신 `message`만 노출한다. (현재 Status API 계약에 부합, 권장)

B) Backend가 별도의 Job log API를 제공하며 Worker가 그 API를 호출한다.

C) Status PATCH payload에 `logs` 또는 `log` 필드를 추가한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9
현재 및 향후 Status API 인증 방식은 무엇입니까?

A) 현재는 인증 없이 호출하고, `PROMPTON_STATUS_API_KEY`가 설정되면 `x-api-key` Header를 추가한다. (API Gateway 일반 방식, 권장)

B) `PROMPTON_STATUS_API_KEY`를 `Authorization: Bearer` Header로 전송한다.

C) Header 이름과 값 환경변수를 각각 설정할 수 있게 한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10
PATCH 성공 응답 계약은 무엇입니까?

A) 본문 유무와 관계없이 모든 2xx를 성공으로 처리한다. 204도 허용한다. (요구사항 원문과 동일, 권장)

B) HTTP 200과 유효한 Job JSON 본문이 있어야 성공이다.

C) HTTP 200 또는 204만 성공이다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11
Python HTTP client 구현 선호는 무엇입니까?

A) 표준 라이브러리 `urllib.request`를 사용하여 새 dependency를 추가하지 않는다.

B) `requests`를 정확한 버전으로 직접 dependency에 추가한다. (동기 Worker와 테스트 편의성 측면에서 권장)

C) `httpx`를 정확한 버전으로 직접 dependency에 추가한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 12
보안 extension 규칙을 이 변경에 적용할까요?

A) Yes — 모든 SECURITY 규칙을 blocking constraint로 적용한다. (production-grade 애플리케이션 권장)

B) No — SECURITY 규칙을 적용하지 않고 기존 비활성 설정을 유지한다.

C) Other (please describe after [Answer]: tag below)

[Answer]: C = 지금은 적용하지 않지만 향후 적용할 여지가 있음

## Question 13
Resiliency Baseline을 이 변경에 적용할까요?

A) Yes — AWS Well-Architected Reliability 기반의 방향성 있는 설계 지침을 적용한다.

B) No — resiliency baseline을 적용하지 않고 기존 비활성 설정을 유지한다.

C) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 14
Property-Based Testing 규칙을 이 변경에 적용할까요?

A) Yes — 모든 PBT 규칙을 blocking constraint로 적용한다.

B) Partial — 순수 함수와 직렬화 round-trip에만 적용한다.

C) No — PBT 규칙을 적용하지 않고 기존 비활성 설정을 유지한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: C
