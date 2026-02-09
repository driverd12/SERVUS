# MCP Playground Hub Security

## Scope

- Local-first server with SQLite persistence in `./data/hub.sqlite`.
- STDIO transport has no network surface.
- HTTP transport is bound to loopback only.

## HTTP Guardrails

- Requires `Authorization: Bearer <token>` with `MCP_HTTP_BEARER_TOKEN`.
- Validates `Origin` against `MCP_HTTP_ALLOWED_ORIGINS`.
- Rejects requests with invalid or missing Origin or token using HTTP 403.
- Does not bind to `0.0.0.0`.

## Data Handling

- Uses SQLite WAL mode for durability.
- Logs are emitted to stderr only.
- No secrets are persisted to disk by default.

## External Providers

- OpenAI and Gemini are optional; calls are skipped when keys are missing.
- Provider failures are captured and returned without crashing the server.
