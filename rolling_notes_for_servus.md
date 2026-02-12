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

- **DECISION:** Emit inline object JSON Schemas for MCP tool `inputSchema` generation.
- **CONTEXT:** MCP clients validated `tools/list` responses and rejected root `$ref` schemas, resulting in `0 tools` despite a successful server connection.
- **CONSEQUENCES:** Tool discovery now succeeds; existing tool handlers and behavior stay unchanged.
- **ROLLBACK:** Restore `zodToJsonSchema(schema, { name })` in `src/server.ts` and rebuild.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/src/server.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/dist/server.js

- **DECISION:** Add a repo-local Cursor rule that enforces local-first MCP continuity capture.
- **CONTEXT:** Need consistent capture behavior during agent work without sending transcript content to external providers by default.
- **CONSEQUENCES:** Cursor agents should append transcripts per meaningful action and checkpoint locally; provider-backed summarize is now explicit opt-in.
- **ROLLBACK:** Delete `.cursor/rules/mcp_capture_local_first.mdc` and remove the associated policy text from Codex config if desired.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/.cursor/rules/mcp_capture_local_first.mdc, /Users/dan.driver/.codex/config.toml

- **DECISION:** Convert MCP hub consultation/summarization to local-only knowledge workflows and add actor attribution fields.
- **CONTEXT:** Goal is a shared on-device knowledge base across IDE clients without cloud model coupling or API key requirements.
- **CONSEQUENCES:** `knowledge.query` and `who_knows` now query local notes/transcripts only; `transcript.summarize` is deterministic/local; notes and transcripts can record `source_client`, `source_model`, and `source_agent`.
- **ROLLBACK:** Revert `src/server.ts`, `src/tools/transcript.ts`, `src/tools/who_knows.ts`, `src/tools/memory.ts`, `src/storage.ts`, and docs updates, then rebuild.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/src/server.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/src/tools/transcript.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/src/tools/who_knows.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/src/storage.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/CONNECT.md

- **DECISION:** Ship MCP v0.2 orchestration tools with local policy gates, run ledgering, lock leasing, incidents, and idempotent mutation journaling.
- **CONTEXT:** Need stronger predictability, replay safety, and cross-agent continuity for concurrent Cursor/Codex work without relying on cloud provider tooling.
- **CONSEQUENCES:** Added 21 local MCP tools and new SQLite tables for policy evaluations, run events, mutation journal, locks, decisions, and incidents; mutating tools now require `mutation.idempotency_key` and `mutation.side_effect_fingerprint`.
- **ROLLBACK:** Revert `src/server.ts`, `src/storage.ts`, new tool modules under `src/tools/`, and related docs updates; rebuild and restart MCP clients.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/src/server.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/src/storage.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/src/tools/mutation.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/src/tools/run.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/CONNECT.md

- **DECISION:** Add a committed MCP integration test suite (`npm test`), support isolated DB override via `MCP_HUB_DB_PATH`, and harden `adr.create` path parsing.
- **CONTEXT:** Ad-hoc smoke checks were not sufficient for repeatable confidence; tests exposed a real parser bug where `adr.create` could return the `Updated:` line instead of the created ADR file path.
- **CONSEQUENCES:** Validation now runs end-to-end with deterministic assertions over all 28 tools, including edge-case failures; test runs avoid polluting the default SQLite store by using a temporary DB path.
- **ROLLBACK:** Remove `tests/mcp_v02.integration.test.mjs`, remove `test` script in `package.json`, revert `MCP_HUB_DB_PATH` support in `src/server.ts`, and restore prior `adr.create` stdout parsing logic.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/tests/mcp_v02.integration.test.mjs, /Users/dan.driver/Cursor_projects/python/SERVUS/package.json, /Users/dan.driver/Cursor_projects/python/SERVUS/src/server.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/src/tools/adr.ts, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/CONNECT.md

- **DECISION:** Add a scheduler-managed manual onboarding override CSV queue with strict row validation, two-source confirmation metadata, success dedupe, and safe dequeue semantics.
- **CONTEXT:** Urgent onboarding requests need a controlled override path without hard-coding profiles in scripts, while preserving SERVUS idempotency and audit discipline.
- **CONSEQUENCES:** Scheduler now reads `READY` rows from `servus_state/manual_onboarding_overrides.csv` (configurable), removes rows only after successful completion, marks failed/invalid rows as `ERROR`, and prevents re-onboarding users already completed for the same email/start-date.
- **ROLLBACK:** Revert `scripts/scheduler.py`, `servus/core/manual_override_queue.py`, `servus/orchestrator.py`, and config/docs changes; remove `tests_python/test_manual_override_queue.py`; restart scheduler.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/scheduler.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/core/manual_override_queue.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/orchestrator.py, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/Onboarding.md

- **DECISION:** Repurpose `scripts/live_onboard_test.py` from direct execution into a headless-safe queue submission helper for the manual override CSV.
- **CONTEXT:** One-off hardcoded live scripts create operational drift and bypass scheduler controls; manual requests should enter the same unattended pipeline as production trigger handling.
- **CONSEQUENCES:** Operators now enqueue validated requests with explicit confirmation sources and optional dry-run validation; helper defaults to `HOLD` and requires explicit `READY` approval; no direct onboarding execution occurs from this helper.
- **ROLLBACK:** Restore the previous direct-execution version of `scripts/live_onboard_test.py` and remove helper references from docs.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/live_onboard_test.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/core/manual_override_queue.py, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/Onboarding.md

- **DECISION:** Add Rippling/Okta profile enrichment to manual queue ingress so operators can submit primarily by `work_email` (plus `start_date` safety) instead of full profile walls.
- **CONTEXT:** Manual override entry was still too verbose and error-prone for urgent onboarding; placeholder profile values are unsafe for production.
- **CONSEQUENCES:** `scripts/live_onboard_test.py` now auto-fills profile fields from integrations when available, auto-generates confirmation evidence from successful lookups, and still requires two-source confirmation plus explicit/known `start_date` for idempotent dedupe.
- **ROLLBACK:** Revert `servus/core/manual_override_enrichment.py`, `scripts/live_onboard_test.py`, `servus/integrations/rippling.py`, and related test/doc updates.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/core/manual_override_enrichment.py, /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/live_onboard_test.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/rippling.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_manual_override_enrichment.py
