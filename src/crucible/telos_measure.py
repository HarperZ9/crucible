"""Telos witnessed-artifact interop for the Measure seam.

Telos emits ``telos.witnessed-artifact/v1`` envelopes: a claim, a compact certificate, and a
``recheck`` descriptor naming which verifier must be re-run. This module consumes that data without
importing Telos: callers provide a verifier registry, and crucible maps the reproduced verdict into a
Measurement. The emitter's carried verdict is evidence, not authority.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from crucible.claim import Claim
from crucible.verdict import Measurement

PROTOCOL = "telos.witnessed-artifact/v1"

VERIFIED = "verified"
REFUTED = "refuted"
TEL_UNVERIFIABLE = "unverifiable"

Verifier = Callable[[Mapping], str]


def is_telos_artifact(artifact: object) -> bool:
    """Return True for the protocol shape emitted by Telos's witnessed-artifact layer."""
    if not isinstance(artifact, Mapping):
        return False
    recheck = artifact.get("recheck")
    return (artifact.get("protocol") == PROTOCOL and isinstance(recheck, Mapping)
            and isinstance(recheck.get("verifier"), str))


def verify_telos_artifact(artifact: object, verifiers: Mapping[str, Verifier]) -> dict:
    """Re-run an artifact's named verifier and compare the reproduced verdict to the carried one."""
    if not is_telos_artifact(artifact):
        return {"ok": False, "matches": False, "reason": "not a telos witnessed artifact"}
    assert isinstance(artifact, Mapping)
    recheck = artifact["recheck"]
    assert isinstance(recheck, Mapping)
    name = str(recheck["verifier"])
    fn = verifiers.get(name)
    if fn is None:
        return {"ok": False, "matches": False, "reason": f"no verifier registered for {name!r}"}
    try:
        reproduced = _verdict(fn(recheck))
    except Exception as exc:  # noqa: BLE001 - verifier failures are fail-closed evidence.
        return {"ok": False, "matches": False, "reason": f"verifier threw: {exc}"}
    carried = _carried_verdict(artifact)
    return {"ok": True, "reproduced": reproduced, "carried": carried, "matches": reproduced == carried}


def content_hash(value: object) -> str:
    """The same small FNV-1a content hash used by Telos's JavaScript protocol helper."""
    h = 0x811C9DC5
    for ch in str(value):
        h ^= ord(ch)
        h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) & 0xFFFFFFFF
    return f"{h:08x}"


def check_content(artifact: object, content: object) -> bool:
    """Re-check a Telos content artifact against content in hand."""
    if not is_telos_artifact(artifact):
        return False
    assert isinstance(artifact, Mapping)
    recheck = artifact["recheck"]
    assert isinstance(recheck, Mapping)
    return recheck.get("verifier") == "content" and recheck.get("hash") == content_hash(content)


class TelosMeasure:
    """Measure claims by re-running Telos witnessed-artifact verifiers.

    ``artifacts`` maps a crucible claim id or exact claim text to a Telos artifact. A reproduced
    ``verified`` verdict yields deviation 0.0; ``refuted`` yields deviation 2.0 against tolerance 1.0;
    missing, malformed, or unverifiable artifacts yield deviation None. The produced Measurement is
    then decided by ``verdict_for`` like any other measurement.
    """

    name = "telos"

    def __init__(
        self,
        artifacts: Mapping[str, Mapping],
        verifiers: Mapping[str, Verifier],
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._artifacts = dict(artifacts)
        self._verifiers = dict(verifiers)
        self._clock = clock

    def measure(self, claim: Claim) -> Measurement:
        artifact = self._artifacts.get(claim.id) or self._artifacts.get(claim.text)
        if artifact is None:
            return self._measurement(claim, None, "telos:none", ("no Telos artifact for claim",))
        result = verify_telos_artifact(artifact, self._verifiers)
        verifier = _verifier_name(artifact)
        if not result.get("ok"):
            return self._measurement(claim, None, f"telos:{verifier}", (str(result.get("reason", "")),))
        reproduced = str(result["reproduced"])
        evidence = (
            f"telos verifier {verifier} reproduced {reproduced}",
            f"carried {result['carried']}; matches {result['matches']}",
        )
        if reproduced == VERIFIED and result.get("matches"):
            return self._measurement(claim, 0.0, f"telos:{verifier}", evidence)
        if reproduced == REFUTED:
            return self._measurement(claim, 2.0, f"telos:{verifier}", evidence)
        return self._measurement(claim, None, f"telos:{verifier}", evidence)

    def _measurement(self, claim: Claim, deviation: float | None, method: str,
                     evidence: tuple[str, ...]) -> Measurement:
        return Measurement(claim.id, claim.sha256, deviation, 1.0, method, float(self._clock()), evidence)


def _verdict(value: object) -> str:
    text = str(value).lower()
    return text if text in (VERIFIED, REFUTED, TEL_UNVERIFIABLE) else TEL_UNVERIFIABLE


def _carried_verdict(artifact: Mapping) -> str:
    cert = artifact.get("certificate")
    if not isinstance(cert, Mapping):
        return TEL_UNVERIFIABLE
    return _verdict(cert.get("verdict", TEL_UNVERIFIABLE))


def _verifier_name(artifact: object) -> str:
    if not isinstance(artifact, Mapping):
        return "unknown"
    recheck = artifact.get("recheck")
    if not isinstance(recheck, Mapping):
        return "unknown"
    return str(recheck.get("verifier", "unknown"))
