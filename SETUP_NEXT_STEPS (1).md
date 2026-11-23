# Citewise: setup progress and next steps

Last updated: 2026-11-21. For Claude (Claude Code or chat) picking up where setup stopped. Read this whole file before doing anything.

Full project plan (architecture, schedule, evals): https://claude.ai/artifact/GTWupi9QKBXvpG4Unib5tm

## The project in one paragraph

Citewise answers questions about uploaded PDFs, cites the exact passage behind each claim, and scores its own quality with evals that run on every change. It is a portfolio project for a summer 2027 CS internship. The whole application is Python. The owner is a student with limited hours each week, so work in small steps that each end with something runnable.

## Decisions already made (do not re-open)

- Language: Python only, no TypeScript.
- Generation: Anthropic SDK, Claude Haiku 5.5 (`claude-haiku-5-5`).
- Embeddings: Voyage, `voyage-4`, 1024 dimensions. Use `input_type="document"` for chunks and `input_type="query"` for questions.
- Retrieval: hybrid search written in SQL (vector leg + keyword leg), merged with Reciprocal Rank Fusion (RRF, constant 60). Build vector-only first, add keyword and RRF later.
- Database: Supabase free plan (Postgres + pgvector). The keyword leg uses Postgres full-text search (`websearch_to_tsquery` + `ts_rank_cd`), not true BM25. Tiger Data was considered and dropped because its trial credit expires after 30 days. All SQL stays in `retrieve.py` and `sql/`, so the keyword scorer can be swapped later.
- Evals: Ragas (version pinned later), Claude Sonnet 5.5 as judge at temperature 0, golden question set in `evals/golden.json`. Not part of setup.
- Citations: each retrieved chunk gets a short per-request label (S1 to S5); the model returns quotes; code verifies each quote appears in the cited chunk.
- No auth for now. Keep the `owner_id` column on every table and use one fixed dev owner UUID from `config.py`.

## Open decisions (ask the owner, do not guess)

- PDF extractor: start with `pypdf`; swap only if extracted text is poor.
- UI, auth approach, Ragas embeddings for Voyage: all later.

## Where setup stopped

Setup is complete: Steps 1 to 7 are done (as of 2026-11-22). Step 4: package skeleton and `config.py`, `data/` added to `.gitignore`; no `sql/` folder, because schema now lives in `supabase/migrations/` (see `docs/PRD.md`). Step 5: Supabase project `cdmbsouaixedfmaercpp`, CLI linked, `DATABASE_URL` works, pgvector 0.8.2 enabled by migration `20261122050656_enable_pgvector`, Supabase MCP connected. Tables `documents` and `chunks` are live (migration `20261122052846`, RLS on, API roles revoked). Step 6: `python scripts/smoke_test.py` passes for all three services. Next: the first real tasks under "After setup" (the schema is already applied, so start with extract.py and chunking.py). The git repo and remote already exist.

Before creating anything, look at what is already in the repo. Create only what is missing and never overwrite an existing file.

## Remaining steps

### Step 4: finish the project skeleton

Target layout (empty files are fine, except `config.py`):

```
citewise/
  __init__.py
  config.py
  db.py
  extract.py
  chunking.py
  embeddings.py
  ingest.py
  retrieve.py
  answer.py
  pipeline.py
evals/
tests/
scripts/
sql/
data/          # PDFs, git-ignored
```

`config.py` loads `.env` with python-dotenv and holds every tunable in one place:

