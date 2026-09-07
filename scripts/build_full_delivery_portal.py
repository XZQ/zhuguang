"""Reproduce the complete web portal without publishing or modifying source files."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

if __package__:
    from .build_combined_animation import build as build_animation
    from .build_delivery_portal import build_portal
    from .build_native_defense_web import update as build_defense
    from .generate_portal_status import write_status
    from .portal_support import ASSETS, ROOT
else:
    from build_combined_animation import build as build_animation
    from build_delivery_portal import build_portal
    from build_native_defense_web import update as build_defense
    from generate_portal_status import write_status
    from portal_support import ASSETS, ROOT


def build(output: Path, observations: Path | None = None):
    build_portal(output)
    build_animation(output / "architecture-flow.html")
    build_defense(output / "defense.html")
    shutil.copy2(ASSETS / "portal-status.js", output / "portal-status.js")
    shutil.copytree(
        ROOT / "ppt", output / "ppt", dirs_exist_ok=True, ignore=shutil.ignore_patterns(".DS_Store")
    )
    write_status(output / "status.json", observations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/delivery-portal")
    parser.add_argument("--observations", type=Path)
    args = parser.parse_args()
    build(args.output.resolve(), args.observations)


if __name__ == "__main__":
    main()
