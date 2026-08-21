# AI Worker 실제 운영 테스트 실행 계획

## 문서 상태

- **목적**: AI Worker를 실제 AWS dev/test 리소스, kiro-cli Claude Opus 5, Gradle/Android SDK와 연결하여 production-like 검증을 수행한다.
- **실행 상태**: PARTIALLY EXECUTED - NO-GO (2026-08-21)
- **코드 브랜치**: `feature/ai-worker-operational-readiness`
- **주의**: AI-DLC의 Operations 단계는 현재 placeholder다. 이 문서는 사용자 요청으로 작성한 운영 테스트 runbook이며 자동 배포를 의미하지 않는다.
- **변경 위험**: SQS 메시지, S3 객체, Backend Job 생성과 모델 사용 비용이 발생한다. 격리 리소스와 명시적 테스트 윈도우 승인 후 실행한다.
- **Status API migration override**: 아래 historical Gate 3, 4, 9의 direct DynamoDB 단계는 실행하지 않는다. Worker에는 DynamoDB IAM을 추가하지 않고 공식 Backend Job API를 사용한다.
- **공유 Queue 제한**: 외부 consumer와 로컬 systemd Worker가 동시에 polling하므로 journal Job ID로 처리 주체를 구분한다. Queue purge와 메시지 수동 삭제는 금지한다.

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
| Prompt Refiner | Hermes Agent v0.20.4 | service-user `HERMES_HOME`, provider/model, 사용 승인 |
| 대상 호스트 | EC2 t3.xlarge 권장 | 실제 인스턴스/AMI/스토리지 확정 |

## 테스트 시작 전 필수 준비물

### 1. 계약과 테스트 데이터

- [ ] Backend가 UTF-8 top-level raw Client JSON object를 64 KiB 이하로 S3에 저장하고 SQS pointer를 전송
- [ ] 성공이 예상되는 대표 raw Client JSON fixture 1개
- [ ] 실패가 예상되는 malformed/non-object/oversized fixture 1개
- [ ] 예상 Android application ID, API level, Kotlin, Jetpack Compose guardrail 결과 확정
- [ ] 선택적 PNG/JPEG asset fixture와 예상 개수 확정
- [ ] Hermes 성공 시 `refined-prompt.md`와 실패 시 raw Kiro fallback 판정 기준 확정
- [ ] SQS schema version 1.0 producer/consumer 계약 테스트 통과

Worker-side raw ingress, Hermes command/retry/output, and Kiro fallback contracts are implemented. The remaining contract gate is a real Backend endpoint that stores the raw object and sends the S3 pointer, plus live model execution evidence.

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
- [ ] Hermes Agent v0.20.4 설치와 service-user `HERMES_HOME=/data/hermes/.hermes` provider/model 설정
- [ ] `/data/hermes` 서비스 사용자 소유권과 systemd `ReadWritePaths` 반영
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
- [ ] `HERMES_CLI_PATH` 절대 경로와 `HERMES_HOME=/data/hermes/.hermes` 설정
- [ ] 환경 파일에 AWS Access Key, Secret Key, Session Token이 없음
- [ ] 필수 환경 변수와 실제 리소스명 일치

### 5. 승인과 증적 저장 위치

- [ ] AWS 변경 승인
- [ ] Claude Opus 5 사용량/비용 승인
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

1. Raw Client JSON S3 key/size/object 계약과 대표 fixture를 Backend와 승인한다.
2. Hermes Android guardrail, 3-attempt retry, `refined-prompt.md`, and raw Kiro fallback 판정 기준을 승인한다.
3. 전용 리소스 또는 dev 테스트 윈도우를 승인한다.
4. 비용, 중단 조건, cleanup 책임을 승인한다.

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
hermes --version
hermes config get model.provider
hermes config get model.default
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

**통과 조건**: 132 tests passed, Ruff 통과, mypy strict 25 source files 통과, compile 성공.

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
6. ANALYZING, GENERATING_CODE, Hermes completion/fallback, BUILDING, SUCCESS 순서를 기록한다.
7. Hermes 성공 시 `refined-prompt.md` 내용이 64 KiB 이하인지, 실패 시 Kiro raw fallback 로그가 있는지 확인한다.
8. source zip, APK, artifactKey, SQS 삭제 순서를 검증한다.
9. APK를 내려받아 SHA-256과 Android manifest를 검증한다.

