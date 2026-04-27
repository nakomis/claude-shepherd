"""MCP tool registrations for job history."""

import json
from . import job_history


def register(mcp) -> None:

    @mcp.tool()
    def drone_history(project_path: str, limit: int = 50) -> str:
        """
        List recent drone jobs for a project, newest first.

        Shows outcome (success/failed), model, correction rounds, duration,
        and token counts. Persists across sessions unlike drone_list.

        Args:
            project_path: Absolute path to the git repository root.
            limit:        Maximum number of entries to return (default 50).
        """
        entries = job_history.list_jobs(project_path, limit=limit)
        if not entries:
            return "No job history for this project yet."
        return json.dumps(entries, indent=2)

    @mcp.tool()
    def drone_stats(project_path: str) -> str:
        """
        Aggregate drone performance statistics for a project.

        Reports overall success rate, per-model breakdown (success rate,
        average correction rounds, average duration, average token usage),
        and the most common failure reasons.

        Args:
            project_path: Absolute path to the git repository root.
        """
        return json.dumps(job_history.stats(project_path), indent=2)
