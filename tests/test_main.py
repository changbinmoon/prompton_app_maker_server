"""Entrypoint startup and safe configuration logging tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

import main as main_module
from config.settings import ConfigError
from models.entities import Config


class FakeOrchestrator:
    instances: list[FakeOrchestrator] = []

    def __init__(self, config: Config) -> None:
        self.config = config
        self.ran = False
        self.__class__.instances.append(self)

    def run(self) -> None:
        self.ran = True


def test_main_logs_api_base_without_key_or_table(
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configured = replace(
        config,
        prompton_api_base_url="https://status.example.com",
        prompton_status_api_key="sentinel-api-key",
    )
    FakeOrchestrator.instances.clear()
    monkeypatch.setattr(main_module, "load_config", lambda: configured)
    monkeypatch.setattr(main_module, "WorkerOrchestrator", FakeOrchestrator)

    assert main_module.main() == 0

    output = capsys.readouterr().out
    assert "StatusApiBase=https://status.example.com" in output
    assert "sentinel-api-key" not in output
    assert "DYNAMODB_TABLE_NAME" not in output
    assert "Table=" not in output
    assert FakeOrchestrator.instances[-1].ran is True


def test_main_returns_one_and_uses_stderr_for_config_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_config() -> Config:
        raise ConfigError("PROMPTON_API_BASE_URL missing")

    monkeypatch.setattr(main_module, "load_config", fail_config)

    assert main_module.main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "PROMPTON_API_BASE_URL" in captured.err
