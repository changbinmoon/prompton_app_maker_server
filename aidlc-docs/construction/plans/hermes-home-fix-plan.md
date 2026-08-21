# Worker HERMES_HOME 교정 계획

## 상태

- **승인**: 2026-08-21T07:03:16.542Z 사용자 `진행`
- **원인**: systemd Worker의 `HERMES_HOME=/data/hermes`가 exact config directory 대신 OS HOME를 가리켜 `/data/hermes/.hermes/config.yaml`을 우회한다.
- **목표**: source와 active env를 `HERMES_HOME=/data/hermes/.hermes`로 교정하고 Worker-equivalent Hermes 호출을 검증한다.
- **안전 경계**: Active Job/Kiro 강제 종료 금지, Queue/IAM/DynamoDB/external Worker/message 변경 금지, credential/provider/model 값 비기록.

## 실행 단계

### 1. Pre-change 안전 게이트
- [x] 사용자 승인과 root cause를 audit에 기록한다.
- [x] Worker, active Job, Kiro/Hermes child와 current env 상태를 확인한다.
- [x] source/active target과 rollback 조건을 확인한다.

### 2. Source 수정 및 검증
- [ ] `deploy/env.example`의 `HERMES_HOME`을 exact config directory로 수정한다.
- [ ] 관련 테스트와 format/diff 검사를 통과한다.

### 3. Graceful drain 및 active env 배포
- [ ] Active Job이 있으면 main PID에 SIGTERM을 전달하고 현재 Job 완료 후 정상 종료를 기다린다.
- [ ] 기존 protected env와 metadata를 root-only mode `0600` backup으로 보존한다.
- [ ] active env를 한 줄만 atomic replace하고 owner/mode와 비대상 key hash를 검증한다.

### 4. Worker restore 및 Hermes 검증
- [ ] Worker를 시작하고 active/running, `NRestarts=0`, startup error 없음으로 복구한다.
- [ ] Worker와 동일한 환경에서 Hermes config root/status/synthetic one-shot을 검증한다.
- [ ] rollback backup과 no-secret/no-unrelated-change 경계를 검증한다.

### 5. 문서 및 최종 게이트
- [ ] audit, AI-DLC state와 operational test plan을 완료 상태로 갱신한다.
- [ ] plan checkbox, Markdown, diff와 secret 경계를 최종 검증한다.
