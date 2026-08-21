"""Prompton AI Worker 엔트리포인트.

systemd에서 `python -m main` 으로 실행된다.

처리 흐름:
    1. 로깅 초기화
    2. 환경 변수 기반 Config 로드 및 검증
    3. WorkerOrchestrator 생성 및 메인 루프 실행
    4. SIGTERM/SIGINT 수신 시 Graceful Shutdown

Exit code:
    0 - 정상 종료 (Graceful Shutdown 완료)
    1 - 설정 오류 또는 복구 불가능한 초기화 실패
"""

from __future__ import annotations

import logging
import sys

from config.settings import ConfigError, load_config
from worker.orchestrator import WorkerOrchestrator

logger = logging.getLogger(__name__)


def setup_logging(log_level: str) -> None:
    """루트 로거를 구성한다.

    stdout으로 출력하여 systemd journald가 수집하도록 한다.
    (NFR Design Pattern 13: Structured Logging)

    Args:
        log_level: 로그 레벨 문자열 (DEBUG/INFO/WARNING/ERROR)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    root = logging.getLogger()
    root.setLevel(level)
    # systemd 재시작 시 핸들러 중복 방지
    root.handlers.clear()
    root.addHandler(handler)

    # boto3/botocore의 과도한 로그 억제
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main() -> int:
    """Worker 프로세스의 메인 함수.

    Returns:
        프로세스 exit code
    """
    try:
        config = load_config()
    except ConfigError as exc:
        # 로깅 초기화 전에 실패할 수 있으므로 stderr로 직접 출력
        print(f"[FATAL] 설정 오류: {exc}", file=sys.stderr)
        return 1

    setup_logging(config.log_level)

    logger.info("Prompton AI Worker 시작")
    logger.info("Region=%s", config.aws_region)
    logger.info("Queue=%s", config.sqs_queue_url)
    logger.info("StatusApiBase=%s", config.prompton_api_base_url)
    logger.info("Bucket=%s", config.s3_bucket_name)
    logger.info("WorkDir=%s", config.work_dir)

    try:
        orchestrator = WorkerOrchestrator(config)
    except Exception:
        logger.exception("Worker 초기화 실패")
        return 1

    try:
        orchestrator.run()
    except Exception:
        logger.exception("Worker 메인 루프에서 처리되지 않은 예외 발생")
        return 1

    logger.info("Prompton AI Worker 정상 종료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
