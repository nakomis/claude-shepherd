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
from . import worktree, compile, faq, drone_log, faq_tools, spec_library, spec_library_tools

mcp = FastMCP("shepherd-mcp")
faq_tools.register(mcp)
spec_library_tools.register(mcp)

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
    try:
        _run_pipeline_inner(job_id)
    except Exception as exc:
        import traceback
        try:
            job = store.get(job_id)
            job.status = JobStatus.FAILED
            job.failure_reason = f"Unexpected pipeline error: {exc}"
            drone_log.append(job_id, "pipeline_crash", error=str(exc),
                             traceback=traceback.format_exc())
        except Exception:
            pass  # store gone (server restart race) — nothing to do


def _run_pipeline_inner(job_id: str) -> None:
    job = store.get(job_id)
    provider, model_name = _resolve_provider(job.model)

    system = faq.system_prompt(
        "You are a code generation assistant. Output only valid source code files or patches.\n\n"
        "For a NEW file or COMPLETE replacement, use:\n"
        "### FILE: <relative/path/to/file.ext>\n"
        "```\n"
        "<full file content>\n"
        "```\n\n"
        "For a MODIFICATION to an existing file, output a unified diff patch:\n"
        "### PATCH: <relative/path/to/file.ext>\n"
        "```diff\n"
        "<unified diff — must include enough context lines for `git apply` to locate the hunk>\n"
        "```\n\n"
        "Do not include explanations outside of code comments. "
        "Never output a complete file when a patch is sufficient."
    )

    fragments = spec_library.fragments_for_prompt(job.project_path)
    prompt = job.spec
    if fragments:
        prompt = f"{fragments}\n{prompt}"
    if job.feedback:
        prompt = f"{prompt}\n\n# Reviewer feedback\n\n{job.feedback}"

    drone_log.append(job_id, "pipeline_start",
                     model=job.model, project_path=job.project_path,
                     worktree=job.worktree_path, system_prompt=system, spec=prompt)

    for round_num in range(MAX_CORRECTION_ROUNDS + 1):
        # Generate
        job.status = JobStatus.GENERATING if round_num == 0 else JobStatus.CORRECTING
        job.correction_rounds = round_num

        drone_log.append(job_id, "generate_start", round=round_num, prompt=prompt)

        try:
            result = provider.generate(prompt, system, model_name)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.failure_reason = f"Provider error: {exc}"
            drone_log.append(job_id, "provider_error", error=str(exc))
            return

        job.prompt_tokens += result.prompt_tokens
        job.completion_tokens += result.completion_tokens

        drone_log.append(job_id, "generate_complete", round=round_num,
                         prompt_tokens=result.prompt_tokens,
                         completion_tokens=result.completion_tokens,
                         response=result.response)

        # Parse files and patches from response
        files, patches = _parse_response(result.response)
        if not files and not patches:
            job.status = JobStatus.FAILED
            job.failure_reason = "Drone response contained no parseable files or patches."
            drone_log.append(job_id, "parse_failed", response=result.response)
            return

        job.files = files
        drone_log.append(job_id, "files_parsed",
                         files=list(files.keys()), patches=len(patches))

        # Write to worktree, commit, and compile
        if job.worktree_path:
            commit_msg = f"shepherd: drone generation (round {round_num + 1})"
            if files:
                worktree.write_and_commit(job.worktree_path, files, commit_msg)
            if patches:
                try:
                    worktree.apply_patches(job.worktree_path, patches)
                    _run_git_commit(job.worktree_path, commit_msg)
                except RuntimeError as exc:
                    # git apply failed — treat as a compile error so the drone can correct
                    patch_error = f"git apply failed: {exc}"
                    drone_log.append(job_id, "patch_failed", round=round_num, error=patch_error)
                    if round_num >= MAX_CORRECTION_ROUNDS:
                        job.status = JobStatus.FAILED
                        job.failure_reason = patch_error
                        return
                    job.errors = [patch_error]
                    prompt = (
                        f"{prompt}\n\n"
                        f"# Patch application error (round {round_num + 1})\n\n"
                        f"```\n{patch_error}\n```\n\n"
                        "The patch could not be applied. Output a corrected PATCH with valid unified diff format "
                        "and enough context lines for `git apply` to locate the hunk."
                    )
                    continue
            job.status = JobStatus.COMPILING
            compile_result = compile.run(job.worktree_path)

            drone_log.append(job_id, "compile", round=round_num,
                             success=compile_result.success, output=compile_result.output)

            if compile_result.success:
                job.status = JobStatus.READY
                job.errors = []
                drone_log.append(job_id, "pipeline_complete",
                                 correction_rounds=round_num,
                                 total_prompt_tokens=job.prompt_tokens,
                                 total_completion_tokens=job.completion_tokens)
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
            drone_log.append(job_id, "pipeline_complete_no_compile",
                             total_prompt_tokens=job.prompt_tokens,
                             total_completion_tokens=job.completion_tokens)
            return

    job.status = JobStatus.FAILED
    job.failure_reason = (
        f"Compile gate still failing after {MAX_CORRECTION_ROUNDS} correction rounds."
    )
    drone_log.append(job_id, "pipeline_failed", reason=job.failure_reason,
                     total_prompt_tokens=job.prompt_tokens,
                     total_completion_tokens=job.completion_tokens)


