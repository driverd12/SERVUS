# MCP Playground Hub Connect

This server runs as a local-first MCP hub with STDIO or Streamable HTTP transport.

## Node Version

`better-sqlite3` currently expects Node LTS and a C++20 toolchain. Use Node 22 (recommended).

## STDIO (MVP)

Run:

```bash
npm run build
npm run start:stdio
```

Use your client to connect via STDIO:

- Cursor: Add an MCP server entry pointing to `node /Users/dan.driver/Cursor_projects/python/SERVUS/dist/server.js`.
- Codex: Add a local MCP tool using the same command.
- VS Code Copilot Chat: Configure MCP with the command above.

Notes:

- The server loads `.env` from the repo root automatically. Set `DOTENV_CONFIG_PATH=/path/to/.env` to override.
- The SQLite path defaults to `/Users/dan.driver/Cursor_projects/python/SERVUS/data/hub.sqlite`. Set `MCP_HUB_DB_PATH=/absolute/path/to/hub.sqlite` to override (useful for isolated test runs).
- Use the direct `node /Users/dan.driver/Cursor_projects/python/SERVUS/dist/server.js` command (no `-r dotenv/config`) so clients that do not set `cwd` can resolve dependencies.
- API keys are not required for local continuity workflows.

## HTTP (Streamable)

Run:

```bash
npm run build
MCP_HTTP_BEARER_TOKEN="your-token" MCP_HTTP_ALLOWED_ORIGINS="http://localhost,http://127.0.0.1" npm run start:http
```

Notes:

- The server only binds to `127.0.0.1` or `localhost`.
- Requests require `Authorization: Bearer your-token`.
- Requests must include an `Origin` that matches `MCP_HTTP_ALLOWED_ORIGINS`.
- You can also set `MCP_HTTP_BEARER_TOKEN` and `MCP_HTTP_ALLOWED_ORIGINS` in `.env`.

### `.env` (recommended)

```bash
MCP_HTTP_BEARER_TOKEN=dev-token
MCP_HTTP_ALLOWED_ORIGINS=http://localhost,http://127.0.0.1
```

## Data Migration

- SQLite data lives at `./data/hub.sqlite` (plus `-wal` and `-shm`).
- To move to a new machine, copy the entire `data/` directory and your `.env`.
- If you use `MCP_HUB_DB_PATH`, migrate that custom SQLite file instead.

## Validation

Run the full local MCP integration suite:

```bash
npm test
```

This command rebuilds the server and executes end-to-end tool tests against a temporary isolated SQLite database.

## Tool Overview

Core continuity tools:
- `memory.append`, `memory.search`
- `transcript.append`, `transcript.summarize`
- `adr.create`
- `who_knows`, `knowledge.query`

v0.2 orchestration and safety tools:
- `policy.evaluate`
- `run.begin`, `run.step`, `run.end`, `run.timeline`
- `mutation.check`
- `preflight.check`, `postflight.verify`
- `lock.acquire`, `lock.release`
- `knowledge.promote`, `knowledge.decay`
- `retrieval.hybrid`
- `decision.link`
- `simulate.workflow`
- `health.tools`, `health.storage`, `health.policy`
- `incident.open`, `incident.timeline`
- `query.plan`

## Local-Only Knowledge Mode

- This MCP hub now operates as a local shared knowledge base for IDE clients.
- `consult.openai` and `consult.gemini` are disabled and should not be used for continuity workflows.
- `transcript.summarize` is deterministic and local (no provider API call).
- Capture "who wrote this" by setting:
  - `source_client` (for example: `cursor`, `codex`)
  - `source_model` (for example: `claude-opus-4.1`, `gpt-5.3-codex`)
  - `source_agent` (for example: `assistant`, `planner`, `reviewer`)
- Mutating tools require:
  - `mutation.idempotency_key`
  - `mutation.side_effect_fingerprint`
