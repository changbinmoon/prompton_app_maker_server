"""SQS Visibility Timeout 연장 스레드.

설계 근거: business-logic-model.md 섹션 3, nfr-design-patterns.md Pattern 2
비즈니스 규칙: BR-010 (연장 주기 = VT의 50%), BR-011 (연장 실패 시 처리 계속)

daemon thread로 동작하므로 메인 프로세스가 종료되면 함께 종료된다.
"""

from __future__ import annotations

import logging
import threading
from types import TracebackType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqs.client import SQSClient

logger = logging.getLogger(__name__)

#: 연장 주기 비율 (BR-010: Visibility Timeout의 50%)
EXTEND_INTERVAL_RATIO = 0.5

#: 최소 연장 주기 (초) - 과도한 API 호출 방지
MIN_EXTEND_INTERVAL_SECONDS = 5.0

#: stop() 시 스레드 종료 대기 시간 (초)
JOIN_TIMEOUT_SECONDS = 5.0


class VisibilityExtender:
    """처리 중인 SQS 메시지의 Visibility Timeout을 주기적으로 연장한다.

    컨텍스트 매니저로 사용하면 start/stop이 자동으로 짝을 이룬다.

        with VisibilityExtender(sqs, receipt_handle, timeout):
            ...long running work...
    """

    def __init__(
        self,
        sqs_client: SQSClient,
        receipt_handle: str,
        visibility_timeout: int,
    ) -> None:
        """연장기를 초기화한다.

        Args:
            sqs_client: Visibility 연장에 사용할 SQS 클라이언트
            receipt_handle: 대상 메시지의 receipt handle
            visibility_timeout: Queue의 Visibility Timeout (초)
        """
        self._sqs_client = sqs_client
        self._receipt_handle = receipt_handle
        self._visibility_timeout = visibility_timeout
        self._interval = max(
            visibility_timeout * EXTEND_INTERVAL_RATIO, MIN_EXTEND_INTERVAL_SECONDS
        )
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="visibility-extender",
            daemon=True,
        )
        self._extend_count = 0

    @property
    def extend_count(self) -> int:
        """연장 성공 횟수를 반환한다."""
        return self._extend_count

    def start(self) -> None:
        """연장 스레드를 시작한다."""
        logger.info(
            "Visibility Extender 시작 (주기=%.1f초, VT=%d초)",
            self._interval,
            self._visibility_timeout,
        )
        self._thread.start()

    def stop(self) -> None:
        """연장 스레드를 중지하고 종료를 기다린다.

        JOIN_TIMEOUT_SECONDS 내에 종료되지 않으면 경고만 남기고 반환한다
        (daemon thread이므로 프로세스 종료를 막지 않는다).
        """
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=JOIN_TIMEOUT_SECONDS)
            if self._thread.is_alive():
                logger.warning("Visibility Extender 스레드가 시간 내 종료되지 않았습니다")

        logger.info("Visibility Extender 중지 (연장 %d회 수행)", self._extend_count)

    def __enter__(self) -> VisibilityExtender:
        """컨텍스트 진입 시 스레드를 시작한다.

        Returns:
            자기 자신
        """
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """컨텍스트 종료 시 스레드를 중지한다."""
        self.stop()

    def _run(self) -> None:
        """주기적으로 Visibility Timeout을 연장한다.

        BR-011: 연장 실패 시 예외를 전파하지 않고 로그만 남긴다.
        Event.wait()가 True를 반환하면(=stop 호출) 루프를 종료한다.
        """
        while not self._stop_event.wait(self._interval):
            try:
                self._sqs_client.extend_visibility(
                    self._receipt_handle, self._visibility_timeout
                )
                self._extend_count += 1
            except Exception:
                # BR-011: 연장 실패는 Job 처리를 중단시키지 않는다
                logger.warning(
                    "Visibility Timeout 연장 실패 - 처리를 계속합니다", exc_info=True
                )