**통과 조건**:
- progress가 25, 50, 75, 100 순서
- Hermes가 Kiro 전에 실행되고 raw JSON/stdout/stderr가 로그에 노출되지 않음
- Hermes 성공 또는 명시적 raw fallback 후 Kiro가 실행됨
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

## 2026-08-21 승인된 복구 검증 결과

### 완료 체크리스트

- [x] Kiro CLI 서비스 계정 인증과 companion runtime 복구
- [x] `claude-sonnet-4.5` 비대화식 file-generation smoke
- [x] Hermes service-account 실패 원인 진단
- [x] Worker graceful restart와 startup 검증
- [x] 공식 Backend Job 1건의 상태 전이와 artifact 검증
- [x] journal Job ID로 외부 Worker와 로컬 systemd Worker 결과 구분

### 증적과 판정

| 검증 항목 | 결과 | 핵심 증적 |
|---|---|---|
| Kiro service account | PASS | `HOME=/data/hermes` 인증, `chat --help`, non-interactive smoke exit 0 |
| Kiro 모델 | PASS | Kiro 2.18.1 지원 모델 `claude-sonnet-4.5`; 정확한 smoke 파일 생성 |
| Hermes refinement | DEGRADED | provider/model과 usable credential 부재로 3회 exit 1; raw Kiro fallback 정상 |
| systemd Worker | PASS | PID 44641, active/running/enabled, NRestarts=0, 실패 후 polling 복귀 |
| 공식 Backend Job | PASS WITH EXTERNAL WORKER | Job `58c76a31-8715-4804-8cd7-84ac25e5a409`이 SUCCESS 100과 debug APK 제공 |
| 성공 APK | PASS | 10,624,278 bytes, SHA-256 `36bc02994ac1ed73772c3aca97f7d9852f6c71a9f38ab2099491a8e5e7f9e88b`, ZIP/signature/aapt2 통과 |
| 로컬 Kiro code generation | PASS | Job `5d5efe3d-56cb-4297-a1a4-421dc3fc8c76`, 37 files, 58,992 bytes, Gradle project markers 생성 |
| 로컬 Android build | FAIL | 31-byte ASCII `gradle-wrapper.jar` placeholder로 `GradleWrapperMain` ClassNotFoundException |
| 로컬 full E2E 귀속 | BLOCKED | 공유 Queue의 외부 consumer가 공식 성공 Job을 처리했고 로컬은 stale/redelivered Job을 처리 |

외부 Worker 성공 Job의 artifact endpoint와 download는 HTTP 200이었고 metadata size가 실제 APK size와 일치했다. Presigned URL, 인증 code/token, 계정 식별자는 출력하거나 증적 파일에 저장하지 않았다. 안전한 artifact metadata는 `/tmp/prompton-e2e/732ae0a0-37a6-4397-b38f-a5ba8fc124a0/artifact-verification.json`에 저장했다.

로컬 Job은 Hermes raw fallback 후 Kiro가 03:12:22 UTC에 정상 종료하여 BUILDING에 진입했다. 생성된 `gradlew` 때문에 builder가 wrapper 존재만 신뢰했으나 `gradle-wrapper.jar`는 실제 ZIP/JAR가 아니라 `Gradle wrapper JAR placeholder` text였다. 따라서 이번 실패는 Kiro 인증/runtime 실패가 아니라 생성 wrapper 무결성 및 builder validation gap이다.

### 전체 Gate 결정

- Backend/SQS/S3/artifact 성공 경로: **PASS**, 단 처리 주체는 외부 Worker다.
- 로컬 service-account Kiro runtime과 Android 프로젝트 생성: **PASS**.
- 로컬 APK build와 local full E2E: **FAIL/BLOCKED**.
- Production activation: **NO-GO**.
- Extension compliance: Security Baseline, Resiliency Baseline, Property-Based Testing은 disabled이므로 N/A다. Project-specific secret redaction, Status API, SQS 안전 제약은 준수했다.

## 2026-08-21 Gradle Wrapper 복구 후속 결과

- **Source fix**: PASS - Wrapper script/JAR/properties 및 공식 distribution URL을 검증하고, invalid artifact는 격리 최소 Gradle project에서 재생성 후 재검증한다.
- **Kiro prevention**: PASS - Kiro는 wrapper scripts/binary JAR를 생성하지 않고 compatible official properties만 생성한다.
- **Automated gates**: PASS - targeted 19 tests, full 152 tests, Ruff lint, changed-file format, strict mypy 39 files, compileall, lock, diff checks.
- **Real wrapper recovery**: PASS - 31-byte placeholder를 47,505-byte valid JAR로 복구하고 `GradleWrapperMain.class`를 확인했다.
- **Isolated APK smoke**: PASS WITH CORRECTIONS - temporary Platform 35 overlay와 generated Kotlin compatibility 4개 보정 후 7,214,177-byte APK를 생성했다.
- **APK evidence**: SHA-256 `20076c994eb6c3a6862258b5e442df36ce9edc130d213c79c4ecc481d477f799`; ZIP, signature, aapt2 통과; package `com.appmaker.generated.app1945`, targetSdk 35, launchable `MainActivity`.
- **Original preservation**: PASS - 원본 Job의 31-byte placeholder와 SHA-256은 불변이며 temporary project/SDK/APK/log는 삭제했다.
- **Deployment status**: PENDING - source fix는 active `/opt/prompton-ai-worker`에 배포하거나 service restart하지 않았다.

## 2026-08-21 SDK 36 및 생성 호환성 후속 결정

- **Source SDK policy**: `minSdk=26`, `compileSdk=36`, `targetSdk=36`, Build Tools 36.0.0으로 고정하고 Client API level은 무시한다.
- **Source toolchain policy**: AGP 8.10.1, Gradle 8.11.1, JDK 17, Kotlin 1.9.24, Compose compiler 1.5.14, Compose BOM 2024.06.00으로 고정한다.
- **Compose prevention**: Material 3 progress에는 lambda가 아닌 `Float`를 전달하고 foundation pager 등 experimental API는 명시적으로 opt-in한다.
- **Host readiness**: `/opt/android-sdk`에 Platform 36과 Build Tools 36.0.0이 존재한다. Platform 35 부재는 새 source policy에서는 요구되지 않는다.
- **Kiro account plan**: `KIRO FREE`, 50 covered credits 중 4.81 사용(9%), 2026-09-01 reset.
- **Kiro model decision**: Kiro CLI 2.18.1의 9개 supported model에 Opus 계열과 `claude-opus-5`가 없으므로 `claude-sonnet-4.5`를 유지한다.
- **Deployment decision**: 사용자 지시에 따라 source 변경은 active Worker에 배포하지 않고 service를 restart하지 않는다.
- **Duplicate consumer decision**: 사용자 지시에 따라 현재 중복 consumer 상태를 accepted risk로 유지하며 Queue/external Worker를 변경하지 않는다.
- **Historical evidence**: 위 targetSdk 35 APK smoke는 당시 실패 원인 분석 증적으로 보존하며 현재 generation policy를 나타내지 않는다.

## 현재 차단 요소

1. **PENDING POST-DEPLOY E2E**: SDK36/Compose/wrapper source와 Opus 5는 active Worker에 배포됐지만, 배포 후 no-edit Android Job/APK E2E는 아직 실행하지 않았다.
2. **ACCEPTED RISK**: 공유 dev Queue의 외부 consumer와 로컬 systemd Worker 동시 polling은 사용자 결정으로 유지한다.
3. **DEGRADED / ROOT CAUSE CONFIRMED**: systemd Worker의 `HERMES_HOME=/data/hermes`가 잘못됐다. Hermes는 이 값을 exact config/state directory로 사용하므로 실제 `/data/hermes/.hermes/config.yaml`을 우회하고 Provider Auto/인증 없음으로 매번 exit 1을 반환한다. 변수만 동일하게 둔 synthetic call에서 Worker 환경은 exit 1/provider-not-configured였고, `HERMES_HOME=/data/hermes/.hermes`는 exit 0/exact output이었다. Active Job drain 후 protected env와 source `deploy/env.example`을 교정하고 graceful restart/new-Job 검증이 필요하다.
4. **PENDING**: 실패/DLQ, isolated Visibility, 성능 기준선, dependency/Bandit/IAM/systemd security의 전체 Gate 검증이 남아 있다.

