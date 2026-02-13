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

- **DECISION:** Fix `RipplingClient._build_profile` to be a real class method and add a regression unit test to prevent silent enrichment failures.
- **CONTEXT:** A bad indentation placed `_build_profile` under `_response_detail`, so email lookups could fail at runtime with swallowed attribute errors even when API scopes were correct.
- **CONSEQUENCES:** Worker profile enrichment now executes as designed; failures reflect true API/data issues instead of structural method wiring bugs.
- **ROLLBACK:** Revert `servus/integrations/rippling.py`, remove `tests_python/test_rippling_client.py`, and undo the inspection checklist update.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/rippling.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_rippling_client.py, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/SERVUS_INSPECTION_PLAN.md

- **DECISION:** Add CLI shortcuts for manual override confirmations so operators can provide immutable IDs directly (`--rippling-worker-id`, `--freshservice-ticket-id`) without hand-building source strings.
- **CONTEXT:** Urgent off-cycle onboarding required too much manual typing, increasing operator friction and typo risk.
- **CONSEQUENCES:** Manual queue ingress now supports concise commands from email + two IDs; Freshservice ticket shorthand (`INC-140`) and ticket URLs normalize to canonical `freshservice:ticket_id:<id>`.
- **ROLLBACK:** Revert `scripts/live_onboard_test.py`, remove `tests_python/test_live_onboard_cli_shortcuts.py`, and revert related examples in `docs/Onboarding.md`.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/live_onboard_test.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_live_onboard_cli_shortcuts.py, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/Onboarding.md

- **DECISION:** Make `scripts/scheduler.py` self-bootstrap repo imports by adding repo root to `sys.path` at runtime.
- **CONTEXT:** Invoking scheduler by absolute path raised `ModuleNotFoundError: No module named 'servus'` when parent repo was not on `PYTHONPATH`.
- **CONSEQUENCES:** Scheduler can now be launched reliably from any working directory using absolute or relative script paths.
- **ROLLBACK:** Remove the `sys.path` bootstrap block from `scripts/scheduler.py` and run scheduler only from a correctly configured Python path/environment.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/scheduler.py, /Users/dan.driver/Cursor_projects/python/SERVUS/rolling_notes_for_servus.md

- **DECISION:** Extend Slack notifier usage to include per-step start/result events and run summaries with trigger/request context.
- **CONTEXT:** Operator visibility was too coarse (start/success/failure only), making live issue triage harder during unattended onboarding runs.
- **CONSEQUENCES:** Slack now receives step-by-step progress plus completion metrics (`steps_total`, `steps_succeeded`, `steps_failed`) and includes `trigger_source`/`request_id` when available.
- **ROLLBACK:** Revert `servus/notifier.py`, `servus/orchestrator.py`, `scripts/scheduler.py`, remove `tests_python/test_orchestrator_slack_notifications.py`, and remove related inspection checklist text.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/notifier.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/orchestrator.py, /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/scheduler.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_orchestrator_slack_notifications.py, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/SERVUS_INSPECTION_PLAN.md

- **DECISION:** Add scheduler startup hardening with preflight action-registry validation across workflow YAMLs and strict manual override start-date gating with urgent overrides.
- **CONTEXT:** Live onboarding exposed runtime failures from missing workflow action mappings and premature execution of future-dated manual override requests.
- **CONSEQUENCES:** Scheduler now surfaces blocking startup issues before execution and defers `READY` rows until `start_date <= today` unless explicitly overridden (`allow_before_start_date` or global early-execution config).
- **ROLLBACK:** Revert `scripts/scheduler.py`, `servus/core/manual_override_queue.py`, `scripts/live_onboard_test.py`, and related docs/tests; restart scheduler.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/scheduler.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/core/manual_override_queue.py, /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/live_onboard_test.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_scheduler_hardening.py, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/Onboarding.md

