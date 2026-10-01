"""Execute the workflow resolver with controlled Git output and no remote calls."""
import re
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/release.yml"
COMMIT = "a" * 40


def resolver():
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"          python - <<'PYEOF'\n(.*?)          PYEOF", text, re.S)
    assert match is not None
    return "\n".join(line[10:] for line in match[1].splitlines())


@pytest.mark.parametrize("tag,version,commit,exists,valid", [
    ("v1.4.0", "1.4.0", COMMIT, True, True),
    ("v1.4.0;echo bad", "1.4.0", COMMIT, True, False),
    ("v1.4.0\ncommit=bad", "1.4.0", COMMIT, True, False),
    ("../main", "1.4.0", COMMIT, True, False),
    ("refs/tags/v1.4.0", "1.4.0", COMMIT, True, False),
    ("v1.4.0", "1.3.0", COMMIT, True, False),
    ("v1.4.0", "1.4.0", "not-a-sha", True, False),
    ("v1.4.0", "1.4.0", COMMIT, False, False),
])
def test_tag_resolver_fails_closed(tmp_path, monkeypatch, tag, version, commit, exists, valid):
    output = tmp_path / "output"
    monkeypatch.setenv("REQUESTED_TAG", tag)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    calls = []

    def git(argv, *, text):
        calls.append(argv)
        assert text is True
        if argv[1] == "rev-parse":
            assert argv == ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"]
            if not exists:
                raise subprocess.CalledProcessError(128, argv)
            return commit + "\n"
        assert argv == ["git", "show", f"{commit}:pyproject.toml"]
        return f'[project]\nversion = "{version}"\n'

    monkeypatch.setattr(subprocess, "check_output", git)
    if valid:
        exec(compile(resolver(), str(WORKFLOW), "exec"), {})
        assert output.read_text() == f"tag={tag}\ncommit={commit}\n"
        assert len(calls) == 2
    else:
        with pytest.raises((SystemExit, subprocess.CalledProcessError)):
            exec(compile(resolver(), str(WORKFLOW), "exec"), {})
        assert not output.exists()
        if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
            assert calls == []


def test_native_temp_and_qualification_precede_artifact_upload():
    text = WORKFLOW.read_text(encoding="utf-8").split("\n  native-client:\n", 1)[1]
    assert 'D:\\crucible-release-$env:GITHUB_RUN_ID-$env:GITHUB_RUN_ATTEMPT' in text
    assert text.index("TEMP=$nativeTemp") < text.index("Exercise local client boundaries")
    assert text.index("TMP=$nativeTemp") < text.index("Build native client and verify actual stdio")
    assert text.index("--mode release --native") < text.index("name: local-client-assets")
    assert 'gh release upload "$RELEASE_TAG" client-assets/*' in text
