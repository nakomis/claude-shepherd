"""Ollama drone provider — local, free."""

import httpx
from .base import DroneProvider, DroneResult

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_TIMEOUT = 300  # seconds — local models can be slow


class OllamaProvider(DroneProvider):
    def __init__(self, base_url: str = OLLAMA_BASE):
        self.base_url = base_url

    def generate(self, prompt: str, system_prompt: str, model: str) -> DroneResult:
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        with httpx.Client(base_url=self.base_url, timeout=DEFAULT_TIMEOUT) as client:
            r = client.post("/api/generate", json=payload)
            r.raise_for_status()
            data = r.json()

        return DroneResult(
            response=data["response"],
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            model=model,
            provider="ollama",
        )
