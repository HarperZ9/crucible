"""JudgeMeasure: an LLM-as-judge oracle on the Measure seam.

DeepEval- and Ragas-style evaluation scores freeform outputs (a model answer, a RAG response, a
document) against natural-language criteria. crucible does the same WITHOUT putting a model in the
verdict: a judge runs once at the impure Measure seam to produce a grounded numeric deviation, and
``verdict_for`` decides from the stored Measurement like any other. The judge is injected, so tests
use a deterministic stub and a live LLM stays behind the seam. The produced Measurement persists a
``judge:llm`` recheck descriptor that names the judge identity and seals the rubric and artifact, so
the score is witnessed and re-runnable, not asserted. A missing artifact, a judge that returns a
non-numeric deviation, or a judge that raises all fail closed to UNVERIFIABLE: the oracle never reads
a claim as holding on a score it could not soundly produce.
"""
from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Mapping, Sequence

from crucible.artifact_store import ArtifactStore, artifact_sha
from crucible.claim import Claim
from crucible.verdict import Measurement

# A judge takes (claim_text, artifact, rubric) and returns a scored assessment:
#   {"deviation": float | None, "evidence": [str, ...], "recheck"?: {...}}
# The rubric is passed in (not closed over) so the sealed rubric_sha names the exact criteria the
# judge scored against, and a live backend can put the real rubric into its prompt.
JudgeFunc = Callable[[str, str, str], "Mapping[str, object]"]

METHOD = "judge:llm"


def rubric_sha(rubric: str) -> str:
    """The first 16 hex of SHA-256(rubric), so the exact rubric can be verified on replay."""
    return hashlib.sha256(rubric.encode("utf-8")).hexdigest()[:16]


def make_null_judge() -> JudgeFunc:
    """The standing default judge: scores nothing (deviation None -> UNVERIFIABLE).

    It invents no score, so it is safe to be the default and keeps crucible standing alone with zero
    third-party dependencies; a real judge (an LLM backend, a rubric evaluator) must be wired in to
    decide a claim.
    """

    def null_judge(claim_text: str, artifact: str, rubric: str) -> Mapping[str, object]:
        return {"deviation": None, "evidence": ("null judge: no score produced",)}

    null_judge.__name__ = "null_judge"
    return null_judge


class LLMJudgeFunc:
    """An injectable orchestrator that turns an LLM backend into a JudgeFunc.

    ``backend`` is any callable taking one prompt string and returning the judge's raw reply; it is
    the only impure edge and defaults to None, so nothing calls a model until a caller supplies one.
    ``parse`` turns the reply into ``{"deviation": float, "evidence": [...]}``. The prompt is built
    from the rubric (passed in at call time by ``JudgeMeasure``, so it is the exact sealed rubric), the
    claim, and the artifact via ``prompt_template.format(...)``. This keeps the live-LLM dependency
    behind the seam: tests pass a deterministic ``backend`` and never hit a model.
    """

    DEFAULT_TEMPLATE = (
        "Rubric:\n{rubric}\n\nClaim:\n{claim}\n\nArtifact:\n{artifact}\n\n"
        "Score how far the artifact falls short of the claim under the rubric as a non-negative "
        "deviation (0.0 = fully satisfies), and give brief evidence."
    )

    def __init__(
        self,
        backend: Callable[[str], object] | None,
        *,
        parse: Callable[[object], Mapping[str, object]],
        prompt_template: str = DEFAULT_TEMPLATE,
        name: str = "llm",
    ) -> None:
        self._backend = backend
        self._parse = parse
        self._template = prompt_template
        self.__name__ = name

    def __call__(self, claim_text: str, artifact: str, rubric: str) -> Mapping[str, object]:
        if self._backend is None:
            return {"deviation": None, "evidence": ("no LLM backend supplied",)}
        prompt = self._template.format(rubric=rubric, claim=claim_text, artifact=artifact)
        return self._parse(self._backend(prompt))


class JudgeMeasure:
    """Measure claims by asking an injected judge to score a freeform artifact against a rubric.

    ``judge`` is the injected oracle; ``rubric`` is the natural-language criteria; ``artifacts`` maps
    a crucible claim id or exact claim text to the artifact to score (inline text, or, when an
    ``artifact_store`` is given, the artifact's SHA-256). A judge score with a trustworthy numeric
    deviation becomes that deviation against tolerance 1.0; a missing artifact, a non-numeric score,
    or a judge that raises becomes deviation None (UNVERIFIABLE), fail-closed. The produced
    Measurement persists a ``judge:llm`` recheck descriptor naming the judge and sealing the rubric
    and artifact, so a later assessment replay re-runs the same judge from the stored row and a
    forged deviation is caught when the honest score is reproduced.
    """

    name = "judge"

    def __init__(
        self,
        judge: JudgeFunc,
        rubric: str,
        artifacts: Mapping[str, str],
        *,
        artifact_store: ArtifactStore | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._judge = judge
        self._rubric = rubric
        self._artifacts = dict(artifacts)
        self._store = artifact_store
        self._clock = clock

    def measure(self, claim: Claim) -> Measurement:
        artifact = self._resolve_artifact(claim)
        if artifact is None:
            return self._measurement(claim, None, ("no artifact for claim",), None)
        recheck = self._recheck(artifact)
        try:
            scored = self._judge(claim.text, artifact, self._rubric)
        except Exception as exc:  # noqa: BLE001 - the judge is an impure edge; a failure is fail-closed evidence.
            return self._measurement(claim, None, (f"judge raised: {exc}",), recheck)
        deviation = _trusted_deviation(scored)
        evidence = _evidence(scored)
        if deviation is None:
            return self._measurement(claim, None, evidence or ("judge produced no numeric deviation",),
                                     recheck)
        return self._measurement(claim, deviation, evidence, recheck)

    def _resolve_artifact(self, claim: Claim) -> str | None:
        ref = self._artifacts.get(claim.id)
        if ref is None:
            ref = self._artifacts.get(claim.text)
        if ref is None:
            return None
        if self._store is not None:
            return self._store.get(ref)
        return ref

    def _recheck(self, artifact: str) -> dict[str, object]:
        return {
            "oracle": METHOD,
            "judge": _judge_name(self._judge),
            "rubric_sha": rubric_sha(self._rubric),
            "artifact_sha": artifact_sha(artifact),
        }

    def _measurement(self, claim: Claim, deviation: float | None, evidence: tuple[str, ...],
                     recheck: Mapping[str, object] | None) -> Measurement:
        return Measurement(claim.id, claim.sha256, deviation, 1.0, METHOD, float(self._clock()),
                           evidence, recheck)


def _judge_name(judge: JudgeFunc) -> str:
    name = getattr(judge, "__name__", None)
    if isinstance(name, str) and name:
        return name
    return judge.__class__.__name__


def _trusted_deviation(scored: object) -> float | None:
    """Extract a trustworthy numeric deviation from a judge's reply, fail-closed.

    A missing key, a non-Mapping reply, a bool (True must not read as 1.0), or a non-number all
    return None so the verdict is UNVERIFIABLE, never an asserted MATCH. Finiteness and sign are left
    to ``verdict_for``, which is the one authority on whether a deviation is usable.
    """
    if not isinstance(scored, Mapping):
        return None
    value = scored.get("deviation")
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _evidence(scored: object) -> tuple[str, ...]:
    if not isinstance(scored, Mapping):
        return ()
    raw = scored.get("evidence")
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return tuple(str(item) for item in raw)
    return ()
