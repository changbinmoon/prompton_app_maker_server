# AI Worker 실제 운영 테스트 실행 계획

## 문서 상태

- **목적**: AI Worker를 실제 AWS dev/test 리소스, kiro-cli Opus 5, Gradle/Android SDK와 연결하여 production-like 검증을 수행한다.
- **실행 상태**: NOT STARTED
- **코드 브랜치**: `feature/ai-worker-operational-readiness`
- **주의**: AI-DLC의 Operations 단계는 현재 placeholder다. 이 문서는 사용자 요청으로 작성한 운영 테스트 runbook이며 자동 배포를 의미하지 않는다.
- **변경 위험**: SQS 메시지, S3 객체, DynamoDB 레코드 생성·삭제와 모델 사용 비용이 발생한다. 격리 리소스와 명시적 테스트 윈도우 승인 후 실행한다.

## 현재 확인된 대상

| 항목 | 값 | 테스트 전 확인 |
|---|---|---|
| Region | `us-east-1` | 계정 및 리전 재확인 |
| Main Queue | `prompton-app-build-jobs-dev` | 전용 테스트 Queue 사용 권장 |
| Queue URL | `https://sqs.us-east-1.amazonaws.com/440052841756/prompton-app-build-jobs-dev` | VisibilityTimeout 및 RedrivePolicy 확인 |
| DLQ | `prompton-app-build-jobs-dlq-dev` | `maxReceiveCount=3` 확인 |
| S3 | `prompton-app-builder-dev-changbin` | 테스트 Job prefix 격리 |
| DynamoDB | `prompton-jobs-dev`, PK `jobId` | 테스트 레코드만 변경 |
| Worker 모델 | `claude-opus-5` | kiro-cli 인증 및 사용 승인 |
| Worker CLI | kiro-cli 2.18.1 | `chat --no-interactive` 호환성 확인 |
| 대상 호스트 | EC2 t3.xlarge 권장 | 실제 인스턴스/AMI/스토리지 확정 |

## 테스트 시작 전 필수 준비물

### 1. 계약과 테스트 데이터

- [ ] Backend와 versioned `requirements.json` 필드 스키마 확정
- [ ] 성공이 예상되는 대표 requirements fixture 1개
- [ ] 실패가 예상되는 안전한 negative fixture 1개
- [ ] 예상 Android application ID, 최소 SDK, target SDK 확정
- [ ] 선택적 PNG/JPEG asset fixture와 예상 개수 확정
- [ ] SQS schema version 1.0 producer/consumer 계약 테스트 통과

`requirements.json`은 현재 JSON 객체 여부만 검증하므로 필드 스키마 미확정 상태에서는 실제 성공 E2E의 판정 기준이 없다. 이 항목은 첫 번째 차단 요소다.

### 2. 격리된 AWS 테스트 리소스

- [ ] 전용 테스트 Queue와 DLQ 또는 승인된 dev Queue 테스트 윈도우
- [ ] RedrivePolicy와 `maxReceiveCount=3`
- [ ] 테스트 전용 S3 bucket/prefix
- [ ] 테스트 전용 DynamoDB table 또는 고유 Job ID namespace
- [ ] CloudWatch SQS 지표 및 EC2 기본 지표 접근
- [ ] 테스트 Job cleanup 책임자와 보존 기간
- [ ] 공유 Queue에서 `purge-queue`를 사용하지 않는다는 합의

### 3. EC2와 런타임

- [ ] Linux EC2와 Instance Profile 준비
- [ ] 4 vCPU, 16 GB RAM 수준의 기준 인스턴스
- [ ] `/data/jobs` 전용 writable 경로와 충분한 여유 공간
- [ ] `/data/gradle` 사용 시 디렉터리 생성, 서비스 사용자 소유권, systemd `ReadWritePaths` 반영
- [ ] Python 3.12와 uv 0.8.12
- [ ] kiro-cli 2.18.1 로그인 및 `claude-opus-5` 모델 조회
- [ ] Java, Gradle, Android SDK, Android Build Tools 설치
- [ ] Java 버전과 생성 프로젝트의 Android Gradle Plugin 호환성 확인
- [ ] `prompton` 사용자와 systemd 서비스 설치
- [ ] 패키지 저장소, AWS API, kiro-cli 서비스에 필요한 outbound 연결

### 4. IAM과 설정

- [ ] SQS: ReceiveMessage, DeleteMessage, ChangeMessageVisibility, GetQueueAttributes
- [ ] S3: requirements/assets GetObject, assets ListBucket, source/artifact PutObject
- [ ] DynamoDB: GetItem, UpdateItem
- [ ] 리소스 ARN 수준 최소 권한과 명시적 거부 테스트
- [ ] `/etc/prompton-worker/env` mode 0640 이하
- [ ] 환경 파일에 AWS Access Key, Secret Key, Session Token이 없음
- [ ] 필수 환경 변수와 실제 리소스명 일치

