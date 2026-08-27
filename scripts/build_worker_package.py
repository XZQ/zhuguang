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


def package_entries() -> list[tuple[str, Path]]:
    """Return sorted archive names and source paths."""
    _validate_source()
    entries: list[tuple[str, Path]] = [("manifest.json", PACKAGE_ROOT / "manifest.json")]
    for root_name in ("config", "skills"):
        root = PACKAGE_ROOT / root_name
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if root_name == "skills" and path.relative_to(root).parts[0] not in REQUIRED_SKILLS:
                continue
            archive_name = PurePosixPath(path.relative_to(PACKAGE_ROOT).as_posix())
            if archive_name.is_absolute() or ".." in archive_name.parts:
                raise ValueError(f"Unsafe package path: {archive_name}")
            entries.append((archive_name.as_posix(), path))
    return sorted(entries, key=lambda item: item[0])


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
    return {
        "output": str(output),
        "checksum": str(checksum),
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
