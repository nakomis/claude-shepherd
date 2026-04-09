from pathlib import Path

def _fragments_dir(project_path: str) -> Path:
    return Path(__file__).parent.parent.parent / "ignored" / "spec-fragments" / Path(project_path).name

def get_fragments(project_path: str) -> dict[str, str]:
    """Return all fragments for a project as {name: content}."""
    fragments_dir = _fragments_dir(project_path)
    if not fragments_dir.exists():
        return {}
    
    fragments = {}
    for file in fragments_dir.glob("*.md"):
        with open(file, 'r', encoding='utf-8') as f:
            fragments[file.stem] = f.read()
    return fragments

def add_fragment(project_path: str, name: str, content: str) -> None:
    """Write a fragment. name is used as the filename (sanitise to safe chars)."""
    fragments_dir = _fragments_dir(project_path)
    fragments_dir.mkdir(parents=True, exist_ok=True)
    
    # Sanitize name to be safe for filenames
    sanitized_name = ''.join(c if c.isalnum() or c in ('_', '-') else '_' for c in name)
    fragment_file = fragments_dir / f"{sanitized_name}.md"
    
    with open(fragment_file, 'w', encoding='utf-8') as f:
        f.write(content)

def remove_fragment(project_path: str, name: str) -> bool:
    """Delete a fragment. Returns True if it existed, False if not."""
    fragments_dir = _fragments_dir(project_path)
    fragment_file = fragments_dir / f"{name}.md"
    
    if fragment_file.exists():
        fragment_file.unlink()
        return True
    return False

def fragments_for_prompt(project_path: str) -> str:
    """Return all fragments formatted for prepending to a drone prompt.
    Format:
      # Spec fragments\n\n## {name}\n\n{content}\n\n  (repeated)
    Returns empty string if no fragments."""
    fragments = get_fragments(project_path)
    if not fragments:
        return ""
    
    prompt_content = "# Spec fragments\n"
    for name, content in fragments.items():
        prompt_content += f"\n## {name}\n\n{content}\n\n"
    return prompt_content
