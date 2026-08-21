# Status API 요구사항 모순 해소 질문

기존 답변에서 다음 두 가지 모순 또는 불명확성이 확인되었습니다.

1. Q1과 Q2에서는 Worker가 GET을 사용하지 않는다고 답했지만, Q3에서는 `SUCCESS`와 `CANCELED` 상태를 확인하여 중복 메시지를 건너뛰도록 선택했습니다. 원격 상태 조회 없이 해당 상태를 판별할 수 없습니다.
2. Q4에서는 모든 Status API 업데이트를 best-effort로 선택했지만, `SUCCESS` PATCH가 실패한 경우에도 SQS 메시지를 삭제할지 명확하지 않습니다. 이는 완료 상태와 APK artifact의 불일치를 만들 수 있습니다.

아래 `[Answer]:` 뒤에 선택지를 기입해 주세요.

## Question 1
GET 미사용 방침과 SQS 중복 처리 방침을 어떻게 정합시킬까요?

A) 처리 시작 전에만 GET을 호출하여 `SUCCESS`와 `CANCELED`를 건너뛴다. 각 PATCH 뒤에는 GET을 호출하지 않는다. (권장)

B) GET을 전혀 호출하지 않고 수신된 모든 메시지를 처음부터 다시 처리한다. Backend는 동일 상태 반복 및 이전 진행 상태에서 `ANALYZING`으로 돌아가는 PATCH를 허용한다.

C) GET을 사용하지 않고 별도의 durable idempotency 저장소 또는 Backend 중복 방지 API를 추가한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 2
APK 업로드는 성공했지만 `SUCCESS` PATCH가 허용된 재시도 후에도 실패하면 어떻게 처리할까요?

A) `ANALYZING`, `GENERATING_CODE`, `BUILDING`은 best-effort로 유지하지만 `SUCCESS`는 필수로 취급한다. SUCCESS가 2xx가 아니면 SQS 메시지를 삭제하지 않는다. (권장)

B) `SUCCESS`도 best-effort로 처리한다. APK 업로드가 성공했으면 PATCH 결과와 관계없이 SQS 메시지를 삭제한다.

C) 모든 상태 PATCH를 필수로 변경한다. 어느 상태든 최종 실패 시 처리를 중단하고 SQS 메시지를 삭제하지 않는다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A
