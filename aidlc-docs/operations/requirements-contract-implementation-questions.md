# requirements.json 계약 구현 질문

> **Superseded in part (2026-08-20)**: Questions 1-3 describe the former canonical ingress. The later approved flow uses raw Client JSON, Worker Android guardrails, Hermes host defaults with three attempts, and Kiro raw fallback. Questions 4-6 remain historical decision evidence.

첫 번째 clarification으로 다음 방향은 확인되었다.

- Backend가 Client 값을 검증하여 Android 설정을 canonical JSON에 기록한다.
- Hermes는 Worker에서 kiro-cli 전에 실행한다.
- Client 입력은 Hermes가 해석할 JSON이다.
- AOS 값은 Android API level 정수다.
- Client의 applicationId/language/uiToolkit이 invalid하면 Backend가 기본값을 생성한다.

하지만 구현에 필요한 canonical envelope와 Hermes 실행 인터페이스는 아직 정의되지 않았다. 현재 `kiro-cli agent list`에도 `hermes` agent가 등록되어 있지 않다.

아래 6개 답변이 완료되면 추가 질문 없이 JSON Schema와 Worker 검증 구현을 시작한다.

## Question 1
임의 Client JSON과 Backend가 정규화한 필드를 canonical `requirements.json`에서 어떻게 분리할 것인가?

A) root에 `schemaVersion`, `clientPayload`, `android`, `assets`를 둔다. Backend는 원본 Client JSON 전체를 `clientPayload`에 보존하고 정규화된 기술 필드는 별도 객체에 기록한다. 권장안이다.

B) Client가 처음부터 `request`, `android`, `assets` 예약 필드를 포함하는 canonical 구조를 보낸다. Backend는 같은 구조를 검증·보정한다.

C) Client 임의 JSON root를 유지하고 Backend가 `_prompton` 예약 객체를 추가한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
Client가 API level 하나만 보낼 때 minSdk와 targetSdk를 어떻게 계산할 것인가?

A) 유효한 Client API level을 minSdk로 사용하고 targetSdk는 Backend 배포 설정값을 사용한다. 누락·invalid 시 minSdk=26, targetSdk=35를 사용한다. targetSdk는 항상 minSdk 이상이어야 한다. 권장안이다.

B) 유효한 Client API level을 minSdk와 targetSdk 모두에 사용한다. 누락·invalid 시 minSdk=26, targetSdk=35를 사용한다.

C) Client가 minSdk와 targetSdk를 각각 보내고 Backend가 범위와 순서만 검증한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 3
Client의 applicationId, language, uiToolkit을 어떤 규칙으로 검증·보정할 것인가?

A) valid applicationId는 유지하고 invalid 또는 누락이면 `com.prompton.generated.j{jobIdHex}`로 생성한다. language는 `Kotlin`, uiToolkit은 `Jetpack Compose`만 허용하며 다른 값은 이 기본값으로 보정한다. 권장안이다.

B) Client 값을 모두 무시하고 Backend가 항상 applicationId를 생성하며 Kotlin과 Jetpack Compose를 기록한다.

C) applicationId만 Backend가 보정하고 language와 uiToolkit은 여러 enum 값을 허용한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
Worker가 Hermes를 어떤 실제 인터페이스로 호출할 것인가?

A) `hermes`라는 Kiro custom agent를 생성하고 `kiro-cli chat --agent hermes --no-interactive`로 호출한다. agent 설정 파일과 신뢰 도구 범위가 추가로 필요하다.

B) 독립 실행형 로컬 CLI를 호출한다. 선택 시 `[Answer]:` 뒤에 실행 파일 경로와 전체 인자 형식을 함께 적는다.

C) 원격 Hermes HTTP API를 호출한다. 선택 시 `[Answer]:` 뒤에 endpoint, 인증 방식, request/response 형식을 함께 적는다.

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 5
Hermes의 출력은 무엇이며 kiro-cli에 어떻게 전달할 것인가?

A) Hermes가 정제된 prompt text를 반환하고 Worker가 `refined-prompt.md`로 저장한다. Kiro는 refined prompt와 canonical JSON, assets를 함께 읽는다. 권장안이다.

B) Hermes가 변환된 canonical JSON 전체를 출력하고 Kiro는 변환된 JSON만 읽는다.

C) Hermes stdout을 Worker가 별도 파일 없이 Kiro의 첫 입력 문자열에 직접 포함한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
Hermes 실행이 실패하거나 유효한 prompt를 만들지 못하면 어떻게 처리할 것인가?

A) `AI_GENERATION_FAILED`로 Job을 실패 처리하고 Kiro를 호출하지 않는다. MVP 권장안이다.

B) 원본 canonical JSON으로 Kiro 생성을 계속하고 경고 로그를 남긴다.

C) Hermes를 정해진 횟수만큼 재시도한 뒤 실패 처리한다. 선택 시 재시도 횟수와 간격을 함께 적는다.

X) Other (please describe after [Answer]: tag below)

[Answer]: X = Hermes를 정해진 횟수만큼 재시도한 뒤 Kiro 생성을 계속하고 경고 로그를 남긴다.
