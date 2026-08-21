"""작업 디렉토리 관리 및 정리.

설계 근거: active business-rules.md BR-024/025, nfr-design-patterns.md PAT-PERF-04
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def prepare_workdir(base_path: Path) -> Path:
    """Job 작업 디렉토리를 깨끗한 상태로 준비한다 (BR-017).

    이미 존재하면 삭제 후 재생성하여 SQS 재전달의 전체 재처리에 이전 잔여물이 섞이지 않게 한다
    (PAT-RES-05: Queue-managed recovery and full reprocessing).

    Args:
        base_path: 생성할 작업 디렉토리 경로 (예: /data/jobs/{jobId})

    Returns:
        생성된 디렉토리 경로

    Raises:
        OSError: 디렉토리 삭제/생성 실패
    """
    if base_path.exists():
        logger.info("기존 작업 디렉토리 삭제 후 재생성: %s", base_path)
        shutil.rmtree(base_path)

    base_path.mkdir(parents=True, exist_ok=True)
    # 소유자만 접근 가능 (logical-components.md: 권한 700)
    try:
        base_path.chmod(0o700)
    except OSError:
        logger.debug("작업 디렉토리 권한 설정 생략: %s", base_path, exc_info=True)

    return base_path


def cleanup_old_workdirs(work_dir: str, max_age_hours: int = 24) -> int:
    """보존 기간이 지난 작업 디렉토리를 삭제한다 (BR-018).

    정리 실패는 Worker 동작에 영향을 주지 않도록 예외를 흡수한다
    (NFR Pattern 14: Self-Healing Storage).

    Args:
        work_dir: 작업 디렉토리 루트 (예: /data/jobs)
        max_age_hours: 보존 시간(시간). 기본 24시간

    Returns:
        삭제된 디렉토리 개수
    """
    root = Path(work_dir)
    if not root.is_dir():
        logger.debug("작업 디렉토리 루트가 없어 정리를 건너뜁니다: %s", work_dir)
        return 0

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    removed = 0

    try:
        children = list(root.iterdir())
    except OSError:
        logger.warning("작업 디렉토리 목록 조회 실패: %s", work_dir, exc_info=True)
        return 0

    for job_dir in children:
        if not job_dir.is_dir():
            continue

        try:
            mtime = datetime.fromtimestamp(job_dir.stat().st_mtime)
        except OSError:
            logger.warning("디렉토리 정보 조회 실패 - 건너뜁니다: %s", job_dir, exc_info=True)
            continue

        if mtime >= cutoff:
            continue

        shutil.rmtree(job_dir, ignore_errors=True)
        if job_dir.exists():
            logger.warning("작업 디렉토리 삭제 실패: %s", job_dir)
            continue

        removed += 1
        logger.info("오래된 작업 디렉토리 삭제 (mtime=%s): %s", mtime.isoformat(), job_dir)

    if removed:
        logger.info("작업 디렉토리 정리 완료 - %d개 삭제", removed)

    return removed
