"""A Registry: durable, content-addressed storage for theses and their witnessed assessments.

Claim bodies live at ``objects/ab/cdef...`` keyed by the claim's content hash, so an identical claim
is stored once. ``theses.jsonl`` is an append log of one row per registered thesis;
``assessments.jsonl`` keeps the witnessed assessment history. ``verify`` re-hashes every stored body
and reports MATCH / MISSING / CORRUPT. Bodies are written temp-then-rename and fsync'd; the catalog
and history stream a row at a time; a content hash is validated as 64 hex before it builds a path, so
a tampered catalog cannot traverse out of the store. Single-writer.
"""
from __future__ import annotations

import json
import os
from typing import Iterator

from crucible.claim import Claim, claim_body, content_hash
from crucible.thesis import PUBLISHABLE, Thesis

MATCH = "MATCH"
MISSING = "MISSING"
CORRUPT = "CORRUPT"

_HEX = set("0123456789abcdef")


def _check_sha(sha: object) -> str:
    """Validate a value as a 64-char lowercase-hex sha256 before it is used to build a path."""
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in _HEX for c in sha):
        raise ValueError(f"not a sha256 hex digest: {sha!r}")
    return sha


class Registry:
    """Content-addressed storage for theses and assessments under ``root``."""

    def __init__(self, root: str, *, fsync: bool = True) -> None:
        self._root = root
        self._objects = os.path.join(root, "objects")
        self._theses = os.path.join(root, "theses.jsonl")
        self._assessments = os.path.join(root, "assessments.jsonl")
        self._fsync = fsync

    # --- object store ---

    def _object_path(self, sha: str) -> str:
        v = _check_sha(sha)
        return os.path.join(self._objects, v[:2], v[2:])

    def _write_object(self, text: str) -> tuple[str, bool]:
        """Write a body addressed by its hash. Returns ``(sha, is_new)``; an existing body is a
        no-op (dedup). Temp file then rename, so a body is never half-present."""
        sha = content_hash(text)
        path = self._object_path(sha)
        if os.path.exists(path):
            return sha, False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            if self._fsync:
                os.fsync(f.fileno())
        os.replace(tmp, path)
        return sha, True

    def read_body(self, sha: str) -> str:
        """Read a stored claim body by its content hash."""
        with open(self._object_path(sha), encoding="utf-8") as f:
            return f.read()

    # --- registering and loading theses ---

    def register(self, thesis: Thesis) -> dict:
        """Persist a thesis: write each claim body (deduped) and append its catalog row.

        Returns a summary ``{added, deduped, total}``. The bodies are written before the row, so a
        row never points at a body that is not on disk.
        """
        added = deduped = 0
        for c in thesis.claims:
            _sha, is_new = self._write_object(claim_body(c.text, c.falsification))
            added, deduped = (added + 1, deduped) if is_new else (added, deduped + 1)
        self._append(self._theses, self._thesis_row(thesis))
        if self._fsync:
            self._fsync_dir(self._root)
        return {"added": added, "deduped": deduped, "total": len(thesis.claims)}

    @staticmethod
    def _thesis_row(t: Thesis) -> dict:
        return {
            "id": t.id, "title": t.title, "registered_at": t.registered_at,
            "disposition": t.disposition, "seal": t.seal,
            "claims": [{"id": c.id, "sha256": c.sha256} for c in t.claims],
        }

    def theses(self) -> Iterator[dict]:
        """Stream the thesis catalog, one row per registered thesis."""
        yield from self._stream_jsonl(self._theses, "theses")

    def load_thesis(self, row: dict) -> Thesis:
        """Reconstruct a Thesis from a catalog row, reading each claim body from the object store."""
        claims = []
        for cr in row["claims"]:
            sha = _check_sha(cr["sha256"])
            data = json.loads(self.read_body(sha))
            claims.append(Claim(id=cr["id"], text=data["text"],
                                falsification=data["falsification"], sha256=sha))
        return Thesis(id=row["id"], title=row["title"], claims=tuple(claims),
                      registered_at=row["registered_at"],
                      disposition=row.get("disposition", PUBLISHABLE), seal=row["seal"])

    def get_thesis(self, thesis_id: str) -> Thesis | None:
        """Find and reconstruct a thesis by id, or None if it is not registered."""
        for row in self.theses():
            if row.get("id") == thesis_id:
                return self.load_thesis(row)
        return None

    # --- assessments ---

    def add_assessment(self, record: dict) -> None:
        """Append one witnessed assessment record to the durable history."""
        self._append(self._assessments, record)
        if self._fsync:
            self._fsync_dir(self._root)

    def assessments(self) -> Iterator[dict]:
        """Stream the assessment history, one witnessed record per assess session."""
        yield from self._stream_jsonl(self._assessments, "assessments")

    # --- integrity ---

    def verify(self) -> list[dict]:
        """Re-hash every stored claim body against its receipt. One row per claim with a ``status``
        of MATCH, MISSING, or CORRUPT. Reads bodies one at a time."""
        results: list[dict] = []
        for row in self.theses():
            tid = row.get("id", "")
            for cr in row.get("claims", []):
                results.append(self._verify_claim(tid, cr))
        return results

    def _verify_claim(self, tid: str, cr: dict) -> dict:
        cid, sha = cr.get("id", ""), cr.get("sha256")
        base = {"thesis_id": tid, "claim_id": cid, "sha256": sha if isinstance(sha, str) else ""}
        try:
            path = self._object_path(sha)  # type: ignore[arg-type]
        except ValueError:
            return {**base, "status": CORRUPT}
        if not os.path.exists(path):
            return {**base, "status": MISSING}
        status = MATCH if content_hash(self.read_body(sha)) == sha else CORRUPT  # type: ignore[arg-type]
        return {**base, "status": status}

    # --- jsonl helpers ---

    def _append(self, path: str, row: dict) -> None:
        os.makedirs(self._root, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            if self._fsync:
                os.fsync(f.fileno())

    @staticmethod
    def _fsync_dir(path: str) -> None:
        if os.name != "posix":  # opening a directory for fsync is POSIX-only
            return
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _stream_jsonl(path: str, what: str) -> Iterator[dict]:
        """Stream a JSONL file one row at a time. A malformed line raises a located ValueError
        rather than a silent skip: an accountable store surfaces corruption, it does not hide it."""
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"registry {what} line {n} is not valid JSON: {exc}") from exc
