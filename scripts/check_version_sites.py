"""Check that every file stating crucible's version states the same one.

    python scripts/check_version_sites.py [ROOT] [--tag vX.Y.Z]

Exit 0 when every site agrees (and, with ``--tag``, the tag names that version); exit 1 with one
line per disagreement on stderr. ``pyproject.toml`` is the reference. The first versioned heading
in ``CHANGELOG.md`` must name it too, so a release commit that bumps the number without writing
its changelog entry fails here. Stdlib only, so it runs before anything is installed.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_V = r"(?P<v>\d+\.\d+\.\d+(?:[-.+][0-9A-Za-z.]+)?)"

# name -> (file relative to the root, pattern with a named group "v")
SITES: dict[str, tuple[str, str]] = {
    "pyproject": ("pyproject.toml", r'^version = "' + _V + '"'),
    "package_version": ("src/crucible/__init__.py", r'^__version__ = "' + _V + '"'),
    "readme_badge_alt": ("README.md", r"!\[version: " + _V + r"\]"),
    "readme_badge": ("README.md", r"badge/version-" + _V + r"-"),
    "readme_current_status": ("README.md", r"`crucible-bench " + _V + r"` is the current"),
    "readme_release_summary": ("README.md", r"`crucible-bench " + _V + r"` covers the full loop"),
    "changelog_latest": ("CHANGELOG.md", r"^## " + _V + r"\b"),
}
REFERENCE = "pyproject"


def collect(root: Path) -> dict[str, str | None]:
    """Read every site under ``root``. A site whose file or pattern is missing reads None."""
    found: dict[str, str | None] = {}
    for name, (rel, pattern) in SITES.items():
        path = root / rel
        if not path.is_file():
            found[name] = None
            continue
        match = re.search(pattern, path.read_text(encoding="utf-8"), flags=re.MULTILINE)
        found[name] = match.group("v") if match else None
    return found


def problems(root: Path, tag: str | None = None) -> list[str]:
    """One line per disagreement; empty when every site names the reference version."""
    sites = collect(root)
    reference = sites[REFERENCE]
    out: list[str] = []
    for name, value in sites.items():
        rel = SITES[name][0]
        if value is None:
            out.append(f"{name}: version not found in {rel}")
        elif reference is not None and value != reference:
            out.append(f"{name}: {rel} says {value}, pyproject.toml says {reference}")
    if tag is not None and reference is not None and tag.removeprefix("v") != reference:
        out.append(f"tag: {tag} does not name pyproject.toml version {reference}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", help="repository root (default: .)")
    parser.add_argument("--tag", default=None, help="a release tag that must name the version")
    args = parser.parse_args(argv)
    root = Path(args.root)
    found = problems(root, args.tag)
    for line in found:
        print(line, file=sys.stderr)
    if found:
        return 1
    print(f"version sites agree: {collect(root)[REFERENCE]} ({len(SITES)} sites)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
