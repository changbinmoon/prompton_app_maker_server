# Component Dependencies - Prompton AI Worker

## 의존성 매트릭스

| 컴포넌트 | 의존 대상 | 의존 유형 |
|----------|-----------|-----------|
| worker | sqs, s3, dynamo, ai, build, config | 직접 호출 |
| sqs | config | 설정값 참조 |
| s3 | config | 설정값 참조 |
| dynamo | config | 설정값 참조 |
| ai | config | 설정값 참조 |
| build | config | 설정값 참조 |
| config | (없음) | 독립 |

## 의존성 방향

```
                 +----------+
                 |  config  |
                 +----------+
                      ^
                      |
    +-----------------+------------------+
    |        |        |        |         |
+------+ +------+ +-------+ +----+ +-------+
|  sqs | |  s3  | | dynamo| | ai | | build |
+------+ +------+ +-------+ +----+ +-------+
    ^        ^        ^        ^       ^
    |        |        |        |       |
    +--------+--------+--------+-------+
                      |
                 +----------+
                 |  worker  |
                 +----------+
```

## 통신 패턴

### worker → sqs
- **패턴**: 동기 호출
- **빈도**: 메인 루프마다 1회 polling + 완료 시 삭제 + 주기적 Visibility 연장
- **데이터**: SQSMessage (수신), receipt_handle (삭제/연장)

### worker → s3
- **패턴**: 동기 호출
- **빈도**: Job당 다운로드 2회(requirements + assets) + 업로드 2회(source + artifact)
- **데이터**: 파일 바이너리, JSON dict

### worker → dynamo
- **패턴**: 동기 호출
- **빈도**: Job당 최소 5회 (상태 조회 1회 + 상태 업데이트 4회) + 로그 N회
- **데이터**: status, progress, message, logs, errorCode, artifactKey

### worker → ai
- **패턴**: 동기 호출 (subprocess 실행 후 대기)
- **빈도**: Job당 1회
- **데이터**: requirements dict, 에셋 경로, 작업 디렉토리

### worker → build
- **패턴**: 동기 호출 (subprocess 실행 후 대기)
- **빈도**: Job당 1회
- **데이터**: 프로젝트 디렉토리 경로

### 모든 컴포넌트 → config
- **패턴**: 읽기 전용 참조
- **빈도**: 초기화 시 1회
- **데이터**: Config dataclass 인스턴스

## 외부 의존성

| 외부 시스템 | 연결 컴포넌트 | 프로토콜 | 인증 |
|-------------|---------------|----------|------|
| AWS SQS | sqs | HTTPS (boto3) | IAM Role |
| AWS S3 | s3 | HTTPS (boto3) | IAM Role |
| AWS DynamoDB | dynamo | HTTPS (boto3) | IAM Role |
| kiro-cli | ai | subprocess (로컬) | N/A |
| Gradle/Android SDK | build | subprocess (로컬) | N/A |

## 데이터 흐름

```
[SQS Message]
     |
     v
  sqs.receive_message()
     |
     v
  [Message: jobId, bucket, key, assetsPrefix, receiptHandle]
     |
     v
  dynamo.get_job_status(jobId)
     |
     v
  s3.download_requirements(bucket, key) --> [requirements dict]
     |
  s3.download_assets(bucket, prefix, dir) --> [asset file paths]
     |
     v
  ai.generate_code(requirements, assets, work_dir) --> [project dir]
     |
     v
  build.build_apk(project_dir) --> [apk file path]
     |
     v
  s3.upload_source(project_dir, bucket, source_key)
  s3.upload_artifact(apk_path, bucket, artifact_key) --> [artifactKey]
     |
     v
  dynamo.update_status(jobId, SUCCESS, 100, msg, artifactKey=...)
     |
     v
  sqs.delete_message(receiptHandle)
```
