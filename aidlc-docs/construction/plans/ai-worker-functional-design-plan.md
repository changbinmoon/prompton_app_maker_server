# Functional Design Plan - AI Worker

## Design Plan

- [x] 비즈니스 로직 모델 정의 (처리 시퀀스, 상태 머신)
- [x] 비즈니스 규칙 및 유효성 검증 정의
- [x] 도메인 엔티티 정의

---

## Design Questions

### Business Logic

## Question 1
kiro-cli 호출 시 프롬프트 구성 방식은 어떻게 할 예정입니까?

A) requirements.json 내용을 그대로 kiro-cli에 전달 (파이프라인)

B) requirements.json을 분석하여 구조화된 프롬프트 템플릿에 삽입 후 전달

C) requirements.json + 에셋 정보를 결합한 마크다운 형식으로 변환 후 전달

D) kiro-cli가 직접 requirements.json 파일을 읽도록 경로만 전달

X) Other (please describe after [Answer]: tag below)

[Answer]: D

## Question 2
Visibility Timeout 연장 주기는 어떻게 설정하시겠습니까?

A) Queue의 Visibility Timeout 값의 50% 주기 (예: 30초 Timeout → 15초마다 연장)

B) 고정 주기 (예: 60초마다 연장)

C) 각 처리 단계 시작 시 연장 (단계별 1회)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
Job 처리 완료 후 작업 디렉토리(/data/jobs/{jobId}/) 정리 방식은?

A) 즉시 삭제 (Job 완료/실패 후 바로 정리)

B) 일정 기간 보존 후 삭제 (디버깅용, 예: 24시간)

C) 수동 정리 (자동 삭제 하지 않음)

X) Other (please describe after [Answer]: tag below)

[Answer]: B = 24시간

## Question 4
kiro-cli 실행 시 타임아웃을 설정해야 합니까?

A) 예 - 고정 타임아웃 (예: 10분)

B) 예 - 단계별 다른 타임아웃 (분석: 5분, 코드 생성: 15분)

C) 아니오 - 타임아웃 없이 완료까지 대기

X) Other (please describe after [Answer]: tag below)

[Answer]: C
