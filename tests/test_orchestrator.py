"""WorkerOrchestrator tests for the Status API target lifecycle."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from models.entities import Config, SQSMessage
from models.enums import ErrorCode, JobStatus
from models.exceptions import (
    AIGenerationError,
    ArtifactUploadError,
    BuildError,
    RequirementsReadError,
    StatusApiFailure,
    StatusApiFailureKind,
)
from worker.orchestrator import (
    EMPTY_POLL_DELAY_SECONDS,
    WorkerOrchestrator,
)


class FakeSQSClient:
    def __init__(
        self,
        messages: list[SQSMessage | None] | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.messages = list(messages or [])
        self.events = events if events is not None else []
        self.deleted: list[str] = []
        self.delete_attempts = 0
        self.delete_error: Exception | None = None
        self.extended: list[tuple[str, int]] = []
        self.visibility_timeout = 300
        self.receive_error: Exception | None = None

    def receive_message(self) -> SQSMessage | None:
        if self.receive_error is not None:
            error, self.receive_error = self.receive_error, None
            raise error
        if not self.messages:
            return None
        return self.messages.pop(0)

    def delete_message(self, receipt_handle: str) -> None:
        self.delete_attempts += 1
        self.events.append("sqs_delete")
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append(receipt_handle)

    def extend_visibility(self, receipt_handle: str, timeout_seconds: int) -> None:
        self.extended.append((receipt_handle, timeout_seconds))

    def get_visibility_timeout(self, fallback: int) -> int:
        return self.visibility_timeout


class FakeStatusApiClient:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.updates: list[dict[str, Any]] = []
        self.failures: dict[JobStatus, list[BaseException]] = {}

    def fail_next(self, status: JobStatus, error: BaseException) -> None:
        self.failures.setdefault(status, []).append(error)

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: int | None = None,
        message: str | None = None,
        artifact_key: str | None = None,
        error_code: ErrorCode | None = None,
    ) -> None:
        self.events.append(f"status:{status.value}")
        self.updates.append(
            {
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "message": message,
                "artifact_key": artifact_key,
                "error_code": error_code,
            }
        )
        failures = self.failures.get(status)
        if failures:
            raise failures.pop(0)

    @property
    def status_sequence(self) -> list[JobStatus]:
        return [update["status"] for update in self.updates]


class FakeS3Client:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.uploaded_source: list[str] = []
        self.uploaded_artifact: list[str] = []
        self.assets: list[Path] = []
        self.download_error: Exception | None = None
        self.artifact_error: Exception | None = None

    def download_requirements(
        self,
        bucket: str,
        key: str,
        dest_path: Path,
    ) -> dict[str, Any]:
        self.events.append("requirements")
        if self.download_error is not None:
            raise self.download_error
        payload: dict[str, Any] = {"request": "demo", "custom": {"theme": "green"}}
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def download_assets(self, bucket: str, prefix: str, dest_dir: Path) -> list[Path]:
        self.events.append("assets")
        dest_dir.mkdir(parents=True, exist_ok=True)
        return list(self.assets)

    def upload_source(self, project_dir: Path, key: str) -> str:
        self.events.append("source_upload")
        self.uploaded_source.append(key)
        return key

    def upload_artifact(self, apk_path: Path, key: str) -> str:
        self.events.append("artifact_verify")
        if self.artifact_error is not None:
            raise self.artifact_error
        self.uploaded_artifact.append(key)
        return key


class FakePromptRefiner:
    def __init__(self, succeeds: bool = True) -> None:
        self.succeeds = succeeds
        self.calls: list[tuple[Path, Path, str]] = []

    def refine(
        self,
        requirements_path: Path,
        output_path: Path,
        job_id: str,
    ) -> Path | None:
        self.calls.append((requirements_path, output_path, job_id))
        if not self.succeeds:
            return None
        output_path.write_text("refined prompt", encoding="utf-8")
        return output_path


class FakeAIGenerator:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[Path, Path, Path, str, Path | None]] = []

    def generate_code(
        self,
        requirements_path: Path,
        assets_dir: Path,
        output_dir: Path,
        *,
        job_id: str,
        refined_prompt_path: Path | None = None,
    ) -> Path:
        if self.error is not None:
            raise self.error
        self.calls.append((requirements_path, assets_dir, output_dir, job_id, refined_prompt_path))
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "settings.gradle").write_text("x", encoding="utf-8")
        return output_dir


class FakeApkBuilder:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[Path, Path]] = []

    def build_apk(self, project_dir: Path, output_apk_path: Path) -> Path:
        if self.error is not None:
            raise self.error
        self.calls.append((project_dir, output_apk_path))
        output_apk_path.parent.mkdir(parents=True, exist_ok=True)
        output_apk_path.write_bytes(b"apk")
        return output_apk_path


class RecordingVisibilityExtender:
    instances: list[RecordingVisibilityExtender] = []

    def __init__(
        self,
        sqs_client: object,
        receipt_handle: str,
        visibility_timeout: int,
    ) -> None:
        self.receipt_handle = receipt_handle
        self.visibility_timeout = visibility_timeout
        self.started = 0
        self.stopped = 0
        self.__class__.instances.append(self)

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1


def status_failure(
    kind: StatusApiFailureKind = StatusApiFailureKind.HTTP_5XX,
) -> StatusApiFailure:
    return StatusApiFailure(kind, status_code=503, attempt_count=3)


@pytest.fixture
def message(job_id: str) -> SQSMessage:
    return SQSMessage(
        job_id=job_id,
        requirements_bucket="test-bucket",
        requirements_key=f"jobs/{job_id}/requirements/requirements.json",
        assets_prefix=f"jobs/{job_id}/assets/",
        receipt_handle="rh-1",
        schema_version="1.0",
    )


def build_orchestrator(
    config: Config,
    *,
    events: list[str] | None = None,
    sqs: FakeSQSClient | None = None,
    status: FakeStatusApiClient | None = None,
    s3: FakeS3Client | None = None,
    refiner: FakePromptRefiner | None = None,
    ai: FakeAIGenerator | None = None,
    builder: FakeApkBuilder | None = None,
) -> tuple[WorkerOrchestrator, dict[str, Any]]:
    recorder = events if events is not None else []
    deps: dict[str, Any] = {
        "sqs": sqs or FakeSQSClient(events=recorder),
        "status": status or FakeStatusApiClient(events=recorder),
        "s3": s3 or FakeS3Client(events=recorder),
        "refiner": refiner or FakePromptRefiner(),
        "ai": ai or FakeAIGenerator(),
        "builder": builder or FakeApkBuilder(),
    }
    orchestrator = WorkerOrchestrator(
        config,
        sqs_client=deps["sqs"],
        s3_client=deps["s3"],
        status_client=deps["status"],
        prompt_refiner=deps["refiner"],
        ai_generator=deps["ai"],
        apk_builder=deps["builder"],
    )
    return orchestrator, deps


def test_process_job_happy_path_exact_payloads_and_order(
    config: Config,
    message: SQSMessage,
) -> None:
    events: list[str] = []
    orchestrator, deps = build_orchestrator(config, events=events)

    orchestrator.process_job(message)

    status: FakeStatusApiClient = deps["status"]
    assert status.status_sequence == [
        JobStatus.ANALYZING,
        JobStatus.GENERATING_CODE,
        JobStatus.BUILDING,
        JobStatus.SUCCESS,
    ]
    assert [(u["progress"], u["message"]) for u in status.updates] == [
        (25, "요구조건을 분석하고 있습니다."),
        (50, "Android 코드를 생성하고 있습니다."),
        (75, "APK를 빌드하고 있습니다."),
        (100, "앱 생성이 완료되었습니다."),
    ]
    artifact_key = f"jobs/{message.job_id}/artifact/app-debug.apk"
    assert status.updates[-1]["artifact_key"] == artifact_key
    assert events.index("artifact_verify") < events.index("status:SUCCESS")
    assert events.index("status:SUCCESS") < events.index("sqs_delete")
    assert deps["sqs"].deleted == ["rh-1"]


@pytest.mark.parametrize(
    "failed_status",
    [JobStatus.ANALYZING, JobStatus.GENERATING_CODE, JobStatus.BUILDING],
)
def test_intermediate_status_failure_continues_to_success(
    config: Config,
    message: SQSMessage,
    failed_status: JobStatus,
) -> None:
    status = FakeStatusApiClient()
    status.fail_next(failed_status, status_failure())
    orchestrator, deps = build_orchestrator(config, status=status)

    orchestrator.process_job(message)

    assert status.status_sequence[-1] is JobStatus.SUCCESS
    assert deps["ai"].calls
    assert deps["builder"].calls
    assert deps["sqs"].deleted == ["rh-1"]


def test_every_redelivery_runs_complete_pipeline(
    config: Config,
    message: SQSMessage,
) -> None:
    orchestrator, deps = build_orchestrator(config)

    orchestrator.process_job(message)
    orchestrator.process_job(message)

    status: FakeStatusApiClient = deps["status"]
    expected = [
        JobStatus.ANALYZING,
        JobStatus.GENERATING_CODE,
        JobStatus.BUILDING,
        JobStatus.SUCCESS,
    ]
    assert status.status_sequence == expected * 2
    assert len(deps["ai"].calls) == 2
    assert len(deps["builder"].calls) == 2
    assert deps["sqs"].deleted == ["rh-1", "rh-1"]
    assert not hasattr(status, "get_job_status")


@pytest.mark.parametrize(
    ("component", "failure", "expected_code"),
    [
        ("requirements", RequirementsReadError(detail="read"), ErrorCode.REQUIREMENTS_READ_FAILED),
        ("ai", AIGenerationError(detail="ai"), ErrorCode.AI_GENERATION_FAILED),
        ("build", BuildError(detail="build"), ErrorCode.BUILD_FAILED),
        ("artifact", ArtifactUploadError(detail="artifact"), ErrorCode.ARTIFACT_UPLOAD_FAILED),
    ],
)
def test_processing_failure_reports_safe_failed_and_keeps_message(
    config: Config,
    message: SQSMessage,
    component: str,
    failure: Exception,
    expected_code: ErrorCode,
) -> None:
    s3 = FakeS3Client()
    ai = FakeAIGenerator()
    builder = FakeApkBuilder()
    if component == "requirements":
        s3.download_error = failure
    elif component == "ai":
        ai.error = failure
    elif component == "build":
        builder.error = failure
    else:
        s3.artifact_error = failure

    orchestrator, deps = build_orchestrator(config, s3=s3, ai=ai, builder=builder)
    orchestrator.process_job(message)

    status: FakeStatusApiClient = deps["status"]
    failed = status.updates[-1]
    assert failed["status"] is JobStatus.FAILED
    assert failed["error_code"] is expected_code
    assert failed["progress"] is None
    assert failed["artifact_key"] is None
    assert str(failure) not in str(failed["message"])
    assert deps["sqs"].deleted == []


def test_failed_reporting_failure_preserves_original_error(
    config: Config,
    message: SQSMessage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    status = FakeStatusApiClient()
    status.fail_next(JobStatus.FAILED, status_failure(StatusApiFailureKind.TIMEOUT))
    orchestrator, deps = build_orchestrator(
        config,
        status=status,
        builder=FakeApkBuilder(error=BuildError(detail="sentinel-build-detail")),
    )

    with caplog.at_level(logging.DEBUG):
        orchestrator.process_job(message)

    failed = status.updates[-1]
    assert failed["error_code"] is ErrorCode.BUILD_FAILED
    assert deps["sqs"].deleted == []
    assert "original_error_code=BUILD_FAILED" in caplog.text
    assert "sentinel-build-detail" not in caplog.text


def test_success_failure_reports_internal_error_and_does_not_delete(
    config: Config,
    message: SQSMessage,
) -> None:
    status = FakeStatusApiClient()
    status.fail_next(JobStatus.SUCCESS, status_failure())
    orchestrator, deps = build_orchestrator(config, status=status)

    orchestrator.process_job(message)

    assert status.status_sequence[-2:] == [JobStatus.SUCCESS, JobStatus.FAILED]
    assert status.updates[-1]["error_code"] is ErrorCode.INTERNAL_ERROR
    assert status.updates[-1]["progress"] is None
    assert deps["sqs"].delete_attempts == 0


def test_delete_failure_after_success_does_not_report_failed(
    config: Config,
    message: SQSMessage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    events: list[str] = []
    sqs = FakeSQSClient(events=events)
    sqs.delete_error = RuntimeError("sentinel-delete-detail")
    orchestrator, deps = build_orchestrator(config, events=events, sqs=sqs)

    with caplog.at_level(logging.DEBUG):
        orchestrator.process_job(message)

    status: FakeStatusApiClient = deps["status"]
    assert status.status_sequence[-1] is JobStatus.SUCCESS
    assert JobStatus.FAILED not in status.status_sequence
    assert sqs.delete_attempts == 1
    assert sqs.deleted == []
    assert "sqs_delete_failed_after_success" in caplog.text
    assert "sentinel-delete-detail" not in caplog.text


def test_artifact_failure_prevents_success_and_delete(
    config: Config,
    message: SQSMessage,
) -> None:
    s3 = FakeS3Client()
    s3.artifact_error = ArtifactUploadError(detail="upload")
    orchestrator, deps = build_orchestrator(config, s3=s3)

    orchestrator.process_job(message)

    sequence = deps["status"].status_sequence
    assert JobStatus.SUCCESS not in sequence
    assert sequence[-1] is JobStatus.FAILED
    assert deps["sqs"].delete_attempts == 0


def test_raw_fallback_reaches_success(
    config: Config,
    message: SQSMessage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    orchestrator, deps = build_orchestrator(
        config,
        refiner=FakePromptRefiner(succeeds=False),
    )

    with caplog.at_level(logging.INFO):
        orchestrator.process_job(message)

    assert deps["status"].status_sequence[-1] is JobStatus.SUCCESS
    assert deps["ai"].calls[0][4] is None
    assert "hermes_fallback" in caplog.text


def test_asset_count_is_logged_safely(
    config: Config,
    message: SQSMessage,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    s3 = FakeS3Client()
    s3.assets = [tmp_path / "logo.png", tmp_path / "hero.jpg"]
    orchestrator, _ = build_orchestrator(config, s3=s3)

    with caplog.at_level(logging.INFO):
        orchestrator.process_job(message)

    assert f"assets_downloaded job_id={message.job_id} count=2" in caplog.text


def test_process_job_recreates_workdir(config: Config, message: SQSMessage) -> None:
    base = Path(config.work_dir) / message.job_id
    base.mkdir(parents=True)
    stale = base / "stale.txt"
    stale.write_text("old", encoding="utf-8")

    orchestrator, _ = build_orchestrator(config)
    orchestrator.process_job(message)

    assert not stale.exists()
    assert base.is_dir()


def test_process_job_passes_expected_paths(config: Config, message: SQSMessage) -> None:
    orchestrator, deps = build_orchestrator(config)

    orchestrator.process_job(message)

    base = Path(config.work_dir) / message.job_id
    assert deps["refiner"].calls[0] == (
        base / "requirements.json",
        base / "refined-prompt.md",
        message.job_id,
    )
    assert deps["ai"].calls[0] == (
        base / "requirements.json",
        base / "assets",
        base / "project",
        message.job_id,
        base / "refined-prompt.md",
    )
    assert deps["builder"].calls[0] == (
        base / "project",
        base / "output" / "app-debug.apk",
    )


@pytest.mark.parametrize("fail_build", [False, True])
def test_visibility_extender_is_paired_on_every_path(
    config: Config,
    message: SQSMessage,
    monkeypatch: pytest.MonkeyPatch,
    fail_build: bool,
) -> None:
    RecordingVisibilityExtender.instances.clear()
    monkeypatch.setattr(
        "worker.orchestrator.VisibilityExtender",
        RecordingVisibilityExtender,
    )
    builder = FakeApkBuilder(error=BuildError(detail="build") if fail_build else None)
    orchestrator, _ = build_orchestrator(config, builder=builder)

    orchestrator.process_job(message)

    extender = RecordingVisibilityExtender.instances[-1]
    assert extender.started == 1
    assert extender.stopped == 1


def test_process_job_contains_unexpected_failed_reporting_error(
    config: Config,
    message: SQSMessage,
) -> None:
    status = FakeStatusApiClient()
    status.fail_next(JobStatus.FAILED, RuntimeError("unexpected reporter failure"))
    orchestrator, deps = build_orchestrator(
        config,
        status=status,
        builder=FakeApkBuilder(error=BuildError(detail="build")),
    )

    orchestrator.process_job(message)

    assert deps["sqs"].deleted == []


def test_process_job_uses_configured_visibility_timeout(
    config: Config,
    message: SQSMessage,
) -> None:
    sqs = FakeSQSClient()
    sqs.visibility_timeout = 600
    orchestrator, _ = build_orchestrator(config, sqs=sqs)

    assert orchestrator._visibility_timeout == config.visibility_timeout
    orchestrator._visibility_timeout = sqs.get_visibility_timeout(config.visibility_timeout)
    assert orchestrator._visibility_timeout == 600


def test_run_stops_after_current_job(config: Config, message: SQSMessage) -> None:
    sqs = FakeSQSClient(messages=[message, message])
    orchestrator, deps = build_orchestrator(config, sqs=sqs)
    original = orchestrator.process_job

    def process_and_shutdown(message: SQSMessage) -> None:
        original(message)
        orchestrator._handle_shutdown(15, None)

    orchestrator.process_job = process_and_shutdown  # type: ignore[method-assign]
    orchestrator.run()

    assert len(sqs.messages) == 1
    assert deps["status"].status_sequence[-1] is JobStatus.SUCCESS
    assert orchestrator.shutdown_requested is True


def test_run_continues_after_receive_error(
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("worker.orchestrator.time.sleep", sleeps.append)
    sqs = FakeSQSClient(messages=[None])
    sqs.receive_error = RuntimeError("receive")
    orchestrator, _ = build_orchestrator(config, sqs=sqs)
    calls = 0
    original_receive = sqs.receive_message

    def receive_then_stop() -> SQSMessage | None:
        nonlocal calls
        calls += 1
        if calls >= 3:
            orchestrator._handle_shutdown(15, None)
            return None
        return original_receive()

    sqs.receive_message = receive_then_stop  # type: ignore[method-assign]
    orchestrator.run()

    assert calls >= 3
    assert sleeps == [EMPTY_POLL_DELAY_SECONDS]


def test_run_waits_500ms_after_empty_poll(
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("worker.orchestrator.time.sleep", sleeps.append)
    sqs = FakeSQSClient()
    orchestrator, _ = build_orchestrator(config, sqs=sqs)
    calls = 0

    def receive_then_stop() -> SQSMessage | None:
        nonlocal calls
        calls += 1
        if calls >= 2:
            orchestrator._handle_shutdown(15, None)
        return None

    sqs.receive_message = receive_then_stop  # type: ignore[method-assign]
    orchestrator.run()

    assert calls == 2
    assert EMPTY_POLL_DELAY_SECONDS == 0.5
    assert sleeps == [EMPTY_POLL_DELAY_SECONDS]


def test_run_performs_cleanup_before_receive(
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_cleanup(work_dir: str, max_age_hours: int) -> int:
        calls.append(f"cleanup:{work_dir}:{max_age_hours}")
        return 0

    monkeypatch.setattr("worker.orchestrator.cleanup_old_workdirs", fake_cleanup)
    sqs = FakeSQSClient()
    orchestrator, _ = build_orchestrator(config, sqs=sqs)

    def receive_then_shutdown() -> SQSMessage | None:
        calls.append("receive")
        orchestrator._handle_shutdown(15, None)
        return None

    sqs.receive_message = receive_then_shutdown  # type: ignore[method-assign]
    orchestrator.run()

    assert calls == [f"cleanup:{config.work_dir}:{config.cleanup_hours}", "receive"]