- **DECISION:** Normalize onboarding integration outcomes to structured idempotent results so pre-created users and optional-tool gaps emit explicit skip reasons instead of ambiguous failures.
- **CONTEXT:** Onboarding runs needed to continue predictably when accounts were already present or when optional integrations were intentionally unavailable.
- **CONSEQUENCES:** Slack/Zoom/Linear/Ramp/Brivo/Okta/Google steps now return richer `ok/detail` outcomes used by per-step notifications (for example, "already exists", "SCIM lag skip", or "config missing skip").
- **ROLLBACK:** Revert integration updates and registry/tests, then restart scheduler to restore legacy bool-only behavior.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/slack.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/zoom.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/linear.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/ramp.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/brivo.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/google_gam.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/okta.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_google_gam_group_semantics.py

- **DECISION:** Pin `pyjwt` and `cryptography` in Python runtime dependencies to make Apple ABM integration imports deterministic across environments.
- **CONTEXT:** `servus/integrations/apple.py` imports `jwt` at module load time; environments built strictly from `requirements.txt` could crash startup with `ModuleNotFoundError` even if local developer machines pass.
- **CONSEQUENCES:** Fresh environments install required crypto/JWT libraries by default, reducing startup drift between local, NOC, and headless hosts.
- **ROLLBACK:** Remove `pyjwt`/`cryptography` from `requirements.txt` and reinstall dependencies.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/requirements.txt, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/apple.py

- **DECISION:** Switch default Slack run reporting to consolidated summaries and keep step-level notifications behind an explicit verbose mode.
- **CONTEXT:** Per-step start/result/failure notifications generated high-volume alert noise and obscured the actual onboarding outcome.
- **CONSEQUENCES:** Default webhook output is now start + final summary (or final-only if configured), while detailed step spam is opt-in via `SERVUS_SLACK_NOTIFICATION_MODE=verbose`.
- **ROLLBACK:** Revert `servus/orchestrator.py`, `servus/notifier.py`, and related tests/config keys to restore always-on step-level messaging.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/orchestrator.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/notifier.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/config.py, /Users/dan.driver/Cursor_projects/python/SERVUS/.env.example

- **DECISION:** Make Brivo badge queue failures non-blocking by posting a manual Slack action card (with best-effort profile image URL) instead of hard-failing onboarding.
- **CONTEXT:** Badge queue infrastructure may be intentionally offline during rollout/testing; blocking onboarding on SQS connectivity creates avoidable operator churn.
- **CONSEQUENCES:** On badge queue errors, SERVUS now emits a single manual task notification ("create Brivo account + print badge") and continues onboarding flow, preserving operational visibility without aborting run.
- **ROLLBACK:** Revert `servus/integrations/brivo.py` and tests to restore hard-fail behavior on SQS failures.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/brivo.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/notifier.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_brivo_manual_fallback.py

- **DECISION:** Update Linear onboarding invite mutation to `organizationInviteCreate` with `UserRoleType` role values.
- **CONTEXT:** Existing mutation (`userInvite` + `UserRole`) no longer matches current Linear schema and fails with GraphQL validation errors.
- **CONSEQUENCES:** Linear invite step now targets active schema primitives and normalizes role values (`user`, `guest`, etc.) for reliable invite creation.
- **ROLLBACK:** Revert `servus/integrations/linear.py` and tests to previous mutation implementation.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/linear.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_linear_invite_mutation.py

- **DECISION:** Add an integration preflight check script (`scripts/preflight_check.py`) to validate Google, Slack, Linear, and Brivo connectivity before runtime.
- **CONTEXT:** Operators needed a way to verify critical integration health and credentials without running a full onboarding/offboarding workflow.
- **CONSEQUENCES:** New CLI tool provides a concise status table; supports `--strict` mode for CI/CD or hard-gated checks; reduces runtime surprises.
- **ROLLBACK:** Remove `scripts/preflight_check.py`, `tests_python/test_preflight_check.py`, and revert `rolling_notes_for_servus.md`.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/preflight_check.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_preflight_check.py

