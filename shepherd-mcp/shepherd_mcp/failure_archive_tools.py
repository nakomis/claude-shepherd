"""MCP tool registrations for the failure archive."""

import json
from mcp.server.fastmcp import FastMCP
from . import failure_archive


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def failure_archive_list(project_path: str) -> str:
        """
        List all recorded drone failures for a project, newest first.

        Each entry includes: timestamp, job_id, model, failure_reason,
        correction_rounds, and a truncated spec summary.

        Args:
            project_path: Absolute path to the git repository root.
        """
        entries = failure_archive.list_failures(project_path)
        if not entries:
            return "No failures recorded for this project."
        summaries = [
            {
                "timestamp": e.get("timestamp"),
                "job_id": e.get("job_id"),
                "model": e.get("model"),
                "failure_reason": e.get("failure_reason"),
                "correction_rounds": e.get("correction_rounds"),
                "spec_summary": (e.get("spec") or "")[:120],
            }
            for e in entries
        ]
        return json.dumps(summaries, indent=2)

    @mcp.tool()
    def failure_archive_get(project_path: str, job_id: str) -> str:
        """
        Get the full details of a recorded failure by job_id (or prefix).

        Args:
            project_path: Absolute path to the git repository root.
            job_id:       Full job_id or a unique prefix of it.
        """
        entry = failure_archive.get_failure(project_path, job_id)
        if entry is None:
            return f"No failure found for job_id prefix {job_id!r}."
        return json.dumps(entry, indent=2)