- `DATABASE_URL`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY` (from the environment)
- `EMBEDDING_MODEL = "voyage-4"`, `EMBEDDING_DIM = 1024`
- `GENERATION_MODEL = "claude-haiku-5-5"`, `JUDGE_MODEL = "claude-sonnet-5-5"`
- `CHUNK_TOKENS = 500`, `CHUNK_OVERLAP = 50`, `TOP_K = 5`, `CANDIDATES_PER_LEG = 20`, `RRF_K = 60`
- `DEV_OWNER_ID`: one fixed UUID used until real auth exists

Done when: `python -c "import citewise.config"` runs without errors and prints nothing secret.

### Step 5: set up the Supabase database

The owner does the console parts; Claude must not guess results.

1. Create a free Supabase project and pick a US region close to Texas.
2. In the SQL editor, run `create extension if not exists vector;` and confirm with `select extname from pg_extension where extname = 'vector';`.
3. Copy the Postgres connection string from the project's database settings into `DATABASE_URL` in `.env`. If the direct connection string fails, try the pooler connection string instead.
4. Write `sql/001_schema.sql` (draft below; review it, it has not been run).

Free plan limits to remember: 500 MB database on shared CPU, the project pauses after a week of inactivity (open it at least weekly), and automatic backups are not included. Keep the schema file, the ingestion script and the PDFs (or download links) in the repo so everything can be rebuilt.

Schema draft:

```sql
create extension if not exists vector;

create table documents (
  id           uuid primary key default gen_random_uuid(),
  owner_id     uuid not null,
  filename     text not null,
  content_hash text not null,
  page_count   int,
  created_at   timestamptz not null default now(),
  unique (owner_id, content_hash)
);

create table chunks (
  id              bigserial primary key,
  document_id     uuid not null references documents(id) on delete cascade,
  owner_id        uuid not null,
  page            int not null,
  chunk_index     int not null,
  content         text not null,
  embedding       vector(1024) not null,
  embedding_model text not null
);

create index on chunks (owner_id);
```

Do not add a vector index or a keyword index yet. With a handful of documents an exact scan is fast enough. Those indexes belong to the hybrid-search phase, when the keyword leg adds a generated `fts tsvector` column (`to_tsvector('english', content)`) with a GIN index.

### Step 6: write `scripts/smoke_test.py`

It checks that all three services answer, so later failures are in the code and not the setup:

1. Connect to the database with `psycopg` and run `select 1`.
2. Embed one sentence with Voyage (`input_type="document"`) and print the vector length. It should be 1024.
3. Send one short message to Claude with the Anthropic SDK and print the reply.

Never print key values. If a service fails, report which one and the error message, then stop and ask.

### Step 7: commit and push

Commit with a message like "Project skeleton, config and smoke test" and push. Check first that `.env`, `.venv/` and `data/` are not staged.

## After setup: the first real tasks, in order

1. Apply `sql/001_schema.sql`.
2. `extract.py` and `chunking.py`: extract text per page, chunk within pages (about 500 tokens, small overlap, never across a page break), and print the chunks with page numbers. Needs no API keys. Review the printed chunks with the owner.
3. `embeddings.py` and `ingest.py`: embed in batches, store in one transaction, skip a PDF whose hash already exists.
4. `retrieve.py` with vector-only retrieval: print the top 5 chunks for a question.
5. `answer.py`: cited answer with quote verification.
6. Start `evals/golden.json` (20 questions, 3 to 4 openly licensed PDFs, types: paraphrased, keyword-heavy, unanswerable, multi-part).

## Rules for Claude

- Never read, print, echo or commit `.env` or any key.
- Do not add dependencies beyond anthropic, voyageai, psycopg, pypdf, python-dotenv and pytest without asking. Ragas, Langfuse and FastAPI come later.
- All SQL lives in `retrieve.py` and `sql/`. Only `embeddings.py` and `answer.py` call Voyage or Anthropic.
- One small step at a time, each ending with something the owner can run and check.
- When a step is finished, tick it below and update "Where setup stopped".

## Checklist

- [x] Step 1: virtual environment and packages
- [x] Step 2: `.gitignore`
- [x] Step 3: `.env` and `.env.example`
- [x] Step 4: project skeleton and `config.py`
- [x] Step 5: Supabase project created, `vector` extension enabled, connection string in `.env`, schema applied (migrations `20261122050656`, `20261122052846`, `20261122053225`)
- [x] Step 6: `scripts/smoke_test.py` passes (2026-11-22; 17 unit tests in `tests/test_smoke_test.py`)
- [x] Step 7: committed and pushed (2026-11-22, commit 37ab72a)
