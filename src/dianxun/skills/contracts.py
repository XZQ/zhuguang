"""Runtime output-contract enforcement for the six P0 cold-chain Skills."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from enum import Enum
from functools import cache, wraps
from pathlib import Path
from typing import Any

from ..validation import validate_json


class SkillOutputContractError(ValueError):
    """Raised when a Skill result does not satisfy its published output schema."""


@cache
def _output_schema(skill_name: str) -> dict[str, Any]:
    repository_root = Path(__file__).resolve().parents[3]
    path = repository_root / "skills" / skill_name / "output.schema.json"
    if not path.is_file():
        raise SkillOutputContractError(f"Missing output contract for Skill {skill_name}: {path}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise SkillOutputContractError(f"Output contract for Skill {skill_name} must be an object")
    return schema


def validate_skill_output(skill_name: str, output: Any) -> Any:
    """Validate the JSON-compatible Skill result and return the original value."""
    errors = validate_json(_json_compatible(output), _output_schema(skill_name))
    if errors:
        details = "; ".join(errors)
        raise SkillOutputContractError(f"Skill {skill_name} output contract failed: {details}")
    return output


def enforce_output_contract(skill_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate one runtime Skill entrypoint with its published output contract."""

    def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            return validate_skill_output(skill_name, function(*args, **kwargs))

        return wrapped

    return decorate


def _json_compatible(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_compatible(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return value
