"""worker.orchestrator 단위 테스트.

핵심 비즈니스 규칙 검증:
    BR-001 (중복 처리 방지), BR-002 (메시지 삭제 시점), BR-003 (실패 시 유지),
    BR-004 (상태 전이 순서), BR-007 (progress 규칙), BR-008 (에러 분류),
    BR-017 (디렉토리 재생성), BR-018 (정리)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from models.entities import Config, SQSMessage
from models.enums import ErrorCode, JobStatus
from models.exceptions import AIGenerationError, ArtifactUploadError, BuildError
from worker.orchestrator import WorkerOrchestrator


class FakeSQSClient:
    def __init__(self, messages: list[SQSMessage | None] | None = None) -> None:
        self.messages: list[SQSMessage | None] = messages or []
        self.deleted: list[str] = []
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
        self.deleted.append(receipt_handle)

    def extend_visibility(self, receipt_handle: str, timeout_seconds: int) -> None:
        self.extended.append((receipt_handle, timeout_seconds))

    def get_visibility_timeout(self, fallback: int) -> int:
        return self.visibility_timeout


class FakeDynamoClient:
    def __init__(self, initial_status: JobStatus | None = JobStatus.QUEUED) -> None:
        self.status: JobStatus | None = initial_status
        self.updates: list[dict[str, Any]] = []
        self.logs: list[str] = []
        self.get_error: Exception | None = None

    def get_job_status(self, job_id: str) -> JobStatus | None:
        if self.get_error is not None:
            raise self.get_error
        return self.status

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: int | None = None,
        message: str | None = None,
        error_code: ErrorCode | None = None,
        artifact_key: str | None = None,
    ) -> None:
        self.updates.append(
            {
                "status": status,
                "progress": progress,
                "message": message,
                "error_code": error_code,
                "artifact_key": artifact_key,
            }
        )

    def append_log(self, job_id: str, message: str) -> None:
        self.logs.append(message)

    @property
    def status_sequence(self) -> list[JobStatus]:
        return [update["status"] for update in self.updates]


class FakeS3Client:
    def __init__(self) -> None:
        self.uploaded_source: list[str] = []
        self.uploaded_artifact: list[str] = []
        self.assets: list[Path] = []
        self.download_error: Exception | None = None
        self.artifact_error: Exception | None = None

    def download_requirements(
        self, bucket: str, key: str, dest_path: Path
    ) -> dict[str, Any]:
        if self.download_error is not None:
            raise self.download_error
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text('{"appName": "demo"}', encoding="utf-8")
        return {"appName": "demo"}

    def download_assets(self, bucket: str, prefix: str, dest_dir: Path) -> list[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        return list(self.assets)

    def upload_source(self, project_dir: Path, key: str) -> str:
        self.uploaded_source.append(key)
        return key

    def upload_artifact(self, apk_path: Path, key: str) -> str:
        if self.artifact_error is not None:
            raise self.artifact_error
        self.uploaded_artifact.append(key)
        return key


class FakeAIGenerator:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[Path, Path, Path]] = []

    def generate_code(
        self, requirements_path: Path, assets_dir: Path, output_dir: Path
    ) -> Path:
        if self.error is not None:
            raise self.error
        self.calls.append((requirements_path, assets_dir, output_dir))
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
    sqs: FakeSQSClient | None = None,
    dynamo: FakeDynamoClient | None = None,
    s3: FakeS3Client | None = None,
    ai: FakeAIGenerator | None = None,
    builder: FakeApkBuilder | None = None,
) -> tuple[WorkerOrchestrator, dict[str, Any]]:
    """의존성이 주입된 오케스트레이터와 대역 모음을 생성한다."""
    deps = {
        "sqs": sqs or FakeSQSClient(),
        "dynamo": dynamo or FakeDynamoClient(),
        "s3": s3 or FakeS3Client(),
        "ai": ai or FakeAIGenerator(),
        "builder": builder or FakeApkBuilder(),
    }
    orchestrator = WorkerOrchestrator(
        config,
        sqs_client=deps["sqs"],  # type: ignore[arg-type]
        s3_client=deps["s3"],  # type: ignore[arg-type]
        dynamo_client=deps["dynamo"],  # type: ignore[arg-type]
        ai_generator=deps["ai"],  # type: ignore[arg-type]
        apk_builder=deps["builder"],  # type: ignore[arg-type]
    )
    return orchestrator, deps


# ------------------------------------------------------------- 정상 흐름


def test_process_job_happy_path(config: Config, message: SQSMessage) -> None:
    """정상 처리 시 상태 전이 순서와 삭제 시점이 규칙을 따른다 (BR-002, BR-004)."""
    orchestrator, deps = build_orchestrator(config)

    orchestrator.process_job(message)

    dynamo: FakeDynamoClient = deps["dynamo"]
    sqs: FakeSQSClient = deps["sqs"]
    s3: FakeS3Client = deps["s3"]

    assert dynamo.status_sequence == [
        JobStatus.ANALYZING,
        JobStatus.GENERATING_CODE,
        JobStatus.BUILDING,
        JobStatus.SUCCESS,
    ]
    assert sqs.deleted == ["rh-1"]
    assert s3.uploaded_artifact == [f"jobs/{message.job_id}/artifact/app-debug.apk"]
    assert s3.uploaded_source == [f"jobs/{message.job_id}/source/project.zip"]


def test_process_job_sets_fixed_progress_values(config: Config, message: SQSMessage) -> None:
    """상태별 progress 고정값이 사용된다 (BR-007)."""
    orchestrator, deps = build_orchestrator(config)

    orchestrator.process_job(message)

    dynamo: FakeDynamoClient = deps["dynamo"]
    progresses = [update["progress"] for update in dynamo.updates]
    assert progresses == [25, 50, 75, 100]


def test_process_job_records_artifact_key_on_success(
    config: Config, message: SQSMessage
) -> None:
    """SUCCESS 전이 시에만 artifactKey를 기록한다 (BR-006)."""
    orchestrator, deps = build_orchestrator(config)

    orchestrator.process_job(message)

    dynamo: FakeDynamoClient = deps["dynamo"]
    success = dynamo.updates[-1]
    assert success["status"] == JobStatus.SUCCESS
    assert success["artifact_key"] == f"jobs/{message.job_id}/artifact/app-debug.apk"
    assert all(update["artifact_key"] is None for update in dynamo.updates[:-1])


def test_process_job_writes_required_logs(config: Config, message: SQSMessage) -> None:
    """필수 로그 시점이 모두 기록된다 (BR-012)."""
    orchestrator, deps = build_orchestrator(config)

    orchestrator.process_job(message)

    logs: list[str] = deps["dynamo"].logs
    assert "[worker] 작업을 시작했습니다." in logs
    assert "[worker] 요구조건 다운로드 완료" in logs
    assert "[llm] 코드 생성 시작" in logs
    assert "[llm] 코드 생성 완료" in logs
    assert "[gradle] APK 빌드 시작" in logs
    assert "[gradle] APK 빌드 완료" in logs
    assert "[worker] 작업 완료" in logs


def test_process_job_logs_asset_count_when_present(
    config: Config, message: SQSMessage, tmp_path: Path
) -> None:
    """에셋이 있으면 개수 로그가 추가된다 (BR-012, BR-014)."""
    s3 = FakeS3Client()
    s3.assets = [tmp_path / "0-logo.png", tmp_path / "1-hero.png"]
    orchestrator, deps = build_orchestrator(config, s3=s3)

    orchestrator.process_job(message)

    assert "[worker] 에셋 2개 다운로드 완료" in deps["dynamo"].logs


def test_process_job_no_asset_log_when_absent(config: Config, message: SQSMessage) -> None:
    """에셋이 없으면 에셋 로그가 없고 정상 처리된다 (BR-014)."""
    orchestrator, deps = build_orchestrator(config)

    orchestrator.process_job(message)

    assert not any("에셋" in log for log in deps["dynamo"].logs)
    assert deps["dynamo"].status_sequence[-1] == JobStatus.SUCCESS


# ------------------------------------------------------- 중복 처리 방지


@pytest.mark.parametrize("terminal", [JobStatus.SUCCESS, JobStatus.CANCELED])
def test_process_job_skips_terminal_status(
    config: Config, message: SQSMessage, terminal: JobStatus
) -> None:
    """SUCCESS/CANCELED Job은 처리하지 않고 메시지를 삭제한다 (BR-001)."""
    dynamo = FakeDynamoClient(initial_status=terminal)
    orchestrator, deps = build_orchestrator(config, dynamo=dynamo)

    orchestrator.process_job(message)

    assert dynamo.updates == []
    assert deps["sqs"].deleted == ["rh-1"]
    assert deps["ai"].calls == []


def test_process_job_proceeds_when_status_lookup_fails(
    config: Config, message: SQSMessage
) -> None:
    """상태 조회 실패 시에도 처리를 시도한다 (Job 유실 방지)."""
    dynamo = FakeDynamoClient()
    dynamo.get_error = RuntimeError("DynamoDB 장애")
    orchestrator, deps = build_orchestrator(config, dynamo=dynamo)

    orchestrator.process_job(message)

    assert dynamo.status_sequence[-1] == JobStatus.SUCCESS
    assert deps["sqs"].deleted == ["rh-1"]


def test_process_job_proceeds_when_record_missing(
    config: Config, message: SQSMessage
) -> None:
    """레코드가 없어도(None) 처리를 진행한다."""
    dynamo = FakeDynamoClient(initial_status=None)
    orchestrator, deps = build_orchestrator(config, dynamo=dynamo)

    orchestrator.process_job(message)

    assert dynamo.status_sequence[-1] == JobStatus.SUCCESS


# ------------------------------------------------------------- 실패 처리


@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        (AIGenerationError(detail="cli 실패"), ErrorCode.AI_GENERATION_FAILED),
        (RuntimeError("알 수 없는 오류"), ErrorCode.INTERNAL_ERROR),
    ],
)
def test_process_job_ai_failure(
    config: Config,
    message: SQSMessage,
    failure: Exception,
    expected_code: ErrorCode,
) -> None:
    """코드 생성 실패 시 FAILED 기록 후 메시지를 유지한다 (BR-003, BR-008)."""
    orchestrator, deps = build_orchestrator(config, ai=FakeAIGenerator(error=failure))

    orchestrator.process_job(message)

    dynamo: FakeDynamoClient = deps["dynamo"]
    last = dynamo.updates[-1]
    assert last["status"] == JobStatus.FAILED
    assert last["error_code"] == expected_code
    assert deps["sqs"].deleted == []


def test_process_job_build_failure(config: Config, message: SQSMessage) -> None:
    """빌드 실패 시 BUILD_FAILED가 기록된다 (BR-008)."""
    orchestrator, deps = build_orchestrator(
        config, builder=FakeApkBuilder(error=BuildError(detail="gradle 실패"))
    )

    orchestrator.process_job(message)

    last = deps["dynamo"].updates[-1]
    assert last["status"] == JobStatus.FAILED
    assert last["error_code"] == ErrorCode.BUILD_FAILED
    assert deps["sqs"].deleted == []


def test_process_job_artifact_upload_failure(config: Config, message: SQSMessage) -> None:
    """APK 업로드 실패 시 SUCCESS로 전이하지 않는다 (BR-006, BR-008)."""
    s3 = FakeS3Client()
    s3.artifact_error = ArtifactUploadError(detail="업로드 실패")
    orchestrator, deps = build_orchestrator(config, s3=s3)

    orchestrator.process_job(message)

    dynamo: FakeDynamoClient = deps["dynamo"]
    assert JobStatus.SUCCESS not in dynamo.status_sequence
    assert dynamo.updates[-1]["status"] == JobStatus.FAILED
    assert dynamo.updates[-1]["error_code"] == ErrorCode.ARTIFACT_UPLOAD_FAILED
    assert deps["sqs"].deleted == []


def test_failure_does_not_overwrite_progress(config: Config, message: SQSMessage) -> None:
    """실패 시 progress를 전달하지 않아 마지막 값이 유지된다 (BR-007)."""
    orchestrator, deps = build_orchestrator(
        config, builder=FakeApkBuilder(error=BuildError(detail="실패"))
    )

    orchestrator.process_job(message)

    failed = deps["dynamo"].updates[-1]
    assert failed["progress"] is None


def test_failure_message_has_no_internal_detail(
    config: Config, message: SQSMessage
) -> None:
    """실패 message에 내부 상세 정보가 노출되지 않는다 (BR-009)."""
    orchestrator, deps = build_orchestrator(
        config,
        builder=FakeApkBuilder(error=BuildError(detail="/data/jobs/x/project 경로 오류")),
    )

    orchestrator.process_job(message)

    failed = deps["dynamo"].updates[-1]
    assert failed["message"] == "APK 빌드에 실패했습니다."
    assert "/data/jobs" not in str(failed["message"])


def test_failure_logs_error_code(config: Config, message: SQSMessage) -> None:
    """실패 로그에 errorCode가 기록된다 (BR-012)."""
    orchestrator, deps = build_orchestrator(
        config, builder=FakeApkBuilder(error=BuildError(detail="실패"))
    )

    orchestrator.process_job(message)

    assert "[worker] 실패: BUILD_FAILED" in deps["dynamo"].logs


def test_process_job_never_raises(config: Config, message: SQSMessage) -> None:
    """상태 기록까지 실패해도 예외가 전파되지 않는다 (메인 루프 보호)."""

    class BrokenDynamo(FakeDynamoClient):
        def update_status(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("DynamoDB 완전 장애")

    orchestrator, _ = build_orchestrator(config, dynamo=BrokenDynamo())

    orchestrator.process_job(message)


# --------------------------------------------------- 작업 디렉토리 / 멱등성


def test_process_job_recreates_workdir(config: Config, message: SQSMessage) -> None:
    """기존 작업 디렉토리를 삭제하고 재생성한다 (BR-017)."""
    base = Path(config.work_dir) / message.job_id
    base.mkdir(parents=True)
    stale = base / "stale.txt"
    stale.write_text("old", encoding="utf-8")

    orchestrator, _ = build_orchestrator(config)
    orchestrator.process_job(message)

    assert not stale.exists()
    assert base.is_dir()


def test_process_job_passes_expected_paths(config: Config, message: SQSMessage) -> None:
    """AI/빌드 모듈에 규약된 경로가 전달된다."""
    orchestrator, deps = build_orchestrator(config)

    orchestrator.process_job(message)

    base = Path(config.work_dir) / message.job_id
    ai: FakeAIGenerator = deps["ai"]
    builder: FakeApkBuilder = deps["builder"]

    assert ai.calls[0] == (base / "requirements.json", base / "assets", base / "project")
    assert builder.calls[0] == (base / "project", base / "output" / "app-debug.apk")


# ---------------------------------------------------------- Visibility 연장


def test_process_job_uses_queue_visibility_timeout(
    config: Config, message: SQSMessage
) -> None:
    """run()에서 조회한 Queue Visibility Timeout이 연장에 사용된다 (BR-010)."""
    sqs = FakeSQSClient()
    sqs.visibility_timeout = 600
    orchestrator, _ = build_orchestrator(config, sqs=sqs)

    # run() 없이 process_job만 호출하면 config 기본값을 사용한다
    assert orchestrator._visibility_timeout == config.visibility_timeout

    orchestrator._visibility_timeout = sqs.get_visibility_timeout(
        config.visibility_timeout
    )
    assert orchestrator._visibility_timeout == 600


# ------------------------------------------------------ 메인 루프 / Shutdown


def test_run_stops_after_shutdown_request(config: Config, message: SQSMessage) -> None:
    """shutdown 요청 후에는 다음 Job을 받지 않는다 (NFR Pattern 7)."""
    sqs = FakeSQSClient(messages=[message, message])
    orchestrator, deps = build_orchestrator(config, sqs=sqs)

    original = orchestrator.process_job

    def process_and_shutdown(msg: SQSMessage) -> None:
        original(msg)
        orchestrator._handle_shutdown(15, None)

    orchestrator.process_job = process_and_shutdown  # type: ignore[method-assign]

    orchestrator.run()

    # 첫 Job만 처리되고 두 번째는 큐에 남는다
    assert len(sqs.messages) == 1
    assert deps["dynamo"].status_sequence[-1] == JobStatus.SUCCESS
    assert orchestrator.shutdown_requested is True


def test_run_continues_after_receive_error(config: Config) -> None:
    """메시지 수신 실패 시 루프가 중단되지 않는다."""
    sqs = FakeSQSClient(messages=[None])
    sqs.receive_error = RuntimeError("수신 실패")
    orchestrator, _ = build_orchestrator(config, sqs=sqs)

    call_count = {"n": 0}
    original_receive = sqs.receive_message

    def counting_receive() -> SQSMessage | None:
        call_count["n"] += 1
        if call_count["n"] >= 3:
            orchestrator._handle_shutdown(15, None)
            return None
        return original_receive()

    sqs.receive_message = counting_receive  # type: ignore[method-assign]

    orchestrator.run()

    assert call_count["n"] >= 3


def test_run_performs_cleanup_before_receive(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """루프에서 메시지 수신 전에 디렉토리 정리를 수행한다 (BR-018)."""
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
