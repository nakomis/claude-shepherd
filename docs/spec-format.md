# Drone Spec Format

The spec is the most important input to the pipeline. A tight spec dramatically reduces correction rounds.

## Fields

```
# Task: <short title>

## target_files
- path/to/file1.ts
- path/to/file2.ts

## description
What these files do and why.

## interfaces
Exact TypeScript types / function signatures the code must implement or consume.
Copy from existing source where possible — the drone must match exactly.

## dependencies
Exact package names and import paths the drone should use:
- `import { Foo } from '@aws-sdk/client-dynamodb'`
- `import { Bar } from 'aws-cdk-lib/aws-s3'`

## env_vars
Environment variable names as set by CDK (Lambda reads these at runtime):
- TABLE_NAME
- COGNITO_USER_POOL_ID

## constraints
Explicit rules for this task:
- Never use X — use Y instead
- Always include Z field in DynamoDB items
- Route must be GET /things/{id}, not POST

## example_input / example_output (optional)
For Lambda handlers: example event + expected response body.
For CDK constructs: example instantiation.

## related_files (optional)
Paths to read for cross-file consistency:
- infra/lib/api-stack.ts  (to match existing route registration pattern)
- web/src/api/client.ts   (to match fetch helper pattern)
```

## Tips

- Include exact import paths — drones hallucinate package names.
- Copy exact TypeScript interface definitions from existing source rather than describing them in prose.
- List env_vars by the name CDK sets them, not what you'd like to call them.
- Be explicit about HTTP methods — drones frequently mismatch GET/POST between frontend and backend.
