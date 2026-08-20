"""Worker 오케스트레이터 - 메인 루프 및 Job 처리 시퀀스.

설계 근거: business-logic-model.md 섹션 2 (메인 처리 시퀀스), 섹션 5 (Graceful Shutdown),
          logical-components.md 섹션 2/4
비즈니스 규칙:
    BR-001 (중복 처리 방지), BR-002 (메시지 삭제 시점), BR-003 (실패 시 메시지 유지),
    BR-004 (상태 전이 순서), BR-005 (원자적 상태 갱신), BR-006 (artifactKey 기록 시점),
    BR-007 (progress 규칙), BR-008 (에러 분류), BR-009 (실패 상태 기록),
    BR-012 (로그 기록), BR-017 (디렉토리 생성), BR-018 (디렉토리 정리)
NFR 패턴: Pattern 2 (Visibility 연장), Pattern 3 (Idempotent Consumer),
         Pattern 7 (Graceful Shutdown), Pattern 14 (Periodic Cleanup)
"""

from __future__ import annotations

import logging
import signal
import types
from typing import TYPE_CHECKING

from ai.generator import AIGenerator
from ai.refiner import PromptRefiner
from build.builder import ApkBuilder
from dynamo.client import DynamoClient
from models.entities import Config, JobWorkDir, S3Paths, SQSMessage
from models.enums import JOB_PROGRESS, STATUS_MESSAGES, TERMINAL_STATUSES, JobStatus
from models.exceptions import classify_error, user_message_for
from s3.client import S3Client
from sqs.client import SQSClient
from utils.cleanup import cleanup_old_workdirs, prepare_workdir
from worker.visibility_extender import VisibilityExtender

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

logger = logging.getLogger(__name__)


