# Plan: PDF extraction and page-aware chunking

Spec: `docs/specs/extract-and-chunk.md` (approved 2026-11-27). Task list: `tasks/todo.md`. Previous plans are in `tasks/archive/`.

## Starting point (verified 2026-11-27)

- `citewise/extract.py` and `citewise/chunking.py` are empty files. `tests/` has only `test_smoke_test.py`.
- `config.py` already has `CHUNK_TOKENS = 500`, `CHUNK_OVERLAP = 50` and `EMBEDDING_MODEL = "voyage-4"`.
- `pypdf` 7.1.0, `langchain-text-splitters` 1.1.3 and `tokenizers` 0.23.3 are pinned in `requirements.txt` and import cleanly in `.venv`.
- The tokenizer is already cached locally as `models--MongoDB--voyage-4`.
- The review PDF is `data/docent_handbook_13-14.pdf`: 30 pages, pages 2 and 29 have no text. It's git-ignored and for local testing only.
- **Spec correction needed:** the spec says the tokenizer loads from `voyageai/voyage-4`. The installed `voyageai` 0.6.0 client actually loads `f"{HF_ORG}/{model}"` with `HF_ORG = "MongoDB"` (`voyageai/util.py:16`, `_base.py:226`). The code should derive the repo the same way (`MongoDB/<EMBEDDING_MODEL>`). T2 fixes the spec line before writing the code.

## Components and order

```
T1 extract.py (test-first) ──> T2 chunking.py (test-first) ──> T3 show_chunks.py ──> T4 owner review ──> T5 docs ──> T6 commit
```

The tasks run in order. `chunking.py` imports `Page` from `extract.py`, and the script uses both. T4 is yours: you read the printed chunks and decide whether they're good enough.

Each code task follows red → green → refactor: write the tests from the spec, see them fail, then write the code until they pass.

## Verification checkpoints

| After | Check | Pass |
|---|---|---|
| T1 | `pytest tests/test_extract.py` | All pass, no network, no PDF on disk |
| T2 | `pytest tests/test_chunking.py` and then the full `pytest` | All pass, no network; the smoke-test tests still pass |
| T3 | `python scripts/show_chunks.py data/docent_handbook_13-14.pdf --head 5` | Prints 30 pages, empty pages `[2, 29]`, a chunk count, min/avg/max tokens, and chunks tagged `[chunk N · page P · T tokens]` with max ≤ 500 |
| T4 | Owner reads the full output | Accepted, or a specific change requested (that change goes through "Ask first") |
| T5 | CLAUDE.md and spec are current | Project state names the new modules, tests and command; spec success criteria ticked |
| T6 | `git status`, staged files | No PDFs, `.env` or `__pycache__` staged |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| pypdf plain mode ends each visual line with `\n` and rarely emits `\n\n`, so chunks split on lines, not paragraphs | T4 will show it. If it's bad, propose `extraction_mode="layout"` or rejoining wrapped lines, and ask before changing. |
| Repeated headers ("Page 3 Page 3") and the table of contents dots end up in chunks | Out of scope for v1 (spec). Note how much noise there is in T4 for later keyword-search work. |
| The splitter calls `length_function` many times, and the real tokenizer is slower than word counting | The tokenizer loads once and is cached in the module. Check that the 30-page PDF chunks in a few seconds in T3. |
| A fake reader doesn't match `pypdf`'s real API, so tests pass but real use fails | The injectable reader only uses `.pages` and `page.extract_text()`, which match pypdf 7.1.0. T3 runs the real reader on a real PDF. |
| Tests accidentally download the tokenizer | Tests always pass their own `count_tokens`. The module loads the tokenizer lazily, not on import. |
| Wrong tokenizer repo name | Use `MongoDB/<EMBEDDING_MODEL>`, as the client does. A T2 unit test checks that the repo name equals `f"{voyageai.util.HF_ORG}/{config.EMBEDDING_MODEL}"`, so a client upgrade that moves the repo fails the test. No network needed. |

## Out of scope

Hashing, embedding, database writes (`ingest.py`, the next spec), header and footer removal, golden questions, and any other PDF.
