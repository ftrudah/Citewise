# Citewise RAG Pipeline Plan

Nov 14, 2026 · @Josh

## Goal and scope

Citewise answers questions about PDFs you upload, cites the exact passage behind each claim, and scores its own quality on every code change.

**In scope for v1:** PDF upload, page-aware chunking, Voyage embeddings, hybrid search in Postgres (vector + keyword, merged with RRF), cited answers from Claude, a golden question set scored with Ragas, a CI gate, per-user isolation, one deployed URL.

**Out for now:** reranker, background workers, AWS and Terraform, file types other than PDF, chat history, UI polish.

**Definition of done for v1:**

- [ ] One PDF in, a cited answer out, from a plain Python script
- [ ] 20+ golden questions with reference answers, including a few the document cannot answer
- [ ] Vector-only, keyword-only and hybrid retrieval compared on that set, in one table
- [ ] Every citation machine-checked against the retrieved text
- [ ] Ragas scores for faithfulness, answer relevancy, context precision and context recall on every run
- [ ] CI fails when a score drops past the threshold
- [ ] Two users cannot see each other's documents
- [ ] Deployed, with a README holding the architecture diagram and the comparison table

## Architecture

&#91;embedded content: architecture · ingestion, query and eval flows\]

A PDF is chunked, embedded and stored once; each question is embedded, retrieved against that store, answered and verified; the eval harness drives the same `ask()` path and scores what comes back.

## Data model

Two tables carry the app, and the owner id sits on both so isolation can be added later without a schema change.

| Table | Key columns | Purpose |
| --- | --- | --- |
| documents | id, owner\_id, filename, content\_hash, page\_count, created\_at | One row per uploaded PDF; the hash makes ingestion idempotent (same PDF twice = no duplicates) |
| chunks | id, document\_id, owner\_id, page, chunk\_index, content, embedding vector(1024), embedding\_model | One row per chunk; page gives every citation a page number; embedding\_model flags stale vectors if the model ever changes |

Indexes on chunks: a plain index on owner\_id, a full-text index on content (a generated tsvector column with a GIN index), and later a pgvector index on embedding. Skip the vector index at first, because an exact scan is fast enough for a few documents.

The golden question set lives in the repo as JSON, not in the database, so a change to it shows up in code review. Eval results are written to JSON files per run for the same reason.

## Ingestion pipeline

Ingestion turns one PDF into rows in the chunks table, runs once per document, and must be safe to repeat.

1. **Receive and hash.** Hash the file bytes; if a document with that hash already exists for this owner, stop and return it.
2. **Extract text per page.** Keep the page number with the text. A page with no extractable text (a scanned image) is reported to the user, not silently skipped.
3. **Chunk within pages.** Split on paragraph boundaries into roughly 400 to 600 tokens with a small overlap, and never let a chunk cross a page break. That gives every chunk exactly one page number, which keeps citations simple.
4. **Embed in batches.** Send chunk texts to Voyage with `input_type="document"` (queries use `"query"`), and store the model name beside each vector.
5. **Insert in one transaction.** The document row and all its chunks commit together, so a failure never leaves a half-ingested PDF.

Chunk size, overlap and batch size all live in one config file. They are the first things to tune against the golden set, not decisions to agonize over now.

## Retrieval

Retrieval is one function, `retrieve(query, owner_id, mode, k)`, where mode is `vector`, `keyword` or `hybrid`, so the same code produces every row of the comparison table.

1. Embed the question with Voyage (`input_type="query"`).
2. **Vector leg:** the 20 nearest chunks by cosine distance, filtered to the owner.
3. **Keyword leg:** the top 20 chunks by keyword rank for the same question, filtered to the owner.
4. **Merge with Reciprocal Rank Fusion:** each chunk scores 1 / (60 + rank) from each leg it appears in, summed; a full outer join keeps chunks only one leg found.
5. Return the top 5 with both ranks and the fused score attached, so traces and evals can show why a chunk was picked.

The keyword leg uses Postgres full-text search on Supabase: `websearch_to_tsquery` parses the question and `ts_rank_cd` ranks the matches. This is not true BM25, which needs an extension Supabase may not offer. All SQL stays inside `retrieve.py`, so the keyword scorer can be swapped later and compared on the same golden set.

## Answer generation and citation verification

Claude answers only from the retrieved chunks, and every citation is checked by code before the user sees it.

1. **Label the sources.** Give each retrieved chunk a short per-request label (S1 to S5) rather than a database id, so the model never has to copy a long identifier.
2. **Ask for structured output.** The model returns the answer split into statements, each with the source labels and a short supporting quote.
3. **Verify in code.** For every citation, check that the label was one of the sources sent and that the quote appears in that chunk's text after whitespace is normalized. A failed citation is flagged; retry once, then return the answer with a warning.
4. **Allow "not in the document."** If the sources do not contain the answer, the model must say so instead of guessing. The golden set includes unanswerable questions to test exactly this.
5. **Return a result object** holding the answer, the verified citations (chunk id, page, quote) and the retrieved contexts, because the evals need all three.

Generation uses Claude Haiku 5.5 through the Anthropic SDK. Citation validity rate, the share of citations that pass step 3, is tracked as its own metric.

## Evaluation pipeline

The eval harness calls the same `ask()` function the API calls, scores every answer two ways, and blocks a merge when quality drops.

**Golden set.** A JSON file of 20 to 30 questions over two or three documents. Each entry has an id, the question, a reference answer, the reference page, and a type: paraphrased, keyword-heavy (names, codes, acronyms) or unanswerable. Include at least 3 unanswerable questions.

