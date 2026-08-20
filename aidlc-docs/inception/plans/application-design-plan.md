# Application Design Plan - Prompton AI Worker

## Design Plan

- [x] 컴포넌트 식별 및 책임 정의
- [x] 컴포넌트 메서드 시그니처 정의
- [x] 서비스 계층 설계
- [x] 컴포넌트 의존성 관계 정의
- [x] 설계 완전성 및 일관성 검증

---

## Design Questions

아래 질문에 답변하여 설계 방향을 확정해주세요.

### Component Organization

## Question 1
AI Worker의 프로젝트 구조를 어떤 패턴으로 구성하시겠습니까?

A) Layered Architecture - 계층별 분리 (handler → service → repository/client)

B) Modular by Feature - 기능별 모듈 분리 (sqs/, s3/, dynamo/, ai/, build/)

C) Simple Flat Structure - 최소한의 파일 구조 (main.py + 헬퍼 모듈 몇 개)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

### Service Layer Design

## Question 2
Worker의 메인 루프 구현 방식은 어떤 것을 선호하시겠습니까?

A) 단순 while-loop + sleep (polling interval 기반)

B) Long Polling (WaitTimeSeconds=20 활용, 메시지 없으면 대기)

C) boto3 SQS 리소스의 기본 polling 메커니즘

X) Other (please describe after [Answer]: tag below)

[Answer]: C

### Component Dependencies

## Question 3
kiro-cli 호출 시 프로젝트 코드를 어디에 생성하시겠습니까?

A) 로컬 임시 디렉토리 (/tmp/jobs/{jobId}/) - 완료 후 정리

B) Worker 작업 디렉토리 내 고정 경로 (./workspace/jobs/{jobId}/)

C) EC2 인스턴스의 전용 데이터 볼륨 (/data/jobs/{jobId}/)

X) Other (please describe after [Answer]: tag below)

[Answer]: C

### Design Patterns

## Question 4
에러 처리 및 재시도 패턴은 어떤 수준으로 구현하시겠습니까?

A) 기본 try/except - 단계별 예외 캐치 후 FAILED 상태 기록

B) 재시도 로직 포함 - S3/DynamoDB 호출에 exponential backoff 적용

C) Circuit Breaker 패턴 - 외부 서비스(kiro-cli, Gradle) 장애 감지 및 차단

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 5
설정 관리 방식은 어떤 것을 선호하시겠습니까?

A) 환경 변수 기반 (AWS_REGION, QUEUE_URL, TABLE_NAME 등)

B) 설정 파일 (config.yaml 또는 config.json)

C) AWS Systems Manager Parameter Store

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
Graceful Shutdown (프로세스 종료 시 진행 중인 Job 처리)이 필요합니까?

A) 예 - SIGTERM 수신 시 현재 Job 완료 후 종료

B) 아니오 - 즉시 종료 (SQS Visibility Timeout으로 자동 재처리)

C) 기본 수준 - 현재 단계까지만 완료 후 종료

X) Other (please describe after [Answer]: tag below)

[Answer]: C
