"""ai.refiner 단위 테스트."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ai.refiner import (
    HERMES_MAX_ATTEMPTS,
    MAX_REFINED_PROMPT_BYTES,
    PromptRefiner,
)


class RunSequence:
    """순서대로 CompletedProcess 또는 예외를 반환하는 subprocess 대역."""

    def __init__(self, outcomes: list[subprocess.CompletedProcess[str] | Exception]) -> None:
        self.outcomes = outcomes
        self.commands: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        self.kwargs.append(kwargs)
        outcome = self.outcomes[min(len(self.commands) - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _completed(
    returncode: int = 0,
    stdout: str = "refined prompt",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["hermes"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _raw_requirements(path: Path, secret: str = "private-client-value") -> Path:
    path.write_text(
        json.dumps({"request": "지렁이 게임", "secretMarker": secret}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_refine_success_writes_prompt_and_uses_restricted_oneshot(
    tmp_path: Path, job_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirements = _raw_requirements(tmp_path / "requirements.json")
    output = tmp_path / "refined-prompt.md"
    recorder = RunSequence([_completed(stdout="  Build the requested game.  ")])
    monkeypatch.setattr(subprocess, "run", recorder)

    result = PromptRefiner("/opt/hermes").refine(requirements, output, job_id)

    assert result == output
    assert output.read_text(encoding="utf-8") == "Build the requested game.\n"
    command = recorder.commands[0]
    assert command[:5] == [
        "/opt/hermes",
        "--ignore-rules",
        "--toolsets",
        "context_engine",
        "--oneshot",
    ]
    prompt = command[5]
    assert "CLIENT_JSON_DATA_BEGIN" in prompt
    assert "지렁이 게임" in prompt
    assert "Kotlin and Jetpack Compose" in prompt
    assert "Always use minSdk 26, compileSdk 36, targetSdk 36" in prompt
    assert "Android Gradle Plugin 8.10.1, Gradle 8.11.1, JDK 17" in prompt
    assert "Kotlin 1.9.24" in prompt
    assert "Compose compiler 1.5.14" in prompt
    assert "Compose BOM 2024.06.00" in prompt
    assert "LinearProgressIndicator progress" in prompt
    assert "ExperimentalFoundationApi" in prompt
    assert f"com.prompton.generated.j{job_id.replace('-', '')}" in prompt
    assert recorder.kwargs[0]["cwd"] == str(tmp_path)
    assert recorder.kwargs[0]["check"] is False


def test_refine_retries_with_exponential_delays(
    tmp_path: Path, job_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirements = _raw_requirements(tmp_path / "requirements.json")
    recorder = RunSequence(
        [
            _completed(returncode=1),
            _completed(stdout="  "),
            _completed(stdout="usable prompt"),
        ]
    )
    sleeps: list[float] = []
    monkeypatch.setattr(subprocess, "run", recorder)
    monkeypatch.setattr("ai.refiner.time.sleep", sleeps.append)

    result = PromptRefiner("hermes").refine(requirements, tmp_path / "refined-prompt.md", job_id)

    assert result is not None
    assert len(recorder.commands) == HERMES_MAX_ATTEMPTS
    assert sleeps == [1.0, 2.0]


@pytest.mark.parametrize(
    "outcome",
    [
        _completed(returncode=2, stderr="provider failed"),
        _completed(stdout=""),
        _completed(stdout="x" * (MAX_REFINED_PROMPT_BYTES + 1)),
        _completed(stdout="invalid\x00prompt"),
    ],
    ids=["nonzero", "empty", "oversized", "nul"],
)
def test_refine_exhaustion_returns_none(
    outcome: subprocess.CompletedProcess[str],
    tmp_path: Path,
    job_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requirements = _raw_requirements(tmp_path / "requirements.json")
    recorder = RunSequence([outcome])
    sleeps: list[float] = []
    monkeypatch.setattr(subprocess, "run", recorder)
    monkeypatch.setattr("ai.refiner.time.sleep", sleeps.append)
    output = tmp_path / "refined-prompt.md"

    assert PromptRefiner("hermes").refine(requirements, output, job_id) is None
    assert len(recorder.commands) == HERMES_MAX_ATTEMPTS
    assert sleeps == [1.0, 2.0]
    assert not output.exists()


def test_refine_missing_executable_retries_and_falls_back(
    tmp_path: Path, job_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirements = _raw_requirements(tmp_path / "requirements.json")
    recorder = RunSequence([FileNotFoundError("hermes")])
    sleeps: list[float] = []
    monkeypatch.setattr(subprocess, "run", recorder)
    monkeypatch.setattr("ai.refiner.time.sleep", sleeps.append)

    result = PromptRefiner("missing-hermes").refine(
        requirements, tmp_path / "refined-prompt.md", job_id
    )

    assert result is None
    assert len(recorder.commands) == HERMES_MAX_ATTEMPTS
    assert sleeps == [1.0, 2.0]


def test_refine_write_error_retries_and_falls_back(
    tmp_path: Path, job_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirements = _raw_requirements(tmp_path / "requirements.json")
    recorder = RunSequence([_completed(stdout="valid prompt")])
    sleeps: list[float] = []

    def fail_write(output_path: Path, content: str) -> None:
        raise PermissionError("read-only workdir")

    monkeypatch.setattr(subprocess, "run", recorder)
    monkeypatch.setattr("ai.refiner.time.sleep", sleeps.append)
    monkeypatch.setattr(PromptRefiner, "_write_atomic", staticmethod(fail_write))

    result = PromptRefiner("hermes").refine(requirements, tmp_path / "refined-prompt.md", job_id)

    assert result is None
    assert len(recorder.commands) == HERMES_MAX_ATTEMPTS
    assert sleeps == [1.0, 2.0]


def test_refine_missing_requirements_returns_none_without_subprocess(
    tmp_path: Path, job_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = RunSequence([_completed()])
    monkeypatch.setattr(subprocess, "run", recorder)

    result = PromptRefiner("hermes").refine(
        tmp_path / "missing.json", tmp_path / "refined-prompt.md", job_id
    )

    assert result is None
    assert recorder.commands == []


def test_refine_logs_do_not_echo_untrusted_output(
    tmp_path: Path,
    job_id: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "never-log-this-client-secret"
    requirements = _raw_requirements(tmp_path / "requirements.json", secret=secret)
    recorder = RunSequence([_completed(returncode=1, stderr=secret)])
    monkeypatch.setattr(subprocess, "run", recorder)
    monkeypatch.setattr("ai.refiner.time.sleep", lambda _: None)

    with caplog.at_level(logging.WARNING):
        PromptRefiner("hermes").refine(requirements, tmp_path / "refined-prompt.md", job_id)

    assert secret not in caplog.text
