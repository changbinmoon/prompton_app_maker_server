# requirements.json 계약 제안서

## 결론

MVP 권장안은 기존 Client API를 유지하고 Backend Lambda가 자유 텍스트 입력을 versioned `requirements.json`으로 정규화하는 방식이다.

현재 계약 불일치:

| 영역 | 현재 Backend 요구사항 | 현재 Worker |
|---|---|---|
| API 입력 | `{"requirements": "자유 텍스트"}` | 직접 관여하지 않음 |
| S3 입력 파일 | `requirements.md` 예시 | `requirements.json` 필수 |
| 내용 검증 | 명시되지 않음 | JSON 객체 여부만 검증 |

운영 테스트 전에 하나의 canonical JSON 계약으로 통일해야 한다.

## 권장 책임 분리

| 주체 | 책임 |
|---|---|
| Client | 자유 텍스트 요구사항과 선택적 이미지 업로드 |
| Backend Lambda | 입력 검증, Job ID 생성, schemaVersion 및 Android 정책 주입, canonical JSON 저장 |
| AI Worker | schemaVersion과 필드 검증, JSON을 untrusted data로 취급, kiro-cli에 전달 |
| Test/CI | 동일 JSON Schema로 producer와 consumer를 모두 검증 |

Client가 SDK 버전, application ID 같은 빌드 정책을 임의로 정하지 않게 하고 Backend 설정이 결정하는 것을 권장한다.

## 권장 v1 예시

```json
{
  "schemaVersion": "1.0",
  "request": {
    "prompt": "지렁이 게임 Android 앱을 만들어주세요.",
    "locale": "ko-KR"
  },
  "android": {
    "applicationId": "com.prompton.generated.j1234567890abcdef",
    "minSdk": 26,
    "targetSdk": 35,
    "language": "Kotlin",
    "uiToolkit": "Jetpack Compose"
  },
  "assets": [
    {
      "fileName": "0-logo.png",
      "contentType": "image/png",
      "purpose": "앱 아이콘 참고 이미지"
    }
  ]
}
```

`applicationId`, `minSdk`, `targetSdk`, `language`, `uiToolkit`은 Client 요청값이 아니라 Backend의 승인된 서버 설정에서 생성하는 것을 권장한다.

## v1 필드 규칙

### Root

| 필드 | 필수 | 규칙 |
|---|---|---|
| `schemaVersion` | Yes | 정확히 `1.0` |
| `request` | Yes | 사용자 요구사항 객체 |
| `android` | Yes | Backend가 결정한 Android 빌드 정책 |
| `assets` | Yes | 없으면 빈 배열, 최대 5개 |

### request

| 필드 | 필수 | 규칙 |
|---|---|---|
| `prompt` | Yes | UTF-8 문자열, trim 후 1~10,000자 |
| `locale` | Yes | BCP 47 형태, MVP 기본값 `ko-KR` |

### android

| 필드 | 필수 | 규칙 |
|---|---|---|
| `applicationId` | Yes | 소문자 Java package 형식, Job마다 유일 |
| `minSdk` | Yes | 21~targetSdk |
| `targetSdk` | Yes | 테스트 EC2에 설치된 SDK와 일치 |
| `language` | Yes | MVP는 `Kotlin`만 허용 |
| `uiToolkit` | Yes | MVP는 `Jetpack Compose`만 허용 |

### assets

| 필드 | 필수 | 규칙 |
|---|---|---|
| `fileName` | Yes | basename만 허용, 경로 구분자 금지 |
| `contentType` | Yes | `image/png` 또는 `image/jpeg` |
| `purpose` | No | 0~500자 설명 |

추가 규칙:
- root 및 각 객체의 미정의 필드는 기본적으로 거부한다.
- asset metadata의 `fileName`은 S3 assets prefix 아래 실제 객체 basename과 일치해야 한다.
- 배열 순서가 AI에 전달되는 asset 우선순위다.
- JSON 크기 상한을 정한다. MVP 권장값은 64 KiB다.
- 사용자 prompt는 데이터이며 Worker/Kiro 시스템 제약을 변경할 권한이 없다.

## 저장 및 메시지 계약

Canonical 파일:

```text
jobs/{jobId}/requirements/requirements.json
```

SQS 메시지는 기존 schema 1.0을 유지한다.

```json
{
  "schemaVersion": "1.0",
  "jobId": "00000000-0000-4000-8000-000000000000",
  "requirements": {
    "bucket": "prompton-app-builder-dev-changbin",
    "key": "jobs/00000000-0000-4000-8000-000000000000/requirements/requirements.json"
  },
  "assetsPrefix": "jobs/00000000-0000-4000-8000-000000000000/assets/"
}
```

SQS `schemaVersion`은 메시지 envelope 버전이고, 파일 내부 `schemaVersion`은 requirements 계약 버전이다. 현재 둘 다 `1.0`이지만 독립적으로 관리한다.

## 유효성 실패 처리

- Backend는 invalid Client 입력을 S3/SQS에 쓰기 전에 4xx로 거부한다.
- Worker는 invalid canonical JSON을 `INVALID_REQUIREMENTS`로 기록한다.
- Worker는 실패 메시지를 삭제하지 않는다.
- 반복 실패는 Queue RedrivePolicy에 따라 3회 후 DLQ로 이동한다.
- 사용자 표시 메시지에는 원문 prompt, 내부 경로, schema 상세, 자격증명을 포함하지 않는다.

## 버전 정책

- Worker는 지원 버전 목록을 명시적으로 가진다.
- `1.0` 내 필드의 의미나 타입을 변경하지 않는다.
- optional 필드 추가도 producer/consumer 양쪽 배포 및 fixture 통과 후 적용한다.
- breaking change는 `2.0`으로 올리고 migration window 동안 두 버전을 동시에 지원한다.
- Backend producer를 먼저 배포하더라도 기존 Worker가 이해할 수 있는 버전만 전송한다.

## 계약 확정 절차

1. `requirements-contract-questions.md`의 6개 결정을 완료한다.
2. 결정된 계약을 JSON Schema Draft 2020-12 파일로 생성한다.
3. 정상, 최소, 최대, assets 없음, 잘못된 package, 과대 prompt, unknown field fixture를 만든다.
4. Backend에서 API 입력을 canonical JSON으로 변환하고 저장 전에 검증한다.
5. Worker에서 S3 다운로드 후 같은 schema를 검증한다.
6. Backend producer CI와 Worker consumer CI에서 동일 fixture를 실행한다.
7. dev S3에 canonical fixture를 올리고 1-Job E2E를 통과한다.
8. 계약 문서, schema, fixture, 구현을 하나의 PR에서 함께 승인한다.

## 확정 완료 기준

- JSON Schema 파일이 단일 source of truth로 지정됨
- 필드 owner가 Client/Backend/Worker 중 하나로 명확함
- Backend와 Worker가 동일 valid/invalid fixture를 통과함
- `requirements.md`와 `requirements.json` 경로 불일치가 제거됨
- SDK 값이 테스트 EC2 설치 환경과 일치함
- 1-Job 실제 Android APK E2E가 성공함

결정 전에는 이 문서를 Draft로 취급하고 production contract로 사용하지 않는다.
