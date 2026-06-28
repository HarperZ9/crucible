import io
import json

from crucible.assess import assess
from crucible.claim import make_claim
from crucible.mcp import handle_request, serve
from crucible.registry import Registry
from crucible.thesis import make_thesis
from crucible.verdict import Measurement

CLOCK = lambda: 1000.0  # noqa: E731


def _call(name, arguments=None):
    return handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    })


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def _seed_recheck_registry(tmp_path):
    reg_dir = tmp_path / "reg"
    claim = make_claim("energy is conserved", "Telos verifier refutes conservation")
    legacy = make_claim("period stays stable", "period measurement drifts")
    thesis = make_thesis("Telos replay", [claim, legacy], clock=CLOCK)
    desc = {"oracle": "telos:conservation", "verifier": "conservation", "expr": "energy"}
    measured = Measurement(
        claim.id,
        claim.sha256,
        0.0,
        0.1,
        "telos:conservation",
        42.0,
        ("telos verified conservation",),
        recheck=desc,
    )
    legacy_measured = Measurement(legacy.id, legacy.sha256, 0.0, 0.1, "manual", 43.0)
    assess(thesis, [measured, legacy_measured], clock=CLOCK, registry=Registry(str(reg_dir), fsync=False))
    return str(reg_dir), thesis, measured


def _replay_pack(path, measurement, *, deviation=0.0):
    return _write(path, {"replays": [{
        "recheck": measurement.recheck,
        "measurement": {
            "claim_id": measurement.claim_id,
            "claim_sha256": measurement.claim_sha256,
            "deviation": deviation,
            "tolerance": measurement.tolerance,
            "method": measurement.method,
            "measured_at": measurement.measured_at,
            "evidence": list(measurement.evidence),
        },
    }]})


def test_initialize_announces_crucible():
    resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["result"]["serverInfo"]["name"] == "crucible"
    assert resp["result"]["protocolVersion"]


def test_tools_list_uses_catalog_names():
    resp = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {tool["name"] for tool in resp["result"]["tools"]}
    assert {
        "crucible.status",
        "crucible.doctor",
        "crucible.assess",
        "crucible.recheck",
        "crucible.run",
        "crucible.review",
        "crucible.report",
        "crucible.batch",
        "crucible.registry",
        "crucible.drift",
        "crucible.refine",
        "crucible.measurement_gate",
    } <= names


def test_status_tool_returns_action_envelope():
    resp = _call("crucible.status")
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["schema"] == "project-telos.flagship-action/v1"
    assert body["tool"] == "crucible"
    assert body["next_actions"][0]["tool"] == "telos"


def test_assess_tool_returns_witnessed_counts(tmp_path):
    thesis = tmp_path / "thesis.json"
    measurements = tmp_path / "measurements.json"
    thesis.write_text(json.dumps({
        "title": "smoke",
        "claims": [
            {"text": "measured claim", "falsification": "measurement exceeds tolerance"},
            {"text": "unmeasured claim", "falsification": "no measurement exists"},
        ],
    }), encoding="utf-8")
    measurements.write_text(json.dumps({
        "measurements": [
            {
                "claim": "measured claim",
                "deviation": 0.0,
                "tolerance": 0.1,
                "method": "smoke",
                "evidence": ["fixture"],
            }
        ]
    }), encoding="utf-8")

    resp = _call("crucible.assess", {"thesis": str(thesis), "measurements": str(measurements)})
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["assessment"]["match"] == 1
    assert body["assessment"]["unverifiable"] == 1
    assert [verdict["status"] for verdict in body["verdicts"]] == ["MATCH", "UNVERIFIABLE"]


def test_measurement_gate_tool_verifies_telos_packet(tmp_path):
    packet = _write(tmp_path / "packet.json", {
        "schema": "project-telos.measurement-layers/v1",
        "tool": "telos.measurement.layers",
        "source_receipts": [{
            "title": "Project Telos measurement layers",
            "url": "demo/measurement-layers.mjs",
            "provenance_class": "lawful_source",
            "receipt_hash": "sha256:abc",
        }],
        "privacy": {"raw_payload_required": False, "raw_assets_required_for_interop": False},
        "measurements": [{
            "layer_id": "lighting.cluster-meter",
            "cluster_count": 12,
            "max_lights_per_cluster": 4,
            "over_budget_clusters": 1,
            "measurement_hash": "fnv1a:cluster",
        }],
    })
    criteria = _write(tmp_path / "criteria.json", {
        "lighting.cluster-meter": {"max_over_budget_clusters": 0},
    })

    resp = _call("crucible.measurement_gate", {"packet": packet, "criteria": criteria})
    body = json.loads(resp["result"]["content"][0]["text"])

    assert body["verification_verdict"] == "DRIFT"
    assert body["decision_outcome"] == "require_review"
    assert body["rows"][0]["failure_code"] == "cluster_budget_exceeded"


def test_recheck_tool_returns_cli_recheck_plan(tmp_path):
    reg, thesis, _measurement = _seed_recheck_registry(tmp_path)

    resp = _call("crucible.recheck", {"dir": reg})
    body = json.loads(resp["result"]["content"][0]["text"])

    assert body["assessment"]["thesis_id"] == thesis.id
    assert body["summary"] == {"descriptors": 1, "skipped": 1}
    assert body["descriptors"][0]["claim_text"] == "energy is conserved"
    assert body["descriptors"][0]["oracle"] == "telos:conservation"
    assert body["descriptors"][0]["recheck"]["expr"] == "energy"


