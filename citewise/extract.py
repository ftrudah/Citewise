"""Turn a PDF into one Page per PDF page, keeping page numbers for citations."""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class Page:
    number: int  # 1-based, as a reader would cite it
    text: str  # "" when the page has no extractable text


def extract_pages(path: str | Path, reader_factory=PdfReader) -> list[Page]:
    """One Page per PDF page, in order. Never skips a page.

    `reader_factory(path)` must return an object with `.pages`, each page having
    `.extract_text(**kwargs) -> str` (pypdf 7.1.0's PdfReader by default).
    """
    reader = reader_factory(path)
    return [
        Page(number=i, text=_normalize(page.extract_text(extraction_mode="plain")))
        for i, page in enumerate(reader.pages, start=1)
    ]


def empty_pages(pages: list[Page]) -> list[int]:
    """Page numbers with no extractable text, for the user-facing warning."""
    return [p.number for p in pages if not p.text]


def _normalize(text: str) -> str:
    """Light normalization only: CRLF to LF, strip the page. Paragraph breaks stay."""
    return text.replace("\r\n", "\n").strip()
