# Rolling Notes for SERVUS

- **DECISION:** Add a local-first MCP server (`mcp-playground-hub`) alongside SERVUS to share memory, transcripts, and ADR creation via MCP.
- **CONTEXT:** Need a shared MCP hub for multiple clients with safe local persistence and optional provider consults.
- **CONSEQUENCES:** Easier cross-client knowledge capture; adds a Node/TS build path and local SQLite file.
- **ROLLBACK:** Remove `src/`, `docs/CONNECT.md`, `docs/SECURITY.md`, `package.json`, `tsconfig.json`, and `data/hub.sqlite`.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/src/server.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/src/storage.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/CONNECT.md, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/SECURITY.md
