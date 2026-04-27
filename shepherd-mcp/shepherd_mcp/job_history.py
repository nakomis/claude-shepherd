"""
Persistent job history — one JSONL file per project, one entry per completed job.

Tracks both successes and failures so that success rate, duration, and token usage
can be computed across sessions. The failure archive remains separate (it stores
full spec + error text for diagnosis); this is the lightweight metrics log.

Stored under ignored/job-history/{project-name}.jsonl
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path


def _history_path(project_path: str) -> Path:
    base = Path(__file__).parent.parent.parent / "ignored" / "job-history"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{Path(project_path).name}.jsonl"


def log_job(
    project_path: str,
    job_id: str,
    model: str,
    outcome: str,           # "success" | "failed"
    failure_reason: str | None,
    correction_rounds: int,
    started_at: float | None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    completed_at = time.time()
    duration = round(completed_at - started_at, 1) if started_at else None
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "job_id": job_id,
        "model": model,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "correction_rounds": correction_rounds,
        "duration_seconds": duration,
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
        },
    }
    with _history_path(project_path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def list_jobs(project_path: str, limit: int = 50) -> list[dict]:
    """Return up to `limit` recent job entries, newest first."""
    path = _history_path(project_path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
        if len(entries) >= limit:
            break
    return entries


def stats(project_path: str) -> dict:
    """Aggregate statistics across all recorded jobs for this project."""
    all_jobs = list_jobs(project_path, limit=10_000)
    if not all_jobs:
        return {"total_jobs": 0, "message": "No history yet."}

    total = len(all_jobs)
    successes = sum(1 for j in all_jobs if j["outcome"] == "success")

    by_model: dict[str, dict] = {}
    failure_counts: dict[str, int] = {}

    for j in all_jobs:
        m = j["model"]
        if m not in by_model:
            by_model[m] = {"total": 0, "success": 0, "durations": [], "prompt_tokens": [], "completion_tokens": [], "correction_rounds": []}
        bm = by_model[m]
        bm["total"] += 1
        if j["outcome"] == "success":
            bm["success"] += 1
        if j.get("duration_seconds") is not None:
            bm["durations"].append(j["duration_seconds"])
        tokens = j.get("tokens", {})
        if tokens.get("prompt"):
            bm["prompt_tokens"].append(tokens["prompt"])
        if tokens.get("completion"):
            bm["completion_tokens"].append(tokens["completion"])
        bm["correction_rounds"].append(j.get("correction_rounds", 0))

        reason = j.get("failure_reason")
        if reason:
            # Truncate long reasons for grouping
            key = reason[:80]
            failure_counts[key] = failure_counts.get(key, 0) + 1

    def _avg(lst: list) -> float | None:
        return round(sum(lst) / len(lst), 1) if lst else None

    model_stats = {}
    for m, bm in by_model.items():
        model_stats[m] = {
            "total": bm["total"],
            "success": bm["success"],
            "success_rate": f"{round(100 * bm['success'] / bm['total'])}%",
            "avg_correction_rounds": _avg(bm["correction_rounds"]),
            "avg_duration_seconds": _avg(bm["durations"]),
            "avg_prompt_tokens": _avg(bm["prompt_tokens"]),
            "avg_completion_tokens": _avg(bm["completion_tokens"]),
        }

    return {
        "total_jobs": total,
        "success_rate": f"{round(100 * successes / total)}%",
        "by_model": model_stats,
        "top_failure_reasons": dict(
            sorted(failure_counts.items(), key=lambda x: -x[1])[:5]
        ),
    }