class WorkerOrchestrator:
    """단일 Job을 순차 처리하는 Worker 메인 오케스트레이터.

    동시성 없이 항상 1개의 Job만 처리한다 (NFR-004).
    """

    def __init__(
        self,
        config: Config,
        sqs_client: SQSClient | None = None,
        s3_client: S3Client | None = None,
        dynamo_client: DynamoClient | None = None,
        prompt_refiner: PromptRefiner | None = None,
        ai_generator: AIGenerator | None = None,
        apk_builder: ApkBuilder | None = None,
    ) -> None:
        """오케스트레이터를 초기화한다.

        의존성은 테스트를 위해 주입 가능하다. None이면 실제 클라이언트를 생성한다.

        Args:
            config: Worker 설정
            sqs_client: SQS 클라이언트 (테스트용 주입)
            s3_client: S3 클라이언트 (테스트용 주입)
            dynamo_client: DynamoDB 클라이언트 (테스트용 주입)
            prompt_refiner: Hermes prompt 정제기 (테스트용 주입)
            ai_generator: AI 코드 생성기 (테스트용 주입)
            apk_builder: APK 빌더 (테스트용 주입)
        """
        self._config = config
        self._sqs = sqs_client if sqs_client is not None else SQSClient(config)
        self._s3 = s3_client if s3_client is not None else S3Client(config)
        self._dynamo = dynamo_client if dynamo_client is not None else DynamoClient(config)
        self._refiner = (
            prompt_refiner
            if prompt_refiner is not None
            else PromptRefiner(config.hermes_cli_path)
        )
        self._ai = ai_generator if ai_generator is not None else AIGenerator(config)
        self._builder = apk_builder if apk_builder is not None else ApkBuilder(config)

        self._shutdown_requested = False
        self._visibility_timeout = config.visibility_timeout

    # ------------------------------------------------------------------
    # 메인 루프
    # ------------------------------------------------------------------

    def run(self) -> None:
        """메인 루프를 실행한다.

        루프 구조 (business-logic-model.md 섹션 2.1, BR-018):
            1. 오래된 작업 디렉토리 정리
            2. SQS Long Polling으로 메시지 수신
            3. 메시지가 있으면 Job 처리
            4. shutdown 요청 확인 후 반복
        """
        self._install_signal_handlers()
        self._visibility_timeout = self._sqs.get_visibility_timeout(
            self._config.visibility_timeout
        )

        logger.info("메인 루프 시작")

        while not self._shutdown_requested:
            # BR-018: 새 메시지를 수신하기 전에 정리한다
            cleanup_old_workdirs(self._config.work_dir, self._config.cleanup_hours)

            try:
                message = self._sqs.receive_message()
            except Exception:
                # 메시지 파싱/수신 실패는 루프를 중단시키지 않는다.
                # (파싱 실패 메시지는 삭제하지 않으므로 재시도 후 DLQ로 이동한다)
                logger.exception("SQS 메시지 수신 실패 - 루프를 계속합니다")
                continue

            if message is None:
                continue

            self.process_job(message)

        logger.info("Shutdown 요청 처리 완료 - 메인 루프 종료")

    # ------------------------------------------------------------------
    # Job 처리
    # ------------------------------------------------------------------

    def process_job(self, message: SQSMessage) -> None:
        """단일 Job의 전체 처리 시퀀스를 수행한다.

        business-logic-model.md 섹션 2.2의 흐름을 그대로 구현한다.
        예외는 이 메서드 내부에서 모두 처리되며 호출자에게 전파되지 않는다
        (메인 루프가 중단되지 않도록 보장).

        Args:
            message: 처리할 SQS 메시지
        """
        job_id = message.job_id
        logger.info("Job 처리 시작 (jobId=%s)", job_id)

        # Phase 0: 중복 처리 방지 (BR-001)
        if self._skip_if_already_done(message):
            return

        extender: VisibilityExtender | None = None
        try:
            work = JobWorkDir.for_job(self._config.work_dir, job_id)
            paths = S3Paths.for_job(job_id)

            # BR-017: 기존 디렉토리 삭제 후 재생성 (멱등성)
            prepare_workdir(work.base_path)

            # NFR Pattern 2: 장시간 처리 중 메시지 보호 (BR-010)
            extender = VisibilityExtender(
                self._sqs, message.receipt_handle, self._visibility_timeout
            )
            extender.start()

            self._phase_analyzing(message, work)
            self._phase_generating_code(job_id, work)
            self._phase_building(job_id, work)
            self._phase_finalize(message, work, paths)

        except Exception as exc:  # noqa: BLE001 - 모든 실패를 FAILED로 기록해야 한다
            self._handle_failure(job_id, exc)
            # BR-003: 실패 시 SQS 메시지를 삭제하지 않는다 (재시도 가능)

        finally:
            if extender is not None:
                extender.stop()

    # ------------------------------------------------------------------
    # Phase 구현
    # ------------------------------------------------------------------

    def _skip_if_already_done(self, message: SQSMessage) -> bool:
        """이미 완료/취소된 Job이면 메시지를 삭제하고 건너뛴다 (BR-001).

        상태 조회 자체가 실패한 경우에는 건너뛰지 않고 처리를 시도한다
        (조회 실패로 정상 Job을 유실하지 않기 위함).

        Args:
            message: 확인할 메시지

        Returns:
            처리를 건너뛰어야 하면 True
        """
        try:
            current = self._dynamo.get_job_status(message.job_id)
        except Exception:
            logger.warning(
                "Job 상태 조회 실패 - 처리를 계속 시도합니다 (jobId=%s)",
                message.job_id,
                exc_info=True,
            )
            return False

        if current in TERMINAL_STATUSES:
            logger.info(
                "이미 종결된 Job이므로 건너뜁니다 (jobId=%s, status=%s)",
                message.job_id,
                current.value if current else None,
            )
            self._safe_delete_message(message.receipt_handle)
            return True

        return False

    def _phase_analyzing(self, message: SQSMessage, work: JobWorkDir) -> None:
        """ANALYZING 단계: 요구조건 및 에셋 다운로드.

        Args:
            message: 처리 중인 메시지
            work: Job 작업 디렉토리 구조

        Raises:
            RequirementsReadError: requirements.json 다운로드 실패
            InvalidRequirementsError: requirements.json 형식 오류
        """
        job_id = message.job_id
        self._transition(job_id, JobStatus.ANALYZING)
        self._dynamo.append_log(job_id, "[worker] 작업을 시작했습니다.")

        self._s3.download_requirements(
            message.requirements_bucket,
            message.requirements_key,
            work.requirements_path,
        )
        self._dynamo.append_log(job_id, "[worker] 요구조건 다운로드 완료")

        assets: Sequence[Path] = self._s3.download_assets(
            message.requirements_bucket,
            message.assets_prefix,
            work.assets_dir,
        )
        # BR-014: 에셋이 없어도 정상 Job이다
        if assets:
            self._dynamo.append_log(job_id, f"[worker] 에셋 {len(assets)}개 다운로드 완료")

    def _phase_generating_code(self, job_id: str, work: JobWorkDir) -> None:
        """GENERATING_CODE 단계: Hermes prompt 정제 후 kiro-cli로 코드 생성.

        Hermes가 최대 시도를 소진해도 Job을 실패시키지 않고 원본 Client JSON과
        동일 Android guardrail을 사용하는 Kiro fallback을 실행한다.

        Args:
            job_id: 처리 중인 Job ID
            work: Job 작업 디렉토리 구조

        Raises:
            AIGenerationError: Kiro 코드 생성 실패
        """
        self._transition(job_id, JobStatus.GENERATING_CODE)
        self._dynamo.append_log(job_id, "[hermes] 프롬프트 정제 시작")

        refined_prompt = self._refiner.refine(
            requirements_path=work.requirements_path,
            output_path=work.refined_prompt_path,
            job_id=job_id,
        )
        if refined_prompt is None:
            self._dynamo.append_log(
                job_id,
                "[hermes] 프롬프트 정제 실패 - 원본 요구조건으로 계속",
            )
        else:
            self._dynamo.append_log(job_id, "[hermes] 프롬프트 정제 완료")

        self._dynamo.append_log(job_id, "[llm] 코드 생성 시작")
        self._ai.generate_code(
            requirements_path=work.requirements_path,
            assets_dir=work.assets_dir,
            output_dir=work.project_dir,
            job_id=job_id,
            refined_prompt_path=refined_prompt,
        )
        self._dynamo.append_log(job_id, "[llm] 코드 생성 완료")

    def _phase_building(self, job_id: str, work: JobWorkDir) -> None:
        """BUILDING 단계: Gradle로 APK 빌드.

        Args:
            job_id: 처리 중인 Job ID
            work: Job 작업 디렉토리 구조

        Raises:
            BuildError: 빌드 실패
        """
        self._transition(job_id, JobStatus.BUILDING)
        self._dynamo.append_log(job_id, "[gradle] APK 빌드 시작")

        self._builder.build_apk(work.project_dir, work.apk_path)
        self._dynamo.append_log(job_id, "[gradle] APK 빌드 완료")

    def _phase_finalize(
        self, message: SQSMessage, work: JobWorkDir, paths: S3Paths
    ) -> None:
        """업로드 및 완료 처리.

        순서가 중요하다 (BR-002, BR-006):
            APK S3 업로드 성공 확인 -> DynamoDB SUCCESS -> SQS 메시지 삭제

        Args:
            message: 처리 중인 메시지
            work: Job 작업 디렉토리 구조
            paths: Job S3 경로 구조

        Raises:
            ArtifactUploadError: APK 업로드 또는 검증 실패
        """
        job_id = message.job_id

        # BR-016: 소스 코드 저장 (실패해도 Job은 계속 진행)
        self._s3.upload_source(work.project_dir, paths.source_key)

        # BR-006: 업로드 성공이 검증된 후에만 artifactKey를 사용한다
        artifact_key = self._s3.upload_artifact(work.apk_path, paths.artifact_key)

        self._transition(job_id, JobStatus.SUCCESS, artifact_key=artifact_key)
        self._dynamo.append_log(job_id, "[worker] 작업 완료")

        # BR-002: 모든 처리가 정상 완료된 후에만 메시지를 삭제한다
        self._sqs.delete_message(message.receipt_handle)
        logger.info("Job 처리 완료 (jobId=%s)", job_id)

    # ------------------------------------------------------------------
    # 상태 전이 및 실패 처리
    # ------------------------------------------------------------------

    def _transition(
        self, job_id: str, status: JobStatus, artifact_key: str | None = None
    ) -> None:
        """상태를 전이하고 progress/message를 함께 갱신한다 (BR-004, BR-005, BR-007).

        Args:
            job_id: 대상 Job ID
            status: 새 상태
            artifact_key: SUCCESS 시 기록할 APK S3 키
        """
        self._dynamo.update_status(
            job_id,
            status,
            progress=JOB_PROGRESS.get(status),
            message=STATUS_MESSAGES.get(status),
            artifact_key=artifact_key,
        )

    def _handle_failure(self, job_id: str, exc: BaseException) -> None:
        """실패 상태를 기록한다 (BR-007, BR-008, BR-009).

        progress는 전달하지 않아 마지막 값이 유지된다.
        message에는 사용자 노출 가능한 한국어 메시지만 기록한다.
        상태 기록 자체가 실패해도 메인 루프는 계속되어야 하므로 예외를 흡수한다.

        Args:
            job_id: 대상 Job ID
            exc: 발생한 예외
        """
        error_code = classify_error(exc)
        logger.error(
            "Job 처리 실패 (jobId=%s, errorCode=%s)", job_id, error_code.value, exc_info=exc
        )

        try:
            self._dynamo.update_status(
                job_id,
                JobStatus.FAILED,
                message=user_message_for(exc),
                error_code=error_code,
            )
            self._dynamo.append_log(job_id, f"[worker] 실패: {error_code.value}")
        except Exception:
            logger.exception("실패 상태 기록에 실패했습니다 (jobId=%s)", job_id)

    def _safe_delete_message(self, receipt_handle: str) -> None:
        """메시지 삭제를 시도하고 실패 시 로그만 남긴다.

        Args:
            receipt_handle: 삭제할 메시지의 receipt handle
        """
        try:
            self._sqs.delete_message(receipt_handle)
        except Exception:
            logger.warning("SQS 메시지 삭제 실패", exc_info=True)

    # ------------------------------------------------------------------
    # Graceful Shutdown
    # ------------------------------------------------------------------

    def _install_signal_handlers(self) -> None:
        """SIGTERM/SIGINT 핸들러를 등록한다 (NFR Pattern 7).

        메인 스레드가 아닌 경우(테스트 등) 등록을 건너뛴다.
        """
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, self._handle_shutdown)
            except (ValueError, OSError):
                logger.debug("시그널 핸들러 등록 생략: %s", sig, exc_info=True)

    def _handle_shutdown(
        self, signum: int, frame: types.FrameType | None
    ) -> None:  # noqa: ARG002 - 시그널 핸들러 시그니처 고정
        """종료 시그널을 받아 shutdown 플래그를 설정한다.

        현재 처리 중인 Job은 완료까지 진행하고, 다음 Job은 수신하지 않는다.

        Args:
            signum: 수신한 시그널 번호
            frame: 현재 스택 프레임 (사용하지 않음)
        """
        logger.info("종료 시그널 수신 (signum=%d) - 현재 작업 완료 후 종료합니다", signum)
        self._shutdown_requested = True

    @property
    def shutdown_requested(self) -> bool:
        """종료가 요청되었는지 여부를 반환한다."""
        return self._shutdown_requested
