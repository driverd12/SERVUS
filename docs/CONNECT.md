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

## Tool Overview

- `memory.append`, `memory.search`
- `transcript.append`, `transcript.summarize`
- `adr.create`
- `who_knows`, `knowledge.query`

## Local-Only Knowledge Mode

- This MCP hub now operates as a local shared knowledge base for IDE clients.
- `consult.openai` and `consult.gemini` are disabled and should not be used for continuity workflows.
- `transcript.summarize` is deterministic and local (no provider API call).
- Capture "who wrote this" by setting:
  - `source_client` (for example: `cursor`, `codex`)
  - `source_model` (for example: `claude-opus-4.1`, `gpt-5.3-codex`)
  - `source_agent` (for example: `assistant`, `planner`, `reviewer`)