- **DECISION:** Harden the preflight tool to run from any invocation path and enforce checks that match real onboarding failure modes (Slack scopes + badge queue endpoint reachability).
- **CONTEXT:** Initial `scripts/preflight_check.py` could fail at import time (`ModuleNotFoundError: servus`) and only validated Slack auth / SQS URL shape, missing the exact runtime blockers seen in production (`missing_scope`, unreachable queue endpoint).
- **CONSEQUENCES:** Operators can now execute preflight reliably via `python3 scripts/preflight_check.py`; Slack preflight explicitly validates `users:read.email` and invite-write scopes; Brivo preflight now verifies endpoint reachability in addition to configuration format.
- **ROLLBACK:** Revert `scripts/preflight_check.py`, `tests_python/test_preflight_check.py`, and associated doc updates if a lighter preflight policy is preferred.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/preflight_check.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_preflight_check.py, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/Onboarding.md, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/SERVUS_INSPECTION_PLAN.md

- **DECISION:** Replace hardcoded Google/Slack onboarding targets with policy files so production runs track real org resources without code edits.
- **CONTEXT:** Hardcoded targets (`all-hands@boom.aero`, `engineering-all@boom.aero`, and Slack `all-hands`) produced deterministic onboarding failures when those resources were missing or not configured for API automation.
- **CONSEQUENCES:** Google group adds now resolve from `servus/data/google_groups.yaml`; Slack channel adds now resolve from `servus/data/slack_channels.yaml`; if no targets match policy, steps succeed with explicit skip detail.
- **ROLLBACK:** Revert `servus/integrations/google_gam.py`, `servus/integrations/slack.py`, and remove `servus/data/google_groups.yaml` to restore hardcoded target behavior.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/google_gam.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/slack.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/data/google_groups.yaml

- **DECISION:** Make Brivo preflight strictness configurable (`SERVUS_BRIVO_QUEUE_REQUIRED`) to align with manual badge fallback operations.
- **CONTEXT:** Badge queue is intentionally optional during some onboarding windows, but strict preflight previously failed even when workflow fallback was designed and tested.
- **CONSEQUENCES:** With default `SERVUS_BRIVO_QUEUE_REQUIRED=false`, unreachable/missing queue emits warning (not blocker); strict queue enforcement remains available by setting the flag true.
- **ROLLBACK:** Remove `BRIVO_QUEUE_REQUIRED` config handling and revert preflight logic to always fail on queue reachability/config issues.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/config.py, /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/preflight_check.py, /Users/dan.driver/Cursor_projects/python/SERVUS/.env.example

- **DECISION:** Set production onboarding policy defaults from exported Google/Slack inventories (FTE -> `team@boom.aero`; non-FTE -> `contractors@boom.aero`; curated global Slack channels for all non-suppliers).
- **CONTEXT:** Operators provided full CSV inventories and required deterministic, data-driven defaults without hardcoded action logic changes.
- **CONSEQUENCES:** Group/channel targeting is now explicit in policy YAMLs; future tuning is file-only and auditable. Intern policy currently uses `internships@boom.aero` (existing group) alongside contractors baseline; suppliers get `suppliers@boom.aero` in addition to contractors baseline.
- **ROLLBACK:** Revert `servus/data/google_groups.yaml`, `servus/data/slack_channels.yaml`, related docs updates, and rerun preflight/tests.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/data/google_groups.yaml, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/data/slack_channels.yaml, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/Onboarding.md, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/SERVUS_INSPECTION_PLAN.md

- **DECISION:** Accept Slack invite-specific OAuth scopes (`channels:write.invites` / `groups:write.invites`) as valid for onboarding channel automation preflight checks.
- **CONTEXT:** Slack app reinstall provided invite-specific scope variant, but preflight only recognized legacy/general write scopes and raised a false blocker.
- **CONSEQUENCES:** Preflight now aligns with modern Slack scope naming and accurately reflects channel invite capability.
- **ROLLBACK:** Revert `scripts/preflight_check.py` and `tests_python/test_preflight_check.py` to prior scope matcher behavior.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/preflight_check.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_preflight_check.py

