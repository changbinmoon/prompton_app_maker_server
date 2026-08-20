"""SQS 클라이언트.

설계 근거: logical-components.md 섹션 6, component-methods.md
비즈니스 규칙:
    BR-002 (메시지 삭제 시점), BR-003 (실패 시 메시지 유지),
    BR-010 (Visibility Timeout 연장), BR-011 (연장 실패 처리),
    BR-019 (SQS 메시지 유효성)
NFR 패턴: Pattern 1 (retry), Pattern 11 (Long Polling)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import boto3

from config.settings import build_boto_config
from models.entities import SQSMessage

if TYPE_CHECKING:
    from models.entities import Config

logger = logging.getLogger(__name__)

#: Long Polling 대기 시간 (NFR Design Pattern 11)
LONG_POLL_WAIT_SECONDS = 20

#: 순차 처리 정책상 항상 1건만 수신한다 (NFR-004)
MAX_MESSAGES_PER_RECEIVE = 1


class SQSClient:
    """SQS Queue 연동 래퍼.

    Attributes:
        queue_url: 대상 SQS Queue URL
    """

    def __init__(self, config: Config, client: Any | None = None) -> None:
        """SQS 클라이언트를 초기화한다.

        Args:
            config: Worker 설정
            client: 주입할 boto3 SQS 클라이언트 (테스트용). None이면 새로 생성
        """
        self.queue_url = config.sqs_queue_url
        self._client = client or boto3.client(
            "sqs",
            region_name=config.aws_region,
            config=build_boto_config(),
        )

    def receive_message(self) -> SQSMessage | None:
        """Long Polling으로 메시지 1건을 수신한다.

        NFR Design Pattern 11: WaitTimeSeconds=20으로 빈 응답과 API 호출을 줄인다.

        Returns:
            수신한 메시지. 대기 시간 내 메시지가 없으면 None

        Raises:
            InvalidRequirementsError: 메시지 본문 파싱/검증 실패 (BR-019)
        """
        response = self._client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=MAX_MESSAGES_PER_RECEIVE,
            WaitTimeSeconds=LONG_POLL_WAIT_SECONDS,
            MessageAttributeNames=["All"],
        )

        messages = response.get("Messages", [])
        if not messages:
            return None

        raw = messages[0]
        receipt_handle = raw["ReceiptHandle"]
        body = raw.get("Body", "")

        logger.info("SQS 메시지 수신 (MessageId=%s)", raw.get("MessageId"))
        return SQSMessage.from_raw(body, receipt_handle)

    def delete_message(self, receipt_handle: str) -> None:
        """메시지를 Queue에서 삭제한다.

        BR-002: 모든 처리가 정상 완료된 후에만 호출해야 한다.
        BR-003: 처리 실패 시 호출하지 않는다.

        Args:
            receipt_handle: 삭제할 메시지의 receipt handle
        """
        self._client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle,
        )
        logger.info("SQS 메시지 삭제 완료")

    def extend_visibility(self, receipt_handle: str, timeout_seconds: int) -> None:
        """메시지의 Visibility Timeout을 연장(리셋)한다.

        BR-010: Queue의 원래 Visibility Timeout 값으로 리셋한다.

        Args:
            receipt_handle: 대상 메시지의 receipt handle
            timeout_seconds: 새로 설정할 Visibility Timeout (초)
        """
        self._client.change_message_visibility(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=timeout_seconds,
        )
        logger.debug("Visibility Timeout %d초로 연장", timeout_seconds)

    def get_visibility_timeout(self, fallback: int) -> int:
        """Queue에 설정된 Visibility Timeout을 조회한다.

        조회 실패 시 프로세스를 중단하지 않고 fallback 값을 사용한다.
        (연장 주기 계산에만 쓰이는 값이므로 기동 실패 사유가 되지 않는다)

        Args:
            fallback: 조회 실패 시 사용할 기본값 (초)

        Returns:
            Queue의 VisibilityTimeout 또는 fallback
        """
        try:
            response = self._client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=["VisibilityTimeout"],
            )
            value = response.get("Attributes", {}).get("VisibilityTimeout")
            if value is None:
                logger.warning(
                    "Queue VisibilityTimeout 속성이 없어 기본값 %d초를 사용합니다", fallback
                )
                return fallback

            timeout = int(value)
            if timeout <= 0:
                logger.warning(
                    "Queue VisibilityTimeout이 유효하지 않아(%d) 기본값 %d초를 사용합니다",
                    timeout,
                    fallback,
                )
                return fallback

            logger.info("Queue VisibilityTimeout=%d초", timeout)
            return timeout
        except Exception:
            logger.warning(
                "Queue VisibilityTimeout 조회 실패 - 기본값 %d초를 사용합니다",
                fallback,
                exc_info=True,
            )
            return fallback
