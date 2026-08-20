# requirements.json 계약 Clarification Questions

기존 답변에서 다음 충돌과 모호성이 발견되었다.

- Q2는 applicationId, SDK 버전, 언어, UI toolkit을 Worker가 결정한다고 선택했다.
- Q3는 Client의 AOS 버전으로 minSdk를 결정한다고 답해 SDK 소유권이 Q2와 충돌한다.
- Q1의 Hermes는 현재 저장소에 정의가 없어서 실행 위치, 입력, 출력이 불명확하다.
- AOS 버전이 Android OS 버전인지 API level인지 불명확하며 targetSdk 정책도 필요하다.

아래 답변이 완료될 때까지 JSON Schema와 Worker 검증 구현을 시작하지 않는다.

## Contradiction 1: SDK 소유권

Q2의 Worker 결정과 Q3의 Client 기반 minSdk 결정을 동시에 적용할 수 있도록 책임 경계를 확정해야 한다.

### Clarification Question 1
SDK 값을 최종 검증하고 canonical JSON에 기록할 주체는 누구인가?

A) Client가 AOS 버전을 보내고 Backend가 이를 검증·매핑하여 minSdk를 기록한다. targetSdk는 Backend 배포 설정값을 기록하고 Worker는 받은 값을 사용한다. 권장안이다.

B) Client의 AOS 버전은 참고 정보일 뿐이며 Worker가 minSdk와 targetSdk를 모두 결정한다.

C) Client가 minSdk와 targetSdk를 직접 보내고 Backend와 Worker는 허용 범위만 검증한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: X = Client가 AOS 버전을 보내고 Backend가 이를 검증 매핑하여 minSDK, targetSDK를 기록한다. Client로 부터 유효한 값을 받지 못 한 경우 기본값으로 진행

## Ambiguity 1: Hermes 실행 경계

Hermes가 어느 컴포넌트에서 실행되는지에 따라 Client API, S3 계약, 실패 처리 방식이 달라진다.

### Clarification Question 2
Hermes는 어디에서 실행하고 무엇을 출력하는가?

A) Backend Lambda가 S3/SQS 처리 전에 Hermes를 호출한다. Hermes는 정제된 prompt를 반환하고 Lambda가 canonical JSON을 생성한다. 권장안이다.

B) Backend의 별도 Hermes 서비스가 Client JSON을 canonical JSON 전체로 변환하고 Lambda는 결과를 저장한다.

C) Worker가 requirements.json을 받은 뒤 kiro-cli 호출 전에 Hermes를 실행한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Ambiguity 2: Client JSON 형태

Q1은 Client에게 JSON을 받는다고 했지만 JSON의 최소 필드가 정해지지 않았다.

### Clarification Question 3
Client가 `POST /jobs`로 보내는 JSON 형태는 무엇인가?

A) `requirements` 자유 텍스트와 선택적 `aosVersion`만 JSON 필드로 받는다. assets는 기존 업로드 흐름을 사용하고 Hermes는 requirements 텍스트만 정제한다. 권장안이다.

B) Client가 request, android, assets를 포함한 canonical JSON 전체를 보낸다.

C) Client가 임의 JSON을 보내고 Hermes가 해석하여 canonical JSON으로 변환한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: X = Client가 임의 JSON을 보내고 Hermes가 해석하여 프롬프트를 작성한다.

## Ambiguity 3: AOS 버전 표현

Android OS 버전과 Android API level은 값 체계가 다르므로 계약에서 하나를 선택해야 한다.

### Clarification Question 4
Client의 AOS 버전 값은 어떤 형식인가?

A) Android OS major version 문자열이다. 예를 들어 `"8"`, `"13"`, `"14"`를 Backend가 API level 26, 33, 34로 매핑한다.

B) Android API level 정수다. 예를 들어 26, 33, 34를 보내며 Backend가 허용 범위를 검증한다. 권장안이다.

C) `{"osVersion": "14", "apiLevel": 34}`처럼 둘 다 보내고 일치 여부를 검증한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Ambiguity 4: applicationId와 기술 스택

Q2의 Worker 결정에는 SDK 외에 applicationId, language, uiToolkit도 포함되어 있다. 운영 테스트에서 예상 package와 빌드 정책을 판정하려면 결정 시점이 필요하다.

### Clarification Question 5
applicationId, language, uiToolkit은 누가 결정하는가?

A) Backend가 Job ID 기반 applicationId를 생성하고 `Kotlin`과 `Jetpack Compose`를 canonical JSON에 고정한다. Worker는 그대로 사용한다. 권장안이다.

B) Worker가 세 값을 모두 결정한다. canonical JSON에는 포함하지 않고 생성 결과에서만 확인한다.

C) Client가 세 값을 보내고 Backend와 Worker가 검증한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: X = Client가 세 값을 보내고 유효하지 않은 경우 Backend가 적절히 생성한다.
