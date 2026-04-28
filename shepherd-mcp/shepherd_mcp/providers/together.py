"""Together.ai drone provider — OpenAI-compatible API, pay-as-you-go."""

import os
import subprocess
import httpx
from .base import DroneProvider, DroneResult

TOGETHER_BASE = "https://api.together.xyz/v1"
DEFAULT_TIMEOUT = 300  # seconds


def _get_api_key() -> str:
    key = os.environ.get("TOGETHER_API_KEY")
    if key:
        return key
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "together", "-a", "api-key", "-w"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        raise RuntimeError(
            "Together.ai API key not found. Set TOGETHER_API_KEY env var or store it in "
            "macOS Keychain: security add-generic-password -s together -a api-key -w <key>"
        )


class TogetherProvider(DroneProvider):
    def __init__(self, base_url: str = TOGETHER_BASE):
        self.base_url = base_url

    def generate(self, prompt: str, system_prompt: str, model: str) -> DroneResult:
        api_key = _get_api_key()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
        }

        with httpx.Client(base_url=self.base_url, timeout=DEFAULT_TIMEOUT) as client:
            r = client.post("/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return DroneResult(
            response=choice["message"]["content"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=model,
            provider="together",
        )
