# Drone Spec Format

The spec is the most important input to the pipeline. A tight spec dramatically reduces correction rounds.

## Template

```markdown
## Spec: <short title>

**target_file**: path/to/file.py          (relative to repo root)
**action**: create | patch | delete

**description**:
One paragraph — what the file does and why it exists.

**interfaces**:
Exact signatures the drone must implement. Copy-paste or write precisely.
- `class Foo(bar: int, baz: str)`
- `def method(self) -> bool`
(For TypeScript: exact type definitions, copy from source where possible.)

**dependencies**:
Exact import paths — drones hallucinate package names.
- stdlib: `time`, `os`
- third-party: `import { Foo } from '@aws-sdk/client-dynamodb'`
- internal: `from .jobs import JobStore`

**env_vars**: (for Lambda/CDK projects)
Environment variable names exactly as CDK sets them:
- TABLE_NAME
- COGNITO_USER_POOL_ID

**constraints**:
Explicit rules the drone must follow; the reviewer checks each one.
- Use `time.monotonic()`, not `time.time()`
- Route must be GET /things/{id}, not POST
- Never use X — use Y instead

**related_files**: (optional)
Files the drone should read for context or consistency.
- `shepherd_mcp/jobs.py` — JobStore pattern to follow
- `infra/lib/api-stack.ts` — to match existing route registration

**test_file**: (optional)
Path to test file written by Claude before the drone job was started.
The compile gate will run pytest against it automatically.
- `shepherd-mcp/tests/test_foo.py`
```

## Field guidance

**target_file** — always relative to the repository root, not the Python package root. In a monorepo subdirectory, include the subdirectory prefix: `shepherd-mcp/shepherd_mcp/compile.py`, not `shepherd_mcp/compile.py`. This is the single most common cause of PATCH failures.

**action** — `create` for new files (drone uses `### FILE:` header); `patch` for modifications (drone uses `### PATCH:` with FIND/REPLACE blocks). Never ask for `create` when patching — drones that output a full file when a patch was needed risk clobbering unrelated code.

**interfaces** — the most important field for reviewer accuracy. Be exact. If a method returns `int`, say so. If a class takes keyword-only arguments, show that. Ambiguity here is the leading cause of reviewer rejections.

**constraints** — write as rules the reviewer can verify without running the code. "Thread-safe" is too vague; "use `threading.Lock` in `acquire()`" is checkable.

**test_file** — when present, the compile gate runs pytest after pyflakes. Write tests before firing the drone job (test-first workflow). The drone receives the test file path so it knows what to pass.

## Patch specs

When `action: patch`, include the exact current code in the spec so the FIND text is unambiguous:

```
The current implementation (copy this exactly as FIND text):

    def _pycompile(worktree_path: str) -> CompileResult:
        result = subprocess.run(...)
        ...

Replace it with a version that also runs pytest.
```

Drones cannot read the worktree — they will hallucinate the existing content if you don't provide it.

## Reviewer checklist mapping

The reviewer agent checks:
- **Spec compliance**: every `interfaces` entry present with correct signature
- **Correctness**: logic matches `description`; all `constraints` satisfied
- **Project conventions**: imports match `dependencies`; no extras
- **Scope**: no unprompted additions unless harmless

The reviewer is given the spec verbatim alongside the generated files. Fields not present are not checked.
