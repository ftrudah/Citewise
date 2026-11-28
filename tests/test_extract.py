"""Unit tests for citewise/extract.py. No network and no real PDF: the reader is a fake."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from citewise.extract import Page, empty_pages, extract_pages


class FakePage:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def extract_text(self, **kwargs):
        self.calls.append(kwargs)
        return self._text


class FakeReader:
    def __init__(self, texts):
        self.pages = [FakePage(t) for t in texts]


THREE_PAGES = [
    "  First page.\n\nSecond paragraph.  \n",
    "   \n\t ",
    "Line one\r\nLine two\r\n\r\nNew paragraph\r\n",
]


def make_factory(texts, opened=None):
    reader = FakeReader(texts)

    def factory(path):
        if opened is not None:
            opened.append(path)
        return reader

    return factory, reader


def test_returns_one_page_per_pdf_page_numbered_from_1():
    factory, _ = make_factory(THREE_PAGES)

    pages = extract_pages("doc.pdf", reader_factory=factory)

    assert [p.number for p in pages] == [1, 2, 3]
    assert all(isinstance(p, Page) for p in pages)


def test_strips_each_page_and_keeps_paragraph_breaks():
    factory, _ = make_factory(THREE_PAGES)

    pages = extract_pages("doc.pdf", reader_factory=factory)

    assert pages[0].text == "First page.\n\nSecond paragraph."


def test_empty_page_is_kept_as_empty_string():
    factory, _ = make_factory(THREE_PAGES)

    pages = extract_pages("doc.pdf", reader_factory=factory)

    assert pages[1] == Page(number=2, text="")


def test_crlf_becomes_lf():
    factory, _ = make_factory(THREE_PAGES)

    pages = extract_pages("doc.pdf", reader_factory=factory)

    assert pages[2].text == "Line one\nLine two\n\nNew paragraph"
    assert "\r" not in pages[2].text


def test_empty_pages_lists_page_numbers_without_text():
    factory, _ = make_factory(THREE_PAGES)

    pages = extract_pages("doc.pdf", reader_factory=factory)

    assert empty_pages(pages) == [2]


def test_empty_pages_is_empty_when_every_page_has_text():
    assert empty_pages([Page(1, "a"), Page(2, "b")]) == []


def test_calls_extract_text_in_plain_mode():
    factory, reader = make_factory(THREE_PAGES)

    extract_pages("doc.pdf", reader_factory=factory)

    for page in reader.pages:
        assert page.calls == [{"extraction_mode": "plain"}]


@pytest.mark.parametrize("path", ["doc.pdf", Path("doc.pdf")])
def test_passes_path_to_reader_factory(path):
    opened = []
    factory, _ = make_factory(["x"], opened)

    extract_pages(path, reader_factory=factory)

    assert opened == [path]


def test_pdf_with_no_pages_gives_empty_list():
    factory, _ = make_factory([])

    assert extract_pages("doc.pdf", reader_factory=factory) == []


def test_page_is_frozen():
    page = Page(1, "text")

    with pytest.raises(FrozenInstanceError):
        page.text = "changed"


def test_default_reader_factory_is_pypdf_reader():
    import inspect

    from pypdf import PdfReader

    default = inspect.signature(extract_pages).parameters["reader_factory"].default
    assert default is PdfReader