### 5. 승인과 증적 저장 위치

- [ ] AWS 변경 승인
- [ ] Opus 5 사용량/비용 승인
- [ ] 테스트 시작·종료 시각과 담당자 확정
- [ ] 중단 권한자와 롤백 담당자 확정
- [ ] 테스트 증적 저장 위치 확정

권장 증적:
- 배포 commit SHA와 환경 버전
- Job별 UTC 상태 전이 시각
- sanitized journald 로그
- DynamoDB 최종 레코드
- S3 object metadata와 APK SHA-256
- SQS receive count, DLQ 및 Visibility 증적
- CPU, 메모리, 디스크, 처리시간 측정값

## 단계별 실행 절차

## Gate 0: 계약 및 변경 승인

1. `requirements.json` 스키마와 대표 fixture를 Backend와 승인한다.
2. 전용 리소스 또는 dev 테스트 윈도우를 승인한다.
3. 비용, 중단 조건, cleanup 책임을 승인한다.

**통과 조건**: 모든 필수 입력과 변경 승인이 문서화됨.

## Gate 1: 대상 브랜치와 호스트 배포

```bash
git fetch origin
git checkout -B operational-test \
  origin/feature/ai-worker-operational-readiness
git rev-parse HEAD
export PATH="$HOME/.local/bin:$PATH"
uv sync --extra dev --frozen
uv lock --check
```

1. 출력된 commit SHA를 테스트 기록에 남긴다.
2. `deploy/env.example`을 기반으로 실제 환경 파일을 작성한다.
3. systemd unit의 사용자, 작업 경로, Java/Gradle/SDK 경로, `ReadWritePaths`를 확인한다.
4. 서비스를 시작하기 전 설정을 검증한다.

```bash
kiro-cli --version
kiro-cli chat --list-models --format json-pretty
gradle --version
java -version
systemd-analyze verify deploy/prompton-worker.service
```

**통과 조건**: frozen 환경과 외부 도구 버전이 기록되고 설정 오류가 없음.

## Gate 2: 로컬 품질 게이트

```bash
uv run python -m compileall -q \
  main.py ai build config dynamo models s3 sqs utils worker tests
uv run pytest
uv run ruff check .
uv run mypy main.py config models sqs s3 dynamo ai build utils worker
```

**통과 조건**: 105 tests passed, Ruff 통과, mypy strict 통과, compile 성공.

## Gate 3: AWS 및 IAM 비파괴 preflight

```bash
set -a
source /etc/prompton-worker/env
set +a
aws sts get-caller-identity
aws sqs get-queue-attributes \
  --queue-url "$SQS_QUEUE_URL" \
  --attribute-names VisibilityTimeout RedrivePolicy
aws s3api head-bucket --bucket "$S3_BUCKET_NAME"
aws dynamodb describe-table --table-name "$DYNAMODB_TABLE_NAME"
```

1. AWS account ID와 Region이 승인 대상과 같은지 확인한다.
2. Queue와 DLQ 연결, VisibilityTimeout, maxReceiveCount를 기록한다.
3. 허용 동작과 금지된 관리 동작의 IAM 결과를 기록한다.

**통과 조건**: 올바른 계정/리전이며 필수 최소 권한만 동작함.

## Gate 4: 성공 경로 1-Job E2E

상세 생성·전송·조회·cleanup 명령은 `../construction/build-and-test/integration-test-instructions.md`를 따른다.

1. 고유 UUID Job ID를 생성한다.
2. DynamoDB에 QUEUED 테스트 레코드를 넣는다.
3. 승인된 requirements와 assets를 Job prefix에 업로드한다.
4. SQS schema 1.0 메시지를 1건 전송한다.
5. systemd Worker를 시작하고 로그를 추적한다.
6. ANALYZING, GENERATING_CODE, BUILDING, SUCCESS 순서를 기록한다.
7. source zip, APK, artifactKey, SQS 삭제 순서를 검증한다.
8. APK를 내려받아 SHA-256과 Android manifest를 검증한다.

**통과 조건**:
- progress가 25, 50, 75, 100 순서
- SUCCESS 전에 APK upload가 검증됨
- SUCCESS 이후에만 SQS 메시지 삭제
- APK가 비어 있지 않고 Android 도구로 파싱됨
- 로그에 자격증명, 토큰, signed URL, 내부 비밀이 없음

