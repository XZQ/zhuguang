"""Build the deterministic AgentTeams v1.2.3 Worker package."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "packages" / "dianxun-worker"
CANONICAL_SKILLS_ROOT = ROOT / "skills"
DEFAULT_OUTPUT = ROOT / "dist" / "dianxun-worker.zip"
REQUIRED_SKILLS = (
    "anomaly-detect",
    "coldchain-risk-assess",
    "rootcause-drilldown",
    "work-order-dispatch",
    "outcome-verify",
    "review-report",
)
SKILL_SUPPORT_FILES = ("registry.json", "LIFECYCLE.md")
TEXT_SUFFIXES = {".json", ".md", ".py", ".toml", ".yaml", ".yml"}
ZIP_TIMESTAMP = (2026, 8, 28, 0, 0, 0)


def _normalized_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def _validate_source() -> None:
    manifest = json.loads((PACKAGE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != "1.0":
        raise ValueError("Worker manifest version must be 1.0")
    worker = manifest.get("worker", {})
    expected = {"model": "qwen3.5-plus", "runtime": "qwenpaw"}
    for key, value in expected.items():
        if worker.get(key) != value:
            raise ValueError(f"Worker manifest {key} must be {value}")

    for name in ("SOUL.md", "AGENTS.md"):
        if not (PACKAGE_ROOT / "config" / name).is_file():
            raise ValueError(f"Missing package config/{name}")

    actual_skills = sorted(
        path.name for path in (PACKAGE_ROOT / "skills").iterdir() if path.is_dir()
    )
    if actual_skills != sorted(REQUIRED_SKILLS):
        raise ValueError(f"Worker package skills differ: {actual_skills}")

    for skill in REQUIRED_SKILLS:
        packaged = PACKAGE_ROOT / "skills" / skill
        canonical = CANONICAL_SKILLS_ROOT / skill
        packaged_files = sorted(
            path.relative_to(packaged) for path in packaged.rglob("*") if path.is_file()
        )
        canonical_files = sorted(
            path.relative_to(canonical) for path in canonical.rglob("*") if path.is_file()
        )
        if packaged_files != canonical_files:
            raise ValueError(f"Packaged files for {skill} differ from canonical files")
        for relative in canonical_files:
            if _normalized_bytes(packaged / relative) != _normalized_bytes(canonical / relative):
                raise ValueError(f"Packaged {skill}/{relative} differs from canonical source")
        skill_md = _normalized_bytes(packaged / "SKILL.md").decode("utf-8")
        if not skill_md.startswith(f"---\nname: {skill}\n"):
            raise ValueError(f"{skill}/SKILL.md lacks AgentTeams frontmatter")

    for filename in SKILL_SUPPORT_FILES:
        packaged = PACKAGE_ROOT / "skills" / filename
        canonical = CANONICAL_SKILLS_ROOT / filename
        if not packaged.is_file() or not canonical.is_file():
            raise ValueError(f"Missing Skill support file: {filename}")
        if _normalized_bytes(packaged) != _normalized_bytes(canonical):
            raise ValueError(f"Packaged skills/{filename} differs from canonical source")

    registry = json.loads((CANONICAL_SKILLS_ROOT / "registry.json").read_text(encoding="utf-8"))
    registered = {item["name"]: item for item in registry.get("skills", [])}
    provenance = {item["name"]: item for item in _skill_provenance()}
    if set(registered) != set(REQUIRED_SKILLS):
        raise ValueError("Skill registry names differ from required P0 Skills")
    for skill in REQUIRED_SKILLS:
        stable = registered[skill].get("stable", {})
        if stable.get("channel") != "stable":
            raise ValueError(f"{skill} has no stable Registry release")
        if stable.get("version") != provenance[skill]["version"]:
            raise ValueError(f"{skill} Registry version differs from manifest")
        if stable.get("digest") != provenance[skill]["sha256"]:
            raise ValueError(f"{skill} Registry digest differs from canonical source")


def package_entries() -> list[tuple[str, Path]]:
    """Return sorted archive names and source paths."""
    _validate_source()
    entries: list[tuple[str, Path]] = [("manifest.json", PACKAGE_ROOT / "manifest.json")]
    for root_name in ("config", "skills"):
        root = PACKAGE_ROOT / root_name
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if root_name == "skills":
                relative_parts = path.relative_to(root).parts
                is_skill_file = relative_parts[0] in REQUIRED_SKILLS
                is_support_file = len(relative_parts) == 1 and path.name in SKILL_SUPPORT_FILES
                if not is_skill_file and not is_support_file:
                    continue
            archive_name = PurePosixPath(path.relative_to(PACKAGE_ROOT).as_posix())
            if archive_name.is_absolute() or ".." in archive_name.parts:
                raise ValueError(f"Unsafe package path: {archive_name}")
            entries.append((archive_name.as_posix(), path))
    return sorted(entries, key=lambda item: item[0])


def _skill_provenance() -> list[dict[str, str]]:
    result = []
    for skill in REQUIRED_SKILLS:
        root = CANONICAL_SKILLS_ROOT / skill
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256()
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(_normalized_bytes(path))
            digest.update(b"\0")
        result.append(
            {
                "name": skill,
                "version": manifest["version"],
                "sha256": digest.hexdigest(),
            }
        )
    return result


def build_worker_package(output: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    """Build the ZIP and SHA-256 sidecar, returning its machine-readable summary."""
    entries = package_entries()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for archive_name, source in entries:
            info = zipfile.ZipInfo(archive_name, ZIP_TIMESTAMP)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, _normalized_bytes(source), compresslevel=9)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
    provenance = output.with_suffix(".provenance.json")
    registry_path = CANONICAL_SKILLS_ROOT / "registry.json"
    lifecycle_path = CANONICAL_SKILLS_ROOT / "LIFECYCLE.md"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    provenance.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "package": output.name,
                "package_sha256": digest,
                "runtime": "qwenpaw",
                "model": "qwen3.5-plus",
                "skills": _skill_provenance(),
                "skill_registry": {
                    "path": "skills/registry.json",
                    "registry_version": registry["registry_version"],
                    "sha256": hashlib.sha256(_normalized_bytes(registry_path)).hexdigest(),
                },
                "skill_lifecycle": {
                    "path": "skills/LIFECYCLE.md",
                    "sha256": hashlib.sha256(_normalized_bytes(lifecycle_path)).hexdigest(),
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "output": str(output),
        "checksum": str(checksum),
        "provenance": str(provenance),
        "sha256": digest,
        "files": len(entries),
        "skills": list(REQUIRED_SKILLS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_worker_package(args.output.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
