# Todo: Supabase MCP server

Plan: `tasks/plan.md` · Spec: `docs/specs/supabase-mcp.md`

- [x] **T1: write `.mcp.json` (Claude)**
  - Run: `claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp?project_ref=cdmbsouaixedfmaercpp&features=database,docs,debugging,development"`
  - Acceptance: `.mcp.json` exists at the repo root with only that one HTTP server entry.
  - Verify: `claude mcp get supabase` shows project scope, http and that URL.
  - Files: `.mcp.json`

- [x] **T2: approve and log in (owner)**
  - Exit this session, then run `claude --continue` in `~/Citewise`. Accept the prompt to approve the project server `supabase`.
  - Run `/mcp`, choose **supabase** → **Authenticate**, and pick the org that owns `cdmbsouaixedfmaercpp` in the browser.
  - Acceptance and verify: `claude mcp list` shows `supabase … ✔ Connected`.
  - Files: none

- [x] **T3: verify tools and scope (Claude, each call approved by you)**
  - Compare the loaded `mcp__supabase__*` tools with the spec: database, docs, debugging and development present; account, Edge Function, storage, branching and notebook tools absent.
  - Approved calls: `list_extensions` (expect `vector` 0.8.2 in `extensions`), `get_advisors` with type security (expect the two `rls_auto_enable` WARNs), and `list_migrations` (expect `20261122050656`).
  - If the group names are wrong: fix the URL in `.mcp.json`, restart, and recheck.
  - Files: `.mcp.json` (only if needed)

- [x] **T4: docs (Claude)**
  - README: add an "MCP setup (optional, for Claude Code)" section with the T2 steps. CLAUDE.md: change "Not connected yet" to connected, and add the `features` value we confirmed. Spec: tick the tasks and record the confirmed group names.
  - Verify: the README alone is enough to reconnect from a fresh clone.
  - Files: `README.md`, `CLAUDE.md`, `docs/specs/supabase-mcp.md`

- [x] **T5: commit (Claude, after you say go)**
  - Stage `.mcp.json`, `supabase/` (config, migrations, `.gitignore`), `docs/`, `tasks/`, `README.md`, `CLAUDE.md` and `.env.example`. Confirm `.env` and `supabase/.temp/` aren't staged. Show you the list first.
  - Files: none