def _parse_response(response: str) -> tuple[dict[str, str], list[str]]:
    """
    Parse the drone's response into full files and unified diff patches.

    Recognised header formats:
        ### FILE: path/to/file.ext    — full file (new or replacement)
        ### PATCH: path/to/file.ext   — unified diff, applied via `git apply`
        ### path/to/file.ext          — treated as FILE (legacy, drones often omit the keyword)

    Both must be followed by a fenced code block.
    Returns (files, patches) where:
        files   = {relative_path: full_content}
        patches = [raw_unified_diff_string, ...]
    """
    import re
    files: dict[str, str] = {}
    patches: list[str] = []
    BLOCK = r"```[^\n]*\n(.*?)```"

    # PATCH blocks — explicit keyword required, path captured separately
    patch_spans: set[tuple[int, int]] = set()
    for m in re.finditer(r"###\s*PATCH:\s*([^\n]+)\n" + BLOCK, response, re.DOTALL):
        patches.append(m.group(2))
        patch_spans.add((m.start(), m.end()))

    # FILE blocks — keyword optional (legacy drones omit it); skip any PATCH span
    for m in re.finditer(r"###\s*(?:FILE:\s*)?([^\n]+?\.[^\n]+?)\n" + BLOCK, response, re.DOTALL):
        if any(m.start() >= s and m.end() <= e for s, e in patch_spans):
            continue
        path = m.group(1).strip()
        files[path] = m.group(2)
    return files, patches


def _run_git_commit(worktree_path: str, message: str) -> None:
    """Stage all changes and commit in the worktree (used after patch application)."""
    import subprocess
    for cmd in (["git", "add", "-A"], ["git", "commit", "-m", message]):
        r = subprocess.run(cmd, cwd=worktree_path, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{cmd} failed:\n{r.stderr}")


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
def drone_wait(job_id: str, timeout: int = 600) -> str:
    """
    Block until a drone job reaches 'ready' or 'failed', then return its status.

    Replaces repeated drone_status polling with a single call.
    Times out after `timeout` seconds (default 600 = 10 minutes).

    Args:
        job_id:  Job to wait for.
        timeout: Maximum seconds to wait before returning 'timeout'.
    """
    import time
    try:
        job = store.get(job_id)
    except KeyError:
        return "error: unknown job_id"

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if job.status in (JobStatus.READY, JobStatus.FAILED):
            return job.status.value
        time.sleep(3)
    return f"timeout after {timeout}s (current status: {job.status.value})"


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


@mcp.tool()
def drone_cost_summary() -> str:
    """Summarise token usage and estimated cost across all jobs in this session."""
    jobs = store.all()
    total_prompt = sum(j.prompt_tokens for j in jobs)
    total_completion = sum(j.completion_tokens for j in jobs)
    has_paid = any("/" in j.model and not j.model.startswith("ollama/") for j in jobs)
    estimated_cost = "unknown (paid provider present)" if has_paid else "£0.00 (all Ollama)"
    return json.dumps({
        "total_jobs": len(jobs),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "estimated_cost": estimated_cost,
        "per_job": [
            {
                "job_id": j.job_id,
                "model": j.model,
                "status": j.status.value,
                "prompt_tokens": j.prompt_tokens,
                "completion_tokens": j.completion_tokens,
                "correction_rounds": j.correction_rounds,
            }
            for j in jobs
        ],
    }, indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