- **DECISION:** Add a one-command off-cycle onboarding wrapper (`scripts/offcycle_onboard.sh`) that submits manual override requests with minimal required inputs.
- **CONTEXT:** Operators needed a faster workflow than invoking `live_onboard_test.py` with many flags for urgent/missed onboardings.
- **CONSEQUENCES:** Off-cycle onboarding can now be queued with email + immutable Rippling/Freshservice IDs in a single command; default behavior is immediate queueing (`READY` + `urgent`) with optional `--hold` for staged approval.
- **ROLLBACK:** Remove `scripts/offcycle_onboard.sh` and revert related doc/inspection updates.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/offcycle_onboard.sh, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/Onboarding.md, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/SERVUS_INSPECTION_PLAN.md

- **DECISION:** Package scheduler auto-restart deployment as committed service templates and installer/render scripts for both macOS (`launchd`) and Linux (`systemd`).
- **CONTEXT:** Team requires set-and-forget headless operation now on macOS and later migration to a dedicated host without re-authoring service definitions.
- **CONSEQUENCES:** `scripts/install_scheduler_launchd.sh` installs/loads a strict-preflight launchd service from template; `scripts/render_scheduler_systemd.sh` renders a portable systemd unit for dedicated hosts.
- **ROLLBACK:** Remove service template files and helper scripts, then return to manual scheduler startup.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/install_scheduler_launchd.sh, /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/render_scheduler_systemd.sh, /Users/dan.driver/Cursor_projects/python/SERVUS/ops/launchd/com.boom.servus.scheduler.plist.template, /Users/dan.driver/Cursor_projects/python/SERVUS/ops/systemd/servus-scheduler.service.template

- **DECISION:** Implement dual-validation offboarding automation in scheduler with staged-by-default safety, and require explicit `--execute-live` for CLI offboarding.
- **CONTEXT:** Headless lifecycle coverage was incomplete (onboarding-only scheduler), and CLI offboarding could run destructively without an explicit confirmation gate, violating safety defaults.
- **CONSEQUENCES:** Scheduler now processes validated departures (Rippling + Freshservice), writes deterministic pending rows to `servus_state/pending_offboards.csv`, and only executes offboarding when `SERVUS_OFFBOARDING_EXECUTION_ENABLED=true`; default remains staged. CLI offboarding now defaults to dry-run and requires `--execute-live` for destructive execution.
- **ROLLBACK:** Revert `scripts/scheduler.py`, `servus/core/trigger_validator.py`, `servus/integrations/freshservice.py`, and `servus/__main__.py`; remove new scheduler/offboarding tests; restore previous docs guidance.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/scheduler.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/core/trigger_validator.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/freshservice.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/__main__.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_scheduler_offboarding.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_trigger_validator_offboarding.py

- **DECISION:** Make dry-run paths isolation-safe by short-circuiting external lookups before API/GAM calls and repair `scripts/dry_run_simulation.py` to current orchestrator interfaces.
- **CONTEXT:** Dry-run rehearsals still touched live integrations in several steps and the simulation script was broken by stale imports, reducing confidence in non-destructive validation.
- **CONSEQUENCES:** Google and Slack dry-run steps now avoid live lookups, simulation script executes end-to-end with current workflow/orchestrator APIs, and new tests enforce dry-run isolation and CLI safety defaults.
- **ROLLBACK:** Revert `servus/integrations/google_gam.py`, `servus/integrations/slack.py`, `scripts/dry_run_simulation.py`, and associated tests.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/google_gam.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/slack.py, /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/dry_run_simulation.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_dry_run_isolation.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_cli_safety_defaults.py