이 차단 요소가 해소되기 전에는 production activation을 승인하지 않는다.

## 2026-08-21 current source Worker 배포 결과

- **Scope**: Source/active release inventory 27개 중 달랐던 `ai/generator.py`, `ai/refiner.py`, `build/builder.py` 세 파일만 배포했다. Manifest, lock, unit은 이미 동일했다.
- **Predeploy gate**: frozen lock/sync, full pytest 152 passed/70 known warnings, Ruff, strict mypy 39 files, compileall, diff, Status API/no-DynamoDB boundary 통과.
- **Host readiness**: protected env owner/mode와 key contract, writable data paths, Platform 36, Build Tools 36.0.0, Worker JDK 17, disk, idle state 통과.
- **Rollback**: 기존 active 세 파일과 checksum/mode manifest를 root-only mode 0600 backup으로 보존했다.
- **Install**: Worker graceful stop 후 세 파일을 fsync 및 atomic replace했고 owner/mode를 보존했다. Installed hash는 source와 일치하고 전체 27-file inventory difference는 0이다.
- **Deployed verification**: compile, exact `claude-opus-5`, SDK36/Compose fixed guardrails, Wrapper recovery, pinned dependencies, Status API/no-DynamoDB boundary, systemd unit 검증 통과.
- **Worker restore**: PID 49807, active/running, Result=success, NRestarts=0, TasksCurrent=1, startup error marker 0, Kiro child 0.
- **Authentication**: post-start `IamIdentityCenter`와 exact Opus 5 catalog support 확인.
- **Boundary**: Job을 제출하지 않았고 Queue/IAM/DynamoDB/external Worker/env/unit/venv/authentication을 변경하지 않았다.

## 2026-08-21 Kiro 조직 프로필 전환 결과

- **Credential transition**: PASS - 명시적으로 승인된 local DB transfer를 SQLite online snapshot과 atomic replace로 수행했고 source, pre-copy backup, installed DB integrity가 모두 `ok`다.
- **Identity/profile**: PASS - service account는 `IamIdentityCenter`이며 TTY profile fetch와 현재 profile 확정이 정상 종료했다.
- **Plan**: `KIRO PRO+`, 2000 covered credits 중 1603.14 사용(80%), 2026-09-01 reset.
- **Catalog**: 19개 모델이며 exact `claude-opus-5`를 지원한다. Source와 active deployed model 모두 Opus 5다.
- **Opus 5 smoke**: PASS - non-interactive exit 0, 정확히 한 파일과 정확한 content를 검증했고 temporary directory를 삭제했다.
- **Worker restore**: PASS - PID 49141, active/running, NRestarts=0, TasksCurrent=1, startup error marker 없음.
- **Deployment boundary**: Opus 5 model-only active hotfix만 적용됐다. SDK36/Compose/wrapper 등 나머지 source 변경은 계속 미배포 상태다.
- **Safety**: 인증 URL/code/token, email/account/provider 식별자를 기록하지 않았고 Queue, IAM, DynamoDB, external Worker를 변경하지 않았다.


## 2026-08-21 Kiro Opus 5 quick activation

- **Approval**: 사용자가 exact Opus 5 지원 확인 후 quick source/runtime activation을 요청했다.
- **Source**: `KIRO_CLI_MODEL`과 focused assertion을 `claude-opus-5`로 변경했다.
- **Source validation**: generator tests 9 passed; Ruff lint/format, strict mypy, compileall, selected diff check 통과.
- **Active hotfix**: Worker idle 확인 후 graceful stop하고 deployed generator를 root-only mode 0600으로 backup했다. Deployed unified diff는 Sonnet 4.5에서 Opus 5로 바뀐 두 줄뿐이다.
- **Runtime validation**: deployed venv compile과 AST model 검증 통과. Service-account Opus 5 smoke는 exit 0, 정확히 한 파일과 exact content를 생성하고 cleanup했다.
- **Worker restore**: PID 49405, active/running, NRestarts=0, TasksCurrent=1, startup error marker 0, idle Kiro child 0.
- **Boundary**: 전체 source tree는 배포하지 않았다. Queue, IAM, DynamoDB, external Worker, authentication state는 변경하지 않았다.

