"""Every place that states crucible's version states the same one.

Before 1.3.0 the version sat in six files with nothing tying them together, so a source install of
``main`` reported 1.2.0 while behaving differently from the 1.2.0 wheel. The guard in
``scripts/check_version_sites.py`` reads each site. These tests run it on the tree, then edit one
site at a time in a copy and require the guard to name that site.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("check_version_sites",
                                               ROOT / "scripts" / "check_version_sites.py")
assert _SPEC is not None and _SPEC.loader is not None
guard = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(guard)

_FILES = ("pyproject.toml", "src/crucible/__init__.py", "README.md", "CHANGELOG.md")


def _copy_tree(tmp_path: Path) -> Path:
    for rel in _FILES:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest)
    return tmp_path


def test_the_tree_agrees_with_itself():
    assert guard.problems(ROOT) == []


def test_every_site_is_found():
    sites = guard.collect(ROOT)
    assert set(sites) == set(guard.SITES)
    assert all(value is not None for value in sites.values()), sites


@pytest.mark.parametrize("site", sorted(guard.SITES))
def test_editing_one_site_fails_the_guard(tmp_path, site):
    root = _copy_tree(tmp_path)
    rel, pattern = guard.SITES[site]
    path = root / rel
    text = path.read_text(encoding="utf-8")
    edited, count = re.subn(pattern, lambda m: m.group(0).replace(m.group("v"), "9.9.9"), text, count=1,
                            flags=re.MULTILINE)
    assert count == 1, f"{site} pattern did not match {rel}"
    path.write_text(edited, encoding="utf-8")
    found = guard.problems(root)
    assert found and any(site in line for line in found), found


def test_a_missing_site_fails_the_guard(tmp_path):
    root = _copy_tree(tmp_path)
    readme = root / "README.md"
    readme.write_text(re.sub(r"!\[version: [^\]]*\]", "![no badge]", readme.read_text(encoding="utf-8")),
                      encoding="utf-8")
    assert any("readme_badge" in line and "not found" in line for line in guard.problems(root))


def test_the_guard_script_exits_nonzero_on_a_mismatch(tmp_path, capsys):
    root = _copy_tree(tmp_path)
    init = root / "src/crucible/__init__.py"
    init.write_text(init.read_text(encoding="utf-8").replace('__version__ = "', '__version__ = "0.', 1),
                    encoding="utf-8")
    assert guard.main([str(root)]) == 1
    assert "package_version" in capsys.readouterr().err
    assert guard.main([str(ROOT)]) == 0


def test_the_tag_must_match_the_declared_version(capsys):
    version = guard.collect(ROOT)["pyproject"]
    assert guard.main([str(ROOT), "--tag", f"v{version}"]) == 0
    assert guard.main([str(ROOT), "--tag", "v0.0.1"]) == 1
    assert "tag" in capsys.readouterr().err


def test_status_derives_its_version_from_the_package(monkeypatch):
    from crucible import flagship

    monkeypatch.setattr(flagship, "__version__", "7.7.7")
    native = flagship.status_payload()["native"]
    assert native["presentation"]["status_block"].startswith("7.7.7 ")
    assert native["current_status"].startswith("7.7.7 ")
    source = (ROOT / "src/crucible/flagship.py").read_text(encoding="utf-8")
    assert not re.search(r'"\d+\.\d+\.\d+ operator floor', source)
