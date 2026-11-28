# Spec: PDF extraction and page-aware chunking

Status: approved 2026-11-27 · Last updated: 2026-11-27 · Parent: `docs/PRD.md` (first "After setup" task)

## Objective

Turn one PDF into a list of text chunks, each tagged with exactly one page number, ready to embed later. The owner reviews the printed chunks before anything is embedded or stored.

This covers the plan's ingestion steps 2 and 3: "Extract text per page" and "Chunk within pages". Hashing, embedding and storage (steps 1, 4 and 5) belong to `ingest.py`, the next spec.

**Acceptance criteria**
1. Every page of the PDF comes back as a `Page` with its 1-based page number, including pages with no text.
2. Pages with no extractable text (such as scanned images) are reported by number, not silently skipped.
3. No chunk crosses a page break: each chunk's text comes from one page only.
4. Chunks split on paragraph boundaries first, then lines, then words. Each is at most `CHUNK_TOKENS` (500) Voyage tokens, with `CHUNK_OVERLAP` (50) tokens of overlap between neighboring chunks on the same page.
5. `chunk_index` runs 0, 1, 2… across the whole document, matching the `unique (document_id, owner_id, chunk_index)` constraint.
6. One command prints the chunks of a PDF with their page numbers, for the owner to review.
7. No API keys and no database are needed. The only network use is the one-time tokenizer download, which is cached afterward.

## Decisions (owner-approved)

| Decision | Choice |
|---|---|
| Chunking library | `langchain-text-splitters` 1.1.3, `RecursiveCharacterTextSplitter` (approved 2026-11-22) |
| Token counting | Voyage's own `voyage-4` tokenizer, loaded locally with `tokenizers` (approved 2026-11-22) |
| PDF extractor | `pypdf` 7.1.0, `extraction_mode="plain"`; swap only if the text is poor (PRD) |

## Design

### `citewise/extract.py`

```python
@dataclass(frozen=True)
class Page:
    number: int   # 1-based, as a reader would cite it
    text: str     # "" when the page has no extractable text


def extract_pages(path: str | Path, reader_factory=PdfReader) -> list[Page]:
    """One Page per PDF page, in order. Never skips a page."""
```

- Uses `reader_factory(path)`, which defaults to `pypdf.PdfReader`, and calls `page.extract_text(extraction_mode="plain")` on each page (checked against the installed 7.1.0 signatures). Tests pass a fake factory: any object with `.pages` whose pages have `.extract_text(**kwargs) -> str` works.
- Light normalization only: `\r\n` becomes `\n`, and leading and trailing whitespace is stripped from each page. Paragraph breaks are kept.
- A page whose text is empty after stripping keeps `text=""`. Reporting it is the caller's job (see `empty_pages`).

```python
def empty_pages(pages: list[Page]) -> list[int]:
    """Page numbers with no extractable text, for the user-facing warning."""
```

### `citewise/chunking.py`

```python
@dataclass(frozen=True)
class Chunk:
    page: int          # the single page this text came from
    chunk_index: int   # 0-based, unique across the document
    content: str
    token_count: int   # Voyage tokens, for review and later tuning


def chunk_pages(
    pages: list[Page],
    chunk_tokens: int = config.CHUNK_TOKENS,
    overlap: int = config.CHUNK_OVERLAP,
    count_tokens: Callable[[str], int] | None = None,
) -> list[Chunk]:
    """Split each page on its own; empty pages produce no chunks."""
```

- A `RecursiveCharacterTextSplitter` with `chunk_size=chunk_tokens`, `chunk_overlap=overlap` and `length_function=count_tokens`. The default separators are `["\n\n", "\n", " ", ""]`.
- The splitter runs once **per page**, so overlap and splitting never reach across a page break.
- `count_tokens` defaults to the Voyage tokenizer: `tokenizers.Tokenizer.from_pretrained("voyageai/voyage-4")`. That's the same call `voyageai.Client.tokenizer` makes internally, so no API key is needed. It's loaded once and cached in the module. Tests pass in their own counter, so they never touch the network.
- The tokenizer repo is derived from `config.EMBEDDING_MODEL`, so changing the model keeps the token counts consistent.
- **Verified 2026-11-22:** the tokenizer downloads from Hugging Face and loads in under a second, and its count matches `voyageai.Client.count_tokens` (17 = 17 on a sample sentence).