## Gate 5: 실패·재시도·DLQ

전용 Queue에서만 실행한다.

1. 안전한 deterministic failure Job을 전송한다.
2. FAILED, errorCode, 마지막 progress 보존을 확인한다.
3. 실패 메시지가 즉시 삭제되지 않음을 확인한다.
4. VisibilityTimeout 후 재수신과 3회 실패 후 DLQ 이동을 확인한다.
5. 재시도 시 Job 작업 디렉터리가 깨끗하게 재생성되는지 확인한다.

**통과 조건**: 데이터 유실 없이 retry/DLQ 정책이 정확히 동작함.

## Gate 6: 장시간 처리 및 Visibility 연장

1. VisibilityTimeout보다 오래 걸리는 대표 Job을 실행한다.
2. 약 50% 주기로 ChangeMessageVisibility가 호출되는지 확인한다.
3. 다른 Worker가 같은 Job을 동시에 처리하지 않는지 확인한다.
4. 한 번의 연장 실패를 허용했을 때 Job 처리와 멱등성이 유지되는지 확인한다.

**통과 조건**: 정상 연장 중 중복 처리가 없고 일시 실패가 프로세스를 중단하지 않음.

## Gate 7: 성능 기준선

상세 절차는 `../construction/build-and-test/performance-test-instructions.md`를 따른다.

1. 대표 Job 1건으로 cold/warm cache 처리시간과 peak resource를 측정한다.
2. 3개 Job을 연속 전송하여 strict sequential 처리를 확인한다.
3. 전용 환경에서 10개 backlog를 생성해 drain time을 측정한다.
4. CPU, RSS, 디스크, EBS I/O, Jobs/hour, visibility count를 기록한다.

현재 승인된 latency/throughput SLA는 없다. 첫 실행 결과를 기준선으로 저장하고 이후 회귀 기준을 합의한다.

## Gate 8: 보안·서비스 운영성

상세 절차는 `../construction/build-and-test/security-test-instructions.md`를 따른다.

1. dependency audit와 Bandit을 실행한다.
2. 환경 파일과 소스의 secret scan을 실행한다.
3. IAM least-privilege와 금지 동작을 확인한다.
4. `systemd-analyze security`와 journald를 확인한다.
5. SIGTERM 시 현재 Job 완료 후 종료되는지 확인한다.
6. 비정상 종료 후 `Restart=on-failure`가 동작하는지 확인한다.
7. 24시간 초과 Job 디렉터리 cleanup을 검증한다.

**통과 조건**: High 보안 이슈가 없고 서비스 재시작·종료·cleanup이 설계대로 동작함.

## Gate 9: Cleanup 및 Go/No-Go

1. 테스트 S3 prefix와 DynamoDB 레코드를 Job ID 단위로 삭제한다.
2. 잔류 메시지는 receipt handle로만 삭제한다. 공유 Queue를 purge하지 않는다.
3. 로컬 Job 디렉터리와 테스트 결과 보존 정책을 적용한다.
4. 모든 증적과 예외를 검토한다.
5. production activation 여부를 별도로 승인한다.

**Go 조건**:
- Gate 0~8 필수 항목 통과
- 미해결 Blocker 또는 High 보안 이슈 없음
- requirements 계약과 rollback 책임자 확정
- 실제 성공 E2E, 실패/DLQ, Visibility, 성능 기준선 증적 존재

## 즉시 중단 조건

- AWS account 또는 Region 불일치
- 공유/production 리소스에 승인되지 않은 변경 감지
- 유효 Job의 비정상 반복 실패
- 중복 Job 처리 또는 메시지 조기 삭제
- 자격증명/토큰 로그 노출
- OOM, 디스크 안전 임계치 미만, 반복 systemd restart
- 예상 밖의 모델 사용량 또는 비용 증가

중단 시 Worker를 정지하고 새 메시지 전송을 중단한다. 진행 중 메시지는 삭제하지 않고 Visibility/DLQ 상태를 보존한 뒤 증적을 수집한다.

## 현재 차단 요소

1. **BLOCKER**: field-level `requirements.json` 스키마와 대표 성공 fixture 미확정
2. **BLOCKER**: 실제 테스트 EC2, IAM Role, Queue/DLQ 격리 방식 미검증
3. **BLOCKER**: 실제 Java/Android Gradle Plugin 호환 조합 미확정
4. **APPROVAL REQUIRED**: AWS 리소스 변경과 Opus 5 사용 비용
5. **PENDING**: live E2E, performance baseline, dependency/Bandit/IAM/systemd security 검증

이 차단 요소가 해소되기 전에는 production activation을 승인하지 않는다.
