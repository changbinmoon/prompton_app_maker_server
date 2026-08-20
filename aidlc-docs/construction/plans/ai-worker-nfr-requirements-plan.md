# NFR Requirements Plan - AI Worker

## Plan

- [x] Python 기술 스택 상세 결정
- [x] 성능/처리량 요구사항 정의
- [x] 안정성/가용성 요구사항 정의
- [x] 보안 요구사항 확정
- [x] 운영/유지보수 요구사항 정의

---

## NFR Questions

### Tech Stack

## Question 1
Python 버전은 무엇을 사용하시겠습니까?

A) Python 3.11

B) Python 3.12

C) Python 3.13

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 2
Python 패키지 관리자는 무엇을 사용하시겠습니까?

A) pip + requirements.txt

B) pip + pyproject.toml

C) Poetry

D) uv

X) Other (please describe after [Answer]: tag below)

[Answer]: X = 추천

### Performance

## Question 3
단일 Job의 최대 허용 처리 시간은 얼마입니까? (AI 생성 + 빌드 포함)

A) 10분 이내

B) 30분 이내

C) 1시간 이내

D) 제한 없음 (완료까지)

X) Other (please describe after [Answer]: tag below)

[Answer]: D

### Operations

## Question 4
Worker 프로세스 관리 방식은 어떻게 하시겠습니까?

A) systemd 서비스로 등록 (자동 재시작)

B) 수동 실행 (python main.py)

C) supervisor 등 프로세스 매니저 사용

D) Docker 컨테이너로 실행

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
EC2 인스턴스 사양은 어느 정도를 예상하시겠습니까?

A) t3.medium (2 vCPU, 4GB RAM) - 경량 처리

B) t3.large (2 vCPU, 8GB RAM) - 빌드 고려

C) t3.xlarge (4 vCPU, 16GB RAM) - 여유 확보

D) 아직 결정되지 않음

X) Other (please describe after [Answer]: tag below)

[Answer]: C
