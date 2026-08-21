"""config.settings 단위 테스트."""

from __future__ import annotations

import pytest

from config.settings import (
    DEFAULT_AWS_REGION,
    DEFAULT_CLEANUP_HOURS,
    DEFAULT_HERMES_CLI_PATH,
    DEFAULT_VISIBILITY_TIMEOUT,
    DEFAULT_WORK_DIR,
    ConfigError,
    build_boto_config,
    load_config,
)

REQUIRED_ENV = {
    "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789012/q",
    "S3_BUCKET_NAME": "prompton-bucket",
    "PROMPTON_API_BASE_URL": "https://api.example.com",
}

OPTIONAL_ENV_KEYS = (
    "PROMPTON_STATUS_API_KEY",
    "AWS_REGION",
    "WORK_DIR",
    "VISIBILITY_TIMEOUT",
    "CLEANUP_HOURS",
    "LOG_LEVEL",
    "HERMES_CLI_PATH",
    "KIRO_CLI_PATH",
    "GRADLE_PATH",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """각 테스트 시작 시 관련 환경 변수를 모두 제거한다."""
    for key in (*REQUIRED_ENV, *OPTIONAL_ENV_KEYS):
        monkeypatch.delenv(key, raising=False)


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_load_config_applies_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """필수 변수만 있으면 나머지는 기본값이 적용된다."""
    _set_required(monkeypatch)

    config = load_config()

    assert config.sqs_queue_url == REQUIRED_ENV["SQS_QUEUE_URL"]
    assert config.s3_bucket_name == REQUIRED_ENV["S3_BUCKET_NAME"]
    assert config.prompton_api_base_url == REQUIRED_ENV["PROMPTON_API_BASE_URL"]
    assert config.prompton_status_api_key is None
    assert config.aws_region == DEFAULT_AWS_REGION
    assert config.work_dir == DEFAULT_WORK_DIR
    assert config.visibility_timeout == DEFAULT_VISIBILITY_TIMEOUT
    assert config.cleanup_hours == DEFAULT_CLEANUP_HOURS
    assert config.log_level == "INFO"
    assert config.hermes_cli_path == DEFAULT_HERMES_CLI_PATH


def test_load_config_reads_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """선택 환경 변수를 지정하면 그 값이 반영된다."""
    _set_required(monkeypatch)
    monkeypatch.setenv("PROMPTON_API_BASE_URL", "https://api.example.com///")
    monkeypatch.setenv("PROMPTON_STATUS_API_KEY", "  test-secret-key  ")
    monkeypatch.setenv("AWS_REGION", "ap-northeast-2")
    monkeypatch.setenv("WORK_DIR", "/mnt/work")
    monkeypatch.setenv("VISIBILITY_TIMEOUT", "600")
    monkeypatch.setenv("CLEANUP_HOURS", "48")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("HERMES_CLI_PATH", "/usr/local/bin/hermes")
    monkeypatch.setenv("KIRO_CLI_PATH", "/usr/local/bin/kiro-cli")
    monkeypatch.setenv("GRADLE_PATH", "/opt/gradle/bin/gradle")

    config = load_config()

    assert config.aws_region == "ap-northeast-2"
    assert config.prompton_api_base_url == "https://api.example.com"
    assert config.prompton_status_api_key == "test-secret-key"
    assert config.work_dir == "/mnt/work"
    assert config.visibility_timeout == 600
    assert config.cleanup_hours == 48
    assert config.log_level == "DEBUG"
    assert config.hermes_cli_path == "/usr/local/bin/hermes"
    assert config.kiro_cli_path == "/usr/local/bin/kiro-cli"
    assert config.gradle_path == "/opt/gradle/bin/gradle"


@pytest.mark.parametrize("missing", list(REQUIRED_ENV))
def test_load_config_missing_required(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """필수 환경 변수가 없으면 ConfigError가 발생한다."""
    _set_required(monkeypatch)
    monkeypatch.delenv(missing, raising=False)

    with pytest.raises(ConfigError) as exc_info:
        load_config()

    assert missing in str(exc_info.value)


@pytest.mark.parametrize("name", list(REQUIRED_ENV))
def test_load_config_rejects_whitespace_required(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """필수 값이 공백뿐이면 기동 전에 거부한다."""
    _set_required(monkeypatch)
    monkeypatch.setenv(name, "   ")

    with pytest.raises(ConfigError) as exc_info:
        load_config()

    assert name in str(exc_info.value)


@pytest.mark.parametrize("value", ["", "   ", "\t"])
def test_load_config_normalizes_blank_status_api_key(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """선택 API key가 비어 있으면 None으로 정규화한다."""
    _set_required(monkeypatch)
    monkeypatch.setenv("PROMPTON_STATUS_API_KEY", value)

    assert load_config().prompton_status_api_key is None


def test_config_repr_excludes_status_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config repr에 API key 값이 노출되지 않는다."""
    _set_required(monkeypatch)
    monkeypatch.setenv("PROMPTON_STATUS_API_KEY", "sentinel-api-key")

    config = load_config()

    assert "sentinel-api-key" not in repr(config)
    assert not hasattr(config, "dynamodb_table_name")


def test_load_config_invalid_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """허용되지 않은 LOG_LEVEL은 ConfigError를 발생시킨다."""
    _set_required(monkeypatch)
    monkeypatch.setenv("LOG_LEVEL", "VERBOSE")

    with pytest.raises(ConfigError):
        load_config()


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_load_config_invalid_visibility_timeout(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """VISIBILITY_TIMEOUT이 양의 정수가 아니면 ConfigError가 발생한다."""
    _set_required(monkeypatch)
    monkeypatch.setenv("VISIBILITY_TIMEOUT", value)

    with pytest.raises(ConfigError):
        load_config()


def test_load_config_empty_work_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """WORK_DIR이 공백이면 ConfigError가 발생한다."""
    _set_required(monkeypatch)
    monkeypatch.setenv("WORK_DIR", "   ")

    with pytest.raises(ConfigError):
        load_config()


def test_build_boto_config_sets_adaptive_retry() -> None:
    """boto3 재시도 설정이 adaptive/3회로 구성된다 (NFR Pattern 1)."""
    boto_config = build_boto_config()

    assert boto_config.retries is not None  # type: ignore[attr-defined]
    assert boto_config.retries["max_attempts"] == 3  # type: ignore[attr-defined]
    assert boto_config.retries["mode"] == "adaptive"  # type: ignore[attr-defined]
