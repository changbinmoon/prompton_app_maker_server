"""Deterministic contract tests for status_api.client."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast

import pytest
import requests

from models.entities import Config
from models.enums import ErrorCode, JobStatus
from models.exceptions import StatusApiFailure, StatusApiFailureKind
from status_api.client import REQUEST_TIMEOUT, StatusApiClient


class FakeResponse:
    def __init__(self, status_code: int, body_sentinel: str = "") -> None:
        self.status_code = status_code
        self.body_sentinel = body_sentinel

    @property
    def text(self) -> str:
        raise AssertionError("response body must not be read")

    def json(self) -> object:
        raise AssertionError("response body must not be parsed")


class FakeSession:
    def __init__(self, outcomes: list[FakeResponse | BaseException]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def patch(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def build_client(
    config: Config,
    outcomes: list[FakeResponse | BaseException],
    *,
    sleep: Callable[[float], None] | None = None,
) -> tuple[StatusApiClient, FakeSession]:
    session = FakeSession(outcomes)
    client = StatusApiClient(
        config,
        session=cast(requests.Session, session),
        sleep=sleep,
    )
    return client, session


def test_builds_url_headers_payload_and_timeout(config: Config, job_id: str) -> None:
    client, session = build_client(config, [FakeResponse(204)])

    client.update_job_status(
        job_id,
        JobStatus.ANALYZING,
        progress=25,
        message="요구조건을 분석하고 있습니다.",
    )

    url, kwargs = session.calls[0]
    assert url == f"https://api.example.com/v1/jobs/{job_id}/status"
    assert kwargs["headers"] == {"Content-Type": "application/json"}
    assert kwargs["json"] == {
        "status": "ANALYZING",
        "progress": 25,
        "message": "요구조건을 분석하고 있습니다.",
    }
    assert kwargs["timeout"] == REQUEST_TIMEOUT
    assert "verify" not in kwargs


def test_configured_key_is_header_only(config: Config, job_id: str) -> None:
    keyed = Config(
        **{
            **config.__dict__,
            "prompton_api_base_url": "https://api.example.com///",
            "prompton_status_api_key": "sentinel-api-key",
        }
    )
    client, session = build_client(keyed, [FakeResponse(200)])

    client.update_job_status(job_id, JobStatus.BUILDING, progress=75, message="build")

    url, kwargs = session.calls[0]
    assert url == f"https://api.example.com/v1/jobs/{job_id}/status"
    assert kwargs["headers"] == {
        "Content-Type": "application/json",
        "x-api-key": "sentinel-api-key",
    }
    assert "sentinel-api-key" not in str(kwargs["json"])


def test_failed_payload_omits_none_fields(config: Config, job_id: str) -> None:
    client, session = build_client(config, [FakeResponse(200)])

    client.update_job_status(
        job_id,
        JobStatus.FAILED,
        message="APK 빌드에 실패했습니다.",
        error_code=ErrorCode.BUILD_FAILED,
    )

    assert session.calls[0][1]["json"] == {
        "status": "FAILED",
        "message": "APK 빌드에 실패했습니다.",
        "errorCode": "BUILD_FAILED",
    }


@pytest.mark.parametrize("status_code", [200, 204, 299])
def test_any_2xx_succeeds_without_reading_body(
    config: Config, job_id: str, status_code: int
) -> None:
    client, session = build_client(
        config, [FakeResponse(status_code, body_sentinel="sensitive-response")]
    )

    client.update_job_status(job_id, JobStatus.SUCCESS)

    assert len(session.calls) == 1


@pytest.mark.parametrize(
    ("status_code", "kind"),
    [
        (301, StatusApiFailureKind.HTTP_OTHER),
        (400, StatusApiFailureKind.HTTP_4XX),
        (404, StatusApiFailureKind.HTTP_4XX),
        (499, StatusApiFailureKind.HTTP_4XX),
    ],
)
def test_non_retryable_http_response_fails_once(
    config: Config,
    job_id: str,
    status_code: int,
    kind: StatusApiFailureKind,
) -> None:
    sleep = SleepRecorder()
    client, session = build_client(config, [FakeResponse(status_code)], sleep=sleep)

    with pytest.raises(StatusApiFailure) as exc_info:
        client.update_job_status(job_id, JobStatus.ANALYZING)

    assert exc_info.value.kind is kind
    assert exc_info.value.status_code == status_code
    assert exc_info.value.attempt_count == 1
    assert len(session.calls) == 1
    assert sleep.delays == []


@pytest.mark.parametrize(
    ("outcomes", "expected_delays", "expected_calls"),
    [
        ([FakeResponse(500), FakeResponse(200)], [1.0], 2),
        ([FakeResponse(503), FakeResponse(502), FakeResponse(204)], [1.0, 2.0], 3),
    ],
)
def test_5xx_retries_until_2xx(
    config: Config,
    job_id: str,
    outcomes: list[FakeResponse | BaseException],
    expected_delays: list[float],
    expected_calls: int,
) -> None:
    sleep = SleepRecorder()
    client, session = build_client(config, outcomes, sleep=sleep)

    client.update_job_status(job_id, JobStatus.BUILDING)

    assert len(session.calls) == expected_calls
    assert sleep.delays == expected_delays


def test_exhausted_5xx_raises_after_three_attempts(config: Config, job_id: str) -> None:
    sleep = SleepRecorder()
    client, session = build_client(
        config,
        [FakeResponse(500), FakeResponse(502), FakeResponse(503)],
        sleep=sleep,
    )

    with pytest.raises(StatusApiFailure) as exc_info:
        client.update_job_status(job_id, JobStatus.SUCCESS)

    assert exc_info.value.kind is StatusApiFailureKind.HTTP_5XX
    assert exc_info.value.status_code == 503
    assert exc_info.value.attempt_count == 3
    assert len(session.calls) == 3
    assert sleep.delays == [1.0, 2.0]


@pytest.mark.parametrize(
    ("final", "kind", "status_code"),
    [
        (FakeResponse(400), StatusApiFailureKind.HTTP_4XX, 400),
        (requests.ConnectionError("sentinel-connection"), StatusApiFailureKind.CONNECTION, None),
        (requests.Timeout("sentinel-timeout"), StatusApiFailureKind.TIMEOUT, None),
    ],
)
def test_mixed_sequence_stops_after_non_retryable_outcome(
    config: Config,
    job_id: str,
    final: FakeResponse | BaseException,
    kind: StatusApiFailureKind,
    status_code: int | None,
) -> None:
    sleep = SleepRecorder()
    client, session = build_client(config, [FakeResponse(500), final], sleep=sleep)

    with pytest.raises(StatusApiFailure) as exc_info:
        client.update_job_status(job_id, JobStatus.GENERATING_CODE)

    assert exc_info.value.kind is kind
    assert exc_info.value.status_code == status_code
    assert exc_info.value.attempt_count == 2
    assert len(session.calls) == 2
    assert sleep.delays == [1.0]


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (requests.ConnectionError("sentinel-connection"), StatusApiFailureKind.CONNECTION),
        (requests.Timeout("sentinel-timeout"), StatusApiFailureKind.TIMEOUT),
    ],
)
def test_transport_failure_is_not_retried(
    config: Config,
    job_id: str,
    error: BaseException,
    kind: StatusApiFailureKind,
) -> None:
    sleep = SleepRecorder()
    client, session = build_client(config, [error], sleep=sleep)

    with pytest.raises(StatusApiFailure) as exc_info:
        client.update_job_status(job_id, JobStatus.ANALYZING)

    assert exc_info.value.kind is kind
    assert exc_info.value.status_code is None
    assert exc_info.value.attempt_count == 1
    assert len(session.calls) == 1
    assert sleep.delays == []


def test_logs_and_exception_exclude_secrets_and_bodies(
    config: Config,
    job_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    keyed = Config(
        **{
            **config.__dict__,
            "prompton_status_api_key": "sentinel-api-key",
        }
    )
    client, _ = build_client(
        keyed,
        [
            FakeResponse(500, body_sentinel="sentinel-response-body"),
            requests.ConnectionError("sentinel-external-error"),
        ],
        sleep=SleepRecorder(),
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(StatusApiFailure) as exc_info:
        client.update_job_status(
            job_id,
            JobStatus.GENERATING_CODE,
            message="sentinel-request-payload",
        )

    combined = caplog.text + str(exc_info.value)
    for secret in (
        "sentinel-api-key",
        "sentinel-response-body",
        "sentinel-external-error",
        "sentinel-request-payload",
        "x-api-key",
    ):
        assert secret not in combined
