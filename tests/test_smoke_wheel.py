"""The wheel smoke test hands its children only the environment they need.

In the release workflow the smoke runs inside a job, and a job's environment can hold tokens.
The children (pip and the installed ``crucible``) get an allowlisted environment, so a planted
secret in the parent never reaches them.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("smoke_wheel", ROOT / "scripts" / "smoke_wheel.py")
assert _SPEC is not None and _SPEC.loader is not None
smoke = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(smoke)


def test_child_environment_drops_planted_secrets(monkeypatch):
    monkeypatch.setenv("CRUCIBLE_SMOKE_FAKE_SECRET", "fake-value-for-test")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "fake-oidc-request-token")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-github-token")
    monkeypatch.setenv("PYTHONPATH", "/somewhere/planted")
    env = smoke.child_env()
    assert "fake-value-for-test" not in env.values()
    assert not {"CRUCIBLE_SMOKE_FAKE_SECRET", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "GITHUB_TOKEN",
                "PYTHONPATH"} & set(env)
    assert env["PYTHONSAFEPATH"] == "1"
    assert "PATH" in env


def test_wheel_version_reads_the_file_name():
    assert smoke.wheel_version(Path("crucible_bench-1.3.0-py3-none-any.whl")) == "1.3.0"
