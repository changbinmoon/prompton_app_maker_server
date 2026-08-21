# Backend Producer and Hermes Integration Questions

> **Superseded (2026-08-20)**: Question 1 is no longer applicable. The user subsequently approved raw Client JSON storage with Worker-owned Android guardrails. Questions 2-4 supplied the active Hermes model, retry, and fallback policies.

확인된 사실:

- 현재 작업공간에는 Worker 코드만 있고 실제 API Gateway/Lambda Backend 저장소는 없다.
- 로컬 Hermes는 `/home/ubuntu/.local/bin/hermes`에 설치된 Hermes Agent v0.20.4다.
- Hermes는 `--oneshot`으로 prompt를 받고 최종 응답 text만 stdout에 출력한다.
- `--safe-mode`는 user config, project rules, plugins, MCP customizations를 비활성화한다.
- `--toolsets context_engine`은 정의상 정적 도구가 없는 최소 toolset이다.
- Worker의 현재 fallback 경로는 canonical `requirements.json`과 assets를 Kiro가 직접 읽는 방식이다.

아래 결정은 실제 Backend 연결 및 재시도 비용·장애 동작을 바꾸므로 명시적 답변이 필요하다.

## Question 1
Backend canonical producer를 어디에 구현할 것인가?

A) 실제 Backend 저장소의 로컬 경로를 `[Answer]:` 뒤에 함께 제공한다. 해당 Lambda/API 코드에 schema 정규화와 S3/SQS 전 검증을 직접 연결한다. 권장안이다.

B) 이 Worker 저장소에 재사용 가능한 producer reference module과 테스트를 만든다. 실제 Lambda 연결은 Backend 저장소가 제공될 때 후속 진행한다.

C) 실행 코드는 만들지 않고 Backend 팀이 사용할 언어 중립 정규화 명세와 shared fixture 검증 명령만 완성한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: Backend canonical producer가 뭐지?

## Question 2
Hermes model/provider와 격리 실행 정책을 어떻게 구성할 것인가?

A) `HERMES_PROVIDER`와 `HERMES_MODEL`을 필수 환경 변수로 받고, `hermes --safe-mode --provider {provider} --model {model} --toolsets context_engine --oneshot {prompt}`로 실행한다. 배포별 값이 명시적이고 project/user rules 및 custom tools를 차단하는 권장안이다.

B) Hermes 사용자 설정의 기본 provider/model을 사용하고, `hermes --ignore-rules --toolsets context_engine --oneshot {prompt}`로 실행한다. 현재 호스트 설정에 의존한다.

C) provider/model 환경 변수가 둘 다 있으면 A를 사용하고 둘 다 없으면 B를 사용한다. 하나만 설정된 경우 Worker 시작을 거부한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 3
Hermes 재시도 횟수와 간격을 어떻게 적용할 것인가?

A) 최초 호출 포함 최대 3회 시도하고, 실패 후 1초와 2초를 기다리는 exponential backoff를 사용한다. 권장안이다.

B) 최초 호출 포함 최대 3회 시도하고, 각 실패 후 2초를 기다리는 fixed delay를 사용한다.

C) 최초 호출 포함 최대 2회 시도하고, 첫 실패 후 1초를 기다린다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
모든 Hermes 시도가 실패하거나 출력이 비어 있거나 64 KiB를 초과하면 Kiro에 무엇을 전달할 것인가?

A) 현재 동작처럼 Kiro가 canonical `requirements.json`과 assets를 직접 읽게 하고 warning 및 DynamoDB log를 남긴다. 실패한 `refined-prompt.md`는 생성하지 않는다. 권장안이다.

B) canonical JSON을 deterministic local fallback prompt로 변환해 `refined-prompt.md`에 저장하고 Kiro가 해당 파일과 canonical JSON 및 assets를 함께 읽게 한다.

C) Job을 `AI_GENERATION_FAILED`로 종료하고 Kiro를 호출하지 않는다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A
