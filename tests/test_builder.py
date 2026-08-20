"""build.builder 단위 테스트."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from build.builder import GRADLE_BUILD_TASK, GRADLEW_SCRIPT, ApkBuilder
from models.entities import Config
from models.exceptions import BuildError

APK_RELATIVE = Path("app/build/outputs/apk/debug/app-debug.apk")


def _make_project(root: Path, with_wrapper: bool = True) -> Path:
    """테스트용 Android 프로젝트 디렉토리를 만든다."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "settings.gradle").write_text("rootProject.name='demo'", encoding="utf-8")
    if with_wrapper:
        (root / GRADLEW_SCRIPT).write_text("#!/bin/sh\n", encoding="utf-8")
    return root


class GradleStub:
    """subprocess.run 대역 - Gradle 실행을 시뮬레이션한다."""

    def __init__(
        self,
        build_returncode: int = 0,
        wrapper_returncode: int = 0,
        produce_apk: bool = True,
        raises: Exception | None = None,
    ) -> None:
        self.build_returncode = build_returncode
        self.wrapper_returncode = wrapper_returncode
        self.produce_apk = produce_apk
        self.raises = raises
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if self.raises is not None:
            raise self.raises

        self.commands.append(command)
        cwd = Path(kwargs["cwd"])

        if "wrapper" in command:
            if self.wrapper_returncode == 0:
                (cwd / GRADLEW_SCRIPT).write_text("#!/bin/sh\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, self.wrapper_returncode, "", "")

        if self.build_returncode == 0 and self.produce_apk:
            apk = cwd / APK_RELATIVE
            apk.parent.mkdir(parents=True, exist_ok=True)
            apk.write_bytes(b"apk-bytes")

        return subprocess.CompletedProcess(
            command, self.build_returncode, "BUILD", "error output"
        )


def test_build_apk_success(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """빌드 성공 시 APK가 출력 경로로 복사된다 (BR-015)."""
    project = _make_project(tmp_path / "project")
    output = tmp_path / "output" / "app-debug.apk"
    stub = GradleStub()
    monkeypatch.setattr(subprocess, "run", stub)

    result = ApkBuilder(config).build_apk(project, output)

    assert result == output
    assert output.read_bytes() == b"apk-bytes"
    assert GRADLE_BUILD_TASK in stub.commands[0]


def test_build_apk_generates_wrapper_when_missing(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gradlew가 없으면 wrapper를 먼저 생성한다 (FR-008)."""
    project = _make_project(tmp_path / "project", with_wrapper=False)
    stub = GradleStub()
    monkeypatch.setattr(subprocess, "run", stub)

    ApkBuilder(config).build_apk(project, tmp_path / "output" / "app-debug.apk")

    assert "wrapper" in stub.commands[0]
    assert GRADLE_BUILD_TASK in stub.commands[1]


def test_build_apk_wrapper_failure(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """wrapper 생성 실패 시 BuildError가 발생한다 (BR-008)."""
    project = _make_project(tmp_path / "project", with_wrapper=False)
    monkeypatch.setattr(subprocess, "run", GradleStub(wrapper_returncode=1))

    with pytest.raises(BuildError):
        ApkBuilder(config).build_apk(project, tmp_path / "output" / "app-debug.apk")


def test_build_apk_build_failure(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """빌드 실패 시 BuildError가 발생한다 (BR-008)."""
    project = _make_project(tmp_path / "project")
    monkeypatch.setattr(subprocess, "run", GradleStub(build_returncode=1))

    with pytest.raises(BuildError):
        ApkBuilder(config).build_apk(project, tmp_path / "output" / "app-debug.apk")


def test_build_apk_missing_artifact(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """빌드는 성공했지만 APK가 없으면 BuildError가 발생한다."""
    project = _make_project(tmp_path / "project")
    monkeypatch.setattr(subprocess, "run", GradleStub(produce_apk=False))

    with pytest.raises(BuildError):
        ApkBuilder(config).build_apk(project, tmp_path / "output" / "app-debug.apk")


def test_build_apk_missing_project(config: Config, tmp_path: Path) -> None:
    """프로젝트 디렉토리가 없으면 BuildError가 발생한다."""
    with pytest.raises(BuildError):
        ApkBuilder(config).build_apk(
            tmp_path / "nope", tmp_path / "output" / "app-debug.apk"
        )


def test_build_apk_gradle_not_installed(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gradle 실행 파일이 없으면 BuildError로 변환된다."""
    project = _make_project(tmp_path / "project")
    monkeypatch.setattr(
        subprocess, "run", GradleStub(raises=FileNotFoundError("gradlew"))
    )

    with pytest.raises(BuildError):
        ApkBuilder(config).build_apk(project, tmp_path / "output" / "app-debug.apk")
