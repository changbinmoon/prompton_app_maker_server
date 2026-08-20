"""ai.generator 단위 테스트."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ai.generator import AIGenerator
from models.entities import Config
from models.exceptions import AIGenerationError


def _write_requirements(path: Path) -> Path:
    """테스트용 requirements.json을 생성한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"appName": "demo"}), encoding="utf-8")
    return path


class RunRecorder:
    """subprocess.run 대역."""

    def __init__(
        self,
        returncode: int = 0,
        create_marker: str | None = "settings.gradle",
        raises: Exception | None = None,
    ) -> None:
        self.returncode = returncode
        self.create_marker = create_marker
        self.raises = raises
        self.commands: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if self.raises is not None:
            raise self.raises

        self.commands.append(command)
        self.kwargs.append(kwargs)

        if self.create_marker and self.returncode == 0:
            output_dir = Path(kwargs["cwd"])
            (output_dir / self.create_marker).write_text("// generated", encoding="utf-8")

        return subprocess.CompletedProcess(
            args=command, returncode=self.returncode, stdout="generated", stderr=""
        )


def test_generate_code_success(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """정상 생성 시 출력 디렉토리를 반환한다."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    assets = tmp_path / "assets"
    assets.mkdir()
    output = tmp_path / "project"

    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = AIGenerator(config).generate_code(requirements, assets, output)

    assert result == output
    assert recorder.commands[0][0] == config.kiro_cli_path
    assert str(requirements) in recorder.commands[0]
    assert str(output) in recorder.commands[0]


def test_generate_code_includes_assets_arg_when_present(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """에셋이 있으면 --assets 인자가 추가된다."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "0-logo.png").write_bytes(b"png")
    output = tmp_path / "project"

    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    AIGenerator(config).generate_code(requirements, assets, output)

    assert "--assets" in recorder.commands[0]
    assert str(assets) in recorder.commands[0]


def test_generate_code_omits_assets_arg_when_empty(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """에셋이 없으면 --assets 인자를 넣지 않는다 (BR-014)."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    assets = tmp_path / "assets"
    assets.mkdir()
    output = tmp_path / "project"

    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    AIGenerator(config).generate_code(requirements, assets, output)

    assert "--assets" not in recorder.commands[0]


def test_generate_code_missing_requirements(config: Config, tmp_path: Path) -> None:
    """requirements.json이 없으면 AIGenerationError가 발생한다."""
    with pytest.raises(AIGenerationError):
        AIGenerator(config).generate_code(
            tmp_path / "missing.json", tmp_path / "assets", tmp_path / "project"
        )


def test_generate_code_nonzero_exit(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """exit code != 0이면 AIGenerationError가 발생한다 (BR-008)."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    monkeypatch.setattr(subprocess, "run", RunRecorder(returncode=1))

    with pytest.raises(AIGenerationError):
        AIGenerator(config).generate_code(
            requirements, tmp_path / "assets", tmp_path / "project"
        )


def test_generate_code_cli_not_found(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI 실행 파일이 없으면 AIGenerationError로 변환된다 (BR-008)."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    monkeypatch.setattr(
        subprocess, "run", RunRecorder(raises=FileNotFoundError("kiro-cli"))
    )

    with pytest.raises(AIGenerationError):
        AIGenerator(config).generate_code(
            requirements, tmp_path / "assets", tmp_path / "project"
        )


def test_generate_code_rejects_non_gradle_output(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gradle 마커가 없으면 생성 실패로 처리한다."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    monkeypatch.setattr(subprocess, "run", RunRecorder(create_marker=None))

    with pytest.raises(AIGenerationError):
        AIGenerator(config).generate_code(
            requirements, tmp_path / "assets", tmp_path / "project"
        )


def test_generate_code_no_timeout_passed(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """타임아웃을 설정하지 않는다 (완료까지 대기)."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    AIGenerator(config).generate_code(requirements, tmp_path / "assets", tmp_path / "project")

    assert "timeout" not in recorder.kwargs[0]
