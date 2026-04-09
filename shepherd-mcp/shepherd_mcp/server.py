#!/usr/bin/env python3
"""
Shepherd MCP Server

Exposes the drone LLM pipeline as tools Claude can call directly.
Claude orchestrates; the MCP handles the loop internals.
Claude only sees a job when it's ready or genuinely stuck — not every
intermediate compile failure.
"""

import json
import threading
from mcp.server.fastmcp import FastMCP

from .jobs import store, JobStatus
from .providers.ollama import OllamaProvider
from . import worktree, compile, faq

mcp = FastMCP("shepherd-mcp")

MAX_CORRECTION_ROUNDS = 3

_PROVIDERS = {
    "ollama": OllamaProvider(),
}


def _resolve_provider(model: str):
    """
    Select a provider from a scoped model string.

    Examples:
        "ollama/qwen2.5-coder:14b" → OllamaProvider, model="qwen2.5-coder:14b"
        "qwen2.5-coder:14b"        → OllamaProvider (default), model="qwen2.5-coder:14b"
    """
    if "/" in model:
        provider_name, model_name = model.split("/", 1)
    else:
        provider_name, model_name = "ollama", model

    provider = _PROVIDERS.get(provider_name)
    if provider is None:
        raise ValueError(f"Unknown provider {provider_name!r}. Available: {list(_PROVIDERS)}")
    return provider, model_name


def _run_pipeline(job_id: str) -> None:
    """
    Background thread: generate → compile → correct loop → mark ready/failed.
    Claude polls via drone_status / drone_result and is not involved until the
    job reaches 'ready' or 'failed'.
    """
    job = store.get(job_id)
    provider, model_name = _resolve_provider(job.model)

    system = faq.system_prompt(
        "You are a code generation assistant. Output only valid source code files. "
        "For each file, use the format:\n\n"
        "### FILE: <relative/path/to/file.ext>\n"
        "```\n"
        "<file content>\n"
        "```\n\n"
        "Do not include explanations outside of code comments."
    )

    prompt = job.spec
    if job.feedback:
        prompt = f"{job.spec}\n\n# Reviewer feedback\n\n{job.feedback}"

    for round_num in range(MAX_CORRECTION_ROUNDS + 1):
        # Generate
        job.status = JobStatus.GENERATING if round_num == 0 else JobStatus.CORRECTING
        job.correction_rounds = round_num

        try:
            result = provider.generate(prompt, system, model_name)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.failure_reason = f"Provider error: {exc}"
            return

        job.prompt_tokens += result.prompt_tokens
        job.completion_tokens += result.completion_tokens

        # Parse files from response
        files = _parse_files(result.response)
        if not files:
            job.status = JobStatus.FAILED
            job.failure_reason = "Drone response contained no parseable files."
            return

        job.files = files

        # Write to worktree and compile
        if job.worktree_path:
            worktree.write_files(job.worktree_path, files)
            job.status = JobStatus.COMPILING
            compile_result = compile.run(job.worktree_path)

            if compile_result.success:
                job.status = JobStatus.READY
                job.errors = []
                return

            if round_num >= MAX_CORRECTION_ROUNDS:
                break

            # Feed errors back into next round
            job.errors = [compile_result.output]
            prompt = (
                f"{prompt}\n\n"
                f"# Compilation errors (round {round_num + 1})\n\n"
                f"```\n{compile_result.output}\n```\n\n"
                "Fix all errors above and regenerate the complete files."
            )
        else:
            # No worktree — just mark ready (compile gate skipped)
            job.status = JobStatus.READY
            return

    job.status = JobStatus.FAILED
    job.failure_reason = (
        f"Compile gate still failing after {MAX_CORRECTION_ROUNDS} correction rounds."
    )


def _parse_files(response: str) -> dict[str, str]:
    """
    Parse the drone's response into a dict of {relative_path: content}.

    Expected format per file:
        ### FILE: path/to/file.ext
        ```
        <content>
        ```
    """
    import re
    files: dict[str, str] = {}
    pattern = re.compile(
        r"###\s*FILE:\s*(.+?)\n```(?:\w+)?\n(.*?)```",
        re.DOTALL,
    )
    for match in pattern.finditer(response):
        path = match.group(1).strip()
        content = match.group(2)
        files[path] = content
    return files