- **DECISION:** Add centralized protected-target enforcement for offboarding with a mandatory workflow policy gate and per-action defense-in-depth wrappers.
- **CONTEXT:** Destructive offboarding safety relied on integration-local behavior and did not guarantee explicit protected-target blocking across all destructive actions.
- **CONSEQUENCES:** `builtin.validate_target_email` now evaluates merged protected-target policy (`servus/data/protected_targets.yaml` + `SERVUS_PROTECTED_*` env overrides) before offboarding; offboarding workflow includes this gate first; destructive actions (`okta.deactivate_user`, `ad.verify_user_disabled`, `slack.deactivate_user`, `google_gam.deprovision_user`) re-run the same guard to prevent bypass.
- **ROLLBACK:** Revert `servus/safety.py`, `servus/actions.py`, `servus/actions_builtin.py`, `servus/workflows/offboard_us.yaml`, `scripts/scheduler.py`, `scripts/preflight_check.py`, and new safety tests.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/safety.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/actions.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/actions_builtin.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/workflows/offboard_us.yaml, /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/scheduler.py, /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/preflight_check.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_offboarding_safety_guards.py

- **DECISION:** Add autonomous offboarding execution mode (`auto`) plus manager-first transfer routing so validated departures can execute headlessly without manual live toggles.
- **CONTEXT:** Operations requirement is fully unattended lifecycle automation where offboarding executes automatically after dual-source validation, with Drive/Calendar/mail handoff to the manager and no ad-hoc IT input.
- **CONSEQUENCES:** Scheduler now supports `SERVUS_OFFBOARDING_EXECUTION_MODE=auto`, which executes live offboarding only when preflight has no blocking issues and protected-target policy is non-empty; offboarding workflow now requires `okta.verify_manager_resolved`; Google offboarding now transfers artifacts to resolved manager email by default (optional admin fallback via `SERVUS_OFFBOARDING_TRANSFER_FALLBACK_TO_ADMIN=true`).
- **ROLLBACK:** Revert `scripts/scheduler.py`, `servus/integrations/okta.py`, `servus/integrations/google_gam.py`, `servus/workflows/offboard_us.yaml`, and new offboarding transfer/auto-mode tests.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/scripts/scheduler.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/okta.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/google_gam.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/workflows/offboard_us.yaml, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_scheduler_offboarding.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_google_offboarding_transfer.py

- **DECISION:** Expand protected-target policy to include explicit protected usernames and AD Service Accounts OU safeguards.
- **CONTEXT:** Security requirements now include non-email privileged identities (for example `danadmin`) and all service/resource accounts under `Boom Users/Service Accounts`, which must never be disabled by automated offboarding.
- **CONSEQUENCES:** Protected policy now supports `usernames`; baseline protected targets populated with named admin/service identities; AD disable action now aborts when target DN matches protected OU patterns (`SERVUS_PROTECTED_AD_OU_PATTERNS`, default includes `OU=Service Accounts,OU=Boom Users`).
- **ROLLBACK:** Revert `servus/safety.py`, `servus/data/protected_targets.yaml`, `servus/integrations/ad.py`, config/env keys, and related tests/docs.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/servus/safety.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/data/protected_targets.yaml, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/integrations/ad.py, /Users/dan.driver/Cursor_projects/python/SERVUS/servus/config.py, /Users/dan.driver/Cursor_projects/python/SERVUS/tests_python/test_ad_offboarding_safety.py

- **DECISION:** Refresh top-level README and add a one-page operator runbook card for coworker handoff onboarding operations.
- **CONTEXT:** Existing `README.md` no longer reflected current headless execution modes and safeguards, and operators needed a short copy/paste handoff card instead of a long process document.
- **CONSEQUENCES:** `README.md` now matches current scheduler/offboarding model and links operator docs; new `docs/OPERATOR_RUNBOOK_CARD.md` provides minimal commands for shift-start preflight, scheduler startup, off-cycle queueing, approval, monitoring, and retry.
- **ROLLBACK:** Restore previous `README.md` and remove `docs/OPERATOR_RUNBOOK_CARD.md` if a longer-form-only documentation strategy is preferred.
- **LINKS:** /Users/dan.driver/Cursor_projects/python/SERVUS/README.md, /Users/dan.driver/Cursor_projects/python/SERVUS/docs/OPERATOR_RUNBOOK_CARD.md
