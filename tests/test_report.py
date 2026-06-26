from __future__ import annotations

from crucible.assess import assess
from crucible.claim import make_claim
from crucible.report import render_assessment_report
from crucible.thesis import make_thesis
from crucible.verdict import Measurement

CLOCK = lambda: 3000.0  # noqa: E731


def _thesis():
    return make_thesis(
        "Pipe | safety report",
        [
            make_claim("latency stays under budget", "latency exceeds budget"),
            make_claim("quality stays above floor", "quality falls below floor"),
            make_claim("operator can inspect the outcome", "no report can be produced"),
        ],
        clock=CLOCK,
    )


def _assessment(thesis):
    return assess(
        thesis,
        [
            Measurement(thesis.claims[0].id, thesis.claims[0].sha256, 0.0, 0.1, "bench", 0.0,
                        ("p95 latency 42ms",)),
            Measurement(thesis.claims[1].id, thesis.claims[1].sha256, 1.0, 0.1, "bench", 0.0,
                        ("quality fell to 0.71",)),
        ],
        clock=CLOCK,
    )[0]


def test_render_assessment_report_is_readable_deterministic_markdown():
    thesis = _thesis()
    assessment = _assessment(thesis)
    checks = {"seals_ok": True, "thesis_ok": True, "verdicts_rederive": True}

    report = render_assessment_report(thesis, assessment, checks=checks)

    assert report.startswith("# crucible report: Pipe \\| safety report\n")
    assert f"- thesis_id: `{thesis.id}`" in report
    assert f"- assessment_seal: `{assessment.seal}`" in report
    assert "- counts: MATCH 1 / DRIFT 1 / UNVERIFIABLE 1" in report
    assert "- integrity: seals_ok=True, thesis_ok=True, verdicts_rederive=True" in report
    assert "| Claim | Status | Disposition | Margin | Method | Grounds |" in report
    assert "| latency stays under budget | MATCH | publishable | 1 | bench | deviation 0 within tolerance 0.1 |" in report
    assert "| quality stays above floor | DRIFT | publishable | -9 | bench | deviation 1 exceeds tolerance 0.1 |" in report
    assert "| operator can inspect the outcome | UNVERIFIABLE | publishable |  | none | no measurement |" in report
    assert report == render_assessment_report(thesis, assessment, checks=checks)


def test_render_assessment_report_includes_measurement_evidence_and_recheck_descriptors():
    thesis = _thesis()
    measured = Measurement(
        thesis.claims[0].id,
        thesis.claims[0].sha256,
        0.0,
        0.1,
        "bench",
        0.0,
        ("value | escaped",),
        recheck={"oracle": "bench", "input": {"case": "latency"}},
    )
    assessment = assess(thesis, [measured], clock=CLOCK)[0]

    report = render_assessment_report(thesis, assessment)

    assert "## Measurement Evidence" in report
    assert "| latency stays under budget | bench | value \\| escaped |" in report
    assert "## Recheck Descriptors" in report
    assert '| latency stays under budget | bench | {"input":{"case":"latency"},"oracle":"bench"} |' in report
