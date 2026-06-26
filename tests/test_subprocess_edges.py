from __future__ import annotations

import sys

import pytest

from crucible.claim import make_claim
from crucible.subprocess_edges import SubprocessMeasure, SubprocessSteelman
from crucible.verdict import MATCH, verdict_for

CLOCK = lambda: 1000.0  # noqa: E731


def _script(tmp_path, body: str) -> str:
    path = tmp_path / "edge.py"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_subprocess_steelman_reads_json_and_stamps_claim_identity(tmp_path):
    script = _script(tmp_path, """
import json, sys
payload = json.load(sys.stdin)
print(json.dumps({"refutations": [{
    "claim_id": "wrong",
    "claim_sha256": "wrong",
    "challenge": "attack " + payload["claim"]["text"],
    "measurable": "measure " + payload["claim"]["id"],
    "source": "self-reported",
}]}))
""")
    claim = make_claim("latency is below 10ms", "latency rises above 10ms")

    refutation = SubprocessSteelman([sys.executable, script], name="edge").refute(claim)[0]

    assert refutation.claim_id == claim.id
    assert refutation.claim_sha256 == claim.sha256
    assert refutation.challenge == "attack latency is below 10ms"
    assert refutation.measurable == f"measure {claim.id}"
    assert refutation.source == "edge"


def test_subprocess_measure_reads_json_and_returns_a_grounded_measurement(tmp_path):
    script = _script(tmp_path, """
import json, sys
payload = json.load(sys.stdin)
print(json.dumps({"measurement": {
    "claim_id": "wrong",
    "claim_sha256": "wrong",
    "deviation": 0.0,
    "tolerance": 0.1,
    "method": "self-reported",
    "evidence": ["certificate:" + payload["claim"]["sha256"][:8]],
}}))
""")
    claim = make_claim("x equals 1", "x differs from 1")

    measurement = SubprocessMeasure([sys.executable, script], name="toy-oracle", clock=CLOCK).measure(claim)

    assert measurement.claim_id == claim.id
    assert measurement.claim_sha256 == claim.sha256
    assert measurement.method == "toy-oracle"
    assert measurement.measured_at == 1000.0
    assert measurement.evidence == (f"certificate:{claim.sha256[:8]}",)
    assert verdict_for(claim, measurement).status == MATCH


def test_subprocess_edges_reject_shell_strings():
    with pytest.raises(ValueError, match="sequence"):
        SubprocessSteelman("python edge.py")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="sequence"):
        SubprocessMeasure("python edge.py")  # type: ignore[arg-type]


def test_subprocess_edges_enforce_input_and_output_bounds(tmp_path):
    claim = make_claim("a" * 200, "f")
    quiet = _script(tmp_path, "import json; print(json.dumps({'refutations': []}))")
    loud = _script(tmp_path, "print('x' * 200)")

    with pytest.raises(ValueError, match="input"):
        SubprocessSteelman([sys.executable, quiet], max_input_bytes=20).refute(claim)
    with pytest.raises(ValueError, match="output"):
        SubprocessMeasure([sys.executable, loud], max_output_bytes=20).measure(make_claim("x", "f"))


def test_subprocess_edges_do_not_inherit_parent_environment_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("CRUCIBLE_SHOULD_NOT_LEAK", "secret")
    script = _script(tmp_path, """
import json, os
print(json.dumps({"measurement": {
    "deviation": 0.0 if "CRUCIBLE_SHOULD_NOT_LEAK" not in os.environ else 5.0,
    "tolerance": 0.1,
}}))
""")

    measurement = SubprocessMeasure([sys.executable, script]).measure(make_claim("x", "f"))

    assert measurement.deviation == 0.0


def test_subprocess_edges_discard_unbounded_stderr(tmp_path):
    script = _script(tmp_path, """
import json, sys
sys.stderr.write("x" * 200000)
print(json.dumps({"measurement": {"deviation": 0.0, "tolerance": 0.1}}))
""")

    measurement = SubprocessMeasure([sys.executable, script], max_output_bytes=200).measure(make_claim("x", "f"))

    assert measurement.deviation == 0.0


def test_subprocess_measure_rejects_invalid_json_shape(tmp_path):
    script = _script(tmp_path, "print('not json')")

    with pytest.raises(ValueError, match="JSON"):
        SubprocessMeasure([sys.executable, script]).measure(make_claim("x", "f"))
