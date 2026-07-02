"""A content-addressed cache for the freeform artifacts a judge scores.

An artifact (a model answer, a RAG response, a document) is the substrate the JudgeMeasure oracle
scores against a rubric. It is often too large to inline in every measurement, so this store keeps
the text keyed by its SHA-256 and lets a recheck descriptor carry only the hash. On replay the exact
bytes are recovered by hash, so the score is sealed to a specific artifact and a swapped artifact is
caught. The store is stdlib-only and holds no model.
"""
from __future__ import annotations

import hashlib


def artifact_sha(text: str) -> str:
    """The SHA-256 of an artifact's text, as 64 hex characters. Pure and deterministic."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ArtifactStore:
    """An in-memory artifact cache keyed by the SHA-256 of the artifact text.

    ``put`` stores an artifact and returns its content hash (idempotent: the same text always yields
    the same key). ``get`` returns the exact stored text for a hash, or None if it is unknown, so a
    recheck can recover the bytes a descriptor sealed. The store never invents an artifact.
    """

    __slots__ = ("_by_sha",)

    def __init__(self) -> None:
        self._by_sha: dict[str, str] = {}

    def put(self, text: str) -> str:
        sha = artifact_sha(text)
        self._by_sha[sha] = text
        return sha

    def get(self, sha: str) -> str | None:
        return self._by_sha.get(sha)

    def __contains__(self, sha: object) -> bool:
        return isinstance(sha, str) and sha in self._by_sha

    def __len__(self) -> int:
        return len(self._by_sha)
