# Story Generation Persona Clarification

Q1에서는 Worker 운영자만 persona로 선택했고, Q2에서는 Mobile App 사용자의 상태 확인을 cross-system acceptance story로 포함하도록 선택했습니다. Mobile App 사용자를 정식 persona로 만들지 않는 경우 해당 story의 actor와 persona mapping을 확정해야 합니다.

## Question 1
Cross-system 상태 확인 story의 actor를 어떻게 구성할까요?

A) Worker 운영자를 유일한 persona로 유지한다. Story는 Worker 운영자가 Backend GET과 Mobile App에서 상태 전달 결과를 검증할 수 있어야 한다는 관점으로 작성하고, Mobile App 사용자는 외부 beneficiary로만 언급한다. (Q1 답변 유지)

B) Mobile App 사용자를 두 번째 persona로 추가하고, 상태 확인 story는 Mobile App 사용자의 관점으로 작성한다.

C) Worker 운영자만 persona로 유지하고 별도의 cross-system story는 만들지 않으며, 공동 E2E를 기존 story의 외부 acceptance dependency로만 기록한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A
