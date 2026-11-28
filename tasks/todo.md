# Todo: PDF extraction and page-aware chunking

Plan: `tasks/plan.md` · Spec: `docs/specs/extract-and-chunk.md` · Previous: `tasks/archive/`

- [x] **T1: `citewise/extract.py`, test-first (Claude)**
  - Write `tests/test_extract.py` first with a fake reader of three pages: text, empty, and text with `\r\n`. Check: three `Page`s numbered 1–3, the empty page kept as `""`, `\r\n` → `\n`, each page stripped, and `empty_pages(...) == [2]`. Run it and see it fail.
  - Then write `Page`, `extract_pages(path, reader_factory=...)` and `empty_pages(pages)` as the spec describes. The reader parameter defaults to `pypdf.PdfReader`.
  - Verify: `pytest tests/test_extract.py` passes with no network.
  - Files: `tests/test_extract.py`, `citewise/extract.py`

- [ ] **T2: `citewise/chunking.py`, test-first (Claude)**
  - First fix the spec line that says the tokenizer loads from `voyageai/voyage-4`. It's `MongoDB/voyage-4`, derived from `config.EMBEDDING_MODEL`.
  - Write `tests/test_chunking.py` first, using a 1 word = 1 token counter: short page → one chunk; long page → several chunks, each ≤ `chunk_tokens`; neighbors on one page share overlap text; no chunk spans two pages; `chunk_index` continuous across pages; paragraph breaks preferred; empty pages give no chunks; the tokenizer repo name matches `voyageai.util.HF_ORG`. Run them and see them fail.
  - Then write `Chunk` and `chunk_pages(...)`: one `RecursiveCharacterTextSplitter` run per page, and a lazily loaded, module-cached Voyage tokenizer as the default `count_tokens`.
  - Verify: `pytest tests/test_chunking.py` passes with no network, and the full `pytest` still passes.
  - Files: `docs/specs/extract-and-chunk.md` (one line), `tests/test_chunking.py`, `citewise/chunking.py`

- [ ] **T3: `scripts/show_chunks.py` (Claude)**
  - Takes a PDF path and an optional `--head N`. Prints page count, empty pages, chunk count, min/avg/max tokens, then each chunk as `[chunk N · page P · T tokens]` followed by its text.
  - Verify: `python scripts/show_chunks.py data/docent_handbook_13-14.pdf --head 5` reports 30 pages, empty pages `[2, 29]`, max tokens ≤ 500, and finishes in a few seconds.
  - Files: `scripts/show_chunks.py`

- [ ] **T4: chunk review (owner)**
  - Run `python scripts/show_chunks.py data/docent_handbook_13-14.pdf` and read the output together. Look for: line-level splits where paragraphs should be, header and table-of-contents noise, and chunks that cut mid-sentence.
  - Acceptance: you accept the quality, or name a change. Any change to the extractor, header removal or chunk sizes is "Ask first" and gets its own approval.
  - Files: none

- [ ] **T5: docs (Claude)**
  - CLAUDE.md project state: `extract.py` and `chunking.py` done, the new tests, the `show_chunks.py` command, and next step `ingest.py`. Spec: tick the success criteria and note anything from the review.
  - Files: `CLAUDE.md`, `docs/specs/extract-and-chunk.md`

- [ ] **T6: commit (Claude, after you say go)**
  - Stage the code, tests, script, `docs/`, `tasks/` (including `tasks/archive/`) and `CLAUDE.md`. Confirm no PDFs, `.env` or `__pycache__` are staged. Show you the list first.
  - Files: none
