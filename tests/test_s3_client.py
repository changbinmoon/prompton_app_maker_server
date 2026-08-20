"""s3.client 단위 테스트 (moto 사용)."""

from __future__ import annotations

import json
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from models.entities import Config
from models.exceptions import (
    ArtifactUploadError,
    InvalidRequirementsError,
    RequirementsReadError,
)
from s3.client import MAX_ASSET_COUNT, S3Client

BUCKET = "test-bucket"


@pytest.fixture
def s3_setup(config: Config):  # type: ignore[no-untyped-def]
    """moto S3 버킷과 S3Client를 준비한다."""
    with mock_aws():
        raw = boto3.client("s3", region_name="us-east-1")
        raw.create_bucket(Bucket=BUCKET)
        yield S3Client(config, client=raw), raw


def test_download_requirements_parses_json(s3_setup, tmp_path: Path, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """requirements.json을 다운로드하고 파싱한다."""
    client, raw = s3_setup
    key = f"jobs/{job_id}/requirements/requirements.json"
    raw.put_object(Bucket=BUCKET, Key=key, Body=json.dumps({"appName": "demo"}).encode())

    dest = tmp_path / "requirements.json"
    result = client.download_requirements(BUCKET, key, dest)

    assert result == {"appName": "demo"}
    assert dest.is_file()


def test_download_requirements_missing_object(s3_setup, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """객체가 없으면 RequirementsReadError가 발생한다 (BR-008)."""
    client, _ = s3_setup

    with pytest.raises(RequirementsReadError):
        client.download_requirements(BUCKET, "jobs/none/requirements.json", tmp_path / "r.json")


def test_download_requirements_invalid_json(s3_setup, tmp_path: Path, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """JSON 파싱 실패 시 InvalidRequirementsError가 발생한다 (BR-020)."""
    client, raw = s3_setup
    key = f"jobs/{job_id}/requirements/requirements.json"
    raw.put_object(Bucket=BUCKET, Key=key, Body=b"{not json")

    with pytest.raises(InvalidRequirementsError):
        client.download_requirements(BUCKET, key, tmp_path / "r.json")


def test_download_requirements_non_object_json(s3_setup, tmp_path: Path, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """최상위가 객체가 아니면 InvalidRequirementsError가 발생한다 (BR-020)."""
    client, raw = s3_setup
    key = f"jobs/{job_id}/requirements/requirements.json"
    raw.put_object(Bucket=BUCKET, Key=key, Body=b"[1, 2, 3]")

    with pytest.raises(InvalidRequirementsError):
        client.download_requirements(BUCKET, key, tmp_path / "r.json")


def test_download_assets_returns_empty_when_none(s3_setup, tmp_path: Path, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """에셋이 없어도 정상 처리된다 (BR-014)."""
    client, _ = s3_setup

    result = client.download_assets(BUCKET, f"jobs/{job_id}/assets/", tmp_path / "assets")

    assert result == []


def test_download_assets_filters_unsupported_types(s3_setup, tmp_path: Path, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """png/jpeg만 다운로드한다 (BR-014)."""
    client, raw = s3_setup
    prefix = f"jobs/{job_id}/assets/"
    raw.put_object(Bucket=BUCKET, Key=f"{prefix}0-logo.png", Body=b"png")
    raw.put_object(Bucket=BUCKET, Key=f"{prefix}1-hero.jpg", Body=b"jpg")
    raw.put_object(Bucket=BUCKET, Key=f"{prefix}2-notes.txt", Body=b"txt")

    result = client.download_assets(BUCKET, prefix, tmp_path / "assets")

    names = sorted(path.name for path in result)
    assert names == ["0-logo.png", "1-hero.jpg"]


def test_download_assets_caps_at_max_count(s3_setup, tmp_path: Path, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """에셋은 최대 5개까지만 처리한다 (BR-014)."""
    client, raw = s3_setup
    prefix = f"jobs/{job_id}/assets/"
    for index in range(MAX_ASSET_COUNT + 3):
        raw.put_object(Bucket=BUCKET, Key=f"{prefix}{index}-img.png", Body=b"png")

    result = client.download_assets(BUCKET, prefix, tmp_path / "assets")

    assert len(result) == MAX_ASSET_COUNT


def test_upload_source_creates_zip(s3_setup, tmp_path: Path, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """프로젝트 디렉토리를 zip으로 업로드한다 (BR-016)."""
    client, raw = s3_setup
    project = tmp_path / "project"
    (project / "app").mkdir(parents=True)
    (project / "settings.gradle").write_text("rootProject.name='demo'", encoding="utf-8")

    key = f"jobs/{job_id}/source/project.zip"
    result = client.upload_source(project, key)

    assert result == key
    head = raw.head_object(Bucket=BUCKET, Key=key)
    assert head["ContentLength"] > 0


def test_upload_source_missing_dir_returns_empty(s3_setup, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """소스 디렉토리가 없으면 빈 문자열을 반환하고 예외를 던지지 않는다."""
    client, _ = s3_setup

    assert client.upload_source(tmp_path / "nope", "jobs/x/source/project.zip") == ""


def test_upload_artifact_verifies_upload(s3_setup, tmp_path: Path, job_id: str) -> None:  # type: ignore[no-untyped-def]
    """APK 업로드 후 크기를 검증하고 키를 반환한다 (BR-006, BR-015)."""
    client, raw = s3_setup
    apk = tmp_path / "app-debug.apk"
    apk.write_bytes(b"apk-content")

    key = f"jobs/{job_id}/artifact/app-debug.apk"
    result = client.upload_artifact(apk, key)

    assert result == key
    head = raw.head_object(Bucket=BUCKET, Key=key)
    assert head["ContentLength"] == len(b"apk-content")


def test_upload_artifact_missing_file(s3_setup, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """APK 파일이 없으면 ArtifactUploadError가 발생한다 (BR-008)."""
    client, _ = s3_setup

    with pytest.raises(ArtifactUploadError):
        client.upload_artifact(tmp_path / "missing.apk", "jobs/x/artifact/app-debug.apk")
