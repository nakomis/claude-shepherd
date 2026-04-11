# Known-Errors FAQ

## shepherd-mcp internals

- `store` is a `JobStore` instance — it has `.all()` (returns `list[DroneJob]`) and `.get(job_id)`. It does NOT have `.values()`, `.items()`, or support `len()`. Use `len(store.all())` not `len(store)`.
- Every MCP tool function must have `@mcp.tool()` immediately above the `def` line. A function without this decorator will not be registered and Claude will never see it.
- Do not output a complete modified file when only adding a function — stub out the existing context. Instead output only the new function or the new file.



Prepended to every drone system prompt. Each rule here eliminates a class of error before compilation runs.

Rules are seeded from the nakomis-scrum project drone correction taxonomy. Add new rules whenever a drone error reaches the Claude gate — tag with the project and date.

---

## AWS SDK

- Always use AWS SDK v3. Never use `new AWS.DynamoDB.DocumentClient()` — that is v2.
- Correct v3 pattern: `DynamoDBDocumentClient.from(new DynamoDBClient({}))`
- Import DynamoDBClient from `@aws-sdk/client-dynamodb`
- Import document client commands (GetCommand, PutCommand, QueryCommand, etc.) from `@aws-sdk/lib-dynamodb`

## MUI

- Use `@mui/material` v6. Never import from `@material-ui/core` (v4 — no longer used).
- Use the `sx` prop for styling, not `makeStyles`.

## React / TypeScript

- Named imports only: `import { useAuth } from 'react-oidc-context'`, `import { useNavigate } from 'react-router-dom'`. Never use default imports for these.
- Do not import React if only using JSX. The JSX transform handles it. `noUnusedLocals` will error on an unused React import.

## CDK / CloudFront

- Use `S3OriginAccessControl`, not `OriginAccessControl` (the generic one is not for S3).
- When passing an API Gateway endpoint to `HttpOrigin`, strip the `https://` prefix first. `HttpOrigin` does not accept URLs with a protocol scheme.

## Lambda / API Gateway HTTP API

- HTTP headers in Lambda (HTTP API, not REST API): access as `event.headers.authorization` (lowercase). The runtime lowercases all header names.
- Do not assume `event.headers.Authorization` — always use lowercase, or check both with `?? `.

## Route53

- Always set `recordName` explicitly on `ARecord`. Omitting it defaults to the zone apex, which is almost never what you want for a subdomain record.

## WebSocket / TypeScript types

- `event.queryStringParameters` is not typed on `APIGatewayProxyWebsocketHandlerV2`. Cast with `(event as any).queryStringParameters` until `@types/aws-lambda` catches up.


## Output format: FILE vs PATCH

- Use `### FILE: path` only for **new files** or deliberate **complete rewrites**.
- Use `### PATCH: path` for **modifications to existing files**. Output a unified diff with sufficient context lines (3+) for `git apply` to locate the hunk.
- Never output a complete file when only adding or changing a function — the pipeline will overwrite the whole file and destroy any functions not in your context window.
- `### PATCH:` blocks must contain a valid unified diff (starting with `--- a/...` / `+++ b/...` headers). Do not output the raw new content inside a PATCH block.


PATCH paths must be relative to the repository root, not the Python package root. If the project is a monorepo with a subdirectory (e.g. shepherd-mcp/), the PATCH header must include that subdirectory prefix. Example: use `shepherd-mcp/shepherd_mcp/compile.py`, not `shepherd_mcp/compile.py`. When in doubt, always check the spec for the full path from the repo root.


When writing PATCH FIND text to insert between two top-level Python functions, use exactly two blank lines (three newlines) between them — this is PEP 8 convention and what the file will contain. Using one blank line (two newlines) will cause FIND text not found errors. Example: the boundary between `drone_result` and `drone_approve` is `    }, indent=2)\n\n\n@mcp.tool()\ndef drone_approve`.
