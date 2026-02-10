# Rolling Notes for SERVUS

- **DECISION:** Add a local-first MCP server (`mcp-playground-hub`) alongside SERVUS to share memory, transcripts, and ADR creation via MCP.
- **CONTEXT:** Need a shared MCP hub for multiple clients with safe local persistence and optional provider consults.
- **CONSEQUENCES:** Easier cross-client knowledge capture; adds a Node/TS build path and local SQLite file.
- **ROLLBACK:** Remove `src/`, `docs/CONNECT.md`, `docs/SECURITY.md`, `package.json`, `tsconfig.json`, and `data/hub.sqlite`.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/src/server.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/src/storage.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/CONNECT.md, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/SECURITY.md

- **DECISION:** Pin Node support for the MCP hub to Node 20-22 and document Node 22 usage to avoid native addon build failures.
- **CONTEXT:** `better-sqlite3` failed to build under Node 25 (C++20 requirement and ABI mismatch).
- **CONSEQUENCES:** Requires Node LTS; reduces install failures on macOS.
- **ROLLBACK:** Remove the Node engines entry, delete `.nvmrc`, and revert the CONNECT.md note.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/package.json, /Users/dan.driver/Cursor_projects/python/SERVUS/.nvmrc, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/CONNECT.md

- **DECISION:** Upgrade MCP SDK to 1.26.0 to use Streamable HTTP transport (`server/streamableHttp`).
- **CONTEXT:** SDK 0.6.1 lacks streamable HTTP exports, causing build/runtime failures.
- **CONSEQUENCES:** Adds newer SDK dependency; HTTP transport compiles and runs as specified.
- **ROLLBACK:** Downgrade `@modelcontextprotocol/sdk` in package.json and revert `src/transports/http.ts`.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/package.json, /Users/dan.driver/Cursor_projects/python/SERVUS/src/transports/http.ts

- **DECISION:** Add `npm run start:http` helper script for faster HTTP startup.
- **CONTEXT:** Reduce manual typing and ensure consistent HTTP launch flags.
- **CONSEQUENCES:** Slightly more convenience; still requires `MCP_HTTP_BEARER_TOKEN` env.
- **ROLLBACK:** Remove the `start:http` script from package.json and revert CONNECT.md change.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/package.json, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/CONNECT.md

- **DECISION:** Load `.env` for HTTP startup via `dotenv` and document MCP token defaults in `.env.example`.
- **CONTEXT:** Reduce manual setup and ensure consistent HTTP token usage across runs.
- **CONSEQUENCES:** Adds a small dependency and encourages storing the bearer token locally.
- **ROLLBACK:** Remove `dotenv`, revert `start:http`, and delete MCP lines from `.env.example`.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/package.json, /Users/dan.driver/Cursor_projects/python/SERVUS/.env.example, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/CONNECT.md

- **DECISION:** Add `start:stdio` script that loads `.env` and document data migration steps.
- **CONTEXT:** Provide consistent startup and simple portability across machines.
- **CONSEQUENCES:** Easier local usage and safer migration guidance.
- **ROLLBACK:** Remove the `start:stdio` script and revert CONNECT.md updates.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/package.json, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/CONNECT.md

- **DECISION:** Resolve MCP hub paths relative to the repo root and load `.env` without CLI preloads.
- **CONTEXT:** MCP clients that do not set `cwd` failed to resolve `dotenv/config` and could write data or run scripts from the wrong directory.
- **CONSEQUENCES:** More reliable MCP startup; `.env`, SQLite data, and ADR scripts resolve consistently.
- **ROLLBACK:** Revert changes in `src/server.ts`, `src/tools/adr.ts`, `package.json`, and related docs.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/src/server.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/src/tools/adr.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/package.json, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/CONNECT.md
