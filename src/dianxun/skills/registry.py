"""Versioned Skill registry, deterministic canary routing, and trace identity."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from ..validation import validate_json

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = _ROOT / "skills" / "registry.json"
DEFAULT_SCHEMA = _ROOT / "schemas" / "skill-registry.v1.schema.json"
DEFAULT_SKILL_ROOT = _ROOT / "skills"
TEXT_SUFFIXES = {".json", ".md", ".py", ".toml", ".yaml", ".yml"}
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class SkillRegistryError(ValueError):
    """Raised when a registry or requested release is not safe to use."""


@dataclass(frozen=True)
class SkillRelease:
    name: str
    version: str
    digest: str
    channel: str
    registry_version: str

    def trace_fields(self) -> dict[str, str]:
        return {
            "skill_name": self.name,
            "skill_version": self.version,
            "skill_digest": self.digest,
            "skill_channel": self.channel,
            "skill_registry_version": self.registry_version,
        }


def _normalized_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def compute_skill_digest(skill_root: Path) -> str:
    """Return the canonical digest used by Registry, Trace, and provenance."""
    if not skill_root.is_dir():
        raise SkillRegistryError(f"Skill directory does not exist: {skill_root}")
    digest = hashlib.sha256()
    files = sorted(
        (item for item in skill_root.rglob("*") if item.is_file()),
        key=lambda item: _portable_path_key(item.relative_to(skill_root)),
    )
    if not files:
        raise SkillRegistryError(f"Skill directory is empty: {skill_root}")
    for path in files:
        relative = path.relative_to(skill_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_normalized_bytes(path))
        digest.update(b"\0")
    return digest.hexdigest()


def _portable_path_key(path: Path) -> tuple[str, str]:
    """Keep digest ordering identical on case-insensitive and case-sensitive hosts."""
    relative = path.as_posix()
    return relative.casefold(), relative


def classify_version_change(previous: str, current: str) -> str:
    """Classify one SemVer change for compatibility and promotion policy."""
    old = _parse_semver(previous)
    new = _parse_semver(current)
    if new < old:
        raise SkillRegistryError(
            f"Version downgrade requires rollback workflow: {previous} -> {current}"
        )
    if new == old:
        return "unchanged"
    if new[0] != old[0]:
        return "breaking"
    if new[1] != old[1]:
        return "backward_compatible_feature"
    return "backward_compatible_fix"


def load_skill_registry(
    path: Path = DEFAULT_REGISTRY,
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    skill_root: Path = DEFAULT_SKILL_ROOT,
    verify_digests: bool = True,
) -> dict[str, Any]:
    """Load and semantically validate a registry document."""
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillRegistryError(f"Cannot load Skill registry: {exc}") from exc
    errors = validate_json(registry, schema)
    if errors:
        raise SkillRegistryError("Invalid Skill registry: " + "; ".join(errors))
    _validate_semantics(registry, skill_root=skill_root, verify_digests=verify_digests)
    return registry


@cache
def _default_registry() -> dict[str, Any]:
    registry_path, schema_path, skill_root, verify_digests = _runtime_locations()
    return load_skill_registry(
        registry_path,
        schema_path=schema_path,
        skill_root=skill_root,
        verify_digests=verify_digests,
    )


def resolve_skill_release(
    name: str,
    *,
    routing_key: str,
    registry: dict[str, Any] | None = None,
) -> SkillRelease:
    """Resolve stable/canary release using a deterministic 0-99 bucket."""
    document = registry if registry is not None else _default_registry()
    skill = next((item for item in document["skills"] if item["name"] == name), None)
    if skill is None:
        raise SkillRegistryError(f"Skill is not registered: {name}")
    if skill["status"] != "active":
        raise SkillRegistryError(f"Skill does not accept new routing: {name} ({skill['status']})")

    selected = skill["stable"]
    canary = skill.get("canary")
    if canary is not None:
        if not routing_key:
            raise SkillRegistryError(f"Canary routing for {name} requires a non-empty routing key")
        bucket_input = f"{name}\0{routing_key}".encode()
        bucket = int.from_bytes(hashlib.sha256(bucket_input).digest()[:4], "big") % 100
        if bucket < canary["rollout_percent"]:
            selected = canary

    return SkillRelease(
        name=name,
        version=selected["version"],
        digest=selected["digest"],
        channel=selected["channel"],
        registry_version=document["registry_version"],
    )


def registered_skill_trace_fields(name: str, *, routing_key: str) -> dict[str, str] | None:
    """Return trace identity for registered Skills; ignore intentionally unregistered P1/P2 code."""
    registry = _default_registry()
    if not any(item["name"] == name for item in registry["skills"]):
        return None
    return resolve_skill_release(name, routing_key=routing_key, registry=registry).trace_fields()


def _validate_semantics(
    registry: dict[str, Any], *, skill_root: Path, verify_digests: bool
) -> None:
    skills = registry["skills"]
    names = [item["name"] for item in skills]
    if len(names) != len(set(names)):
        raise SkillRegistryError("Skill names must be unique")
    maximum_canary = registry["lifecycle_policy"]["max_canary_percent"]
    for skill in skills:
        stable = skill["stable"]
        if stable["channel"] != "stable":
            raise SkillRegistryError(f"{skill['name']}: stable release has wrong channel")
        _parse_semver(stable["version"])
        expected_artifact = f"skills/{skill['name']}"
        if stable["artifact"] != expected_artifact:
            raise SkillRegistryError(
                f"{skill['name']}: stable artifact must be {expected_artifact}"
            )
        canary = skill.get("canary")
        if canary is not None:
            change = classify_version_change(stable["version"], canary["version"])
            if change == "unchanged":
                raise SkillRegistryError(f"{skill['name']}: canary must change the stable version")
            if canary["channel"] != "canary":
                raise SkillRegistryError(f"{skill['name']}: canary release has wrong channel")
            if not 1 <= canary["rollout_percent"] <= maximum_canary:
                raise SkillRegistryError(
                    f"{skill['name']}: canary rollout exceeds 1..{maximum_canary}"
                )
            if (canary["version"], canary["digest"]) == (
                stable["version"],
                stable["digest"],
            ):
                raise SkillRegistryError(f"{skill['name']}: canary duplicates stable release")
            rollback_target = skill.get("rollback_target")
            if rollback_target is None:
                raise SkillRegistryError(f"{skill['name']}: canary requires rollback_target")
            if (rollback_target["version"], rollback_target["digest"]) != (
                stable["version"],
                stable["digest"],
            ):
                raise SkillRegistryError(
                    f"{skill['name']}: rollback_target must identify the current stable release"
                )
        status = skill["status"]
        retirement = skill.get("retirement")
        if status == "active" and retirement is not None:
            raise SkillRegistryError(
                f"{skill['name']}: active Skill cannot have retirement metadata"
            )
        if status != "active":
            if canary is not None:
                raise SkillRegistryError(f"{skill['name']}: {status} Skill cannot have a canary")
            if retirement is None:
                raise SkillRegistryError(
                    f"{skill['name']}: {status} Skill requires retirement metadata"
                )
        if verify_digests:
            _verify_canonical_release(skill, stable, skill_root)


def _verify_canonical_release(
    skill: dict[str, Any], stable: dict[str, Any], skill_root: Path
) -> None:
    root = skill_root / skill["name"]
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillRegistryError(f"{skill['name']}: cannot load manifest: {exc}") from exc
    if manifest.get("version") != stable["version"]:
        raise SkillRegistryError(
            f"{skill['name']}: registry version {stable['version']} differs from manifest"
        )
    actual_digest = compute_skill_digest(root)
    if actual_digest != stable["digest"]:
        raise SkillRegistryError(
            f"{skill['name']}: registry digest {stable['digest']} differs from {actual_digest}"
        )


def _parse_semver(value: str) -> tuple[int, int, int]:
    match = _SEMVER.fullmatch(value)
    if match is None:
        raise SkillRegistryError(f"Invalid semantic version: {value}")
    return tuple(int(part) for part in match.groups())


def _runtime_locations() -> tuple[Path, Path, Path, bool]:
    configured = os.environ.get("DIANXUN_SKILL_REGISTRY")
    if configured:
        registry_path = Path(configured).expanduser().resolve()
        schema_path = (
            Path(os.environ.get("DIANXUN_SKILL_REGISTRY_SCHEMA", DEFAULT_SCHEMA))
            .expanduser()
            .resolve()
        )
        skill_root = (
            Path(os.environ.get("DIANXUN_SKILL_ROOT", registry_path.parent)).expanduser().resolve()
        )
        return registry_path, schema_path, skill_root, skill_root.is_dir()
    if DEFAULT_REGISTRY.is_file():
        return DEFAULT_REGISTRY, DEFAULT_SCHEMA, DEFAULT_SKILL_ROOT, True
    share = Path(sys.prefix) / "share" / "dianxun"
    return (
        share / "skills" / "registry.json",
        share / "schemas" / "skill-registry.v1.schema.json",
        share / "skills",
        False,
    )
