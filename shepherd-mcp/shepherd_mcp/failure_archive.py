"""
Failure archive — persistent log of drone job failures.

Every job that reaches FAILED status is written here with its spec, error,
model, and correction history. This is the raw evidence that informs FAQ rules
and spec improvements over time.

Stored under ignored/failure-archive/{project-name}/{timestamp}-{job_id}.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def _archive_dir(project_path: str) -> Path:
    return Path(__file__).parent.parent.parent / "ignored" / "failure-archive" / Path(project_path).name


def log_failure(
    project_path: str,
    job_id: str,
    model: str,
    spec: str,
    failure_reason: str,
    errors: list[str],
    correction_rounds: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> str:
    """
    Write a failure entry to the archive.

    Returns the path of the written file.
    """
    archive_dir = _archive_dir(project_path)
    archive_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{ts}-{job_id[:8]}.json"
    entry = {
        "timestamp": ts,
        "job_id": job_id,
        "model": model,
        "spec": spec,
        "failure_reason": failure_reason,
        "errors": errors,
        "correction_rounds": correction_rounds,
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
        },
    }
    path = archive_dir / filename
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def list_failures(project_path: str) -> list[dict]:
    """Return all failure entries for a project, newest first."""
    archive_dir = _archive_dir(project_path)
    if not archive_dir.exists():
        return []
    entries = []
    for f in sorted(archive_dir.glob("*.json"), reverse=True):
        try:
            entries.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass  # corrupt file — skip
    return entries


def get_failure(project_path: str, job_id_prefix: str) -> dict | None:
    """
    Look up a specific failure by full job_id or a prefix of it.

    Returns None if not found.
    """
    for entry in list_failures(project_path):
        if entry.get("job_id", "").startswith(job_id_prefix):
            return entry
    return None
