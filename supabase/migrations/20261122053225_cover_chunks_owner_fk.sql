-- Fully cover the composite foreign key chunks(document_id, owner_id) with an index.
--
-- The performance advisor flagged chunks_document_id_owner_id_fkey as unindexed
-- (lint 0001_unindexed_foreign_keys): the old unique index (document_id, chunk_index)
-- only matched its first column.
--   https://supabase.com/docs/guides/database/database-linter?lint=0001_unindexed_foreign_keys
--
-- Widening the unique to (document_id, owner_id, chunk_index) doesn't change what it
-- guarantees: each document has exactly one owner (documents.id is the primary key, and
-- the composite FK pins chunks.owner_id to it), so the rule is still "one chunk per
-- index per document". It just gains a leading (document_id, owner_id) prefix, with no
-- extra index.
--
-- The new constraint is added before the old one is dropped, so uniqueness is never
-- missing. The table is empty, so the rebuild takes no time.

alter table public.chunks
  add constraint chunks_document_id_owner_id_chunk_index_key
  unique (document_id, owner_id, chunk_index);

alter table public.chunks
  drop constraint chunks_document_id_chunk_index_key;
