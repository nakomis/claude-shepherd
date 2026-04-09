import json
from typing import List

# Assuming necessary imports are already present
# from some_module import mcp, store, Job

def drone_list():
    jobs = store.all()
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
    # Main function implementation
    pass

if __name__ == "__main__":
    main()