### `scripts/show_chunks.py`

```bash
python scripts/show_chunks.py data/<file>.pdf          # summary + every chunk
python scripts/show_chunks.py data/<file>.pdf --head 5 # summary + first 5 chunks
```

Output: the page count, the empty pages (if any), the chunk count and tokens per chunk (min, average, max), then each chunk as `[chunk 3 · page 2 · 487 tokens]` followed by its text.

## Commands

```bash
pytest tests/test_extract.py tests/test_chunking.py   # unit tests, no network
python scripts/show_chunks.py data/<file>.pdf         # owner review
```

## Testing strategy (TDD: tests first)

Small tests only, with no network and no PDFs on disk:

- **extract:** a fake reader with three pages: text, an empty page, and text with `\r\n`. Checks: three `Page`s numbered 1–3, the empty page kept as `""`, line endings normalized, and `empty_pages` returning `[2]`. The reader is injectable, so no fixture PDF is needed.
- **chunking:** a deterministic counter (1 word = 1 token) so sizes are predictable:
  - a short page gives one chunk;
  - a long page gives several chunks, none over `chunk_tokens`;
  - neighboring chunks on one page share overlap text;
  - **two pages never share a chunk**, and no chunk's text spans the page break;
  - `chunk_index` is continuous across pages;
  - paragraph breaks are preferred over mid-paragraph breaks;
  - empty pages produce no chunks.
- **Manual review:** run `show_chunks.py` on `data/docent_handbook_13-14.pdf` and read the output together. That PDF has 30 pages, pages 2 and 29 have no text, and some pages repeat headers (page 3 begins "Page 3 Page 3"). So the review checks the empty-page report and shows how much header noise ends up in chunks.

## Boundaries

- **Always:** take every tunable from `config.py`; keep `extract.py` and `chunking.py` free of I/O beyond reading the PDF and loading the tokenizer.
- **Ask first:** changing the extractor, adding header and footer removal, or changing chunk sizes away from config.
- **Never:** call the Voyage or Anthropic APIs or touch the database here; commit PDFs (`data/` is git-ignored); use `data/docent_handbook_13-14.pdf` for golden questions, eval baselines, committed fixtures or README examples (its license is unknown, so it's for local testing only).

## Success criteria

- [ ] Unit tests for extract and chunking pass with `pytest`, with no network.
- [ ] `show_chunks.py` runs on a real PDF and every chunk shows one page number.
- [ ] The owner has reviewed the printed chunks and either accepted the quality or asked for a change.

## Risks

| Risk | Mitigation |
|---|---|
| `pypdf` plain mode often ends every visual line with `\n` and rarely emits `\n\n`, so "paragraph" splitting can degrade to line splitting | The review will show it. If chunks break badly, try `extraction_mode="layout"` or rejoin wrapped lines, but only after asking. |
| Repeated headers, footers and page numbers end up inside chunks | Out of scope for v1. Note it in review; it may matter for keyword search later. |
| The tokenizer download fails offline | It's needed only on first run, then cached in `~/.cache/huggingface`. Tests never download it. |

## Resolved questions

1. **Which PDF for the review?** Resolved 2026-11-27: `data/docent_handbook_13-14.pdf` (UMKC School of Medicine "Fundamentals of Medicine Handbook"). The PDF states no license, so it's for **local testing only**.

## Follow-ups (outside this spec)

- Find 3–4 openly licensed PDFs (CC BY or public domain) before the golden set work starts, and record each one's source and license.
