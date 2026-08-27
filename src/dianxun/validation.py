"""Small dependency-free JSON Schema subset used at runtime.

The repository publishes schemas for scenarios and MCP tools, but the runtime
must enforce the same basic contract without depending on the development-only
``jsonschema`` package.  This validator intentionally supports only the
keywords used by the checked-in schemas.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any


def validate_json(value: Any, schema: dict[str, Any], *, path: str = "$") -> list[str]:
    """Return deterministic validation errors for the supported schema subset."""
    errors: list[str] = []

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}")
        return errors

    expected_type = schema.get("type")
    if expected_type and not _matches_type(value, expected_type):
        errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}")
        return errors

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(properties)):
                errors.append(f"{path}: unexpected property {key!r}")
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(validate_json(value[key], child_schema, path=f"{path}.{key}"))

    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if minimum_items is not None and len(value) < int(minimum_items):
            errors.append(f"{path}: expected at least {minimum_items} items")
        if schema.get("uniqueItems"):
            canonical = [
                json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) for item in value
            ]
            if len(canonical) != len(set(canonical)):
                errors.append(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(validate_json(item, item_schema, path=f"{path}[{index}]"))

    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        if minimum_length is not None and len(value) < int(minimum_length):
            errors.append(f"{path}: expected at least {minimum_length} characters")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, value) is None:
            errors.append(f"{path}: does not match pattern {pattern!r}")

    if _is_number(value):
        minimum = schema.get("minimum")
        if minimum is not None and value < minimum:
            errors.append(f"{path}: must be greater than or equal to {minimum}")

    return errors


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return _is_number(value)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
