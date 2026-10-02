"""CLI command for manifest-driven batch assessment."""
from __future__ import annotations

import json
import os
import re
import sys
import time

from crucible.assess import assess, recheck_assessment
from crucible.commands import (
    _load_measurements,
    _load_substrate,
    _read_json,
    _resolve_thesis,
)
from crucible.measure import TableMeasure, measure_thesis
from crucible.registry import Registry
from crucible.report import render_assessment_report
from crucible.thesis import Thesis

_INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError)


def cmd_batch(args) -> int:
    try:
        result = _run_batch(args.manifest, args.registry, reports_dir=args.reports)
    except _INPUT_ERRORS as exc:
        print(f"batch failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print(f"batch assessed {len(result['jobs'])} job(s) into {args.registry}")
    for row in result["jobs"]:
        report = f"  report {row['report']}" if row.get("report") else ""
        print(f"  {row['id']:<20} MATCH {row['match']}  DRIFT {row['drift']}  "
              f"UNVERIFIABLE {row['unverifiable']}{report}")
    return 0


def _run_batch(manifest_path: str, registry_dir: str, *, reports_dir: str | None = None) -> dict:
    manifest = _read_json(manifest_path)
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("batch manifest needs a non-empty 'jobs' list")
    base = os.path.dirname(os.path.abspath(manifest_path))
    registry = Registry(registry_dir)
    out = []
    for index, job in enumerate(jobs, 1):
        if not isinstance(job, dict):
            raise ValueError(f"batch job {index} is not an object")
        out.append(_run_job(job, index, base, registry, registry_dir, reports_dir))
    return {"ok": True, "jobs": out}


def _run_job(
    job: dict,
    index: int,
    base: str,
    registry: Registry,
    registry_dir: str,
    reports_dir: str | None,
) -> dict:
    job_id = str(job.get("id") or f"job-{index}")
    thesis_ref = job.get("thesis")
    if not isinstance(thesis_ref, str) or not thesis_ref:
        raise ValueError(f"batch job {job_id!r} needs a thesis")
    has_measurements = "measurements" in job
    has_substrate = "substrate" in job
    if has_measurements == has_substrate:
        raise ValueError(f"batch job {job_id!r} needs exactly one of measurements or substrate")
    thesis = _resolve_batch_thesis(base, thesis_ref, registry_dir)
    report_path = _report_path(reports_dir, index, job_id) if reports_dir else None
    if has_measurements:
        measurements = _load_measurements(thesis, _required_manifest_path(base, str(job["measurements"]), job_id))
    else:
        specs, substrate = _load_substrate(thesis, _required_manifest_path(base, str(job["substrate"]), job_id))
        measurements = measure_thesis(TableMeasure(specs, substrate), thesis)
    assessment, _verdicts = assess(thesis, measurements, clock=time.time, registry=registry)
    row = {
        "id": job_id,
        "thesis_id": assessment.thesis_id,
        "assessment_seal": assessment.seal,
        "match": assessment.match,
        "drift": assessment.drift,
        "unverifiable": assessment.unverifiable,
    }
    if report_path:
        report = render_assessment_report(thesis, assessment, checks=recheck_assessment(thesis, assessment))
        with open(report_path, "x", encoding="utf-8") as f:
            f.write(report)
        row["report"] = report_path
    return row


def _resolve_batch_thesis(base: str, value: str, registry_dir: str) -> Thesis:
    if os.path.isabs(value):
        return _resolve_thesis(_required_manifest_path(base, value, "thesis"), registry_dir)
    candidate = _manifest_path(base, value)
    if os.path.isfile(candidate):
        return _resolve_thesis(candidate, registry_dir)
    if _looks_like_path(value):
        raise ValueError(f"batch thesis file is missing: {value}")
    thesis = Registry(registry_dir).get_thesis(value)
    if thesis is None:
        raise ValueError(f"no thesis {value!r} in registry {registry_dir}")
    return thesis


def _required_manifest_path(base: str, value: str, job_id: str) -> str:
    path = _manifest_path(base, value)
    if not os.path.isfile(path):
        raise ValueError(f"batch job {job_id!r} references a missing file: {value}")
    return path


def _manifest_path(base: str, value: str) -> str:
    root = os.path.realpath(base)
    path = os.path.realpath(value if os.path.isabs(value) else os.path.join(base, value))
    if os.path.commonpath([root, path]) != root:
        raise ValueError(f"batch path is outside manifest bundle: {value}")
    return path


def _report_path(reports_dir: str | None, index: int, job_id: str) -> str:
    if reports_dir is None:
        raise ValueError("reports directory is required")
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, f"{index:04d}-{_slug(job_id)}.md")
    if os.path.exists(path):
        raise FileExistsError(f"report already exists: {path}")
    return path


def _looks_like_path(value: str) -> bool:
    return value.lower().endswith(".json") or any(part in value for part in ("/", "\\", os.sep))


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return slug or "job"
