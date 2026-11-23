# PRD: Citewise v1

Status: draft for review · Owner: Josh · Last updated: 2026-11-21
Source plan: [Citewise RAG Pipeline Plan](https://claude.ai/artifact/GTWupi9QKBXvpG4Unib5tm). Setup checklist: `SETUP_NEXT_STEPS (1).md`.

## Objective

Citewise answers questions about uploaded PDFs, cites the exact passage behind each claim, and scores its own answer quality with evals that run on every change.

- **Who it's for:** the owner, as a portfolio project for a summer 2027 CS internship. Reviewers should be able to read the README, see the architecture and the retrieval comparison table, and run it themselves.
- **Why:** to show a RAG pipeline that measures itself, where retrieval choices are compared with numbers and every citation is checked by code.
- **Constraint:** the owner is a student with limited hours each week. Work happens in small steps, and each one ends with something runnable.

### User stories

1. As a user, I ingest a PDF once, and ingesting the same file again creates no duplicates.
2. As a user, I ask a question and get an answer where every claim cites a page and a quote that really appears in the source.
3. As a user, I'm told plainly when the document doesn't contain the answer.
4. As the developer, I run one command and get vector-only, keyword-only and hybrid retrieval scored on the same golden set.
5. As the developer, a pull request that lowers answer quality past a set threshold fails CI.
6. As a user, I can never see another user's documents.

### In scope for v1

PDF ingestion, page-aware chunking, Voyage embeddings, hybrid search in Postgres (vector + keyword, merged with RRF), cited answers from Claude, a golden question set scored with Ragas, a CI gate, per-user isolation, one deployed URL.

### Out of scope for now

Rerankers, background workers, AWS and Terraform, file types other than PDF, chat history, UI polish.

## Tech stack

| Concern | Choice (settled) |
|---|---|
| Language | Python 3.12 only, no TypeScript |
| Generation | Anthropic SDK, `claude-haiku-5-5` |
| Embeddings | Voyage `voyage-4`, 1024 dims; `input_type="document"` for chunks, `"query"` for questions |
| Database | Supabase free plan: Postgres + pgvector |
| Retrieval | Hybrid in SQL: vector leg + keyword leg (`websearch_to_tsquery` + `ts_rank_cd`, not true BM25), merged with RRF (k = 60). Vector-only is built first. |
| Citations | Per-request labels S1–S5; the model returns quotes, and code verifies each quote appears in the cited chunk |
| Evals | Ragas (version pinned later), `claude-sonnet-5-5` judge at temperature 0, golden set in `evals/golden.json` |
| PDF extraction | `pypdf`; swap only if the extracted text is poor |
| Chunking | `langchain-text-splitters` (`RecursiveCharacterTextSplitter`), run once per page so a chunk never crosses a page break (approved 2026-11-22) |
| Hosting | Vercel website (decided 2026-11-21). The deployed app only queries the database; it never runs schema SQL. |
| Schema migrations | Supabase CLI: files in `supabase/migrations/`, applied with `supabase db push --remote` by the owner (to the live project) or by anyone who clones the repo (to their own project). Never applied by the app or by a Vercel build. |
| Dev tooling | Supabase MCP server for Claude Code, for inspection and docs (see `docs/specs/supabase-mcp.md`) |

Pinned versions live in `requirements.txt`.

## Commands

```bash
source .venv/bin/activate          # every session
pip install -r requirements.txt    # after pulling dependency changes
python -c "import citewise.config" # config loads, prints nothing secret
supabase link --project-ref <ref>  # once per clone
supabase migration new <name>      # new empty migration file
supabase db push --remote          # apply pending migrations to the linked project (CLI v3 defaults to local)
python scripts/smoke_test.py       # DB, Voyage and Claude all answer
pytest                             # all tests
pytest tests/test_chunking.py::test_never_crosses_page   # one test
claude mcp list                    # Supabase MCP shows "✔ Connected"
```

Ingest, ask and eval commands get added here as their scripts land.

## Project structure

```
citewise/
  config.py       # every tunable: chunk size, overlap, k, RRF constant, model names, DEV_OWNER_ID
  db.py           # connection and query helpers
  extract.py      # extract_pages(path) -> list[Page]
  chunking.py     # chunk_pages(pages) -> list[Chunk]
  embeddings.py   # embed_documents(texts), embed_query(text)        (only Voyage caller)
  ingest.py       # ingest_pdf(path, owner_id) -> document_id
  retrieve.py     # retrieve(query, owner_id, mode, k) -> list[RetrievedChunk]   (only SQL outside sql/)
  answer.py       # generate(question, chunks) -> Answer; verify_citations(...)  (only Anthropic caller)
  pipeline.py     # ask(question, owner_id, mode) -> Result   — the single entry point
evals/            # golden.json, run_evals.py, baseline.json
tests/            # unit tests
scripts/          # smoke_test.py and other runnable scripts
supabase/
  config.toml     # created by `supabase init`
  migrations/     # <timestamp>_<name>.sql, e.g. ..._initial_schema.sql
docs/             # PRD.md, specs/
data/             # PDFs, git-ignored
```

## Code style

Plain functions, type hints, small dataclasses passed between modules, and no framework magic. Every tunable comes from `config.py`, never a literal.

```python
from dataclasses import dataclass

from citewise import config


@dataclass(frozen=True)
class Chunk:
    page: int
    chunk_index: int
    content: str


def chunk_pages(pages: list[Page]) -> list[Chunk]:
    """Split each page into ~CHUNK_TOKENS chunks; a chunk never crosses a page break."""
    ...
```

- `snake_case` for functions and modules, `PascalCase` for dataclasses, `UPPER_CASE` for config constants.
- No linter or formatter yet. Match the surrounding code.

## Testing strategy

- **Framework:** pytest, with tests in `tests/` named `test_<module>.py`.
- **Unit tests (no network):** chunking (size, overlap, never across pages), RRF merge, citation verification, content hashing.
- **Smoke test:** `scripts/smoke_test.py` checks that the DB, Voyage and Anthropic all answer.
- **Evals:** the eval harness calls `pipeline.ask()` over the golden set and reports Ragas scores plus two deterministic metrics (hit rate at 5, citation validity). CI compares results against `evals/baseline.json`.
- No coverage target. Every pure-logic function gets a test before it's relied on.

## Boundaries

- **Always:** keep `.env.example` in sync with every variable read; keep `owner_id` on every table, filtered by `config.DEV_OWNER_ID` until auth exists; run `pytest` before committing; put schema changes in a `supabase/migrations/` file and query SQL in `retrieve.py`.
- **Ask first:** adding any dependency beyond anthropic, voyageai, psycopg, pypdf, python-dotenv, pytest and langchain-text-splitters; schema changes; applying SQL to the database (through MCP or otherwise); starting the next setup or build step.
- **Never:** read, print, echo or commit `.env` or any key; write code before the owner says go; call Voyage or Anthropic outside `embeddings.py` and `answer.py`; run DDL that isn't in a migration file; apply migrations from app code or a Vercel build step; reintroduce Tiger Data or Timescale.

## Success criteria (v1 definition of done)

- [ ] One PDF in, a cited answer out, from a plain Python script
- [ ] 20+ golden questions with reference answers, including some the document cannot answer
- [ ] Vector-only, keyword-only and hybrid retrieval compared on that set, in one table
- [ ] Every citation machine-checked against the retrieved text
- [ ] Ragas faithfulness, answer relevancy, context precision and context recall on every run
- [ ] CI fails when a score drops past the threshold
- [ ] Two users cannot see each other's documents
- [ ] Deployed, with a README holding the architecture diagram and the comparison table

## Milestones

| Dates | Milestone |
|---|---|
| Nov 14–21 | Setup, then core script: one PDF in, a cited answer out; first 20 golden questions drafted |
| Nov 22–Dec 11 | Hybrid search compared on the golden set (kept light for the Dec 11 Java final) |
| Dec 12–Jan 10 | FastAPI endpoints, a minimal Python UI, Ragas, the CI gate, per-user isolation, deployment |

## Open questions

1. **Vercel shapes the remaining choices.** To verify against the Vercel and Supabase docs when the deployment spec is written; none of this is checked yet:
   - **UI:** Vercel runs serverless functions, so a long-running Streamlit server probably doesn't fit. A FastAPI app (API plus served HTML) probably does.
   - **Database connections:** serverless functions usually connect through Supabase's transaction pooler, and psycopg may need prepared statements turned off for that.
   - **Limits:** function request-body size and timeouts may cap PDF upload size and ingestion time.
2. **Dependency allowlist vs `requirements.txt`.** `langchain-text-splitters` is approved for chunking (2026-11-22). Still undecided: `aiohttp`, `aiolimiter` and `tenacity`, which are pinned but not on the allowlist.
3. Auth approach (Supabase Auth + RLS, or your own login) and Ragas embeddings for Voyage: decided later, per the plan.

Resolved 2026-11-21: schema migrations live in `supabase/migrations/` and are applied with the Supabase CLI (Option B in the MCP spec). This replaces the setup plan's `sql/` directory for schema files.