**Scores per run:**

| Metric | Kind | What it tells you |
| --- | --- | --- |
| Faithfulness | Ragas, LLM judge | Is the answer supported by the retrieved text? |
| Answer relevancy | Ragas, LLM judge + embeddings | Does it actually answer the question? |
| Context precision | Ragas, LLM judge | Was the retrieved text mostly useful? |
| Context recall | Ragas, LLM judge | Did retrieval find everything needed? |
| Hit rate at 5 | Own code, no LLM | Is a chunk from the reference page in the top 5? |
| Citation validity | Own code, no LLM | Do the quotes appear in the cited chunks? |

The two deterministic metrics are cheap, repeatable and immune to judge bias, so they anchor the judged ones.

**Judge setup.** Ragas pinned to one version (0.4.x collections metrics, not the deprecated `evaluate()`), Claude Sonnet 5.5 as judge at temperature 0, Voyage for the embeddings that answer relevancy needs. Never change the judge between commits without re-baselining. Hand-grade 15 to 20 answers once and compare with the judge to check it.

**CI gate.** A GitHub Actions job runs the harness on each pull request and compares against a committed baseline file. Measure run-to-run noise first (run the baseline three times), then set the failure threshold above that noise.

**Tracing.** Langfuse traces the retrieval and generation steps. Add it once the core works; it is for debugging, not for the gate.

## Repo layout and module interfaces

Each module does one job and hands plain data to the next; `pipeline.ask()` is the only entry point, used by the API, the CLI and the evals.

```text
citewise/
  config.py       # every tunable: chunk size, overlap, k, RRF constant, model names
  db.py           # connection and query helpers
  extract.py      # extract_pages(path) -> list[Page]
  chunking.py     # chunk_pages(pages) -> list[Chunk]
  embeddings.py   # embed_documents(texts), embed_query(text)  (Voyage)
  ingest.py       # ingest_pdf(path, owner_id) -> document_id
  retrieve.py     # retrieve(query, owner_id, mode, k) -> list[RetrievedChunk]
  answer.py       # generate(question, chunks) -> Answer; verify_citations(answer, chunks)
  pipeline.py     # ask(question, owner_id, mode) -> Result (answer, citations, contexts)
  api.py          # FastAPI: upload and ask endpoints (after the scripts work)
evals/
  golden.json     # questions, reference answers, reference pages, types
  run_evals.py    # runs ask() over the golden set, scores, writes results JSON
  baseline.json   # last accepted scores, compared by the CI gate
tests/            # unit tests for chunking, RRF merge, citation verification
```

The rule that keeps this honest: nothing outside `retrieve.py` writes SQL, and nothing outside `embeddings.py` and `answer.py` talks to Voyage or Anthropic. That makes the database, embedding model and generator swappable one file at a time.

## Milestones and schedule

&#91;embedded content: schedule · three phases around the Dec 11 Java final\]

The core script comes first because everything else depends on it, and the dates assume the earlier plan of 6 to 8 hours a week.

- **Nov 14 to 21, core script:** one PDF in, a cited answer out, and the first 20 golden questions drafted.
- **Nov 22 to Dec 11, hybrid search:** vector-only, keyword-only and hybrid retrieval compared on the golden set, kept light for finals.
- **Dec 12 to Jan 10:** FastAPI endpoints and a minimal Python-served UI, Ragas scoring, the CI gate, per-user isolation, and deployment.

## Decisions, open questions and risks

Seven decisions are settled and four are open, and the main tradeoff of the Supabase choice is full-text search instead of true BM25 for the keyword leg.

| Decision | Status | Choice or next step |
| --- | --- | --- |
| Language | Made | Python for everything, no TypeScript |
| Generation | Made | Anthropic SDK, Claude Haiku 5.5 |
| Embeddings | Made | Voyage 4 series (`voyage-4`), 1024 dimensions |
| Retrieval | Made | Hybrid search in SQL, merged with RRF |
| Database | Made | Supabase free plan (Postgres + pgvector), keyword leg uses full-text search; Tiger Data was dropped because its trial credit expires after 30 days |
| Eval harness | Made | Ragas 0.4.x pinned, Claude Sonnet 5.5 as judge at temperature 0 |
| Citations | Made | Per-request source labels, quote verified in code |
| Auth and isolation | Open | Decide in December: Supabase Auth with row-level security, or your own login and token |
| User interface | Open | Python-only: Streamlit or HTML served by FastAPI; decide once the API works |
| PDF text extractor | Open | Start with one library, swap only if the extracted text is poor |
| Ragas embeddings for Voyage | Open | Check whether Ragas supports Voyage directly; otherwise write a small adapter |

**Risks**

- **Finals.** The Java final project is due Dec 11, so keep November and early December light and protect the core milestone.
- **Supabase free plan limits.** The database is 500 MB on shared CPU, projects pause after a week of inactivity, and automatic backups are not included ([Supabase pricing](https://www.supabase.com/pricing)). Open the project at least weekly, watch the database size as the corpus grows, and keep the schema file, ingestion script and PDFs in the repo so everything can be rebuilt.
- **Ragas API drift.** Pin the version, avoid `evaluate()`, and smoke-test one metric on one hand-written sample before wiring CI.
- **Judge self-preference.** The judge and generator are both Claude; the hand-graded sample and the two deterministic metrics are the check.
- **Scope creep.** The eval pipeline is the finish line. Rerankers, workers and infrastructure wait until it passes.
