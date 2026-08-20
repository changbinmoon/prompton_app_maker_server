# requirements.json 계약 확정 질문

각 질문의 `[Answer]:` 뒤에 선택한 문자를 입력한다. 권장 선택은 설명에 표시되어 있다.

## Question 1
Client의 기존 `POST /jobs` 입력을 어떻게 처리할 것인가?

A) 기존 `{"requirements": "자유 텍스트"}` API를 유지하고 Backend Lambda가 canonical JSON으로 변환한다. 권장안이다.

B) Client가 canonical `requirements.json` 전체 구조를 POST하도록 API를 변경한다.

C) 기존 자유 텍스트와 structured JSON 입력을 모두 지원한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: X = Client에게 json을 받아 hermes 를 통해 프롬프트를 정제

## Question 2
`applicationId`, SDK 버전, 언어, UI toolkit의 소유자는 누구인가?

A) Backend의 승인된 서버 설정이 생성하고 Client는 변경할 수 없다. 권장안이다.

B) Client가 모든 Android 기술 필드를 지정한다.

C) Worker가 prompt를 보고 임의로 결정한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 3
Android SDK 버전 정책은 무엇인가?

A) `minSdk=26`, `targetSdk=35`로 v1 계약에 고정한다. 대상 EC2에 SDK 35 설치가 필요하다.

B) `minSdk`와 `targetSdk`를 배포 설정으로 관리하고 Backend가 현재 승인값을 JSON에 주입한다. 권장안이다.

C) 허용 범위 내에서 Client가 선택한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: X = Client에게 AOS 버전을 받아 minSDK를 그 버전으로 설정, 없을 경우 A안

## Question 4
MVP에서 사용자 앱 요구사항을 얼마나 구조화할 것인가?

A) 자유 텍스트 prompt만 필수로 하고 Android 정책과 asset metadata만 구조화한다. 권장안이다.

B) prompt에 더해 screens와 features 배열을 선택 필드로 지원한다.

C) 자유 텍스트를 제거하고 screens, features, theme을 모두 구조화된 필수 필드로 만든다.

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
정의되지 않은 JSON 필드는 어떻게 처리할 것인가?

A) 모든 객체에서 unknown field를 거부한다. 계약 오류를 조기에 발견할 수 있어 권장한다.

B) unknown field를 무시하여 forward compatibility를 우선한다.

C) unknown field는 거부하되 명시적인 `extensions` 객체 내부만 자유 형식으로 허용한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
JSON Schema의 단일 source of truth를 어디에 둘 것인가?

A) 이 Worker 저장소에 두고 Backend 저장소로 복사한다.

B) Backend와 Worker가 함께 참조하는 공유 contract 저장소 또는 versioned package에 둔다. 여러 저장소를 운영한다면 권장안이다.

C) Backend OpenAPI 문서에만 정의하고 Worker는 별도 검증 로직을 유지한다.

X) Other (please describe after [Answer]: tag below)

[Answer]: B