## 2026-08-21 active SQS polling 진단

- **사용자 보고**: Queue에 메시지가 보이지만 local Worker가 가져오지 못하는 것으로 관찰됐다.
- **실제 수신**: Local Worker는 04:42:40 UTC에 메시지 1건을 수신하고 Visibility Extender를 시작했다.
- **현재 처리**: ANALYZING 완료 후 Hermes 3회 실패를 raw requirements fallback으로 처리했고 04:42:53 UTC부터 exact `claude-opus-5` 코드 생성 중이다.
- **순차 처리 원인**: `MAX_MESSAGES_PER_RECEIVE=1`이며 main loop가 `process_job()`을 동기 실행한다. 현재 Job이 종료되기 전에는 다음 `receive_message()`를 호출하지 않는다.
- **Queue read-only evidence**: 최초 visible 0/in-flight 3, 후속 visible 2/in-flight 1, delayed 0이었다. Approximate attributes이며 외부 consumer 또는 신규 메시지의 영향을 받을 수 있다.
- **오류 판정**: `sqs_receive_failed`는 0건이다. Status API intermediate PATCH 409는 `action=continue`로 처리되어 code generation을 막지 않는다.
- **복구 판정**: 복구 불필요. Active Job 중 Worker restart는 redelivery 위험을 높이므로 수행하지 않는다.
- **안전 경계**: Manual receive/delete/purge/change-visibility, Queue/IAM/DynamoDB/external Worker/config 변경을 수행하지 않았다.

## 2026-08-21 Hermes prompt refinement 실패 원인

- **Hermes runtime**: v0.20.4 executable과 `HOME=/data/hermes`는 정상이다.
- **Worker invocation**: `--ignore-rules --toolsets context_engine --oneshot <prompt>`를 실행하고 exit 0/비어 있지 않은 64 KiB 이하 stdout만 승인한다.
- **Retry evidence**: Job마다 attempt 1~3이 모두 exit code 1이며 1초/2초 delay 후 raw fallback으로 전환됐다.
- **Root cause**: Hermes inference backend 미설정. Resolved 상태는 Model `(not set)`, Provider `Auto`이며 inference OAuth/API-key provider가 모두 not logged in/not configured다.
- **Credential evidence**: Service env와 Hermes `.env`에 active provider/model/API-key/endpoint가 없고 `active_provider`는 null이며 Hermes inference auth file도 없다.
- **Non-causes**: executable, service HOME, input JSON, output path, toolset, Kiro organization profile은 정상이다. SQLite WAL compatibility warning은 inference exit 1과 무관하다.
- **Fallback impact**: Prompt refinement만 생략된다. Worker는 원본 JSON과 동일한 SDK36/Compose guardrail을 exact Opus 5에 전달해 generation을 계속한다.
- **Security behavior**: Refiner는 untrusted stdout/stderr를 journal에 기록하지 않아 실제 provider 오류 문자열 대신 exit code만 남긴다.

## 2026-08-21 service Hermes inference 설정 완료

- **승인**: 사용자가 ubuntu의 working Hermes inference 설정을 `prompton` service HOME에 적용하도록 요청했다.
- **최소 이전**: Ubuntu `config.yaml`에서 `model`과 active custom provider 한 항목만 추출했다. Unrelated auth pool과 inference 설정이 없는 `.env`는 복사하지 않았다.
- **Credential 위치**: Active provider definition 안의 literal API credential만 minimal config에 포함되며 값은 출력하거나 audit에 기록하지 않았다.
- **Rollback**: Service target은 이전에 없었다. Incoming minimal config와 absence manifest를 root-only mode 0600 backup에 보존했다.
- **설치**: `/data/hermes/.hermes/config.yaml`, `prompton:prompton`, mode 0600, parent 0700, source snapshot과 hash 일치.
- **Status**: Service Hermes가 configured model/custom provider를 정상 해석하고 exit 0을 반환한다.
- **Inference smoke**: Restricted one-shot은 exit 0과 exact `HERMES_SERVICE_OK`를 반환했다.
- **Worker integration**: Deployed `PromptRefiner`가 synthetic requirements로 nonempty/64 KiB 이하 output을 생성하고 temporary directory를 정리했다.
- **Service coordination**: Active Job은 Hermes 단계를 이미 지난 상태이고 Hermes child가 없어 Worker stop/restart 없이 atomic config만 설치했다.
- **Expected effect**: 이후 Job부터 Hermes refinement가 활성화된다. 이미 raw fallback으로 진행한 Job에는 소급 적용되지 않는다.
- **Safety**: Project/user data를 smoke에 사용하지 않았고 Queue/IAM/DynamoDB/external Worker/Kiro auth를 변경하지 않았다.

