# Citewise

Citewise answers questions about PDFs you upload, cites the exact passage behind each claim, and scores its own answer quality with evals that run on every change.

> Status: early setup. No application code yet. See [docs/PRD.md](docs/PRD.md) for scope and the definition of done.

## How it works (planned)

1. **Ingest.** A PDF is hashed (so the same file is never stored twice), its text is extracted per page, chunked within pages, embedded with Voyage `voyage-4`, and stored in Supabase Postgres with pgvector.
2. **Retrieve.** A question is embedded and matched against the chunks: vector search first, with hybrid search (vector + Postgres full-text, merged with Reciprocal Rank Fusion) later.
3. **Answer.** Claude Haiku 5.5 answers from the top 5 chunks only, citing each one by label with a supporting quote. Code checks that every quote really appears in the cited chunk.
4. **Evaluate.** A golden question set is scored with Ragas (Claude Sonnet 5.5 as judge) plus two checks that need no LLM: hit rate at 5 and citation validity. CI fails if scores drop.

## Stack

Python 3.12 · Anthropic SDK · Voyage AI · Supabase (Postgres + pgvector) · psycopg 3 · pypdf · pytest · hosted on Vercel

## Setup

Requirements: Python 3.12, a Supabase project, and Anthropic and Voyage API keys.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY, VOYAGE_API_KEY, DATABASE_URL
```

`DATABASE_URL` is the Postgres connection string from your Supabase project's **Connect** panel. If the direct connection fails, use the pooler string.

Create the database tables in your own Supabase project with the [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started):

```bash
supabase link --project-ref <your-project-ref>
supabase db push --remote   # applies everything in supabase/migrations/
```

The hosted site runs on Vercel against its own Supabase project. You only need these steps when running a clone.

On the Supabase free plan, the project pauses after a week of inactivity and has no automatic backups. The schema files and ingestion script in this repo are enough to rebuild it.

## MCP setup (optional, for Claude Code)

The repo's `.mcp.json` connects [Claude Code](https://code.claude.com/docs/en/mcp) to Supabase's [hosted MCP server](https://supabase.com/docs/guides/getting-started/mcp), so Claude can inspect the database and search Supabase's docs during development. The app itself doesn't use it.

The server is locked to one project with `project_ref` and limited to the `database`, `docs`, `debugging` and `development` tool groups. No token is stored in the repo; you log in through your browser.

1. **If you cloned the repo,** change `project_ref` in `.mcp.json` to your own project's ref (from `supabase.com/dashboard/project/<ref>`). The ref in the repo belongs to the hosted Citewise project, and your account can't reach it.
2. Start `claude` in the repo and approve the project MCP server `supabase` when asked.
3. Run `/mcp`, choose **supabase** → **Authenticate**, and pick the organization that owns your project.
4. Check it: `claude mcp list` should show `supabase … ✔ Connected`.

Schema changes still go through `supabase db push --remote`, not the MCP server.

## Docs

- [PRD](docs/PRD.md): goals, scope, decisions, success criteria
- [Supabase MCP spec](docs/specs/supabase-mcp.md): connecting Claude Code to the database

## Testing

```bash
pytest                         # unit tests, no network
python scripts/smoke_test.py   # checks the database, Voyage and Claude all answer (real calls)
```

Expected smoke test output:

```
✓ Database: select 1 ok, pgvector 0.8.2
✓ Voyage: voyage-4 returned a 1024-dim vector
✓ Claude: replied: ok
```
