# Known-Errors FAQ

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
