"""Unit tests for scripts/smoke_test.py. No network: every service is a fake."""

from types import SimpleNamespace

import pytest

from citewise import config
from scripts import smoke_test
from scripts.smoke_test import CheckFailed


# --- run_checks: ordering, stopping, reporting -------------------------------------


def test_run_checks_reports_every_service_and_returns_0_when_all_pass():
    lines = []
    checks = [("Database", lambda: "connected"), ("Voyage", lambda: "1024 dims")]

    code = smoke_test.run_checks(checks, secrets=[], out=lines.append)

    assert code == 0
    assert lines == ["✓ Database: connected", "✓ Voyage: 1024 dims"]


def test_run_checks_stops_at_first_failure_and_names_the_service():
    lines, ran = [], []

    def failing():
        raise RuntimeError("connection refused")

    checks = [
        ("Database", failing),
        ("Voyage", lambda: ran.append("voyage") or "ok"),
    ]

    code = smoke_test.run_checks(checks, secrets=[], out=lines.append)

    assert code == 1
    assert ran == []  # later checks never run
    assert lines == ["✗ Database failed: RuntimeError: connection refused"]


def test_run_checks_redacts_secrets_that_appear_in_an_error():
    lines = []

    def leaky():
        raise RuntimeError("bad key sk-secret-123 rejected")

    smoke_test.run_checks([("Claude", leaky)], secrets=["sk-secret-123"], out=lines.append)

    assert "sk-secret-123" not in lines[0]
    assert "***" in lines[0]


# --- redact ------------------------------------------------------------------------


def test_redact_masks_the_password_in_a_postgres_url_even_if_not_listed():
    text = "could not connect to postgresql://postgres.ref:hunter2@host:5432/postgres"

    assert "hunter2" not in smoke_test.redact(text, secrets=[])


def test_redact_ignores_empty_secrets():
    assert smoke_test.redact("plain text", secrets=["", None]) == "plain text"


def test_redact_masks_a_password_that_contains_an_at_sign():
    text = "bad dsn postgresql://postgres.ref:p@ss@host:5432/postgres"

    redacted = smoke_test.redact(text, secrets=[])

    assert "p@ss" not in redacted
    assert "ss@host" not in redacted


# --- database_secrets --------------------------------------------------------------


def test_database_secrets_include_the_password_raw_and_decoded():
    url = "postgresql://postgres.ref:p%40ss%2Fword@host:5432/postgres"

    secrets = smoke_test.database_secrets(url)

    assert url in secrets
    assert "p%40ss%2Fword" in secrets
    assert "p@ss/word" in secrets


def test_a_bare_password_in_an_error_is_masked_via_database_secrets():
    url = "postgresql://postgres.ref:hunter2@host:5432/postgres"
    lines = []

    def leaky():
        raise RuntimeError('invalid dsn: password "hunter2" not accepted')

    smoke_test.run_checks([("Database", leaky)], secrets=smoke_test.database_secrets(url), out=lines.append)

    assert "hunter2" not in lines[0]


# --- missing_settings --------------------------------------------------------------


def test_missing_settings_lists_unset_variable_names_only():
    cfg = SimpleNamespace(DATABASE_URL="postgresql://x", ANTHROPIC_API_KEY=None, VOYAGE_API_KEY=None)

    assert smoke_test.missing_settings(cfg) == ["ANTHROPIC_API_KEY", "VOYAGE_API_KEY"]


# --- check_voyage ------------------------------------------------------------------


class FakeVoyage:
    def __init__(self, dims):
        self.dims = dims
        self.calls = []

    def embed(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        return SimpleNamespace(embeddings=[[0.0] * self.dims], total_tokens=5)


def test_check_voyage_embeds_one_document_with_the_configured_model():
    fake = FakeVoyage(dims=config.EMBEDDING_DIM)

    detail = smoke_test.check_voyage(fake)

    texts, kwargs = fake.calls[0]
    assert len(texts) == 1
    assert kwargs == {"model": config.EMBEDDING_MODEL, "input_type": "document"}
    assert str(config.EMBEDDING_DIM) in detail


def test_check_voyage_fails_when_the_vector_has_the_wrong_length():
    with pytest.raises(CheckFailed, match=f"expected {config.EMBEDDING_DIM}"):
        smoke_test.check_voyage(FakeVoyage(dims=config.EMBEDDING_DIM // 2))


# --- check_claude ------------------------------------------------------------------


class FakeClaude:
    def __init__(self, response):
        self.messages = SimpleNamespace(create=lambda **kwargs: response)


def _response(stop_reason="end_turn", blocks=()):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


def test_check_claude_returns_the_reply_text():
    reply = _response(blocks=[SimpleNamespace(type="thinking", thinking=""),
                              SimpleNamespace(type="text", text="ok")])

    assert smoke_test.check_claude(FakeClaude(reply)) == "replied: ok"


def test_check_claude_fails_on_a_refusal():
    with pytest.raises(CheckFailed, match="refusal"):
        smoke_test.check_claude(FakeClaude(_response(stop_reason="refusal")))


def test_check_claude_fails_when_there_is_no_text():
    with pytest.raises(CheckFailed, match="no text"):
        smoke_test.check_claude(FakeClaude(_response(stop_reason="end_turn")))


def test_check_claude_explains_a_max_tokens_cutoff():
    thinking_only = _response(stop_reason="max_tokens",
                              blocks=[SimpleNamespace(type="thinking", thinking="")])

    with pytest.raises(CheckFailed, match="max_tokens"):
        smoke_test.check_claude(FakeClaude(thinking_only))


# --- check_database ----------------------------------------------------------------


class FakeCursor:
    """Each fetchone() returns the next row: a tuple, or None for "no row" (like psycopg)."""

    def __init__(self, rows):
        self.rows = list(rows)

    def execute(self, sql):
        return self

    def fetchone(self):
        return self.rows.pop(0)


class FakeConnection:
    def __init__(self, rows):
        self._cursor = FakeCursor(rows)

    def execute(self, sql):
        return self._cursor.execute(sql)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_check_database_reports_pgvector_version():
    connect = lambda url, **kw: FakeConnection([(1,), ("0.8.2",)])

    assert smoke_test.check_database("postgresql://x", connect=connect) == "select 1 ok, pgvector 0.8.2"


def test_check_database_fails_when_pgvector_is_missing():
    # No pg_extension row for 'vector' -> psycopg's fetchone() returns None.
    connect = lambda url, **kw: FakeConnection([(1,), None])

    with pytest.raises(CheckFailed, match="pgvector"):
        smoke_test.check_database("postgresql://x", connect=connect)
