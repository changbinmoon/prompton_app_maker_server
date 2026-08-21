"""공용 pytest fixture."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from models.entities import Config


@pytest.fixture
def job_id() -> str:
    """유효한 UUID 형식의 Job ID."""
    return str(uuid.uuid4())


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """테스트용 Config (작업 디렉토리는 tmp_path 사용)."""
    return Config(
        aws_region="us-east-1",
        sqs_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
        s3_bucket_name="test-bucket",
        prompton_api_base_url="https://api.example.com",
        prompton_status_api_key=None,
        work_dir=str(tmp_path / "jobs"),
        visibility_timeout=300,
        cleanup_hours=24,
        log_level="INFO",
        hermes_cli_path="hermes",
        kiro_cli_path="kiro-cli",
        gradle_path="gradle",
    )
