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

JOB_ID = "12345678-1234-5678-1234-567812345678"


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
    """정상 생성 시 실제 kiro-cli chat 규격으로 호출하고 출력 디렉토리를 반환한다."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    assets = tmp_path / "assets"
    assets.mkdir()
    output = tmp_path / "project"

    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = AIGenerator(config).generate_code(requirements, assets, output, job_id=JOB_ID)

    assert result == output
    command = recorder.commands[0]
    assert command[0] == config.kiro_cli_path
    assert command[1] == "chat"
    assert "--no-interactive" in command
    assert command[command.index("--model") + 1] == "claude-opus-5"
    assert "--trust-tools=fs_read,fs_write" in command
    prompt = command[-1]
    assert str(requirements) in prompt
    assert str(assets) in prompt
    assert str(output) in prompt
    assert "No Hermes-refined prompt is available" in prompt
    assert "Kotlin and Jetpack Compose" in prompt
    assert "Always use minSdk 26, compileSdk 36, targetSdk 36" in prompt
    assert "Android SDK Build Tools 36.0.0" in prompt
    assert "Android Gradle Plugin 8.10.1, Gradle 8.11.1, JDK 17" in prompt
    assert "Kotlin 1.9.24" in prompt
    assert "Compose compiler 1.5.14" in prompt
    assert "Compose BOM 2024.06.00" in prompt
    assert "LinearProgressIndicator progress" in prompt
    assert "ExperimentalFoundationApi" in prompt
    assert "Do not create gradlew, gradlew.bat, or gradle-wrapper.jar" in prompt
    assert "services.gradle.org" in prompt
    assert "the Worker creates trusted Wrapper scripts and the binary JAR" in prompt
    assert "com.prompton.generated.j12345678123456781234567812345678" in prompt
    assert recorder.kwargs[0]["cwd"] == str(output)


def test_generate_code_reads_refined_prompt_when_present(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hermes 출력이 있으면 Kiro prompt에 refined-prompt.md 경로를 포함한다."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    refined = tmp_path / "refined-prompt.md"
    refined.write_text("Build a snake game", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    output = tmp_path / "project"
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    AIGenerator(config).generate_code(
        requirements,
        assets,
        output,
        job_id=JOB_ID,
        refined_prompt_path=refined,
    )

    prompt = recorder.commands[0][-1]
    assert str(refined) in prompt
    assert "First read and follow the refined implementation prompt" in prompt
    assert str(requirements) in prompt
    assert "Kotlin and Jetpack Compose" in prompt


def test_generate_code_includes_assets_path_when_present(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """에셋이 있으면 단일 chat 프롬프트에 에셋 경로가 포함된다."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "0-logo.png").write_bytes(b"png")
    output = tmp_path / "project"

    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    AIGenerator(config).generate_code(requirements, assets, output, job_id=JOB_ID)

    assert str(assets) in recorder.commands[0][-1]
    assert "--assets" not in recorder.commands[0]


def test_generate_code_omits_unsupported_assets_option_when_empty(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """에셋이 없어도 실제 CLI에 없는 --assets 옵션을 추가하지 않는다 (BR-014)."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    assets = tmp_path / "assets"
    assets.mkdir()
    output = tmp_path / "project"

    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    AIGenerator(config).generate_code(requirements, assets, output, job_id=JOB_ID)

    assert "--assets" not in recorder.commands[0]
    assert str(assets) in recorder.commands[0][-1]


def test_generate_code_missing_requirements(config: Config, tmp_path: Path) -> None:
    """requirements.json이 없으면 AIGenerationError가 발생한다."""
    with pytest.raises(AIGenerationError):
        AIGenerator(config).generate_code(
            tmp_path / "missing.json", tmp_path / "assets", tmp_path / "project", job_id=JOB_ID
        )


def test_generate_code_nonzero_exit(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """exit code != 0이면 AIGenerationError가 발생한다 (BR-008)."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    monkeypatch.setattr(subprocess, "run", RunRecorder(returncode=1))

    with pytest.raises(AIGenerationError):
        AIGenerator(config).generate_code(
            requirements, tmp_path / "assets", tmp_path / "project", job_id=JOB_ID
        )


def test_generate_code_cli_not_found(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI 실행 파일이 없으면 AIGenerationError로 변환된다 (BR-008)."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    monkeypatch.setattr(subprocess, "run", RunRecorder(raises=FileNotFoundError("kiro-cli")))

    with pytest.raises(AIGenerationError):
        AIGenerator(config).generate_code(
            requirements, tmp_path / "assets", tmp_path / "project", job_id=JOB_ID
        )


def test_generate_code_rejects_non_gradle_output(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gradle 마커가 없으면 생성 실패로 처리한다."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    monkeypatch.setattr(subprocess, "run", RunRecorder(create_marker=None))

    with pytest.raises(AIGenerationError):
        AIGenerator(config).generate_code(
            requirements, tmp_path / "assets", tmp_path / "project", job_id=JOB_ID
        )


def test_generate_code_no_timeout_passed(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """타임아웃을 설정하지 않는다 (완료까지 대기)."""
    requirements = _write_requirements(tmp_path / "requirements.json")
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    AIGenerator(config).generate_code(
        requirements, tmp_path / "assets", tmp_path / "project", job_id=JOB_ID
    )

    assert "timeout" not in recorder.kwargs[0]
