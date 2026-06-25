"""Registry operations that read across the durable store without changing core storage semantics."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from crucible.registry import Registry, _check_sha
from crucible.thesis import FENCED, PUBLISHABLE
from crucible.verdict import DRIFT, MATCH, UNVERIFIABLE

STATUSES = (PUBLISHABLE, FENCED)
VERDICTS = (MATCH, DRIFT, UNVERIFIABLE)


def registry_stats(reg: Registry) -> dict:
    """Summarize the registry's current thesis catalog and latest witnessed verdict posture."""
    rows = list(reg.theses())
    records = list(reg.assessments())
    latest = _latest_by_thesis(records)
    claim_shas = [_claim_sha(cr) for row in rows for cr in row.get("claims", [])]
    dispositions = {status: 0 for status in sorted(STATUSES)}
    for row in rows:
        disposition = str(row.get("disposition", ""))
        dispositions[disposition] = dispositions.get(disposition, 0) + 1
    verdicts = {status: 0 for status in VERDICTS}
    thesis_ids = {str(row.get("id", "")) for row in rows}
    for thesis_id, record in latest.items():
        if thesis_id in thesis_ids:
            for status in _record_statuses(record):
                verdicts[status] = verdicts.get(status, 0) + 1
    return {
        "theses": len(rows),
        "claims": len(claim_shas),
        "unique_claims": len(set(claim_shas)),
        "assessments": len(records),
        "latest_assessments": sum(1 for thesis_id in latest if thesis_id in thesis_ids),
        "dispositions": _nonzero(dispositions),
        "verdicts": verdicts,
    }


def search_theses(
    reg: Registry,
    *,
    scope: str | None = None,
    status: str | None = None,
    verdict: str | None = None,
) -> list[dict]:
    """Search theses by text scope, thesis status, and latest verdict status."""
    if status is not None and status not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    if verdict is not None and verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
    needle = (scope or "").casefold().strip()
    latest = _latest_by_thesis(list(reg.assessments()))
    out: list[dict] = []
    for row in reg.theses():
        if status is not None and row.get("disposition") != status:
            continue
        record = latest.get(str(row.get("id", "")))
        verdicts = sorted(set(_record_statuses(record))) if record else []
        if verdict is not None and verdict not in verdicts:
            continue
        thesis = reg.load_thesis(row)
        if needle and needle not in _search_text(row, thesis).casefold():
            continue
        out.append(_search_row(row, verdicts))
    return out


def prune_objects(reg: Registry, *, apply: bool = False) -> dict:
    """Find claim bodies that are not referenced by any thesis row; delete them only with apply=True."""
    referenced = {_claim_sha(cr) for row in reg.theses() for cr in row.get("claims", [])}
    objects = _object_shas(reg)
    orphans = sorted(sha for sha in objects if sha not in referenced)
    deleted: list[str] = []
    if apply:
        for sha in orphans:
            path = _safe_object_path(reg, sha)
            if path.is_file():
                path.unlink()
                deleted.append(sha)
                _remove_empty_shard(path.parent)
    return {
        "dry_run": not apply,
        "referenced": len(referenced),
        "objects": len(objects),
        "orphans": orphans,
        "deleted": deleted,
    }


def _claim_sha(row: Mapping) -> str:
    return _check_sha(row.get("sha256"))


def _latest_by_thesis(records: Iterable[Mapping]) -> dict[str, Mapping]:
    latest: dict[str, Mapping] = {}
    for record in records:
        thesis_id = record.get("thesis_id")
        if isinstance(thesis_id, str):
            latest[thesis_id] = record
    return latest


def _record_statuses(record: Mapping | None) -> list[str]:
    if record is None:
        return []
    rows = record.get("verdicts")
    if isinstance(rows, list):
        return [str(row.get("status", "")) for row in rows if row.get("status") in VERDICTS]
    return ([MATCH] * _count(record, "match")
            + [DRIFT] * _count(record, "drift")
            + [UNVERIFIABLE] * _count(record, "unverifiable"))


def _count(record: Mapping, key: str) -> int:
    value = record.get(key, 0)
    return value if isinstance(value, int) and value >= 0 else 0


def _nonzero(counts: Mapping[str, int]) -> dict[str, int]:
    return {key: value for key, value in counts.items() if value}


def _search_text(row: Mapping, thesis) -> str:
    claim_bits = [bit for claim in thesis.claims for bit in (claim.text, claim.falsification)]
    return "\n".join([str(row.get("id", "")), str(row.get("title", "")),
                      str(row.get("disposition", "")), str(row.get("seal", "")), *claim_bits])


def _search_row(row: Mapping, latest_verdicts: list[str]) -> dict:
    return {
        "id": row.get("id", ""),
        "title": row.get("title", ""),
        "disposition": row.get("disposition", ""),
        "claims": len(row.get("claims", [])),
        "seal": row.get("seal", ""),
        "latest_verdicts": latest_verdicts,
    }


def _object_shas(reg: Registry) -> set[str]:
    root = Path(getattr(reg, "_objects"))
    if not root.exists():
        return set()
    shas: set[str] = set()
    for shard in root.iterdir():
        if not shard.is_dir() or len(shard.name) != 2:
            continue
        for body in shard.iterdir():
            if body.is_file() and not body.name.endswith(".tmp"):
                sha = shard.name + body.name
                try:
                    shas.add(_check_sha(sha))
                except ValueError:
                    continue
    return shas


def _safe_object_path(reg: Registry, sha: str) -> Path:
    root = Path(getattr(reg, "_objects")).resolve()
    path = Path(reg._object_path(sha)).resolve()  # noqa: SLF001 - same-package object-store helper.
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("object path escaped registry objects directory") from exc
    return path


def _remove_empty_shard(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        return
