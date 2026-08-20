"""Canonical requirements.json contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from models.exceptions import InvalidRequirementsError
from models.requirements import REQUIREMENTS_SCHEMA_PATH, validate_requirements

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "contracts" / "fixtures"
VALID_FIXTURES = sorted((FIXTURE_ROOT / "valid").glob("*.json"))
INVALID_FIXTURES = sorted((FIXTURE_ROOT / "invalid").glob("*.json"))


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_requirements_schema_is_valid_draft_2020_12() -> None:
    """The canonical schema itself conforms to Draft 2020-12."""
    schema = json.loads(REQUIREMENTS_SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("/requirements/1.0/schema.json")


@pytest.mark.parametrize("fixture_path", VALID_FIXTURES, ids=lambda path: path.stem)
def test_valid_requirements_fixtures(fixture_path: Path) -> None:
    """Every shared valid fixture is accepted by the Worker validator."""
    validate_requirements(_load_json(fixture_path))


@pytest.mark.parametrize("fixture_path", INVALID_FIXTURES, ids=lambda path: path.stem)
def test_invalid_requirements_fixtures(fixture_path: Path) -> None:
    """Every shared invalid fixture is rejected by the Worker validator."""
    with pytest.raises(InvalidRequirementsError):
        validate_requirements(_load_json(fixture_path))


def test_validation_error_does_not_echo_client_payload() -> None:
    """Schema failure details identify only the path/rule, not untrusted values."""
    payload = _load_json(VALID_FIXTURES[0])
    secret = "user-private-value-that-must-not-be-logged"
    payload["clientPayload"] = secret

    with pytest.raises(InvalidRequirementsError) as exc_info:
        validate_requirements(payload)

    assert secret not in exc_info.value.detail
    assert "$.clientPayload" in exc_info.value.detail
