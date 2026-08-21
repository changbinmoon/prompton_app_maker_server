"""Optional canonical requirements reference contract validation.

Raw Client JSON ingress does not call this validator. It remains available to shared
contract consumers that explicitly produce the canonical envelope. Cross-field rules
that Draft 2020-12 cannot express portably are enforced after schema validation.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from models.exceptions import InvalidRequirementsError

REQUIREMENTS_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "contracts" / "requirements.schema.json"
)
MAX_REQUIREMENTS_FILE_BYTES = 64 * 1024


@lru_cache(maxsize=1)
def _requirements_validator() -> Draft202012Validator:
    """Load and cache the canonical Draft 2020-12 validator."""
    schema = json.loads(REQUIREMENTS_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_requirements(payload: dict[str, Any]) -> None:
    """Validate a canonical requirements document.

    Args:
        payload: Parsed JSON object downloaded from S3.

    Raises:
        InvalidRequirementsError: The document violates the schema or a
            cross-field contract rule.
    """
    errors = sorted(
        _requirements_validator().iter_errors(payload),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = errors[0]
        path = _format_json_path(error.absolute_path)
        raise InvalidRequirementsError(
            detail=(
                "requirements.json schema validation failed "
                f"at {path} (rule={error.validator})"
            )
        )

    android = payload["android"]
    min_sdk = android["minSdk"]
    target_sdk = android["targetSdk"]
    if min_sdk > target_sdk:
        raise InvalidRequirementsError(
            detail="requirements.json android.minSdk must not exceed android.targetSdk"
        )


def _format_json_path(parts: Any) -> str:
    """Format a jsonschema path without including untrusted field values."""
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path
