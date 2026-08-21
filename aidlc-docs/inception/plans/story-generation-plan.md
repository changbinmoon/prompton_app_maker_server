# Story Generation Plan - Status API Migration

## 문서 상태

- **단계**: User Stories Part 2 - Generation
- **상태**: Part 2 Generation 완료 - 사용자 승인 대기
- **승인된 요구사항**: `../requirements/status-api-requirements.md`
- **Assessment**: `user-stories-assessment.md`
- **Part 2 산출물**: `../user-stories/stories.md`, `../user-stories/personas.md`

## 목표

승인된 Status API 전환 요구사항을 사용자와 운영 이해관계자 관점의 독립적이고 검증 가능한 User Stories로 변환한다. 구현 작업, 일정 또는 sprint 계획은 이 문서의 범위에 포함하지 않는다.

## 확정된 Story 전략

- **Persona**: Worker 운영자 1개
- **External beneficiary**: Mobile App 사용자 (정식 persona 아님)
- **Cross-system story actor**: Worker 운영자
- **Breakdown**: User journey와 reliability, 인증, 관측성을 결합한 Hybrid
- **Granularity**: 6~8개 story
- **Acceptance criteria**: 상태 흐름은 Given/When/Then, 설정·보안·품질은 checklist
- **E2E 책임**: Worker mock/contract 자동 테스트와 승인된 dev Job의 Backend/Mobile 공동 acceptance
- **수용된 위험**: story 또는 공통 제약에 반복하지 않고 승인 requirements의 traceability reference로만 유지

## Story Breakdown 접근 옵션

| 접근 | 장점 | 한계 | 이 변경에 대한 적합성 |
|---|---|---|---|
| User Journey-Based | QUEUED부터 SUCCESS/FAILED까지 사용자 경험을 자연스럽게 표현 | HTTP client와 보안 같은 횡단 관심사 누락 가능 | 높음 |
| Feature-Based | 상태 호출, retry, 인증, SQS 삭제를 명확히 분리 | 사용자 가치가 기술 기능 뒤에 가려질 수 있음 | 높음 |
| Persona-Based | 사용자, 운영자, QA의 서로 다른 목표 표현 | 동일 상태 흐름이 여러 번 반복될 수 있음 | 중간 |
| Domain-Based | Worker, Backend, Mobile 경계를 명확히 표현 | 단일 migration에는 과도한 분할 가능 | 중간 |
| Epic-Based | 전체 migration과 하위 story 관계를 쉽게 파악 | story가 커져 INVEST의 Small 기준을 위반할 수 있음 | 중간 |
| Hybrid | 사용자 journey를 중심으로 reliability/security story를 보완 | 분리 기준을 명확히 정해야 함 | 가장 높음 |

## Part 2 실행 체크리스트

### Step 1: 답변 및 Story 전략 확정

- [x] 모든 `[Answer]:`가 작성되었는지 확인한다.
- [x] 답변의 모호함, 결합 선택지 또는 모순을 검사한다.
- [x] 선택된 persona 범위와 breakdown 접근을 확정한다.
- [x] 선택된 acceptance criteria 형식과 story granularity를 확정한다.

### Step 2: Persona 생성

- [x] `aidlc-docs/inception/user-stories/personas.md`를 생성한다.
- [x] Worker 운영자의 목표, 동기, 주요 작업, pain point 및 성공 기준을 작성한다.
- [x] Mobile App 사용자를 정식 persona가 아닌 external beneficiary로 구분한다.
- [x] Mobile App 구현처럼 이번 Worker 범위 밖의 책임을 명시한다.

### Step 3: Story 구조와 Traceability 구성

- [x] 승인된 요구사항 FR-SA, NFR-SA 및 TR-SA를 story 후보에 매핑한다.
- [x] 정상 흐름, 처리 실패, Status API 장애 및 인증 시나리오를 포함한다.
- [x] GET 미사용, 전체 재처리 및 중간 상태 누락 위험은 story 후보로 만들지 않고 requirements traceability reference로만 유지한다.
- [x] 각 story에 고유 ID와 Worker 운영자 persona를 지정한다.
- [x] Mobile App 사용자는 external beneficiary로, Backend/Mobile 검증은 공동 E2E acceptance로 표시한다.

### Step 4: User Stories 생성

- [x] `aidlc-docs/inception/user-stories/stories.md`를 생성한다.
- [x] 각 story를 `As a / I want / So that` 형식으로 작성한다.
- [x] 각 story에 선택된 형식의 acceptance criteria를 포함한다.
- [x] 중간 PATCH best-effort와 SUCCESS 필수 정책을 서로 다른 검증 시나리오로 표현한다.
- [x] 승인된 수용 위험을 story 본문이나 공통 제약에 반복하지 않는다.
- [x] API Key 비노출, TLS 및 journald 관측성을 포함한다.

