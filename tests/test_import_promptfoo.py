"""Falsifiers for the promptfoo importer — the migration seam.

Load-bearing: (1) every assertion becomes a claim with a REAL falsification
condition (never an untestable claim that could only be UNVERIFIABLE); (2) the
emitted thesis round-trips through crucible's own register/assess path; (3) the
YAML subset parses real promptfoo shape AND fails LOUD (never silently
mis-parses) on unsupported constructs; (4) JSON and YAML inputs agree.
"""
from __future__ import annotations

import json

import pytest

from crucible.import_cmd import thesis_to_json
from crucible.import_promptfoo import (
    PromptfooParseError,
    import_promptfoo,
    parse_yaml_subset,
)


def CLOCK():
    return 1000.0

YAML_CONFIG = """
description: My eval suite
prompts:
  - "Translate to French: {{text}}"
providers:
  - openai:gpt-4o-mini
tests:
  - description: greeting
    vars:
      text: hello
    assert:
      - type: contains
        value: bonjour
      - type: llm-rubric
        value: The translation is natural and fluent
  - description: cost bound
    assert:
      - type: cost
        value: 0.01
"""

JSON_CONFIG = json.dumps({
    "description": "My eval suite",
    "tests": [
        {"description": "greeting", "assert": [
            {"type": "contains", "value": "bonjour"},
            {"type": "llm-rubric", "value": "The translation is natural and fluent"}]},
        {"description": "cost bound", "assert": [{"type": "cost", "value": 0.01}]},
    ],
})


def test_every_assertion_becomes_a_testable_claim():
    thesis = import_promptfoo(YAML_CONFIG, clock=CLOCK)
    assert thesis.title == "My eval suite"
    assert len(thesis.claims) == 3
    for c in thesis.claims:
        assert c.text and c.falsification, \
            "every imported claim must carry a falsification (else it can only be UNVERIFIABLE)"
        assert c.verify()                       # content hash binds text+falsification
    # the contains assertion produced a specific, checkable claim
    contains = next(c for c in thesis.claims if "bonjour" in c.text)
    assert "does not contain" in contains.falsification


def test_json_and_yaml_agree():
    ty = import_promptfoo(YAML_CONFIG, clock=CLOCK)
    tj = import_promptfoo(JSON_CONFIG, clock=CLOCK)
    assert [c.text for c in ty.claims] == [c.text for c in tj.claims]
    assert [c.falsification for c in ty.claims] == [c.falsification for c in tj.claims]
    assert ty.seal == tj.seal                   # identical content -> identical seal


def test_imported_thesis_round_trips_through_register_and_assess(tmp_path):
    # the real payoff: the import feeds crucible's own pipeline unchanged
    from crucible.assess import assess, verify_assessment
    from crucible.commands import _thesis_from_data
    from crucible.thesis import verify_thesis

    thesis = import_promptfoo(JSON_CONFIG, clock=CLOCK)
    payload = thesis_to_json(thesis)
    # re-load via the SAME path `crucible register`/`assess` use
    reloaded = _thesis_from_data(payload, clock=CLOCK)
    assert reloaded.seal == thesis.seal
    assert verify_thesis(reloaded)
    # assess with no measurements: every claim is UNVERIFIABLE, record is witnessed
    record, verdicts = assess(reloaded)
    assert record.claims == 3
    assert record.unverifiable == 3
    assert verify_assessment(record)


def test_yaml_subset_fails_loud_on_unsupported_constructs():
    for bad, why in [
        ("a: &anchor 1\nb: *anchor\n", "anchors"),
        ("x: |\n  a block\n  scalar\n", "block scalars"),
        ("y: [1, 2, 3]\n", "flow"),
        ("z:\n\t- tabbed\n", "tabs"),
    ]:
        with pytest.raises(PromptfooParseError):
            parse_yaml_subset(bad)


def test_no_assertions_is_a_clear_error():
    with pytest.raises(PromptfooParseError, match="no assertions"):
        import_promptfoo('{"description":"x","tests":[{"vars":{"a":1}}]}', clock=CLOCK)


def test_unknown_assertion_type_is_imported_not_dropped():
    cfg = '{"tests":[{"assert":[{"type":"some-future-type","value":"v"}]}]}'
    thesis = import_promptfoo(cfg, clock=CLOCK)
    assert len(thesis.claims) == 1
    assert "some-future-type" in thesis.claims[0].text


def test_duplicate_assertions_collapse():
    cfg = ('{"tests":[{"assert":[{"type":"contains","value":"x"},'
           '{"type":"contains","value":"x"}]}]}')
    thesis = import_promptfoo(cfg, clock=CLOCK)
    assert len(thesis.claims) == 1              # identical content hash -> one claim


def test_tests_as_external_file_ref_is_refused():
    with pytest.raises(PromptfooParseError, match="external file"):
        import_promptfoo('{"description":"x","tests":"file://tests.yaml"}', clock=CLOCK)


def test_cli_import_writes_thesis(tmp_path, capsys):
    from types import SimpleNamespace

    from crucible.import_cmd import cmd_import

    cfg = tmp_path / "promptfooconfig.yaml"
    cfg.write_text(YAML_CONFIG, encoding="utf-8")
    out = tmp_path / "thesis.json"
    args = SimpleNamespace(config=str(cfg), format="auto", out=str(out))

    assert cmd_import(args) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["source"] == "promptfoo-import"
    assert len(doc["claims"]) == 3
    assert "imported 3 claim(s)" in capsys.readouterr().err


def test_comments_and_quoted_hashes_keep_the_assertion_value():
    cfg = "\n".join([
        "# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json",
        "description: suite  # trailing comment",
        "tests:",
        "  - assert:",
        "      - type: contains",
        '        value: "issue #42: fixed"',
        "      - type: contains",
        "        value: 'it''s'",
    ])
    data = parse_yaml_subset(cfg)
    assert list(data) == ["description", "tests"]
    assert data["description"] == "suite"
    values = [a["value"] for a in data["tests"][0]["assert"]]
    assert values == ["issue #42: fixed", "it's"]


def test_quoting_the_reader_cannot_represent_is_refused():
    for bad in ['v: "a\\"b"', 'v: "never closed', "v: 'a'b'"]:
        with pytest.raises(PromptfooParseError):
            parse_yaml_subset(bad)


def test_import_through_the_command_line_feeds_register(tmp_path, capsys):
    from crucible.cli import main

    cfg = tmp_path / "promptfooconfig.yaml"
    cfg.write_text(YAML_CONFIG, encoding="utf-8")
    out = tmp_path / "thesis.json"
    reg = tmp_path / "reg"

    assert main(["import", str(cfg), "--out", str(out)]) == 0
    assert main(["register", str(out), "--registry", str(reg), "--json"]) == 0
    assert main(["registry", "verify", str(reg)]) == 0
    capsys.readouterr()
    assert main(["import", str(cfg), "--format", "json"]) == 1
    assert "import failed: invalid JSON config" in capsys.readouterr().err


def test_import_reports_failures_with_exit_code_one(tmp_path, capsys):
    from crucible.cli import main

    assert main(["import", str(tmp_path / "absent.yaml")]) == 1
    assert "import failed:" in capsys.readouterr().err
    empty = tmp_path / "empty.json"
    empty.write_text('{"tests": []}', encoding="utf-8")
    assert main(["import", str(empty)]) == 1
    captured = capsys.readouterr()
    assert "no assertions found" in captured.err
    assert captured.out == ""
