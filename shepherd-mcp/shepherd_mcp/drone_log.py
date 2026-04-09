import json
import os
from datetime import datetime, timezone
from pathlib import Path

def _log_dir() -> Path:
    log_dir = os.environ.get("SHEPHERD_LOG_DIR")
    if not log_dir:
        return None
    d = Path(log_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d

def _log_path(job_id: str) -> Path:
    log_dir = _log_dir()
    if log_dir is None:
        return None
    return log_dir / f"{job_id}.jsonl"

def append(job_id: str, event: str, **data) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **data,
    }
    log_path = _log_path(job_id)
    if log_path is not None:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
