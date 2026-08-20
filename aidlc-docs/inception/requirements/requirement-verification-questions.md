# AI Worker 요구사항 확인 질문

아래 질문에 답변하여 요구사항을 명확히 해주세요.
각 질문의 [Answer]: 태그 뒤에 선택한 옵션 문자를 기입해주세요.

---

## Question 1
AI Worker의 구현 프로그래밍 언어는 무엇입니까?

A) Python

B) Java/Kotlin

C) Node.js (TypeScript)

D) Go

X) Other (please describe after [Answer]: tag below)

[Answer]: X = 추천하는 언어로

## Question 2
AI Worker의 배포 환경은 무엇입니까?

A) EC2 인스턴스 (IAM Role / Instance Profile 사용)

B) ECS/Fargate 컨테이너

C) 로컬 개발 환경 (AWS CLI 자격증명 사용)

D) Lambda (이벤트 기반)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
AI 코드 생성에 사용할 모델/서비스는 무엇입니까?

A) Amazon Bedrock (Claude)

B) Amazon Bedrock (기타 모델)

C) OpenAI API

D) 자체 호스팅 LLM

X) Other (please describe after [Answer]: tag below)

[Answer]: X = EC2 서버에서 kiro-cli에 Opus5 사용

## Question 4
APK 빌드 환경은 어떻게 구성할 예정입니까?

A) Worker 내부에 Android SDK/Gradle 설치하여 직접 빌드

B) 별도 빌드 서버/컨테이너 호출

C) 아직 결정되지 않음 (MVP에서는 빌드 스텝을 스텁으로 처리)

X) Other (please describe after [Answer]: tag below)

[Answer]: X = EC2 서버에 SDK/Gradle은 미리 설치, 각 프로젝트마다 gradle wrapper를 생성하여 사용

## Question 5
동시에 처리할 수 있는 Job 수는 얼마입니까?

A) 1개 (단일 Job 순차 처리)

B) 2~5개 (제한적 동시 처리)

C) 제한 없음 (Auto-scaling 기반)

D) 아직 결정되지 않음

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
requirements.json의 구체적인 스키마가 정의되어 있습니까?

A) 예 - 별도 문서나 예시가 있음

B) 아니오 - AI Worker 측에서 정의해야 함

C) 아직 결정되지 않음 (Backend 팀과 협의 필요)

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 7
로그 및 모니터링 요구사항은 어느 수준입니까?

A) DynamoDB logs 필드 업데이트만 (요구조건서 기준)

B) CloudWatch Logs 추가 연동

C) 구조화된 로깅 + 메트릭 수집 (CloudWatch Metrics)

D) 아직 결정되지 않음

X) Other (please describe after [Answer]: tag below)

[Answer]: D

## Question 8: Security Extensions
이 프로젝트에 보안 확장 규칙을 적용해야 합니까?

A) 예 - 모든 보안 규칙을 블로킹 제약으로 적용 (프로덕션 수준 애플리케이션 권장)

B) 아니오 - 보안 규칙 건너뛰기 (PoC, 프로토타입, 실험적 프로젝트에 적합)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 9: Resiliency Extensions
이 프로젝트에 복원력 기준선을 적용해야 합니까?

이 확장은 AWS Well-Architected Framework(안정성 기둥)를 기반으로 한 설계 시점의 모범 사례를 제공합니다. 장애 허용, 고가용성, 관찰가능성, 복구 가능성 방향으로 설계를 안내합니다.

A) 예 - 복원력 기준선을 방향적 모범 사례로 적용 (비즈니스 크리티컬 워크로드 권장)

B) 아니오 - 복원력 기준선 건너뛰기 (PoC, 프로토타입, 실험적 프로젝트에 적합)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 10: Property-Based Testing Extension
이 프로젝트에 속성 기반 테스팅(PBT) 규칙을 적용해야 합니까?

A) 예 - 모든 PBT 규칙을 블로킹 제약으로 적용 (비즈니스 로직, 데이터 변환, 직렬화, 상태 컴포넌트가 있는 프로젝트 권장)

B) 부분적 - 순수 함수와 직렬화 라운드트립에만 PBT 규칙 적용

C) 아니오 - 모든 PBT 규칙 건너뛰기 (단순 CRUD, UI 전용 프로젝트에 적합)

X) Other (please describe after [Answer]: tag below)

[Answer]: C
