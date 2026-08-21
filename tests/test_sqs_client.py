"""sqs.client 단위 테스트."""

from __future__ import annotations

import json
from typing import Any

import pytest

from models.entities import SUPPORTED_SCHEMA_VERSION, Config
from models.exceptions import InvalidRequirementsError
from sqs.client import SQS_RECEIVE_WAIT_SECONDS, SQSClient


class FakeSQS:
    """boto3 SQS 클라이언트 대역."""

    def __init__(
        self,
        messages: list[dict[str, Any]] | None = None,
        attributes: dict[str, str] | None = None,
    ) -> None:
        self.messages = messages if messages is not None else []
        self.attributes = attributes if attributes is not None else {}
        self.receive_calls: list[dict[str, Any]] = []
        self.deleted: list[str] = []
        self.visibility_calls: list[tuple[str, int]] = []
        self.fail_get_attributes = False

    def receive_message(self, **kwargs: Any) -> dict[str, Any]:
        self.receive_calls.append(kwargs)
        if not self.messages:
            return {}
        return {"Messages": [self.messages.pop(0)]}

    def delete_message(self, QueueUrl: str, ReceiptHandle: str) -> None:  # noqa: N803
        self.deleted.append(ReceiptHandle)

    def change_message_visibility(
        self,
        QueueUrl: str,  # noqa: N803
        ReceiptHandle: str,  # noqa: N803
        VisibilityTimeout: int,  # noqa: N803
    ) -> None:
        self.visibility_calls.append((ReceiptHandle, VisibilityTimeout))

    def get_queue_attributes(self, **kwargs: Any) -> dict[str, Any]:
        if self.fail_get_attributes:
            raise RuntimeError("attribute 조회 실패")
        return {"Attributes": self.attributes}


def build_body(job_id: str, **overrides: Any) -> str:
    """유효한 SQS 메시지 본문을 생성한다."""
    payload: dict[str, Any] = {
        "schemaVersion": SUPPORTED_SCHEMA_VERSION,
        "jobId": job_id,
        "requirements": {
            "bucket": "test-bucket",
            "key": f"jobs/{job_id}/requirements/requirements.json",
        },
        "assetsPrefix": f"jobs/{job_id}/assets/",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_receive_message_returns_none_when_empty(config: Config) -> None:
    """메시지가 없으면 None을 반환한다."""
    fake = FakeSQS()
    client = SQSClient(config, client=fake)

    assert client.receive_message() is None


def test_receive_message_uses_short_polling(config: Config, job_id: str) -> None:
    """즉시 반환하는 Short Polling 파라미터로 1건만 수신한다."""
    fake = FakeSQS([{"ReceiptHandle": "rh-1", "Body": build_body(job_id)}])
    client = SQSClient(config, client=fake)

    message = client.receive_message()

    assert message is not None
    assert message.job_id == job_id
    assert message.receipt_handle == "rh-1"
    assert message.requirements_bucket == "test-bucket"
    assert SQS_RECEIVE_WAIT_SECONDS == 0
    assert fake.receive_calls[0]["WaitTimeSeconds"] == SQS_RECEIVE_WAIT_SECONDS
    assert fake.receive_calls[0]["MaxNumberOfMessages"] == 1


def test_receive_message_rejects_bad_schema_version(config: Config, job_id: str) -> None:
    """지원하지 않는 schemaVersion은 InvalidRequirementsError를 발생시킨다 (BR-019)."""
    fake = FakeSQS([{"ReceiptHandle": "rh-1", "Body": build_body(job_id, schemaVersion="2.0")}])
    client = SQSClient(config, client=fake)

    with pytest.raises(InvalidRequirementsError):
        client.receive_message()


def test_receive_message_rejects_non_uuid_job_id(config: Config) -> None:
    """jobId가 UUID가 아니면 예외가 발생한다 (BR-019)."""
    fake = FakeSQS([{"ReceiptHandle": "rh-1", "Body": build_body("not-a-uuid")}])
    client = SQSClient(config, client=fake)

    with pytest.raises(InvalidRequirementsError):
        client.receive_message()


def test_receive_message_rejects_malformed_json(config: Config) -> None:
    """JSON 파싱 실패 시 예외가 발생한다 (BR-019)."""
    fake = FakeSQS([{"ReceiptHandle": "rh-1", "Body": "{not json"}])
    client = SQSClient(config, client=fake)

    with pytest.raises(InvalidRequirementsError):
        client.receive_message()


def test_receive_message_requires_requirements_fields(config: Config, job_id: str) -> None:
    """requirements.bucket/key 누락 시 예외가 발생한다 (BR-019)."""
    fake = FakeSQS(
        [{"ReceiptHandle": "rh-1", "Body": build_body(job_id, requirements={"bucket": "b"})}]
    )
    client = SQSClient(config, client=fake)

    with pytest.raises(InvalidRequirementsError):
        client.receive_message()


def test_delete_message(config: Config) -> None:
    """삭제 요청이 전달된다 (BR-002)."""
    fake = FakeSQS()
    client = SQSClient(config, client=fake)

    client.delete_message("rh-42")

    assert fake.deleted == ["rh-42"]


def test_extend_visibility(config: Config) -> None:
    """Visibility Timeout 연장 요청이 전달된다 (BR-010)."""
    fake = FakeSQS()
    client = SQSClient(config, client=fake)

    client.extend_visibility("rh-7", 300)

    assert fake.visibility_calls == [("rh-7", 300)]


def test_get_visibility_timeout_reads_queue_attribute(config: Config) -> None:
    """Queue 속성에서 VisibilityTimeout을 읽는다."""
    fake = FakeSQS(attributes={"VisibilityTimeout": "600"})
    client = SQSClient(config, client=fake)

    assert client.get_visibility_timeout(fallback=300) == 600


def test_get_visibility_timeout_falls_back_on_error(config: Config) -> None:
    """조회 실패 시 fallback 값을 사용한다."""
    fake = FakeSQS()
    fake.fail_get_attributes = True
    client = SQSClient(config, client=fake)

    assert client.get_visibility_timeout(fallback=300) == 300


def test_get_visibility_timeout_falls_back_on_missing_attribute(config: Config) -> None:
    """속성이 없으면 fallback 값을 사용한다."""
    fake = FakeSQS(attributes={})
    client = SQSClient(config, client=fake)

    assert client.get_visibility_timeout(fallback=120) == 120
