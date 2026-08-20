"""dynamo.client 단위 테스트 (moto 사용)."""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from dynamo.client import DynamoClient
from models.entities import Config
from models.enums import ErrorCode, JobStatus

TABLE_NAME = "test-jobs"


@pytest.fixture
def dynamo_setup(config: Config):  # type: ignore[no-untyped-def]
    """moto DynamoDB 테이블과 DynamoClient를 준비한다."""
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        table = resource.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "jobId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "jobId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoClient(config, table=table), table


def test_get_job_status_returns_none_when_missing(dynamo_setup, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """레코드가 없으면 None을 반환한다."""
    client, _ = dynamo_setup

    assert client.get_job_status(job_id) is None


def test_get_job_status_reads_status(dynamo_setup, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """저장된 status를 JobStatus로 반환한다."""
    client, table = dynamo_setup
    table.put_item(Item={"jobId": job_id, "status": "QUEUED"})

    assert client.get_job_status(job_id) == JobStatus.QUEUED


def test_get_job_status_unknown_value(dynamo_setup, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """알 수 없는 status 문자열은 None으로 처리한다."""
    client, table = dynamo_setup
    table.put_item(Item={"jobId": job_id, "status": "WEIRD"})

    assert client.get_job_status(job_id) is None


def test_update_status_writes_atomically(dynamo_setup, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """status/progress/message가 한 번의 UpdateItem으로 기록된다 (BR-005)."""
    client, table = dynamo_setup

    client.update_status(
        job_id,
        JobStatus.ANALYZING,
        progress=25,
        message="요구조건을 분석하고 있습니다.",
    )

    item = table.get_item(Key={"jobId": job_id})["Item"]
    assert item["status"] == "ANALYZING"
    assert int(item["progress"]) == 25
    assert item["message"] == "요구조건을 분석하고 있습니다."


def test_update_status_preserves_progress_when_none(dynamo_setup, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """progress를 전달하지 않으면 기존 값이 유지된다 (BR-007)."""
    client, table = dynamo_setup
    client.update_status(job_id, JobStatus.BUILDING, progress=75, message="빌드 중")

    client.update_status(
        job_id,
        JobStatus.FAILED,
        message="APK 빌드에 실패했습니다.",
        error_code=ErrorCode.BUILD_FAILED,
    )

    item = table.get_item(Key={"jobId": job_id})["Item"]
    assert item["status"] == "FAILED"
    assert int(item["progress"]) == 75
    assert item["errorCode"] == "BUILD_FAILED"


def test_update_status_writes_artifact_key(dynamo_setup, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """SUCCESS 시 artifactKey가 기록된다 (BR-006)."""
    client, table = dynamo_setup
    key = f"jobs/{job_id}/artifact/app-debug.apk"

    client.update_status(
        job_id, JobStatus.SUCCESS, progress=100, message="완료", artifact_key=key
    )

    item = table.get_item(Key={"jobId": job_id})["Item"]
    assert item["artifactKey"] == key


def test_update_status_sanitizes_message(dynamo_setup, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """message에 포함된 민감정보는 마스킹된다 (BR-013)."""
    client, table = dynamo_setup

    client.update_status(
        job_id, JobStatus.FAILED, message="키 AKIAIOSFODNN7EXAMPLE 로 실패"
    )

    item = table.get_item(Key={"jobId": job_id})["Item"]
    assert "AKIAIOSFODNN7EXAMPLE" not in item["message"]
    assert "[REDACTED]" in item["message"]


def test_append_log_creates_and_appends(dynamo_setup, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """logs 배열이 없으면 생성하고, 있으면 뒤에 추가한다 (BR-012)."""
    client, table = dynamo_setup

    client.append_log(job_id, "[worker] 작업을 시작했습니다.")
    client.append_log(job_id, "[worker] 요구조건 다운로드 완료")

    item = table.get_item(Key={"jobId": job_id})["Item"]
    assert item["logs"] == [
        "[worker] 작업을 시작했습니다.",
        "[worker] 요구조건 다운로드 완료",
    ]


def test_append_log_sanitizes_sensitive_data(dynamo_setup, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """로그의 민감정보가 마스킹된다 (BR-013)."""
    client, table = dynamo_setup

    client.append_log(job_id, "presigned https://s3.amazonaws.com/b/k?X-Amz-Signature=abc123")

    item = table.get_item(Key={"jobId": job_id})["Item"]
    assert "X-Amz-Signature" not in item["logs"][0]


def test_append_log_swallows_errors(config: Config, job_id: str) -> None:
    """로그 기록 실패는 예외를 전파하지 않는다."""

    class BrokenTable:
        def update_item(self, **kwargs: object) -> None:
            raise RuntimeError("DynamoDB 장애")

    client = DynamoClient(config, table=BrokenTable())

    client.append_log(job_id, "무시되어야 함")
