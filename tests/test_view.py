"""Falsifiers for crucible view — the self-contained tamper-catch viewer.

Load-bearing: (1) the bundled JS SHA-256 computes the SAME hash as
crucible.claim.content_hash (verified by running it in Node when available, and
by the known-vector self-test always), so the in-browser tamper-catch is real,
not decorative; (2) the view pack faithfully reflects the registry (theses,
claim bodies, verdicts); (3) the page is self-contained.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from crucible.claim import claim_body, content_hash, make_claim
from crucible.import_promptfoo import import_promptfoo
from crucible.registry import Registry
from crucible.thesis import make_thesis
from crucible.view import _SHA256_JS, build_view, render_view_html


def CLOCK():
    return 1000.0


@pytest.fixture
def registry(tmp_path):
    reg = Registry(str(tmp_path / "reg"))
    thesis = import_promptfoo(
        '{"description":"suite","tests":[{"assert":['
        '{"type":"contains","value":"bonjour"},'
        '{"type":"cost","value":0.01}]}]}', clock=CLOCK)
    reg.register(thesis)
    return reg


def test_view_pack_reflects_the_registry(registry):
    pack = build_view(registry)
    assert pack["counts"]["theses"] == 1
    assert pack["counts"]["claims"] == 2
    t = pack["theses"][0]
    for c in t["claims"]:
        assert c["body"], "each claim carries its stored body for in-browser rehash"
        # the stored sha IS sha256 of the body -> untampered body verifies MATCH
        assert content_hash(c["body"]) == c["sha256"]


def test_page_is_self_contained_and_has_the_self_test(registry):
    page = render_view_html(build_view(registry))
    assert page.lstrip().startswith("<!doctype html>")
    for marker in ("http://", "https://", "src=", "@import"):
        assert marker not in page, f"external reference: {marker}"
    # the verifier self-test with known SHA-256 vectors is present and gated
    assert "verifierSelfTest" in page
    assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in page
    assert "if(verifierSelfTest())render()" in page


def test_bundled_js_sha256_equals_python_content_hash():
    """THE correctness gate: the browser tamper-catch is only real if the JS
    SHA-256 reproduces content_hash. Run the bundled JS in Node over real claim
    bodies and known vectors; skip (not pass) if Node is unavailable."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available to cross-check the JS SHA-256")
    bodies = [
        "",
        "abc",
        claim_body("The output contains 'bonjour'.", "The output does not contain 'bonjour'."),
        claim_body("café naïve résumé", "unicode body"),  # UTF-8 path
        "outside the basic plane: 😀 𐍈",  # surrogate pairs in JavaScript
        "x" * 200,  # more than one 64-byte block
    ]
    script = _SHA256_JS + "\nconst B=" + json.dumps(bodies) + ";" \
        + "console.log(JSON.stringify(B.map(sha256)));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    js_hashes = json.loads(out.stdout)
    py_hashes = [content_hash(b) for b in bodies]
    assert js_hashes == py_hashes, "JS SHA-256 diverges from content_hash — tamper-catch would lie"


def test_tamper_would_be_caught(registry):
    # a byte-flip in a body changes content_hash -> the JS recompute yields CORRUPT
    pack = build_view(registry)
    body = pack["theses"][0]["claims"][0]["body"]
    assert content_hash(body) == pack["theses"][0]["claims"][0]["sha256"]
    assert content_hash(body + " ") != pack["theses"][0]["claims"][0]["sha256"]


def test_cli_view_writes_html(registry, tmp_path, capsys):
    from types import SimpleNamespace

    from crucible.view_cmd import cmd_view

    out = tmp_path / "view.html"
    args = SimpleNamespace(dir=str(tmp_path / "reg"), out=str(out), json=False)
    assert cmd_view(args) == 0
    page = out.read_text(encoding="utf-8")
    assert "crucible registry viewer" in page
    assert "registry view ->" in capsys.readouterr().err


def test_view_through_the_command_line(registry, tmp_path, capsys):
    from crucible.cli import main

    reg = str(tmp_path / "reg")
    assert main(["view", reg, "--json"]) == 0
    pack = json.loads(capsys.readouterr().out)
    assert pack["schema"] == "crucible.view/1"
    assert [t["seal_status"] for t in pack["theses"]] == ["MATCH"]
    assert main(["view", reg]) == 0
    assert capsys.readouterr().out.lstrip().startswith("<!doctype html>")


def test_view_refuses_a_directory_that_is_not_a_registry(tmp_path, capsys):
    from crucible.cli import main

    assert main(["view", str(tmp_path / "absent")]) == 1
    captured = capsys.readouterr()
    assert "view failed: no registry at" in captured.err
    assert captured.out == ""


def test_a_tampered_body_on_disk_reaches_the_page_as_a_mismatch(registry):
    row = next(iter(registry.theses()))
    sha = row["claims"][0]["sha256"]
    path = registry._object_path(sha)
    with open(path, "a", encoding="utf-8") as f:
        f.write(" ")
    pack = build_view(registry)
    claim = pack["theses"][0]["claims"][0]
    assert content_hash(claim["body"]) != claim["sha256"]
    assert any(r["status"] == "CORRUPT" for r in pack["integrity"])


def test_two_rows_with_one_id_are_checked_separately(tmp_path):
    # register refuses a reused id, so a hand-edited catalog is the way two rows share one
    reg = Registry(str(tmp_path / "reg"))
    reg.register(make_thesis("first", [make_claim("first claim", "it fails")], clock=CLOCK, id="t-one"))
    reg.register(make_thesis("second", [make_claim("second claim", "it fails")], clock=CLOCK, id="t-two"))
    catalog = tmp_path / "reg" / "theses.jsonl"
    catalog.write_text(catalog.read_text(encoding="utf-8").replace("t-two", "t-one"), encoding="utf-8")
    pack = build_view(reg)
    assert [t["id"] for t in pack["theses"]] == ["t-one", "t-one"]
    page = render_view_html(pack)
    assert "PACK.theses[+el.dataset.t]" in page, "claims are looked up by position, not by thesis id"
    for thesis in pack["theses"]:
        assert content_hash(thesis["claims"][0]["body"]) == thesis["claims"][0]["sha256"]
