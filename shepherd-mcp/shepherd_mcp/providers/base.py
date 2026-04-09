"""Base interface for drone LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DroneResult:
    response: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    provider: str


class DroneProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str, model: str) -> DroneResult:
        """Generate a response from the drone model."""
        ...
