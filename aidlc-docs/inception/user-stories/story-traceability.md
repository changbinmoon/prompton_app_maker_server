# Story Traceability - Status API Migration

## 목적

승인된 Status API 요구사항을 7개 User Story 후보에 매핑한다. 모든 story actor는 `P-01 Worker 운영자`이며, `B-01 Mobile App 사용자`는 cross-system 결과를 받는 external beneficiary다.

승인된 Story Plan에 따라 수용된 위험은 story 또는 공통 제약으로 반복하지 않고 `status-api-requirements.md`의 원문 reference로만 유지한다.

## Story 후보 구조

| Story ID | 후보 제목 | 운영자 가치 | Persona | External beneficiary |
|---|---|---|---|---|
| US-SA-01 | Status API 기반 Worker 배포 구성 | DynamoDB 없이 명확한 상태 전달 경계로 Worker를 배포 | P-01 | B-01 |
| US-SA-02 | 처리 단계 상태 전달 | 실제 분석, 코드 생성, 빌드 단계를 Backend에 전달 | P-01 | B-01 |
| US-SA-03 | 검증된 완료와 SQS 삭제 | 실제 APK가 존재하는 Job만 완료하고 메시지 유실 방지 | P-01 | B-01 |
| US-SA-04 | 안전한 실패 상태 보고 | 실패 원인과 사용자 메시지를 전달하고 SQS retry 보존 | P-01 | B-01 |
| US-SA-05 | 예측 가능한 HTTP 오류 처리 | API 장애 시 timeout, 4xx, 5xx 동작을 일관되게 운영 | P-01 | B-01 |
| US-SA-06 | 인증 및 관측성 보호 | API Key와 민감정보를 보호하며 PATCH 결과를 진단 | P-01 | B-01 |
| US-SA-07 | 자동 계약 및 공동 E2E 검증 | Worker, Backend, Mobile 상태 흐름과 회귀를 증명 | P-01 | B-01 |

## 기능 요구사항 Traceability

| Requirement | 요약 | Story 후보 | 매핑 방식 |
|---|---|---|---|
| FR-SA-001 | PATCH endpoint와 URL 결합 | US-SA-01, US-SA-02 | Story acceptance |
| FR-SA-002 | Header 확장과 선택적 API Key | US-SA-06 | Story acceptance |
| FR-SA-003 | 분리된 Status client | US-SA-01, US-SA-05 | Story acceptance |
| FR-SA-004 | ANALYZING payload | US-SA-02 | Journey scenario |
| FR-SA-005 | GENERATING_CODE payload | US-SA-02 | Journey scenario |
| FR-SA-006 | BUILDING payload | US-SA-02 | Journey scenario |
| FR-SA-007 | 업로드 검증 후 SUCCESS 및 SQS 삭제 | US-SA-03 | Journey scenario |
| FR-SA-008 | progress 없는 FAILED와 errorCode | US-SA-04 | Failure scenario |
| FR-SA-009 | 2xx/4xx/5xx/네트워크 응답 판정 | US-SA-05 | Reliability scenario |
| FR-SA-010 | 5xx 3회와 1초/2초 backoff | US-SA-05 | Reliability scenario |
| FR-SA-011 | connect 3초/read 10초 | US-SA-05 | Quality checklist |
| FR-SA-012 | 상태별 API 실패 치명도 | US-SA-02, US-SA-03, US-SA-04 | Journey and failure scenarios |
| FR-SA-013 | Worker GET 미사용 | Requirements-only reference | 승인된 수용 위험/제약 |
| FR-SA-014 | SQS 재전달 시 전체 재처리 | Requirements-only reference | 승인된 수용 위험/제약 |
| FR-SA-015 | DynamoDB logs 제거 | US-SA-01, US-SA-06 | Scope and observability acceptance |
| FR-SA-016 | journald 관측성 | US-SA-06 | Story acceptance |
| FR-SA-017 | API 환경변수와 DynamoDB 설정 제거 | US-SA-01, US-SA-06 | Configuration checklist |
| FR-SA-018 | requests pin과 DynamoDB extras 정리 | US-SA-01 | Dependency checklist |

