"""utils.cleanup 및 utils.log_sanitizer 단위 테스트."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from utils.cleanup import cleanup_old_workdirs, prepare_workdir
from utils.log_sanitizer import REDACTED, sanitize_log


def _age_directory(path: Path, hours: int) -> None:
    """디렉토리의 mtime을 과거로 설정한다."""
    past = (datetime.now() - timedelta(hours=hours)).timestamp()
    os.utime(path, (past, past))


# ---------------------------------------------------------------- cleanup


def test_prepare_workdir_creates_directory(tmp_path: Path) -> None:
    """작업 디렉토리를 생성한다 (BR-017)."""
    target = tmp_path / "jobs" / "job-1"

    result = prepare_workdir(target)

    assert result == target
    assert target.is_dir()


def test_prepare_workdir_recreates_existing(tmp_path: Path) -> None:
    """이미 존재하면 삭제 후 재생성한다 (BR-017, 멱등성)."""
    target = tmp_path / "jobs" / "job-1"
    target.mkdir(parents=True)
    leftover = target / "stale.txt"
    leftover.write_text("old", encoding="utf-8")

    prepare_workdir(target)

    assert target.is_dir()
    assert not leftover.exists()


def test_cleanup_removes_old_dirs(tmp_path: Path) -> None:
    """24시간을 초과한 디렉토리를 삭제한다 (BR-018)."""
    root = tmp_path / "jobs"
    old = root / "old-job"
    fresh = root / "fresh-job"
    old.mkdir(parents=True)
    fresh.mkdir(parents=True)
    _age_directory(old, hours=25)

    removed = cleanup_old_workdirs(str(root), max_age_hours=24)

    assert removed == 1
    assert not old.exists()
    assert fresh.exists()


def test_cleanup_keeps_recent_dirs(tmp_path: Path) -> None:
    """보존 기간 내 디렉토리는 유지된다 (BR-018)."""
    root = tmp_path / "jobs"
    recent = root / "recent-job"
    recent.mkdir(parents=True)
    _age_directory(recent, hours=23)

    removed = cleanup_old_workdirs(str(root), max_age_hours=24)

    assert removed == 0
    assert recent.exists()


def test_cleanup_ignores_missing_root(tmp_path: Path) -> None:
    """루트가 없으면 0을 반환하고 예외를 던지지 않는다."""
    assert cleanup_old_workdirs(str(tmp_path / "nope"), max_age_hours=24) == 0


def test_cleanup_ignores_files(tmp_path: Path) -> None:
    """루트 하위 파일은 삭제 대상이 아니다."""
    root = tmp_path / "jobs"
    root.mkdir()
    stray = root / "note.txt"
    stray.write_text("keep", encoding="utf-8")
    _age_directory(stray, hours=100)

    removed = cleanup_old_workdirs(str(root), max_age_hours=24)

    assert removed == 0
    assert stray.exists()


def test_cleanup_removes_nested_content(tmp_path: Path) -> None:
    """하위 내용이 있어도 재귀적으로 삭제한다."""
    root = tmp_path / "jobs"
    old = root / "old-job"
    (old / "project" / "app").mkdir(parents=True)
    (old / "project" / "app" / "Main.kt").write_text("fun main() {}", encoding="utf-8")
    time.sleep(0.01)
    _age_directory(old, hours=48)

    removed = cleanup_old_workdirs(str(root), max_age_hours=24)

    assert removed == 1
    assert not old.exists()


# --------------------------------------------------------- log_sanitizer


def test_sanitize_masks_aws_access_key() -> None:
    """AWS Access Key ID를 마스킹한다 (BR-013)."""
    result = sanitize_log("credential AKIAIOSFODNN7EXAMPLE used")

    assert "AKIAIOSFODNN7EXAMPLE" not in result
    assert REDACTED in result


def test_sanitize_masks_temporary_access_key() -> None:
    """ASIA 접두어 임시 키도 마스킹한다."""
    result = sanitize_log("ASIAY34FZKBOKMUTVV7A")

    assert "ASIAY34FZKBOKMUTVV7A" not in result


def test_sanitize_masks_session_token_param() -> None:
    """URL 내 Session Token을 마스킹한다 (BR-013)."""
    result = sanitize_log("url?X-Amz-Security-Token=abc.def.ghi&other=1")

    assert "abc.def.ghi" not in result
    assert "other=1" in result


def test_sanitize_masks_presigned_url() -> None:
    """Presigned URL을 마스킹한다 (BR-013)."""
    result = sanitize_log(
        "download https://bucket.s3.amazonaws.com/k?X-Amz-Signature=deadbeef now"
    )

    assert "X-Amz-Signature" not in result
    assert "deadbeef" not in result
    assert "download" in result


def test_sanitize_masks_secret_key_assignment() -> None:
    """key=value 형태의 자격증명 값을 마스킹하고 키 이름은 남긴다."""
    result = sanitize_log("aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

    assert "wJalrXUtnFEMI" not in result
    assert "aws_secret_access_key" in result
    assert REDACTED in result


def test_sanitize_masks_bearer_token() -> None:
    """Bearer 토큰을 마스킹한다."""
    result = sanitize_log("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9abc")

    assert "eyJhbGciOiJIUzI1NiJ9abc" not in result


def test_sanitize_masks_standalone_secret_key() -> None:
    """독립 40자 대소문자 혼재 토큰을 마스킹한다."""
    secret = "wJalrXUtnFEMIaK7MDENGabPxRfiCYEXAMPLEKEY"
    assert len(secret) == 40

    result = sanitize_log(f"key {secret} end")

    assert secret not in result
    assert REDACTED in result


def test_sanitize_preserves_git_sha() -> None:
    """40자 hex git SHA는 마스킹하지 않는다 (로그 유용성 유지)."""
    sha = "0f2c1a9b8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a"
    assert len(sha) == 40

    result = sanitize_log(f"commit {sha}")

    assert sha in result


def test_sanitize_preserves_normal_message() -> None:
    """일반 메시지는 변경하지 않는다."""
    message = "[worker] 작업을 시작했습니다."

    assert sanitize_log(message) == message


def test_sanitize_handles_empty_and_non_string() -> None:
    """빈 문자열과 비문자열 입력을 안전하게 처리한다."""
    assert sanitize_log("") == ""
    assert sanitize_log(None) == "None"  # type: ignore[arg-type]
