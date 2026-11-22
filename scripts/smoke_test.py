"""Check that the database, Voyage and Claude all answer, so later failures are code, not setup.

Run from the repo root:  python scripts/smoke_test.py

Stops at the first failing service, names it and exits 1. Never prints keys or the
connection string: error text is redacted before it's shown.

This script is a deliberate exception to two project rules ("only embeddings.py and
answer.py call Voyage/Anthropic", "SQL lives in retrieve.py and migrations"): it checks
the services themselves, before those modules exist.
"""

import re
import sys
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import unquote, urlsplit

# Running `python scripts/smoke_test.py` puts scripts/ on sys.path, not the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from citewise import config  # noqa: E402

SECRET_SETTINGS = ("DATABASE_URL", "ANTHROPIC_API_KEY", "VOYAGE_API_KEY")
# Greedy up to the last "@" in the URL, so a password containing "@" is masked whole.
_URL_PASSWORD = re.compile(r"(postgres(?:ql)?://[^:/@\s]+:)\S+@")


class CheckFailed(Exception):
    """A service answered, but not with what we expected."""


def redact(text: str, secrets: Iterable[str | None]) -> str:
    """Mask every known secret, plus any password embedded in a Postgres URL."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return _URL_PASSWORD.sub(r"\1***@", text)


def database_secrets(url: str | None) -> list[str]:
    """The URL plus its password, raw and URL-decoded, so a bare password in an error is masked too."""
    if not url:
        return []
    secrets = [url]
    try:
        password = urlsplit(url).password
    except ValueError:  # malformed URL: fall back to the regex in redact()
        password = None
    if password:
        secrets += [password, unquote(password)]
    return secrets


def missing_settings(cfg=config) -> list[str]:
    """Names (never values) of required settings that are unset."""
    return [name for name in SECRET_SETTINGS if not getattr(cfg, name)]


def check_database(url: str, connect: Callable | None = None) -> str:
    if connect is None:
        import psycopg

        connect = psycopg.connect
    with connect(url, connect_timeout=10) as conn:
        conn.execute("select 1").fetchone()
        (version,) = conn.execute(
            "select extversion from pg_extension where extname = 'vector'"
        ).fetchone() or (None,)
    if not version:
        raise CheckFailed("connected, but the pgvector extension is not installed")
    return f"select 1 ok, pgvector {version}"


def check_voyage(client) -> str:
    # voyageai 0.6.0: Client.embed(texts, model, input_type, ...) -> .embeddings (list of vectors).
    # voyage-4 defaults to 1024 dims; input_type "document" for chunks, "query" for questions.
    # https://docs.voyageai.com/docs/embeddings
    result = client.embed(
        ["Citewise smoke test sentence."],
        model=config.EMBEDDING_MODEL,
        input_type="document",
    )
    dims = len(result.embeddings[0])
    if dims != config.EMBEDDING_DIM:
        raise CheckFailed(f"got a {dims}-dim vector, expected {config.EMBEDDING_DIM}")
    return f"{config.EMBEDDING_MODEL} returned a {dims}-dim vector"


def check_claude(client) -> str:
    # Claude Haiku 5.5 thinks by default (adaptive); thinking can be disabled at effort
    # "high" or below, so a short check can't spend its whole budget on thinking.
    # Effort lives in output_config. Sources: the claude-api skill's thinking/effort table;
    # https://platform.claude.com/docs/en/build-with-claude/effort
    response = client.messages.create(
        model=config.GENERATION_MODEL,
        max_tokens=1024,
        thinking={"type": "disabled"},
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": "Reply with exactly one word: ok"}],
    )
    if response.stop_reason == "refusal":
        raise CheckFailed("the model returned a refusal")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text and response.stop_reason == "max_tokens":
        raise CheckFailed("hit max_tokens before any text; the service answered, but the check needs more room")
    if not text:
        raise CheckFailed(f"no text in the reply (stop_reason={response.stop_reason})")
    return f"replied: {text}"


def run_checks(
    checks: list[tuple[str, Callable[[], str]]],
    secrets: Iterable[str | None],
    out: Callable[[str], None] = print,
) -> int:
    """Run checks in order; stop at the first failure. Returns a process exit code."""
    secrets = list(secrets)
    for name, check in checks:
        try:
            detail = check()
        except Exception as exc:  # report any failure, whatever raised it
            out(redact(f"✗ {name} failed: {type(exc).__name__}: {exc}", secrets))
            return 1
        out(redact(f"✓ {name}: {detail}", secrets))
    return 0


def main() -> int:
    missing = missing_settings()
    if missing:
        print(f"✗ Missing in .env: {', '.join(missing)}")
        return 1

    import anthropic
    import voyageai

    voyage = voyageai.Client(api_key=config.VOYAGE_API_KEY, max_retries=2, timeout=30)
    claude = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=60)

    checks = [
        ("Database", lambda: check_database(config.DATABASE_URL)),
        ("Voyage", lambda: check_voyage(voyage)),
        ("Claude", lambda: check_claude(claude)),
    ]
    secrets = [config.ANTHROPIC_API_KEY, config.VOYAGE_API_KEY, *database_secrets(config.DATABASE_URL)]
    return run_checks(checks, secrets)


if __name__ == "__main__":
    sys.exit(main())
