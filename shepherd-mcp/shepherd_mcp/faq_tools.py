from mcp.server.fastmcp import FastMCP
from .faq import load, _FAQ_PATH


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def faq_list() -> str:
        """Return the current contents of the known-errors FAQ."""
        content = load()
        return content if content.strip() else "FAQ is empty."

    @mcp.tool()
    def faq_add_rule(rule: str) -> str:
        """Append a new rule to the known-errors FAQ."""
        _FAQ_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _FAQ_PATH.open("a", encoding="utf-8") as f:
            f.write(f"\n\n{rule.strip()}\n")
        return "Rule added."
