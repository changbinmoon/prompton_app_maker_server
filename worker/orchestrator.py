"""Sequential Worker orchestration for the Status API target lifecycle.

The orchestrator owns phase criticality and SQS acknowledgment. StatusApiClient
owns HTTP transport behavior. Every validated SQS delivery is fully reprocessed;
there is no Job status GET or terminal-state preflight.
"""

from __future__ import annotations

import logging
import signal
import time
import types
from typing import TYPE_CHECKING

from ai.generator import AIGenerator
from ai.refiner import PromptRefiner
from build.builder import ApkBuilder
from models.entities import Config, JobWorkDir, S3Paths, SQSMessage
from models.enums import JOB_PROGRESS, STATUS_MESSAGES, JobStatus
from models.exceptions import StatusApiFailure, classify_error, user_message_for
from s3.client import S3Client
from sqs.client import SQSClient
from status_api.client import StatusApiClient
from utils.cleanup import cleanup_old_workdirs, prepare_workdir
from worker.visibility_extender import VisibilityExtender

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

logger = logging.getLogger(__name__)

#: SQS short poll이 빈 응답을 반환한 뒤 다음 receive까지 대기하는 시간.
EMPTY_POLL_DELAY_SECONDS = 0.5


class WorkerOrchestrator:
    """Process exactly one SQS Job at a time."""

    def __init__(
        self,
        config: Config,
        sqs_client: SQSClient | None = None,
        s3_client: S3Client | None = None,
        status_client: StatusApiClient | None = None,
        prompt_refiner: PromptRefiner | None = None,
        ai_generator: AIGenerator | None = None,
        apk_builder: ApkBuilder | None = None,
    ) -> None:
        self._config = config
        self._sqs = sqs_client if sqs_client is not None else SQSClient(config)
        self._s3 = s3_client if s3_client is not None else S3Client(config)
        self._status = status_client if status_client is not None else StatusApiClient(config)
        self._refiner = (
            prompt_refiner if prompt_refiner is not None else PromptRefiner(config.hermes_cli_path)
        )
        self._ai = ai_generator if ai_generator is not None else AIGenerator(config)
        self._builder = apk_builder if apk_builder is not None else ApkBuilder(config)
        self._shutdown_requested = False
        self._visibility_timeout = config.visibility_timeout

    def run(self) -> None:
        """Poll and process messages sequentially until shutdown is requested."""
        self._install_signal_handlers()
        self._visibility_timeout = self._sqs.get_visibility_timeout(self._config.visibility_timeout)
        logger.info("worker_loop_started")

        while not self._shutdown_requested:
            cleanup_old_workdirs(self._config.work_dir, self._config.cleanup_hours)
            try:
                message = self._sqs.receive_message()
            except Exception:  # noqa: BLE001 - preserve queue redrive and loop availability
                logger.error("sqs_receive_failed action=continue")
                continue

            if message is None:
                if not self._shutdown_requested:
                    time.sleep(EMPTY_POLL_DELAY_SECONDS)
                continue

            self.process_job(message)

        logger.info("worker_loop_stopped")

    def process_job(self, message: SQSMessage) -> None:
        """Execute one complete processing attempt and contain all Job failures."""
        job_id = message.job_id
        logger.info("job_started job_id=%s", job_id)
        extender: VisibilityExtender | None = None

        try:
            work = JobWorkDir.for_job(self._config.work_dir, job_id)
            paths = S3Paths.for_job(job_id)
            prepare_workdir(work.base_path)

            extender = VisibilityExtender(
                self._sqs,
                message.receipt_handle,
                self._visibility_timeout,
            )
            extender.start()

            self._phase_analyzing(message, work)
            self._phase_generating_code(job_id, work)
            self._phase_building(job_id, work)
            self._phase_finalize(message, work, paths)
        except Exception as exc:  # noqa: BLE001 - classify every Job processing failure
            self._handle_failure(job_id, exc)
        finally:
            if extender is not None:
                extender.stop()

    def _phase_analyzing(self, message: SQSMessage, work: JobWorkDir) -> None:
        job_id = message.job_id
        logger.info("phase_started job_id=%s phase=ANALYZING", job_id)
        self._report_intermediate_status(job_id, JobStatus.ANALYZING)

        self._s3.download_requirements(
            message.requirements_bucket,
            message.requirements_key,
            work.requirements_path,
        )
        logger.info("requirements_downloaded job_id=%s", job_id)

        assets: Sequence[Path] = self._s3.download_assets(
            message.requirements_bucket,
            message.assets_prefix,
            work.assets_dir,
        )
        if assets:
            logger.info("assets_downloaded job_id=%s count=%d", job_id, len(assets))
        logger.info("phase_completed job_id=%s phase=ANALYZING", job_id)

    def _phase_generating_code(self, job_id: str, work: JobWorkDir) -> None:
        logger.info("phase_started job_id=%s phase=GENERATING_CODE", job_id)
        self._report_intermediate_status(job_id, JobStatus.GENERATING_CODE)

        logger.info("hermes_refinement_started job_id=%s", job_id)
        refined_prompt = self._refiner.refine(
            requirements_path=work.requirements_path,
            output_path=work.refined_prompt_path,
            job_id=job_id,
        )
        if refined_prompt is None:
            logger.warning("hermes_fallback job_id=%s mode=raw_requirements", job_id)
        else:
            logger.info("hermes_refinement_completed job_id=%s", job_id)

        logger.info("code_generation_started job_id=%s", job_id)
        self._ai.generate_code(
            requirements_path=work.requirements_path,
            assets_dir=work.assets_dir,
            output_dir=work.project_dir,
            job_id=job_id,
            refined_prompt_path=refined_prompt,
        )
        logger.info("code_generation_completed job_id=%s", job_id)
        logger.info("phase_completed job_id=%s phase=GENERATING_CODE", job_id)

    def _phase_building(self, job_id: str, work: JobWorkDir) -> None:
        logger.info("phase_started job_id=%s phase=BUILDING", job_id)
        self._report_intermediate_status(job_id, JobStatus.BUILDING)
        self._builder.build_apk(work.project_dir, work.apk_path)
        logger.info("phase_completed job_id=%s phase=BUILDING", job_id)

    def _phase_finalize(
        self,
        message: SQSMessage,
        work: JobWorkDir,
        paths: S3Paths,
    ) -> None:
        job_id = message.job_id
        self._s3.upload_source(work.project_dir, paths.source_key)
        artifact_key = self._s3.upload_artifact(work.apk_path, paths.artifact_key)
        logger.info(
            "artifact_verified job_id=%s artifact_key=%s",
            job_id,
            artifact_key,
        )

        self._report_success(job_id, artifact_key)

        try:
            self._sqs.delete_message(message.receipt_handle)
        except Exception:  # noqa: BLE001 - accepted SUCCESS stays authoritative
            logger.warning(
                "sqs_delete_failed_after_success job_id=%s action=redeliver",
                job_id,
            )
            return

        logger.info("job_completed job_id=%s", job_id)

    def _report_intermediate_status(self, job_id: str, status: JobStatus) -> None:
        """Report an intermediate phase without failing local Job processing."""
        try:
            self._status.update_job_status(
                job_id,
                status,
                progress=JOB_PROGRESS[status],
                message=STATUS_MESSAGES[status],
            )
        except StatusApiFailure as exc:
            logger.warning(
                "intermediate_status_failed job_id=%s status=%s kind=%s attempts=%d "
                "action=continue",
                job_id,
                status.value,
                exc.kind.value,
                exc.attempt_count,
            )

    def _report_success(self, job_id: str, artifact_key: str) -> None:
        """Report mandatory SUCCESS; final transport failure propagates."""
        self._status.update_job_status(
            job_id,
            JobStatus.SUCCESS,
            progress=JOB_PROGRESS[JobStatus.SUCCESS],
            message=STATUS_MESSAGES[JobStatus.SUCCESS],
            artifact_key=artifact_key,
        )

    def _handle_failure(self, job_id: str, exc: BaseException) -> None:
        """Best-effort FAILED reporting that preserves the original classification."""
        error_code = classify_error(exc)
        safe_message = user_message_for(exc)
        logger.error("job_failed job_id=%s error_code=%s", job_id, error_code.value)

        try:
            self._status.update_job_status(
                job_id,
                JobStatus.FAILED,
                message=safe_message,
                error_code=error_code,
            )
        except StatusApiFailure as reporting_error:
            logger.error(
                "failed_status_reporting_failed job_id=%s original_error_code=%s "
                "kind=%s attempts=%d",
                job_id,
                error_code.value,
                reporting_error.kind.value,
                reporting_error.attempt_count,
            )
        except Exception:  # noqa: BLE001 - do not replace the original Job error
            logger.error(
                "failed_status_reporting_failed job_id=%s original_error_code=%s kind=UNEXPECTED",
                job_id,
                error_code.value,
            )

    def _install_signal_handlers(self) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, self._handle_shutdown)
            except (ValueError, OSError):
                logger.debug("signal_handler_skipped signal=%s", sig)

    def _handle_shutdown(
        self,
        signum: int,
        frame: types.FrameType | None,
    ) -> None:  # noqa: ARG002 - signal handler signature
        logger.info("shutdown_requested signal=%d", signum)
        self._shutdown_requested = True

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested
