from __future__ import annotations

import hashlib

from crucible.artifact_store import ArtifactStore
from crucible.assess import assess, recheck_assessment, recheck_measurements
from crucible.claim import make_claim
from crucible.judge import (
    JudgeMeasure,
    LLMJudgeFunc,
    make_null_judge,
    rubric_sha,
)
from crucible.thesis import make_thesis
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE, verdict_for

CLOCK = lambda: 1000.0  # noqa: E731

RUBRIC = "The answer must be factually accurate and cite sources."


def stub_judge(deviation):
    """A deterministic stub judge: returns a fixed deviation independent of the artifact content."""

    def judge(claim_text: str, artifact: str, rubric: str) -> dict:
        return {
            "deviation": deviation,
            "evidence": [f"artifact length {len(artifact)} chars"],
        }

    judge.__name__ = f"stub_judge_dev{deviation}"
    return judge


def _thesis(claim):
    return make_thesis("judge", [claim], clock=CLOCK)


def test_judge_measure_maps_a_stub_score_into_a_measurement_and_verdict():
    claim = make_claim("the RAG answer must score 0.9+ on coherence",
                       "the judge scores the artifact below the coherence bar")
    artifact = "a coherent, well-cited answer that stays on topic"
    measure = JudgeMeasure(judge=stub_judge(0.3), rubric=RUBRIC,
                           artifacts={claim.id: artifact}, clock=CLOCK)

    m = measure.measure(claim)

    assert m.method == "judge:llm"
    assert m.deviation == 0.3
    assert m.tolerance == 1.0
    assert m.measured_at == 1000.0
    assert m.evidence == (f"artifact length {len(artifact)} chars",)
    assert verdict_for(claim, m).status == MATCH


def test_judge_measure_drift_when_deviation_exceeds_tolerance():
    claim = make_claim("the RAG answer must score 0.9+ on coherence",
                       "the judge scores the artifact below the coherence bar")
    measure = JudgeMeasure(judge=stub_judge(1.7), rubric=RUBRIC,
                           artifacts={claim.id: "a rambling, off-topic answer"}, clock=CLOCK)

    m = measure.measure(claim)

    assert m.deviation == 1.7
    assert verdict_for(claim, m).status == DRIFT


def test_judge_measure_recheck_descriptor_records_judge_identity_and_seals_artifact():
    claim = make_claim("the answer is grounded", "the judge scores it below the bar")
    artifact = "grounded answer with citations [1][2]"
    measure = JudgeMeasure(judge=stub_judge(0.2), rubric=RUBRIC,
                           artifacts={claim.id: artifact}, clock=CLOCK)

    m = measure.measure(claim)

    assert m.recheck is not None
    assert m.recheck["oracle"] == "judge:llm"
    assert m.recheck["judge"] == "stub_judge_dev0.2"
    assert m.recheck["rubric_sha"] == rubric_sha(RUBRIC)
    assert m.recheck["artifact_sha"] == hashlib.sha256(artifact.encode("utf-8")).hexdigest()


def test_judge_measure_persists_recheck_descriptor_for_assessment_replay():
    claim = make_claim("the answer is grounded", "the judge scores it below the bar")
    artifact = "grounded answer with citations [1][2]"
    judge = stub_judge(0.2)
    measure = JudgeMeasure(judge=judge, rubric=RUBRIC,
                           artifacts={claim.id: artifact}, clock=CLOCK).measure(claim)
    thesis = _thesis(claim)
    assessment, _ = assess(thesis, [measure], clock=CLOCK)

    stored = assessment.measurements[0]["recheck"]
    assert stored["oracle"] == "judge:llm"
    assert stored["judge"] == "stub_judge_dev0.2"

    # An honest replay reproduces the exact stored measurement inputs.
    honest = JudgeMeasure(judge=judge, rubric=RUBRIC,
                          artifacts={claim.id: artifact}, clock=CLOCK)

    def replay(recheck):
        assert recheck["oracle"] == "judge:llm"
        return honest.measure(claim)

    assert recheck_measurements(assessment, {"judge:llm": replay})["checked"] == 1
    result = recheck_assessment(thesis, assessment,
                                measurement_replayers={"judge:llm": replay})
    assert result["measurements_rerun"] is True


def test_llm_judge_func_puts_the_live_backend_behind_the_seam():
    claim = make_claim("the answer is grounded", "the judge scores it below the bar")
    calls: list[str] = []

    def fake_backend(prompt: str) -> str:
        calls.append(prompt)
        return "score: 0.2"

    def parse(reply: object) -> dict:
        score = float(str(reply).split(":")[1])
        return {"deviation": score, "evidence": [f"backend replied {reply!r}"]}

    judge = LLMJudgeFunc(fake_backend, parse=parse, name="fake-llm-v1")
    measure = JudgeMeasure(judge=judge, rubric=RUBRIC,
                           artifacts={claim.id: "grounded answer"}, clock=CLOCK)

    m = measure.measure(claim)

    assert len(calls) == 1  # the backend was called exactly once, at the impure seam
    assert RUBRIC in calls[0]  # the rubric actually reaches the backend prompt, not an empty string
    assert "grounded answer" in calls[0]  # the artifact reaches the prompt too
    assert m.deviation == 0.2
    assert m.recheck["judge"] == "fake-llm-v1"
    assert verdict_for(claim, m).status == MATCH


def test_llm_judge_func_uses_the_measures_rubric_in_the_prompt():
    """The rubric supplied to JudgeMeasure (and sealed) is the rubric the backend actually sees."""
    claim = make_claim("the answer is grounded", "the judge scores it below the bar")
    seen: list[str] = []

    def fake_backend(prompt: str) -> str:
        seen.append(prompt)
        return "score: 0.1"

    def parse(reply: object) -> dict:
        return {"deviation": float(str(reply).split(":")[1]), "evidence": ["ok"]}

    judge = LLMJudgeFunc(fake_backend, parse=parse, name="llm")
    other_rubric = "The answer must be concise and never speculate."
    measure = JudgeMeasure(judge=judge, rubric=other_rubric,
                           artifacts={claim.id: "grounded answer"}, clock=CLOCK)

    measure.measure(claim)

    assert other_rubric in seen[0]
    assert RUBRIC not in seen[0]


def test_llm_judge_func_without_a_backend_is_unverifiable():
    claim = make_claim("the answer is grounded", "the judge scores it below the bar")
    judge = LLMJudgeFunc(None, parse=lambda r: {"deviation": 0.0})
    measure = JudgeMeasure(judge=judge, rubric=RUBRIC,
                           artifacts={claim.id: "grounded answer"}, clock=CLOCK)

    m = measure.measure(claim)

    assert m.deviation is None
    assert verdict_for(claim, m).status == UNVERIFIABLE


def test_null_judge_yields_unverifiable_fail_closed():
    claim = make_claim("the answer is grounded", "the judge scores it below the bar")
    measure = JudgeMeasure(judge=make_null_judge(), rubric=RUBRIC,
                           artifacts={claim.id: "any artifact"}, clock=CLOCK)

    m = measure.measure(claim)

    assert m.deviation is None
    assert verdict_for(claim, m).status == UNVERIFIABLE


def test_judge_measure_no_artifact_is_unverifiable():
    claim = make_claim("the answer is grounded", "the judge scores it below the bar")
    measure = JudgeMeasure(judge=stub_judge(0.1), rubric=RUBRIC, artifacts={}, clock=CLOCK)

    m = measure.measure(claim)

    assert m.deviation is None
    assert verdict_for(claim, m).status == UNVERIFIABLE


def test_judge_measure_non_numeric_deviation_fails_closed():
    claim = make_claim("the answer is grounded", "the judge scores it below the bar")

    def bad_judge(claim_text: str, artifact: str, rubric: str) -> dict:
        return {"deviation": "not a number", "evidence": ["oops"]}

    measure = JudgeMeasure(judge=bad_judge, rubric=RUBRIC,
                           artifacts={claim.id: "artifact"}, clock=CLOCK)

    m = measure.measure(claim)

    assert m.deviation is None
    assert verdict_for(claim, m).status == UNVERIFIABLE


def test_judge_that_raises_is_unverifiable_not_a_crash():
    claim = make_claim("the answer is grounded", "the judge scores it below the bar")

    def throwing_judge(claim_text: str, artifact: str, rubric: str) -> dict:
        raise RuntimeError("live judge backend is down")

    measure = JudgeMeasure(judge=throwing_judge, rubric=RUBRIC,
                           artifacts={claim.id: "artifact"}, clock=CLOCK)

    m = measure.measure(claim)

    assert m.deviation is None
    assert verdict_for(claim, m).status == UNVERIFIABLE


def test_judge_measure_reads_artifact_from_store_by_hash():
    claim = make_claim("the answer is grounded", "the judge scores it below the bar")
    artifact = "grounded answer stored in the artifact cache"
    store = ArtifactStore()
    sha = store.put(artifact)
    measure = JudgeMeasure(judge=stub_judge(0.2), rubric=RUBRIC,
                           artifacts={claim.id: sha}, artifact_store=store, clock=CLOCK)

    m = measure.measure(claim)

    assert m.deviation == 0.2
    assert m.recheck["artifact_sha"] == sha
    assert m.evidence == (f"artifact length {len(artifact)} chars",)


def test_artifact_store_roundtrip_and_integrity():
    store = ArtifactStore()
    text = "the exact artifact bytes"
    sha = store.put(text)

    assert sha == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert store.get(sha) == text
    assert store.get("deadbeef") is None
    # Idempotent: storing the same text yields the same key.
    assert store.put(text) == sha


# The can-it-FAIL negative test: a forged deviation cannot be asserted; the honest
# replay re-derives the true verdict and the recheck exposes the lie.
def test_judge_measure_deviation_is_sealed_and_forgery_is_caught_by_verdict():
    from crucible.assess import verify_assessment
    from crucible.verdict import Measurement

    claim = make_claim("the RAG answer must score 0.9+ on coherence",
                       "the judge scores the artifact below the coherence bar")
    artifact = "a poorly written, incoherent answer that ignores the question"
    thesis = _thesis(claim)

    # Honest judge scores the bad artifact 1.5, exceeding tolerance 1.0 -> DRIFT.
    honest_judge = stub_judge(1.5)
    honest_measure = JudgeMeasure(judge=honest_judge, rubric=RUBRIC,
                                  artifacts={claim.id: artifact}, clock=CLOCK).measure(claim)
    assert verdict_for(claim, honest_measure).status == DRIFT

    # An attacker rewrites the stored deviation to 0.05 (a would-be MATCH), keeps the honest
    # recheck descriptor (tampering it would break the measurement seal), recomputes the verdict
    # FROM the forged deviation, and reseals the whole record via assess. verify_assessment then
    # passes: the forgery is internally consistent.
    forged_measurement = Measurement(
        honest_measure.claim_id, honest_measure.claim_sha256, 0.05, honest_measure.tolerance,
        honest_measure.method, honest_measure.measured_at, honest_measure.evidence,
        honest_measure.recheck,
    )
    forged, _ = assess(thesis, [forged_measurement], clock=CLOCK)
    assert verify_assessment(forged) is True
    assert forged.match == 1 and forged.drift == 0

    # verdicts still re-derive against the forged record alone (it is internally consistent), so a
    # self-consistent lie survives a seal check. It does NOT survive re-running the judge: the honest
    # replay reproduces deviation 1.5, not the forged 0.05, so the sealed measurement inputs mismatch.
    def honest_replay(recheck):
        return JudgeMeasure(judge=honest_judge, rubric=RUBRIC,
                            artifacts={claim.id: artifact}, clock=CLOCK).measure(claim)

    result = recheck_assessment(thesis, forged,
                                measurement_replayers={"judge:llm": honest_replay})
    assert result["verdicts_rederive"] is True  # the forgery is internally consistent
    assert result["measurements_rerun"] is False  # but the honest judge exposes the forged score
