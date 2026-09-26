"""Release hygiene for 1.3.0: disclosure route, changelog, and the release workflow.

Each test names one defect found in the 1.2.0 release: no SECURITY.md on ``main``, a changelog
silent on the cycle 9 integrity fixes with two "Unreleased" headings, a publish step that fails a
re-run, and a GitHub Release with no assets or checksums.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_security_policy_has_a_private_route_and_no_placeholder():
    text = _read("SECURITY.md")
    assert "Report a vulnerability" in text
    assert "security/advisories/new" in text
    assert "<" + "SECURITY CONTACT>" not in text
    assert "| 1.3.x" in text
    assert "1.2.0" in text  # the affected release is named


def test_changelog_has_one_unreleased_heading():
    headings = re.findall(r"^## Unreleased\s*$", _read("CHANGELOG.md"), flags=re.MULTILINE)
    assert len(headings) <= 1


def test_changelog_names_the_integrity_fixes_and_affected_versions():
    text = _read("CHANGELOG.md")
    top = text.split("\n## 1.2.0", 1)[0]
    for needle in ("sealed tolerance", "doctor", "verify_browser_evidence", "FNV",
                   "assessment binding", "FSL-1.1-MIT", "1.2.0 and earlier", "SECURITY.md"):
        assert needle in top, needle


def test_every_action_is_pinned_by_commit():
    for workflow in WORKFLOWS.glob("*.yml"):
        for ref in re.findall(r"uses:\s*(\S+)", workflow.read_text(encoding="utf-8")):
            assert re.search(r"@[0-9a-f]{40}$", ref), f"{workflow.name}: {ref}"


def test_publish_tolerates_a_rerun():
    workflow = _read(".github/workflows/release.yml")
    assert re.search(r"skip-existing:\s*true", workflow)


def test_release_checks_the_tag_and_the_version_sites_before_publishing():
    workflow = _read(".github/workflows/release.yml")
    publish_at = workflow.index("gh-action-pypi-publish")
    guard_at = workflow.index('check_version_sites.py . --tag "$GITHUB_REF_NAME"')
    smoke_at = workflow.index("smoke_wheel.py")
    assert guard_at < publish_at and smoke_at < publish_at


def test_release_attaches_pypi_artifacts_with_checksums():
    workflow = _read(".github/workflows/release.yml")
    assert "SHA256SUMS.txt" in workflow
    assert "pypi.org/pypi/crucible-bench" in workflow
    assert "gh release upload" in workflow
    # Write access is scoped to the job that uploads, never the publish job.
    publish_job = workflow.split("  github-release:", 1)[0]
    assert "contents: write" not in publish_job
    assert "contents: write" in workflow.split("  github-release:", 1)[1]


def test_ci_runs_the_version_guard_and_the_wheel_smoke():
    workflow = _read(".github/workflows/ci.yml")
    assert "scripts/check_version_sites.py" in workflow
    assert "scripts/smoke_wheel.py" in workflow
