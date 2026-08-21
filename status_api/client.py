"""Backend Status API PATCH client.

The client owns HTTP mechanics only. WorkerOrchestrator decides whether a final
StatusApiFailure is best-effort or mandatory for the Job lifecycle.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import requests

from models.enums import ErrorCode, JobStatus
from models.exceptions import StatusApiFailure, StatusApiFailureKind

if TYPE_CHECKING:
    from models.entities import Config

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 3
READ_TIMEOUT_SECONDS = 10
REQUEST_TIMEOUT = (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (1.0, 2.0)


class StatusApiClient:
    """Synchronous outbound client for Job status PATCH commands."""

    def __init__(
        self,
        config: Config,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._base_url = config.prompton_api_base_url.rstrip("/")
        self._api_key = config.prompton_status_api_key
        self._session = session if session is not None else requests.Session()
        self._sleep = sleep if sleep is not None else time.sleep

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: int | None = None,
        message: str | None = None,
        artifact_key: str | None = None,
        error_code: ErrorCode | None = None,
    ) -> None:
        """PATCH one status command and return after any 2xx response.

        Only HTTP 5xx responses are retried. Connection errors and timeouts are
        final immediately, as are 4xx and all other non-2xx/non-5xx responses.
        """
        url = self._build_url(job_id)
        headers = self._build_headers()
        payload = self._build_payload(
            status=status,
            progress=progress,
            message=message,
            artifact_key=artifact_key,
            error_code=error_code,
        )

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._session.patch(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.Timeout:
                self._raise_failure(
                    job_id=job_id,
                    status=status,
                    kind=StatusApiFailureKind.TIMEOUT,
                    status_code=None,
                    attempt=attempt,
                )
            except requests.ConnectionError:
                self._raise_failure(
                    job_id=job_id,
                    status=status,
                    kind=StatusApiFailureKind.CONNECTION,
                    status_code=None,
                    attempt=attempt,
                )

            status_code = response.status_code
            if 200 <= status_code < 300:
                logger.info(
                    "status_api_update_accepted job_id=%s status=%s attempt=%d "
                    "result_class=2xx",
                    job_id,
                    status.value,
                    attempt,
                )
                return

            if 500 <= status_code < 600:
                if attempt < MAX_ATTEMPTS:
                    delay = RETRY_DELAYS_SECONDS[attempt - 1]
                    logger.warning(
                        "status_api_update_retry job_id=%s status=%s attempt=%d "
                        "result_class=5xx next_delay_seconds=%s",
                        job_id,
                        status.value,
                        attempt,
                        delay,
                    )
                    self._sleep(delay)
                    continue
                self._raise_failure(
                    job_id=job_id,
                    status=status,
                    kind=StatusApiFailureKind.HTTP_5XX,
                    status_code=status_code,
                    attempt=attempt,
                )

            kind = (
                StatusApiFailureKind.HTTP_4XX
                if 400 <= status_code < 500
                else StatusApiFailureKind.HTTP_OTHER
            )
            self._raise_failure(
                job_id=job_id,
                status=status,
                kind=kind,
                status_code=status_code,
                attempt=attempt,
            )

        raise AssertionError("Status API attempt loop exited unexpectedly")

    def _build_url(self, job_id: str) -> str:
        return f"{self._base_url}/v1/jobs/{job_id}/status"

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None:
            headers["x-api-key"] = self._api_key
        return headers

    @staticmethod
    def _build_payload(
        *,
        status: JobStatus,
        progress: int | None,
        message: str | None,
        artifact_key: str | None,
        error_code: ErrorCode | None,
    ) -> dict[str, str | int]:
        payload: dict[str, str | int] = {"status": status.value}
        if progress is not None:
            payload["progress"] = progress
        if message is not None:
            payload["message"] = message
        if artifact_key is not None:
            payload["artifactKey"] = artifact_key
        if error_code is not None:
            payload["errorCode"] = error_code.value
        return payload

    @staticmethod
    def _raise_failure(
        *,
        job_id: str,
        status: JobStatus,
        kind: StatusApiFailureKind,
        status_code: int | None,
        attempt: int,
    ) -> None:
        logger.warning(
            "status_api_update_failed job_id=%s status=%s attempt=%d kind=%s "
            "http_status=%s",
            job_id,
            status.value,
            attempt,
            kind.value,
            status_code,
        )
        raise StatusApiFailure(
            kind,
            status_code=status_code,
            attempt_count=attempt,
        )
