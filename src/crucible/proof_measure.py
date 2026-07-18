"""proof_measure.py -- a sound oracle for formal claims: a proof or type checker.

The Measure seam names "a proof or type checker for abstract math" as the oracle for
crucible's north star, verified discovery. This ships it. A claim carries a checker
invocation; the oracle runs it and turns accept/reject into a measurement:

- an accepted proof (checker exits 0) is deviation 0.0            -> MATCH;
- a rejected proof is a deviation that exceeds tolerance          -> DRIFT (it can fail);
- a checker that is absent or errors is deviation None            -> UNVERIFIABLE,
  fail-closed: an unrun checker never reports a proof as holding.

The measurement carries a recheck descriptor (the exact command and, when given, the
artifact's SHA-256) so a stranger re-runs the identical check. Zero-dep: the checker
runs through an injected runner (cmd) -> (ok, output); the default shells the command.
No model is on the verdict path; the checker is the impure edge, exactly like the
judge and table oracles.
"""
from __future__ import annotations

import hashlib
import subprocess
import time
from typing import Callable, Mapping

from crucible.claim import Claim
from crucible.verdict import Measurement

METHOD = "checker:proof"
_DEFAULT_TOLERANCE = 0.5
_CHECK_TIMEOUT = 300


def _subprocess_runner(cmd) -> "tuple[bool, str]":
    """Default runner: shell the checker command and report (accepted, output)."""
    proc = subprocess.run(list(cmd), capture_output=True, text=True, timeout=_CHECK_TIMEOUT)
    return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")


class ProofMeasure:
    """Run a proof/type checker over each claim's artifact and measure accept/reject.

    ``specs`` maps a claim id (or its text) to a checker spec: ``{"checker": "<name>",
    "cmd": [...], "artifact": "<proof source, optional>"}``. ``runner`` is injectable for
    tests; the default shells the command. A claim with no spec, or a checker that cannot
    run, is UNVERIFIABLE (fail-closed)."""

    name = METHOD

    def __init__(self, specs: Mapping[str, Mapping[str, object]], *, runner=None,
                 clock: Callable[[], float] = time.time) -> None:
        self._specs = dict(specs)
        self._runner = runner or _subprocess_runner
        self._clock = clock

    def measure(self, claim: Claim) -> Measurement:
        spec = self._specs.get(claim.id)
        if spec is None:
            spec = self._specs.get(claim.text)
        # honour a sealed tolerance so the verdict binds (verdict_for rejects a
        # measurement whose tolerance differs from the claim's sealed one)
        tol = claim.tolerance if claim.tolerance is not None else _DEFAULT_TOLERANCE
        now = float(self._clock())
        if not isinstance(spec, Mapping):
            return Measurement(claim.id, claim.sha256, None, tol, METHOD, now,
                               ("no checker spec for claim",), None)
        command_spec = spec.get("cmd")
        if (
            not isinstance(command_spec, (list, tuple))
            or not command_spec
            or not all(isinstance(item, str) and item.strip() for item in command_spec)
        ):
            return Measurement(claim.id, claim.sha256, None, tol, METHOD, now,
                               ("no checker spec for claim",), None)
        cmd = tuple(command_spec)
        recheck: dict = {"oracle": METHOD, "checker": str(spec.get("checker", "")), "cmd": cmd}
        artifact = spec.get("artifact")
        if isinstance(artifact, str):
            recheck["artifact_sha256"] = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
        try:
            ok, output = self._runner(cmd)
        except Exception as exc:  # noqa: BLE001 - a checker that cannot run is fail-closed evidence
            return Measurement(claim.id, claim.sha256, None, tol, METHOD, now,
                               (f"checker did not run: {type(exc).__name__}: {exc}",), recheck)
        # a rejected proof deviates beyond tolerance by construction (a binary verdict):
        # deviation 0.0 holds, tol + 1.0 fails, so MATCH/DRIFT is unambiguous at any tolerance.
        deviation = 0.0 if ok else tol + 1.0
        evidence = (f"checker {'accepted' if ok else 'rejected'} the proof", str(output)[:200])
        return Measurement(claim.id, claim.sha256, deviation, tol, METHOD, now, evidence, recheck)