## 비기능 요구사항 Traceability

| Requirement | 요약 | Story 후보 | 매핑 방식 |
|---|---|---|---|
| NFR-SA-001 | DynamoDB IAM 제거와 SQS/S3 최소 권한 | US-SA-01 | Deployment checklist |
| NFR-SA-002 | TLS 검증과 API Gateway egress | US-SA-06 | Security checklist |
| NFR-SA-003 | API Key secret 관리 | US-SA-06 | Security checklist |

## 테스트 요구사항 Traceability

| Requirement | 요약 | Story 후보 | 매핑 방식 |
|---|---|---|---|
| TR-SA-001 | Status client 단위 테스트 | US-SA-05, US-SA-06 | Automated acceptance |
| TR-SA-002 | Orchestrator 상태/SQS 테스트 | US-SA-02, US-SA-03, US-SA-04 | Automated acceptance; GET/전체 재처리 항목은 requirements-only reference |
| TR-SA-003 | 전체 회귀 품질 게이트 | US-SA-07 | Quality checklist |
| TR-SA-004 | 실제 API와 Mobile 공동 E2E | US-SA-07 | Cross-system acceptance |

## Journey 및 횡단 관심사 Coverage

| 관심사 | Story 후보 | 설명 |
|---|---|---|
| 정상 상태 흐름 | US-SA-02, US-SA-03 | 처리 시작부터 검증된 SUCCESS까지 |
| 처리 실패 | US-SA-04 | 안전한 message/errorCode와 SQS 보존 |
| Status API 장애 | US-SA-02, US-SA-03, US-SA-04, US-SA-05 | 중간 best-effort와 SUCCESS 필수 분리 |
| 인증 | US-SA-06 | 선택적 x-api-key와 비노출 |
| 관측성 | US-SA-06 | journald 기반 운영 진단 |
| Worker 자동 검증 | US-SA-05, US-SA-06, US-SA-07 | mock/contract와 회귀 테스트 |
| Backend/Mobile 공동 검증 | US-SA-07 | 승인된 dev Job의 GET 및 화면 상태 |

## Requirements-Only References

다음 항목은 사용자 선택에 따라 stories.md의 story 본문이나 공통 제약에 반복하지 않는다.

- `FR-SA-013`: Worker GET 미사용
- `FR-SA-014`: 모든 SQS 전달의 전체 재처리
- `14. 수용된 위험과 제약`: terminal/canceled 사전 식별 불가, 중복 AI/Build 비용, 중간 상태 누락, 네트워크 무재시도, orphan artifact 가능성 및 Backend idempotency 의존성

이 항목들은 구현 및 설계 단계에서 `status-api-requirements.md`를 직접 참조해야 한다.

## 외부 Dependency 경계

| Dependency | 관련 Story | Worker 산출물 | 외부 확인 |
|---|---|---|---|
| Backend PATCH API | US-SA-02~US-SA-06 | payload, HTTP 처리, 자동 contract 증적 | 반복 요청과 상태 저장 계약 |
| Backend GET API | US-SA-07 | E2E Job ID 및 전송 증적 | 상태/progress/message/artifactKey 조회 |
| Mobile App | US-SA-07 | Worker 최종 상태와 artifact 증적 | 동일 상태 및 artifact 표시 |
| API Gateway egress | US-SA-06 | timeout/TLS 설정 | EC2 outbound 연결 가능 |

## Step 4 생성 규칙

- 정확히 7개 story를 생성한다.
- 모든 story actor는 P-01 Worker 운영자로 작성한다.
- B-01은 External beneficiary outcome에만 사용한다.
- 상태 journey는 Given/When/Then으로, 설정·보안·품질은 checklist로 작성한다.
- Requirements-only reference 항목은 story acceptance에 복제하지 않는다.
