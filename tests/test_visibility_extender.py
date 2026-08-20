"""worker.visibility_extender 단위 테스트."""

from __future__ import annotations

import threading

from worker.visibility_extender import (
    EXTEND_INTERVAL_RATIO,
    MIN_EXTEND_INTERVAL_SECONDS,
    VisibilityExtender,
)


class RecordingSQS:
    """extend_visibility 호출을 기록하는 대역."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, int]] = []
        self.fail = fail
        self.called = threading.Event()

    def extend_visibility(self, receipt_handle: str, timeout_seconds: int) -> None:
        self.calls.append((receipt_handle, timeout_seconds))
        self.called.set()
        if self.fail:
            raise RuntimeError("연장 실패")


def test_interval_is_half_of_visibility_timeout() -> None:
    """연장 주기는 Visibility Timeout의 50%다 (BR-010)."""
    extender = VisibilityExtender(RecordingSQS(), "rh", 300)  # type: ignore[arg-type]

    assert extender._interval == 300 * EXTEND_INTERVAL_RATIO


def test_interval_respects_minimum() -> None:
    """계산된 주기가 최소값보다 작으면 최소값을 사용한다."""
    extender = VisibilityExtender(RecordingSQS(), "rh", 2)  # type: ignore[arg-type]

    assert extender._interval == MIN_EXTEND_INTERVAL_SECONDS


def test_extends_periodically() -> None:
    """주기마다 extend_visibility가 호출된다 (NFR Pattern 2)."""
    fake = RecordingSQS()
    extender = VisibilityExtender(fake, "rh-1", 300)  # type: ignore[arg-type]
    # 테스트 속도를 위해 주기를 짧게 조정
    extender._interval = 0.05

    extender.start()
    try:
        assert fake.called.wait(timeout=2.0), "연장이 호출되지 않았습니다"
    finally:
        extender.stop()

    assert fake.calls[0] == ("rh-1", 300)
    assert extender.extend_count >= 1


def test_extend_failure_does_not_raise() -> None:
    """연장 실패 시 스레드가 죽지 않고 처리를 계속한다 (BR-011)."""
    fake = RecordingSQS(fail=True)
    extender = VisibilityExtender(fake, "rh-1", 300)  # type: ignore[arg-type]
    extender._interval = 0.05

    extender.start()
    try:
        assert fake.called.wait(timeout=2.0)
    finally:
        extender.stop()

    # 연장은 실패했으므로 성공 카운트는 증가하지 않는다
    assert extender.extend_count == 0
    assert len(fake.calls) >= 1


def test_stop_without_extension() -> None:
    """주기 도달 전에 stop하면 연장 호출 없이 종료된다."""
    fake = RecordingSQS()
    extender = VisibilityExtender(fake, "rh-1", 300)  # type: ignore[arg-type]

    extender.start()
    extender.stop()

    assert fake.calls == []
    assert extender.extend_count == 0


def test_context_manager_starts_and_stops() -> None:
    """컨텍스트 매니저로 start/stop이 자동 처리된다."""
    fake = RecordingSQS()
    extender = VisibilityExtender(fake, "rh-1", 300)  # type: ignore[arg-type]
    extender._interval = 0.05

    with extender:
        assert fake.called.wait(timeout=2.0)

    assert not extender._thread.is_alive()
