# Plan: Supabase MCP server

Spec: `docs/specs/supabase-mcp.md` (approved 2026-11-21). Task list: `tasks/todo.md`.

## Starting point (verified 2026-11-21)

- The Supabase CLI is set up and linked to `cdmbsouaixedfmaercpp` ("Citewise").
- `DATABASE_URL` connects (pooler, session mode).
- pgvector 0.8.2 is installed in `extensions` through migration `20261122050656_enable_pgvector`.
- There's no `.mcp.json` yet, and no Supabase entry in any MCP scope.
- No setting auto-approves project MCP servers (`enableAllProjectMcpServers` isn't set), and no allow rule covers `mcp__supabase__*`. Every call will prompt.
- Known advisor findings before connecting: two WARNs on `public.rls_auto_enable()` (lints 0028 and 0029). The MCP `get_advisors` call in Task 3 should report the same two.

## Components and order

```
T1 write .mcp.json ──> T2 owner: restart, approve, log in ──> T3 verify tools + scope ──> T4 docs ──> T5 commit
```

The tasks run in order. Each depends on the one before, and nothing can run in parallel. T2 is yours alone: OAuth runs in your browser, and a new MCP server only loads when a Claude Code session starts.

## Verification checkpoints

| After | Check | Pass |
|---|---|---|
| T1 | `claude mcp get supabase` | scope: project; type: http; URL has `project_ref=cdmbsouaixedfmaercpp` |
| T2 | `claude mcp list` | `supabase: … (HTTP) - ✔ Connected` |
| T3 | The tool list in a new session, plus approved `list_extensions` and `get_advisors` calls | Database, docs, debugging and development tools present; no account, Edge Function, storage, branching or notebook tools; `vector` 0.8.2 in `extensions`; advisors match the CLI |
| T4 | A fresh reader can follow the README alone | — |
| T5 | `git status`, staged files | `.env` not staged; no secrets in the diff |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The `features` group names `debugging` and `development` are wrong (UNVERIFIED; the docs only show `database,docs`) | T3 compares the tool list against what we expect. If the server rejects the URL or a group is missing, fix the name. If the right name can't be found, drop `features` and rely on `project_ref` plus per-call approval. |
| OAuth picks the wrong organization | In T2, choose the org that owns `cdmbsouaixedfmaercpp`. `project_ref` also makes any other project unreachable. |
| Claude uses `apply_migration` or DDL through `execute_sql` | CLAUDE.md and spec rules, plus per-call approval: deny any such call. |
| Prompt injection from chunk text returned by queries | Treat results as data (spec rule 4). There are no chunks yet. |
| This conversation is lost when you restart for T2 | Run `claude --continue` (or `/resume`) in the repo, so the same conversation comes back with the new server loaded. |
| `.mcp.json` leaks something | It holds only the URL. The project ref is already public in the API URL, and the OAuth token is stored outside the repo. T5 checks the diff. |

## Out of scope

The fix for the `rls_auto_enable` advisor warnings (its own migration, later), the tables migration, and any app code.