## 2026-08-21 SQS 500ms short-poll 변경

- **요청**: 빈 Queue polling을 500ms cadence로 변경한다.
- **구현 해석**: SQS `WaitTimeSeconds`는 정수이므로 0초 short poll 후 빈 응답에만 0.5초 sleep을 적용한다.
- **Shutdown**: shutdown requested 상태에서는 추가 sleep을 생략한다.
- **불변 조건**: `MaxNumberOfMessages=1`, 순차 Job 처리, visibility extension, SUCCESS 이후 delete gate는 유지한다.
- **운영 위험**: Idle receive API 요청량이 최대 약 40배 증가하고 short polling false-empty 및 비용/API load가 증가할 수 있다.
- **Queue boundary**: Queue attribute, IAM, DynamoDB, external Worker는 변경하지 않는다.
- **Deployment**: Active Job에 graceful shutdown을 요청해 강제 종료 없이 현재 처리가 반환된 후 Worker가 종료됐다. 두 polling 파일만 root-only backup 후 atomic 배포했다.
- **Rollback**: `/var/backups/prompton-worker/sqs-500ms-polling-20260821T053253Z`, prior files와 manifest는 root:root mode 0600이다.
- **Deployed verification**: 27-file source/active inventory difference 0, deployed compile 통과, execution recorder에서 `WaitTimeSeconds=0`, `MaxNumberOfMessages=1`, empty delay 정확히 0.5초를 확인했다.
- **Worker restore**: PID 53329, active/running, NRestarts=0, TasksCurrent=1, startup/observation error marker 0, `IamIdentityCenter` 유지.
- **Idle observation**: Local receive 0건, Queue visible 0이었다. Approximate in-flight 1건은 다른 consumer일 수 있다.
- **Accepted operational risk**: 약 40배 idle API 요청량과 short-poll CPU/API overhead를 이 quick change에서 수용한다.

## 2026-08-21 실제 요청 Hermes replay 결과

- 사용자 승인으로 terminal Job의 실제 requirements를 service-owned 격리 경로에서 Hermes provider에 다시 전송했다.
- Deployed prompt builder, 실제 Job ID, service HOME/provider/model과 exact one-shot flags를 사용한 3,327-byte prompt가 attempt 1에서 exit 0, stdout 1,255 bytes, stderr 0으로 성공했다.
- Trimmed 1,254-byte output은 deployed size/NUL gate, wrapper/fence/credential 검사와 Android guardrail 16/16을 통과하고 원본의 valid package candidate를 보존했다.
- 결과는 historical 실행과 구분되는 `refined-prompt-replay.md`로 terminal Job에 atomic/mode 0600 보존했다. Canonical `refined-prompt.md`는 생성하지 않았다.
- 같은 실제 입력의 replay가 성공한 이유는 `HOME=/data/hermes`만 설정하고 Worker의 잘못된 `HERMES_HOME=/data/hermes`를 상속하지 않았기 때문이다. 따라서 이 replay는 prompt content를 배제했지만 Worker 환경을 재현하지 않았으며, 이전 transient 판정은 superseded다. 변수-only 재현에서 Worker 값은 Provider Auto/exit 1, corrected `HERMES_HOME=/data/hermes/.hermes`는 exit 0이었다. Historical stderr 원문은 폐기됐지만 동일 190-byte 오류의 안전한 분류는 provider-not-configured/auth-missing이다.
- 격리 복사본은 삭제했고 Worker는 active/running, `NRestarts=0`, child 0을 유지했다. Queue/IAM/DynamoDB/external Worker/message/service는 변경하지 않았다.
