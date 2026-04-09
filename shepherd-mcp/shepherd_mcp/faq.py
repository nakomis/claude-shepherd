"""Known-errors FAQ — loaded from docs/faq.md and prepended to drone system prompts."""

from pathlib import Path

_FAQ_PATH = Path(__file__).parent.parent.parent / "docs" / "faq.md"


def load() -> str:
    """Return the full FAQ text, or an empty string if the file doesn't exist yet."""
    if _FAQ_PATH.exists():
        return _FAQ_PATH.read_text(encoding="utf-8")
    return ""


def system_prompt(base_system: str = "") -> str:
    """
    Build the full system prompt for a drone, with the FAQ prepended.

    The FAQ comes first so it has the strongest influence on generation.
    """
    faq = load()
    parts = []
    if faq:
        parts.append(f"# Known errors and how to avoid them\n\n{faq}")
    if base_system:
        parts.append(base_system)
    return "\n\n---\n\n".join(parts) if parts else ""
