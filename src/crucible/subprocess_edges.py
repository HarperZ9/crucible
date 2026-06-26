"""Stdlib subprocess adapters for the optional steelman and measure edges.

These adapters keep the core honest: the command is a sequence of argv parts, never a shell string;
the request is bounded JSON on stdin; the response is bounded JSON on stdout; claim identity and the
producer label are stamped locally rather than trusted from the child process.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from typing import Callable

from crucible.claim import Claim
from crucible.steelman import Refutation
from crucible.verdict import Measurement

DEFAULT_MAX_BYTES = 65_536
DEFAULT_TIMEOUT = 10.0
_ENV_ALLOWLIST = {"COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}


class SubprocessSteelman:
    """A Steelman edge backed by a configured command that reads and writes JSON."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        name: str = "subprocess-steelman",
        timeout: float = DEFAULT_TIMEOUT,
        max_input_bytes: int = DEFAULT_MAX_BYTES,
        max_output_bytes: int = DEFAULT_MAX_BYTES,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.command = _command(command)
        self.name = _name(name)
        self.timeout = _positive(timeout, "timeout")
        self.max_input_bytes = _positive_int(max_input_bytes, "max_input_bytes")
        self.max_output_bytes = _positive_int(max_output_bytes, "max_output_bytes")
        self.cwd = cwd
        self.env = _env(env)

    def refute(self, claim: Claim) -> tuple[Refutation, ...]:
        data = _run_json(self.command, _request("crucible.steelman/v1", claim), timeout=self.timeout,
                         max_input_bytes=self.max_input_bytes, max_output_bytes=self.max_output_bytes,
                         cwd=self.cwd, env=self.env)
        rows = data.get("refutations", [])
        if not isinstance(rows, list):
            raise ValueError("subprocess steelman JSON field 'refutations' must be a list")
        return tuple(self._refutation(claim, row) for row in rows)

    def _refutation(self, claim: Claim, row: object) -> Refutation:
        if not isinstance(row, Mapping):
            raise ValueError("subprocess steelman refutation rows must be objects")
        challenge = _string(row.get("challenge"), "challenge")
        measurable = _string(row.get("measurable", ""), "measurable")
        return Refutation(claim.id, claim.sha256, challenge, measurable, self.name)


class SubprocessMeasure:
    """A Measure edge backed by a configured command that reads and writes JSON."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        name: str = "subprocess-measure",
        timeout: float = DEFAULT_TIMEOUT,
        max_input_bytes: int = DEFAULT_MAX_BYTES,
        max_output_bytes: int = DEFAULT_MAX_BYTES,
        clock: Callable[[], float] = time.time,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.command = _command(command)
        self.name = _name(name)
        self.timeout = _positive(timeout, "timeout")
        self.max_input_bytes = _positive_int(max_input_bytes, "max_input_bytes")
        self.max_output_bytes = _positive_int(max_output_bytes, "max_output_bytes")
        self.clock = clock
        self.cwd = cwd
        self.env = _env(env)

    def measure(self, claim: Claim) -> Measurement:
        data = _run_json(self.command, _request("crucible.measure/v1", claim), timeout=self.timeout,
                         max_input_bytes=self.max_input_bytes, max_output_bytes=self.max_output_bytes,
                         cwd=self.cwd, env=self.env)
        row = data.get("measurement", data)
        if not isinstance(row, Mapping):
            raise ValueError("subprocess measure JSON response must be an object")
        return Measurement(
            claim.id,
            claim.sha256,
            _optional_float(row.get("deviation"), "deviation"),
            _float(row.get("tolerance", 1.0), "tolerance"),
            self.name,
            float(self.clock()),
            _evidence(row.get("evidence", ())),
        )


def _run_json(
    command: tuple[str, ...],
    payload: Mapping,
    *,
    timeout: float,
    max_input_bytes: int,
    max_output_bytes: int,
    cwd: str | None,
    env: Mapping[str, str],
) -> dict:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(body) > max_input_bytes:
        raise ValueError("subprocess input exceeds configured byte limit")
    try:
        with tempfile.TemporaryFile() as stdout:
            completed = subprocess.run(
                command,
                input=body,
                stdout=stdout,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                cwd=cwd,
                env=dict(env),
                check=False,
            )
            size = stdout.tell()
            if size > max_output_bytes:
                raise ValueError("subprocess output exceeds configured byte limit")
            stdout.seek(0)
            output = stdout.read().decode("utf-8")
    except subprocess.TimeoutExpired as exc:
        raise ValueError("subprocess timed out") from exc
    if completed.returncode != 0:
        raise ValueError(f"subprocess exited with code {completed.returncode}")
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError("subprocess did not return valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("subprocess JSON response must be an object")
    return data


def _request(kind: str, claim: Claim) -> dict:
    return {
        "kind": kind,
        "claim": {
            "id": claim.id,
            "sha256": claim.sha256,
            "text": claim.text,
            "falsification": claim.falsification,
        },
    }


def _command(command: Sequence[str]) -> tuple[str, ...]:
    if isinstance(command, str):
        raise ValueError("command must be a sequence of argv strings, not a shell string")
    parts = tuple(command)
    if not parts or any(not isinstance(part, str) or not part for part in parts):
        raise ValueError("command must be a non-empty sequence of non-empty strings")
    return parts


def _env(env: Mapping[str, str] | None) -> dict[str, str]:
    if env is not None:
        return {str(k): str(v) for k, v in env.items()}
    return {k: v for k, v in os.environ.items() if k.upper() in _ENV_ALLOWLIST}


def _name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    return name.strip()


def _positive(value: float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 0:
        raise ValueError(f"{field} must be positive")
    return float(value)


def _positive_int(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return float(value)


def _optional_float(value: object, field: str) -> float | None:
    return None if value is None else _float(value, field)


def _evidence(value: object) -> tuple[str, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("evidence must be a list of strings")
    return tuple(value)
