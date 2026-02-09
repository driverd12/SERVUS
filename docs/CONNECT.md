# MCP Playground Hub Connect

This server runs as a local-first MCP hub with STDIO or Streamable HTTP transport.

## STDIO (MVP)

Run:

```bash
npm run build
node dist/server.js
```

Use your client to connect via STDIO:

- Cursor: Add an MCP server entry pointing to `node /Users/dan.driver/Cursor_projects/python/SERVUS/dist/server.js`.
- Codex: Add a local MCP tool using the same command.
- VS Code Copilot Chat: Configure MCP with the command above.

## HTTP (Streamable)

Run:

```bash
MCP_HTTP=1 \
MCP_HTTP_BEARER_TOKEN="your-token" \
MCP_HTTP_ALLOWED_ORIGINS="http://localhost,http://127.0.0.1" \
npm run build && node dist/server.js --http --http-port 8787
```

Notes:

- The server only binds to `127.0.0.1` or `localhost`.
- Requests require `Authorization: Bearer your-token`.
- Requests must include an `Origin` that matches `MCP_HTTP_ALLOWED_ORIGINS`.

## Tool Overview

- `memory.append`, `memory.search`
- `transcript.append`, `transcript.summarize`
- `adr.create`
- `who_knows`
- `consult.openai`, `consult.gemini`