# ── MCP Tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def drone_generate(spec: str, model: str, project_path: str) -> str:
    """
    Start a drone code generation job.

    The drone generates code in a git worktree, runs the compile gate, and
    self-corrects on errors (up to 3 rounds) before surfacing to Claude.

    Args:
        spec:         Fine-grained task specification (see docs/spec-format.md).
        model:        Model string, optionally provider-scoped.
                      Examples: "qwen2.5-coder:14b", "ollama/qwen2.5-coder:14b"
        project_path: Absolute path to the git repository root.

    Returns:
        job_id to use with drone_status / drone_result.
    """
    job = store.create(spec=spec, model=model, project_path=project_path)

    # Set up worktree
    branch = f"shepherd/{job.job_id[:8]}"
    try:
        wt_path = worktree.create(project_path, branch)
        job.worktree_path = wt_path
        job.branch = branch
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.failure_reason = f"Worktree creation failed: {exc}"
        return job.job_id

    # Run pipeline in background — Claude polls via drone_status
    thread = threading.Thread(target=_run_pipeline, args=(job.job_id,), daemon=True)
    thread.start()

    return job.job_id


@mcp.tool()
def drone_status(job_id: str) -> str:
    """
    Get the current status of a drone job.

    Returns one of: pending | generating | compiling | correcting | reviewing | ready | failed
    """
    try:
        job = store.get(job_id)
    except KeyError:
        return "error: unknown job_id"
    return job.status.value


@mcp.tool()
def drone_result(job_id: str) -> str:
    """
    Get the full result of a completed drone job.

    Only meaningful once drone_status returns 'ready' or 'failed'.
    Returns a JSON summary: files changed, errors, correction rounds, token counts.
    """
    try:
        job = store.get(job_id)
    except KeyError:
        return json.dumps({"error": f"Unknown job_id {job_id!r}"})

    return json.dumps({
        "status": job.status.value,
        "files": list(job.files.keys()),
        "errors": job.errors,
        "failure_reason": job.failure_reason,
        "correction_rounds": job.correction_rounds,
        "review_notes": job.review_notes,
        "tokens": {
            "prompt": job.prompt_tokens,
            "completion": job.completion_tokens,
        },
    }, indent=2)


@mcp.tool()
def drone_approve(job_id: str) -> str:
    """
    Approve a completed drone job and merge its worktree branch into the current branch.

    Only call this after reviewing drone_result and being satisfied with the output.
    """
    try:
        job = store.get(job_id)
    except KeyError:
        return f"Error: unknown job_id {job_id!r}"

    if job.status != JobStatus.READY:
        return f"Error: job is {job.status.value}, not ready. Cannot approve."

    if not job.worktree_path or not job.branch:
        return "Error: job has no worktree to merge."

    try:
        worktree.merge(job.project_path, job.branch, job.worktree_path)
        job.status = JobStatus.FAILED  # Mark consumed so it can't be approved twice
        job.failure_reason = "Approved and merged."
        return f"Merged branch {job.branch!r} into working tree."
    except Exception as exc:
        return f"Merge failed: {exc}"


@mcp.tool()
def drone_reject(job_id: str, feedback: str) -> str:
    """
    Reject a drone job and re-queue it with additional feedback.

    The feedback is appended to the original spec and the pipeline reruns.

    Args:
        job_id:   Job to reject.
        feedback: Specific instructions for the drone on what to fix.
    """
    try:
        job = store.get(job_id)
    except KeyError:
        return f"Error: unknown job_id {job_id!r}"

    if job.status not in (JobStatus.READY, JobStatus.FAILED):
        return f"Error: job is {job.status.value}. Can only reject ready or failed jobs."

    job.feedback = feedback
    job.status = JobStatus.PENDING
    job.errors = []
    job.correction_rounds = 0
    job.prompt_tokens = 0
    job.completion_tokens = 0
    job.review_notes = None
    job.failure_reason = None

    thread = threading.Thread(target=_run_pipeline, args=(job.job_id,), daemon=True)
    thread.start()

    return f"Job {job_id} re-queued with feedback."


@mcp.tool()
def drone_list() -> str:
    """List all jobs and their current status."""
    jobs = store.all()
    if not jobs:
        return "No jobs."
    return json.dumps([
        {"job_id": j.job_id, "status": j.status.value, "model": j.model}
        for j in jobs
    ], indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
