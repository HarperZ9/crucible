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
import tempfile
from typing import Iterator, Mapping

from crucible.claim import Claim, claim_body, content_hash
from crucible.thesis import PUBLISHABLE, Thesis, verify_thesis

MATCH = "MATCH"
MISSING = "MISSING"
CORRUPT = "CORRUPT"
SEAL_BROKEN = "SEAL_BROKEN"

_HEX = set("0123456789abcdef")


def _check_sha(sha: object) -> str:
    """Validate a value as a 64-char lowercase-hex sha256 before it is used to build a path."""
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in _HEX for c in sha):
        raise ValueError(f"not a sha256 hex digest: {sha!r}")
    return sha


def _field(row: Mapping, key: str, what: str):
    """Read a required field from a row that came from disk, with a located error if it is missing
    (rows can be hand-edited, so a missing field is diagnosed, not a bare KeyError)."""
    if key not in row:
        raise ValueError(f"registry {what} row is missing field {key!r}")
    return row[key]


class Registry:
    """Content-addressed storage for theses and assessments under ``root``."""

    def __init__(self, root: str, *, fsync: bool = True) -> None:
        self._root = root
        self._root_real = os.path.realpath(root)
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
        self._guard_path(path)
        if os.path.lexists(path):
            self._reject_link(path)
            return sha, False
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)
        self._guard_path(parent)
        fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                if self._fsync:
                    os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return sha, True

    def read_body(self, sha: str) -> str:
        """Read a stored claim body by its content hash."""
        path = self._object_path(sha)
        self._guard_path(path)
        with open(path, encoding="utf-8") as f:
            return f.read()

    # --- registering and loading theses ---

    def register(self, thesis: Thesis) -> dict:
        """Persist a thesis: write each claim body (deduped) and append its catalog row.

        Returns a summary ``{added, deduped, total}``. The bodies are written before the row, so a
        row never points at a body that is not on disk.
        """
        existing = [r for r in self.theses() if r.get("id") == thesis.id]
        if any(r.get("seal") != thesis.seal for r in existing):
            raise ValueError(f"thesis id {thesis.id!r} already exists with a different seal")
        added = deduped = 0
        for c in thesis.claims:
            _sha, is_new = self._write_object(claim_body(c.text, c.falsification))
            added, deduped = (added + 1, deduped) if is_new else (added, deduped + 1)
        registered = not existing
        if registered:
            self._append(self._theses, self._thesis_row(thesis))
        if self._fsync:
            self._fsync_dir(self._root)
        return {"added": added, "deduped": deduped, "total": len(thesis.claims), "registered": registered}

    def _has_thesis(self, thesis_id: str, seal: str) -> bool:
        """True if an identical thesis (same id and seal) is already in the catalog."""
        return any(r.get("id") == thesis_id and r.get("seal") == seal for r in self.theses())

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

    def load_thesis(self, row: Mapping) -> Thesis:
        """Reconstruct a Thesis from a catalog row, reading each claim body from the object store.
        Pure reconstruction, no verification (a missing field raises a located error); use
        ``get_thesis`` for a verified load."""
        claims = []
        for cr in _field(row, "claims", "theses"):
            sha = _check_sha(_field(cr, "sha256", "claim"))
            data = json.loads(self.read_body(sha))
            claims.append(Claim(id=_field(cr, "id", "claim"), text=_field(data, "text", "claim body"),
                                falsification=_field(data, "falsification", "claim body"), sha256=sha))
        return Thesis(id=_field(row, "id", "theses"), title=_field(row, "title", "theses"),
                      claims=tuple(claims), registered_at=row.get("registered_at", 0.0),
                      disposition=row.get("disposition", PUBLISHABLE), seal=_field(row, "seal", "theses"))

    def get_thesis(self, thesis_id: str) -> Thesis | None:
        """Find and reconstruct a thesis by id, verifying it; None if it is not registered. Raises
        ValueError if the stored thesis fails verification (a tampered registry), so a caller never
        assesses over unverified claims."""
        for row in self.theses():
            if row.get("id") == thesis_id:
                t = self.load_thesis(row)
                if not verify_thesis(t):
                    raise ValueError(f"thesis {thesis_id!r} failed verification: registry may be tampered")
                return t
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

    def _verify_claim(self, tid: str, cr: Mapping) -> dict:
        cid, sha = cr.get("id", ""), cr.get("sha256")
        base = {"thesis_id": tid, "claim_id": cid, "sha256": sha if isinstance(sha, str) else ""}
        if not isinstance(sha, str):  # a row with a non-string sha is tampered, not merely absent
            return {**base, "status": CORRUPT}
        try:
            path = self._object_path(sha)
            self._guard_path(path)
        except ValueError:
            return {**base, "status": CORRUPT}
        if not os.path.exists(path):
            return {**base, "status": MISSING}
        return {**base, "status": MATCH if content_hash(self.read_body(sha)) == sha else CORRUPT}

    def verify_seals(self) -> list[dict]:
        """Re-check each thesis's seal: load its claims and confirm the seal binds them, the title, and
        the disposition. Catches a swapped or relabelled claim and a flipped disposition that a
        body-level ``verify`` would miss. One row per thesis with a status of MATCH or SEAL_BROKEN."""
        out: list[dict] = []
        for row in self.theses():
            tid = row.get("id", "")
            try:
                t = self.load_thesis(row)
                ok = verify_thesis(t) and t.seal == row.get("seal")
            except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError):
                ok = False
            out.append({"thesis_id": tid, "status": MATCH if ok else SEAL_BROKEN})
        return out

    # --- jsonl helpers ---

    def _append(self, path: str, row: dict) -> None:
        os.makedirs(self._root, exist_ok=True)
        self._guard_path(path)
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

    def _stream_jsonl(self, path: str, what: str) -> Iterator[dict]:
        """Stream a JSONL file one row at a time. A malformed line raises a located ValueError
        rather than a silent skip: an accountable store surfaces corruption, it does not hide it."""
        self._guard_path(path)
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

    def _guard_path(self, path: str) -> None:
        self._reject_links_in_path(path)
        try:
            inside = os.path.commonpath([self._root_real, os.path.realpath(path)]) == self._root_real
        except ValueError:
            inside = False
        if not inside:
            raise ValueError(f"registry path escaped root: {path}")

    @staticmethod
    def _reject_link(path: str) -> None:
        if os.path.lexists(path) and os.path.islink(path):
            raise ValueError(f"registry path is a symlink: {path}")

    def _reject_links_in_path(self, path: str) -> None:
        root = os.path.normcase(os.path.abspath(self._root))
        current = os.path.normcase(os.path.abspath(path))
        while True:
            self._reject_link(current)
            if current == root:
                return
            parent = os.path.dirname(current)
            if parent == current:
                return
            current = parent
