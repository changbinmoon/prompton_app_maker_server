# Raw Client JSON to Hermes Flow Clarification

## Confirmed Target Flow

1. Client가 임의 JSON object를 Backend에 보낸다.
2. Backend는 원본 JSON을 S3에 저장하고 해당 key를 SQS로 전달한다.
3. Worker는 64 KiB, UTF-8, JSON object 조건만 검사하고 canonical schema를 ingress에서 강제하지 않는다.
4. Worker는 JSON 내용을 Hermes `--oneshot` 입력에 data로 포함한다.
5. Hermes의 non-empty 64 KiB 이하 stdout을 `refined-prompt.md`로 저장한다.
6. Kiro는 `refined-prompt.md`, 원본 JSON, assets를 함께 읽는다.
7. Hermes가 최대 3회 실패하면 Kiro가 원본 JSON과 assets를 직접 읽도록 fallback한다.

이 흐름은 가능하지만, 이전 결정인 "Backend가 API level과 applicationId를 정규화한다"와 충돌한다. Backend가 원본만 저장하면 Android 기술 설정을 다른 단계가 책임져야 한다.

## Question 1
원본 JSON을 유지하면서 Android API level, applicationId, Kotlin, Jetpack Compose 기본 규칙을 어느 단계에서 적용할 것인가?

A) Worker가 고정된 guardrail을 Hermes 입력과 Kiro fallback prompt에 추가한다. Hermes는 임의 JSON을 해석해 최종 prompt text만 반환한다. 원본 JSON은 변경하지 않는다. 현재 목표 흐름에 가장 단순한 권장안이다.

B) Hermes가 prompt text뿐 아니라 정규화된 Android 설정도 structured JSON으로 반환하게 하고, Worker가 schema 검증 후 `refined-prompt.md`를 만든다.

C) Backend가 원본 JSON과 별도로 canonical Android metadata 파일도 S3에 저장한다. Worker는 두 파일을 Hermes에 전달한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A
