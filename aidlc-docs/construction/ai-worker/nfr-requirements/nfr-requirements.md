# NFR Requirements - AI Worker

## 1. 성능 요구사항

### NFR-PERF-001: 처리 시간
- **요구사항**: 단일 Job의 처리 시간에 상한 제한 없음
- **근거**: AI 코드 생성 및 Gradle 빌드 시간이 가변적이며, Visibility Timeout 연장으로 관리
- **모니터링**: 각 단계별 소요 시간을 로그로 기록하여 추후 분석 가능

### NFR-PERF-002: 처리량
- **요구사항**: 동시 1개 Job 순차 처리
- **목표**: 최대 가용 처리량은 단일 Job 완료 후 다음 Job 즉시 시작
- **제한**: EC2 단일 인스턴스, 멀티프로세싱 없음

### NFR-PERF-003: SQS Polling 효율
- **요구사항**: boto3 기본 polling 메커니즘 사용 (Long Polling 포함)
- **WaitTimeSeconds**: 20초 (메시지 없을 때 대기, 불필요한 API 호출 절감)

---

## 2. 안정성/가용성 요구사항

### NFR-REL-001: 멱등성
- **요구사항**: 동일 Job 메시지를 여러 번 수신해도 안전하게 처리
- **구현**: jobId 기준 DynamoDB 상태 확인 → SUCCESS/CANCELED이면 skip
- **작업 디렉토리**: 동일 jobId 디렉토리 존재 시 삭제 후 재생성

### NFR-REL-002: 장애 복구
- **요구사항**: Worker 장애 시 미완료 Job이 자동으로 재처리됨
- **메커니즘**: SQS Visibility Timeout 만료 → 메시지 재가시화 → 재처리
- **DLQ**: 3회 연속 실패 시 DLQ로 이동 (prompton-app-build-jobs-dlq-dev)

### NFR-REL-003: 프로세스 자동 재시작
- **요구사항**: Worker 프로세스 비정상 종료 시 자동 재시작
- **구현**: systemd 서비스 등록 (Restart=on-failure)
- **재시작 딜레이**: 5초

### NFR-REL-004: Graceful Shutdown
- **요구사항**: SIGTERM 수신 시 현재 처리 단계까지 완료 후 종료
- **동작**: 새 Job 수신 중지, 현재 단계 완료, 프로세스 종료
- **미완료 Job**: SQS Visibility Timeout 만료 후 자동 재처리

### NFR-REL-005: Visibility Timeout 관리
- **요구사항**: 장시간 처리 시 중복 처리 방지를 위해 Timeout 연장
- **주기**: Queue Visibility Timeout의 50%마다 연장
- **연장 실패**: 로그 기록 후 처리 계속 (멱등성으로 보호)

---

## 3. 보안 요구사항

### NFR-SEC-001: IAM 최소 권한
- **요구사항**: EC2 Instance Profile에 필요 최소한의 권한만 부여
- **필요 권한**:
  - SQS: ReceiveMessage, DeleteMessage, ChangeMessageVisibility, GetQueueAttributes
  - S3: GetObject (jobs/*/requirements/*, jobs/*/assets/*), PutObject (jobs/*/source/*, jobs/*/artifact/*)
  - DynamoDB: GetItem, UpdateItem
- **금지**: AdministratorAccess, 와일드카드(*) 리소스

### NFR-SEC-002: 자격증명 관리
- **요구사항**: 코드에 AWS Access Key를 하드코딩하지 않음
- **구현**: EC2 IAM Role / Instance Profile 사용 (boto3 자동 인증)

### NFR-SEC-003: 로그 보안
- **요구사항**: 로그에 민감 정보를 포함하지 않음
- **대상**: AWS Keys, Session Token, Presigned URL, API Key, 사용자 비밀정보
- **검증**: 로그 메시지 작성 시 패턴 검사

### NFR-SEC-004: 작업 디렉토리 보안
- **요구사항**: 작업 디렉토리 권한을 Worker 프로세스 사용자로 제한
- **권한**: 700 (owner만 읽기/쓰기/실행)

---

## 4. 운영/유지보수 요구사항

### NFR-OPS-001: 프로세스 관리
- **방식**: systemd 서비스
- **서비스 파일**: /etc/systemd/system/prompton-worker.service
- **기능**: 자동 시작, 자동 재시작, 로그 수집 (journalctl)

### NFR-OPS-002: 로깅
- **로컬 로그**: Python logging → stdout/stderr → journalctl 수집
- **사용자 로그**: DynamoDB logs 필드 업데이트 (앱에서 조회)
- **로그 레벨**: INFO (기본), DEBUG (개발 환경)

### NFR-OPS-003: 디스크 관리
- **작업 디렉토리**: /data/jobs/ (전용 볼륨)
- **정리 정책**: 24시간 이후 자동 삭제
- **모니터링**: 디스크 사용량 기본 모니터링 (추후 CloudWatch 연동 가능)

### NFR-OPS-004: 배포
- **방식**: Git 기반 코드 배포 + systemd 서비스 재시작
- **의존성 설치**: uv sync
- **설정**: 환경 변수 (systemd EnvironmentFile 또는 /etc/environment)

---

## 5. 확장성 요구사항

### NFR-SCALE-001: 현재 구조
- **현재**: 단일 EC2, 순차 처리 (1 Job/time)
- **처리량**: AI 생성 + 빌드 시간에 의존 (예상: Job당 5~30분)

### NFR-SCALE-002: 향후 확장 경로 (참고용)
- **수평 확장**: EC2 인스턴스 추가 + SQS 자동 분배 (코드 변경 없이 가능)
- **수직 확장**: 인스턴스 사양 업그레이드
- **현재 단계**: 확장 불필요 (MVP, 단일 인스턴스)
