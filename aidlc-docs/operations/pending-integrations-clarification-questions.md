# Backend Producer Clarification Question

> **Superseded (2026-08-20)**: No answer is required. The later raw Client JSON flow and Worker-owned guardrail answer replace this canonical producer scope question.

## Clarification
`Backend canonical producer`는 Client의 앱 생성 요청을 받는 API Gateway/Lambda 쪽 코드다. 이 코드는 Worker가 읽기 전에 다음 작업을 수행한다.

1. Client가 보낸 임의 JSON을 `clientPayload`에 그대로 보존한다.
2. Android API level과 applicationId를 검증하고 기본값을 적용한다.
3. `schemaVersion`, `clientPayload`, `android`, `assets` 구조의 canonical `requirements.json`을 만든다.
4. shared JSON Schema로 검증한 후 S3에 저장하고 SQS 메시지를 보낸다.

현재 `/home/ubuntu`에는 이 Lambda/Backend 소스 저장소가 없고 Worker 저장소만 있다. 따라서 실제 API에 직접 연결하려면 Backend 저장소가 필요하다.

## Question 1
현재 가능한 Backend producer 작업 범위를 선택해 달라.

A) 이 Worker 저장소에 Backend가 재사용할 수 있는 canonical normalizer reference module과 테스트를 먼저 구현한다. 실제 Lambda 연결은 Backend 저장소가 제공되면 후속 진행한다. 권장안이다.

B) 지금은 Backend producer 구현을 보류한다. 실제 Backend 저장소를 준비한 뒤 해당 저장소에서 직접 구현한다.

C) 실행 코드는 만들지 않고 Backend 개발자가 구현할 정규화 명세와 shared fixture 검증 절차만 문서화한다.

D) Other (please describe after [Answer]: tag below)

[Answer]:
