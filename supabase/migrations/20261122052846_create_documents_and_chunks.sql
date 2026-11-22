-- Core tables: one row per ingested PDF, one row per embedded chunk.
-- Reviewed against the supabase-postgres-best-practices rules (2026-11-22).
--
-- No vector (HNSW) or full-text (tsvector + GIN) index yet: with a handful of
-- documents an exact scan is fast enough. Both arrive in the hybrid-search phase.

create table public.documents (
  id           uuid primary key default gen_random_uuid(),
  owner_id     uuid not null,
  filename     text not null,
  content_hash text not null,
  page_count   int check (page_count > 0),
  created_at   timestamptz not null default now(),
  -- Re-ingesting the same PDF for the same owner is a no-op (insert ... on conflict do nothing).
  -- The leading owner_id also serves "documents for this owner" lookups.
  unique (owner_id, content_hash),
  -- Target for the composite foreign key on chunks.
  unique (id, owner_id)
);

create table public.chunks (
  id              bigint generated always as identity primary key,
  document_id     uuid not null,
  owner_id        uuid not null,
  page            int not null check (page >= 1),
  chunk_index     int not null check (chunk_index >= 0),
  content         text not null,
  -- pgvector lives in the `extensions` schema (migration 20261122050656).
  embedding       extensions.vector(1024) not null,
  -- Flags stale vectors if the embedding model ever changes.
  embedding_model text not null,
  -- Its leading document_id column also indexes the foreign key below
  -- (Postgres doesn't index foreign keys on its own).
  unique (document_id, chunk_index),
  -- A chunk can't belong to a different owner than its document.
  foreign key (document_id, owner_id)
    references public.documents (id, owner_id) on delete cascade
);

-- Retrieval always filters chunks by owner.
create index chunks_owner_id_idx on public.chunks (owner_id);

-- Keep both tables out of Supabase's public Data API. The app connects as `postgres`
-- (the table owner) through DATABASE_URL, which RLS doesn't restrict without FORCE.
-- Per-user policies come with auth.
alter table public.documents enable row level security;
alter table public.chunks    enable row level security;
revoke all on public.documents, public.chunks from anon, authenticated, service_role;