### Step 5: INVEST 및 Persona Mapping 검증

- [x] 모든 story가 Independent인지 검토한다.
- [x] 모든 story가 Negotiable인지 검토한다.
- [x] 모든 story가 사용자 또는 운영 가치가 있는지 검토한다.
- [x] 모든 story가 Estimable인지 검토한다.
- [x] 모든 story가 Small한지 검토한다.
- [x] 모든 story가 Testable한지 검토한다.
- [x] 모든 story를 하나 이상의 persona에 매핑한다.
- [x] story 간 중복 acceptance criteria를 제거한다.

### Step 6: 완전성 및 일관성 검증

- [x] 기능·품질 요구사항은 story에 trace하고, 승인된 수용 위험은 requirements reference로만 trace되는지 확인한다.
- [x] SUCCESS PATCH 2xx 전에 SQS 삭제가 발생하지 않음을 확인한다.
- [x] FAILED payload에 progress가 없음을 확인한다.
- [x] 5xx만 3회 시도하고 연결 오류, timeout 및 4xx는 재시도하지 않는 정책을 확인한다.
- [x] 실제 dev E2E에서 Backend GET과 Mobile App 검증 책임을 확인한다.
- [x] Story와 persona Markdown 구조 및 콘텐츠를 검증한다.

## Story Planning 질문

각 질문의 `[Answer]:` 뒤에 하나의 선택지를 기입해 주세요.

## Question 1
이번 변경에서 persona를 어느 범위로 구성할까요?

A) Mobile App 사용자, Worker/Backend 운영자, QA/릴리스 검증 담당자 3개 persona (권장)

B) Mobile App 사용자와 Worker 운영자 2개 persona

C) Mobile App 사용자 1개 persona만 사용

D) Other (please describe after [Answer]: tag below)

[Answer]: D = Worker 운영자

## Question 2
Mobile App의 상태 조회는 Worker 구현 범위 밖이지만 story에는 어떻게 반영할까요?

A) Mobile App 코드는 범위 밖으로 명시하되, 사용자 상태 확인을 cross-system acceptance story로 포함한다. (권장)

B) Backend/Mobile external dependency로만 기록하고 별도 story는 만들지 않는다.

C) Worker story에서는 Mobile App을 완전히 제외한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
Story breakdown 접근을 선택해 주세요.

A) 사용자 journey를 중심으로 구성하고 reliability, 인증 및 관측성 feature story를 보완하는 Hybrid 방식 (권장)

B) QUEUED부터 SUCCESS/FAILED까지 User Journey-Based 방식

C) Status client, retry, 인증, SQS lifecycle 중심 Feature-Based 방식

D) 하나의 migration epic과 하위 story를 사용하는 Epic-Based 방식

E) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
Story granularity는 어느 정도가 적절합니까?

A) 6~8개의 독립적이고 E2E 검증 가능한 story (권장)

B) 3~4개의 넓은 범위 story

C) 9~12개의 세분화된 story

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
Acceptance criteria 형식을 선택해 주세요.

A) 모든 criteria를 Given/When/Then 형식으로 작성

B) 검증 가능한 checklist 형식으로 작성

C) 핵심 상태 흐름은 Given/When/Then, 설정·보안·품질 조건은 checklist를 사용하는 Hybrid 형식 (권장)

D) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 6
실제 dev API와 Mobile App을 포함한 E2E 검증 책임을 story에 어떻게 표현할까요?

A) Worker 저장소는 mock/contract 자동 테스트를 담당하고, 승인된 dev Job의 Backend GET 및 Mobile 확인은 공동 E2E acceptance로 표시한다. (권장)

B) 모든 실제 API와 Mobile 검증은 Backend/Mobile QA의 외부 책임으로 표시한다.

C) Worker story에는 자동 mock 테스트만 포함하고 실제 E2E는 제외한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
GET 미사용, 전체 재처리, 중간 상태 누락 가능성과 같은 수용된 위험을 story에 어떻게 반영할까요?

A) 관련 story의 acceptance criteria와 명시적 constraint에 포함하여 반드시 검증 또는 확인한다. (권장)

B) stories.md의 공통 비기능 제약 섹션에만 기록한다.

C) 승인된 requirements에 이미 있으므로 user stories에서는 제외한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: C

## 필수 산출물 준수

- [x] `stories.md`에 INVEST 기준을 따르는 User Stories를 생성한다.
- [x] `personas.md`에 사용자 archetype과 특성을 생성한다.
- [x] 각 story에 acceptance criteria를 포함한다.
- [x] persona를 관련 story에 매핑한다.
- [x] 모든 plan checkbox는 Part 2 실행 중 완료 즉시 `[x]`로 갱신한다.
