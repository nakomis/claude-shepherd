"""Per-job drone logging — writes a JSONL file for each job so you can inspect
exactly what the drone was given and what it produced."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Default log dir: shepherd-mcp/../../ignored/claude/drone-jobs/
# Override with SHEPHERD_LOG_DIR env var.
_DEFAULT_LOG_DIR = Path(__file__).parent.parent.parent / "ignored" / "claude" / "drone-jobs"


def _log_dir() -> Path:
    d = Path(os.environ.get("SHEPHERD_LOG_DIR", str(_DEFAULT_LOG_DIR)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log_path(job_id: str) -> Path:
    return _log_dir() / f"{job_id}.jsonl"


def append(job_id: str, event: str, **data) -> None:
    """Append one structured event to the job's log file."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **data,
    }
    with _log_path(job_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
