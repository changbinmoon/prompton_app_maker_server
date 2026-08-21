"""환경 변수 기반 설정 로드 및 검증.

설계 근거: domain-entities.md 섹션 2, tech-stack-decisions.md (환경 변수 표)
보안 규칙: NFR Design Pattern 9 (Credential-Free Authentication)
    - AWS 자격증명은 환경 변수로 받지 않는다. EC2 Instance Profile을 사용한다.
"""

from __future__ import annotations

import os
from typing import Literal

from botocore.config import Config as BotoConfig

from models.entities import Config

#: boto3 재시도 설정 (NFR Design Pattern 1: Automatic Retry with Exponential Backoff)
#: 모든 AWS 클라이언트가 공유한다.
BOTO_MAX_ATTEMPTS = 3
BOTO_RETRY_MODE: Literal["legacy", "standard", "adaptive"] = "adaptive"

#: 필수 환경 변수 목록 - 누락 시 프로세스를 시작하지 않는다
REQUIRED_ENV_VARS = (
    "SQS_QUEUE_URL",
    "S3_BUCKET_NAME",
    "PROMPTON_API_BASE_URL",
)

#: 기본값
DEFAULT_AWS_REGION = "us-east-1"
DEFAULT_WORK_DIR = "/data/jobs"
DEFAULT_VISIBILITY_TIMEOUT = 300
DEFAULT_CLEANUP_HOURS = 24
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_HERMES_CLI_PATH = "hermes"
DEFAULT_KIRO_CLI_PATH = "kiro-cli"
DEFAULT_GRADLE_PATH = "gradle"

VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class ConfigError(Exception):
    """환경 변수 설정 오류.

    이 예외는 프로세스 시작 시점에만 발생하며, 발생 시 Worker를 시작하지 않는다.
    """


def load_config() -> Config:
    """환경 변수에서 설정을 로드하고 검증한다.

    Returns:
        검증된 Config 인스턴스

    Raises:
        ConfigError: 필수 환경 변수 누락 또는 값 형식 오류
    """
    missing = [
        name for name in REQUIRED_ENV_VARS if not os.environ.get(name, "").strip()
    ]
    if missing:
        raise ConfigError(f"필수 환경 변수가 설정되지 않았습니다: {', '.join(missing)}")

    log_level = os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    if log_level not in VALID_LOG_LEVELS:
        raise ConfigError(
            f"LOG_LEVEL 값이 올바르지 않습니다: {log_level} "
            f"(허용: {', '.join(sorted(VALID_LOG_LEVELS))})"
        )

    visibility_timeout = _read_positive_int(
        "VISIBILITY_TIMEOUT", DEFAULT_VISIBILITY_TIMEOUT
    )
    cleanup_hours = _read_positive_int("CLEANUP_HOURS", DEFAULT_CLEANUP_HOURS)

    work_dir = os.environ.get("WORK_DIR", DEFAULT_WORK_DIR).strip()
    if not work_dir:
        raise ConfigError("WORK_DIR 값이 비어 있습니다")

    prompton_api_base_url = os.environ["PROMPTON_API_BASE_URL"].strip().rstrip("/")
    if not prompton_api_base_url:
        raise ConfigError("PROMPTON_API_BASE_URL 값이 비어 있습니다")

    raw_status_api_key = os.environ.get("PROMPTON_STATUS_API_KEY", "").strip()
    prompton_status_api_key = raw_status_api_key or None

    return Config(
        aws_region=os.environ.get("AWS_REGION", DEFAULT_AWS_REGION),
        sqs_queue_url=os.environ["SQS_QUEUE_URL"],
        s3_bucket_name=os.environ["S3_BUCKET_NAME"],
        prompton_api_base_url=prompton_api_base_url,
        prompton_status_api_key=prompton_status_api_key,
        work_dir=work_dir,
        visibility_timeout=visibility_timeout,
        cleanup_hours=cleanup_hours,
        log_level=log_level,
        hermes_cli_path=os.environ.get("HERMES_CLI_PATH", DEFAULT_HERMES_CLI_PATH),
        kiro_cli_path=os.environ.get("KIRO_CLI_PATH", DEFAULT_KIRO_CLI_PATH),
        gradle_path=os.environ.get("GRADLE_PATH", DEFAULT_GRADLE_PATH),
    )


def build_boto_config() -> BotoConfig:
    """모든 AWS 클라이언트가 공유하는 botocore 설정을 생성한다.

    NFR Design Pattern 1 (Automatic Retry with Exponential Backoff):
        max_attempts=3, mode=adaptive

    Returns:
        재시도 정책이 적용된 botocore Config
    """
    return BotoConfig(
        retries={
            "max_attempts": BOTO_MAX_ATTEMPTS,
            "mode": BOTO_RETRY_MODE,
        }
    )


def _read_positive_int(name: str, default: int) -> int:
    """환경 변수를 양의 정수로 읽는다.

    Args:
        name: 환경 변수 이름
        default: 미설정 시 사용할 기본값

    Returns:
        파싱된 양의 정수

    Raises:
        ConfigError: 정수 변환 실패 또는 0 이하인 경우
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 값이 정수가 아닙니다: {raw!r}") from exc

    if value <= 0:
        raise ConfigError(f"{name} 값은 0보다 커야 합니다: {value}")

    return value