def test_recheck_tool_replays_pack_with_cli_result_shape(tmp_path):
    reg, _thesis, measurement = _seed_recheck_registry(tmp_path)
    pack = _replay_pack(tmp_path / "replay.json", measurement)

    resp = _call("crucible.recheck", {"dir": reg, "pack": pack})
    body = json.loads(resp["result"]["content"][0]["text"])

    assert body["ok"] is True
    assert body["checks"]["measurements_rerun"] is True
    assert body["replay"] == {"ok": True, "checked": 1, "skipped": 1, "missing": 0,
                              "mismatched": 0, "failed": 0}


def test_recheck_tool_reports_replay_drift_as_false_not_error(tmp_path):
    reg, _thesis, measurement = _seed_recheck_registry(tmp_path)
    pack = _replay_pack(tmp_path / "drifted.json", measurement, deviation=2.0)

    resp = _call("crucible.recheck", {"dir": reg, "pack": pack})
    body = json.loads(resp["result"]["content"][0]["text"])

    assert resp["result"]["isError"] is False
    assert body["ok"] is False
    assert body["checks"]["measurements_rerun"] is False
    assert body["replay"]["mismatched"] == 1



def _mcp_thesis(path):
    return _write(path, {
        "id": "mcp-thesis",
        "title": "MCP thesis",
        "claims": [
            {"text": "latency holds", "falsification": "latency exceeds budget"},
            {"text": "quality holds", "falsification": "quality falls below floor"},
        ],
    })


def _mcp_measurements(path, *, latency=0.0, quality=1.0):
    return _write(path, {"measurements": [
        {"claim": "latency holds", "deviation": latency, "tolerance": 0.1, "method": "bench"},
        {"claim": "quality holds", "deviation": quality, "tolerance": 0.1, "method": "bench"},
    ]})


def test_run_review_report_and_registry_tools_share_cli_contract(tmp_path):
    thesis = _mcp_thesis(tmp_path / "thesis.json")
    measurements = _mcp_measurements(tmp_path / "measurements.json")
    registry = str(tmp_path / "reg")
    bundle = str(tmp_path / "packet")

    run = _call("crucible.run", {
        "thesis": thesis,
        "measurements": measurements,
        "registry": registry,
        "bundle": bundle,
    })
    run_body = json.loads(run["result"]["content"][0]["text"])
    assert run_body["ok"] is True
    assert run_body["bundle"] == "."

    review = _call("crucible.review", {"bundle": bundle})
    review_body = json.loads(review["result"]["content"][0]["text"])
    assert review_body["ok"] is True
    assert review_body["checks"]["run_integrity"] is True

    report = _call("crucible.report", {"dir": registry})
    assert report["result"]["content"][0]["text"].startswith("# crucible report: MCP thesis")

    stats = _call("crucible.registry", {"action": "stats", "dir": registry})
    stats_body = json.loads(stats["result"]["content"][0]["text"])
    assert stats_body["assessments"] == 1


def test_refine_batch_and_drift_tools_are_host_callable(tmp_path):
    refine_cfg = _write(tmp_path / "refine.json", {
        "title": "MCP refine",
        "claims": [
            {"text": "c-match", "falsification": "f1"},
            {"text": "c-drift", "falsification": "f2"},
        ],
        "specs": {
            "c-match": {"predicted": 10, "tolerance": 0.5, "observe": "a"},
            "c-drift": {"predicted": 2, "tolerance": 0.5, "observe": "b"},
        },
        "rounds": [{"a": 10, "b": 10}, {"a": 10, "b": 2}],
    })
    refined = _call("crucible.refine", {"config": refine_cfg})
    refined_body = json.loads(refined["result"]["content"][0]["text"])
    assert refined_body["status"] == "correct"

    thesis = _mcp_thesis(tmp_path / "thesis.json")
    first = _mcp_measurements(tmp_path / "m1.json", quality=0.05)
    second = _mcp_measurements(tmp_path / "m2.json", quality=1.0)
    registry = str(tmp_path / "reg")

    batch_manifest = _write(tmp_path / "batch.json", {
        "jobs": [{"id": "mcp-job", "thesis": thesis, "measurements": first}],
    })
    batch = _call("crucible.batch", {"manifest": batch_manifest, "registry": registry})
    batch_body = json.loads(batch["result"]["content"][0]["text"])
    assert batch_body["ok"] is True
    assert batch_body["jobs"][0]["id"] == "mcp-job"

    _call("crucible.run", {"thesis": thesis, "measurements": second, "registry": registry})
    drift = _call("crucible.drift", {"dir": registry})
    drift_body = json.loads(drift["result"]["content"][0]["text"])
    assert drift_body["summary"]["regressed"] == 1

def test_unknown_tool_is_jsonrpc_error():
    resp = _call("crucible.nope")
    assert resp["error"]["code"] == -32602


def test_notification_returns_none():
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_serve_writes_responses():
    inp = io.StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
        '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
    )
    out = io.StringIO()
    assert serve(inp, out) == 0
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [row["id"] for row in rows] == [1, 2]
