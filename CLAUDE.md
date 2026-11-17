# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Citewise has no application code yet. The repo holds only `requirements.txt`, an empty `README.md`, an empty `.env` / `.env.example`, and an empty `data/` directory. Update this file once real modules, an entry point, and tests exist.

## Environment

- Python 3.12 virtualenv at `.venv/` (built from Homebrew `python@3.12`).
- Activate it with `source .venv/bin/activate`. Install dependencies with `pip install -r requirements.txt`.
- Config is loaded from `.env` via `python-dotenv`. Keep `.env.example` in sync with every variable the code reads.

## Commands

- Run tests: `pytest`
- Run a single test: `pytest path/to/test_file.py::test_name`

There is no linter, formatter, or build step configured yet.

## Intended stack (inferred from `requirements.txt`)

The pinned dependencies point to a document retrieval / citation pipeline:

- `pypdf` for PDF text extraction, with `langchain-text-splitters` for chunking
- `voyageai` for embeddings
- `psycopg` (v3) for Postgres, probably as the vector store
- `anthropic` for LLM generation
- `aiohttp` + `aiolimiter` + `tenacity` for rate-limited, retried async API calls

Treat this as a hint, not a spec. Confirm the design with the user before building against it.

## Repo hygiene

- `.venv/` (~13k files) and `.env` are committed, and there is no `.gitignore`. Don't add secrets to `.env` until `.env` is ignored and untracked.
