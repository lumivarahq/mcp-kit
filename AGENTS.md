# mcp-kit

Production-grade MCP server starter + cookbook: one hardened TypeScript base (`@mcp-kit/core`),
a Python twin, four worked recipes, and a tool-description lint that gates CI.
Lumivara product line: **Forge** (reusable engine/template; `-kit` naming convention).

## Package manager: pnpm (NOT npm) — pnpm@11.5.1, Node >=20
pnpm workspace; `node-linker=hoisted` (.npmrc) so all packages share root dev tooling (typescript, tsx, vitest).

## Commands (from README "Develop" — authoritative)
- `pnpm install`
- `pnpm build`      — build all packages topologically (`@mcp-kit/core` first, then recipes that import it)
- `pnpm typecheck`  — `tsc --noEmit`, every package
- `pnpm test`       — vitest, every package
- `pnpm lint:tools` — the tool-description lint (`@mcp-kit/lint`); non-zero exit fails CI
- `pnpm check`      — build + typecheck + test + lint:tools, in order = **the CI gate**

Run the starter:
```
MCP_TRANSPORT=stdio node starter/dist/cli.js
MCP_TRANSPORT=http MCP_HTTP_PORT=3000 MCP_AUTH_TOKEN=s3cret node starter/dist/cli.js
```
Inspect: `npx @modelcontextprotocol/inspector --cli node starter/dist/cli.js --method tools/list`

## Layout (pnpm workspaces: starter, recipes/*, lint)
- `starter/`        — `@mcp-kit/core`: importable base + runnable CLI. src/{server,serve,cli,auth,config,errors,result,tool,testing}.ts; transports/{stdio,http}.ts; tools/. Exports `.` and `./testing`. dep: @modelcontextprotocol/sdk, express@5, zod@4.
- `python-twin/`    — FastMCP mirror (`mcp-kit-starter`), uv/venv, Python >=3.11, pytest. Same transports/auth/errors.
- `recipes/wrap-rest-api`   — `@mcp-kit/recipe-rest`: GitHub (public, runs as-is) + Anaplan (needs tenant), shared REST client.
- `recipes/wrap-sql-db`     — read-only parameterised SQL over node:sqlite (seeded demo).
- `recipes/long-running-job`— start → poll → cancel, returns a job id (in-memory).
- `recipes/paginated-search`— opaque cursor pagination (in-memory).
- `lint/describe-lint.ts`   — `@mcp-kit/lint` + rubric.md.
- `docs/`           — transports, schema-design, auth-patterns, hcd-audit.

## Deploy: none — this is a library/starter, not a hosted app. No Vercel project.

## Gotchas / invariants
- stdout is the JSON-RPC channel; logs MUST go to stderr.
- Lint **hard-fails any tool that puts a credential in its inputs** (auth lives at the transport). All tools must score 100/100; keep verb-first names + when-to-use + non-goals + described params + examples.
- Recipes import `@mcp-kit/core` via `workspace:*` — build core before recipes (`pnpm build` handles order).
- Transport via env: `MCP_TRANSPORT` (stdio|http), `MCP_HTTP_PORT`, `MCP_AUTH_TOKEN`.
- Python twin must stay a faithful mirror of starter (same transports, auth, errors).
