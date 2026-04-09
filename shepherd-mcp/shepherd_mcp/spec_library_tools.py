from mcp.server.fastmcp import FastMCP
import json
from . import spec_library

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def spec_fragment_list(project_path: str) -> str:
        fragments = spec_library.get_fragments(project_path)
        if not fragments:
            return "No fragments."
        return json.dumps([{"name": frag.name, "content": frag.content} for frag in fragments])

    @mcp.tool()
    def spec_fragment_add(project_path: str, name: str, content: str) -> str:
        spec_library.add_fragment(project_path, name, content)
        return f"Fragment {name!r} saved."

    @mcp.tool()
    def spec_fragment_remove(project_path: str, name: str) -> str:
        if spec_library.remove_fragment(project_path, name):
            return f"Fragment {name!r} removed."
        else:
            return f"Fragment {name!r} not found."
