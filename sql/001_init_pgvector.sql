CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  corpus_id VARCHAR(100) NOT NULL,
  embedding_model VARCHAR(255) NOT NULL,
  embedding_revision VARCHAR(100) NOT NULL,
  chunk_id VARCHAR(64) NOT NULL,
  document_id VARCHAR(100) NOT NULL,
  heading TEXT NOT NULL,
  citation_label TEXT NOT NULL,
  domain VARCHAR(100) NOT NULL,
  status VARCHAR(64) NOT NULL,
  business_authority BOOLEAN NOT NULL,
  audience VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  content_hash VARCHAR(64) NOT NULL,
  chunk_index INTEGER NOT NULL,
  embedding vector(384) NOT NULL,
  last_ingest_run_id UUID NOT NULL,
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  CONSTRAINT knowledge_chunks_audience_check
    CHECK (audience IN ('customer', 'staff_internal', 'shared')),
  CONSTRAINT knowledge_chunks_embedding_dimension_check
    CHECK (vector_dims(embedding) = 384),
  CONSTRAINT knowledge_chunks_namespace_chunk_key
    UNIQUE (corpus_id, embedding_model, embedding_revision, chunk_id)
);

CREATE INDEX IF NOT EXISTS knowledge_chunks_scope_idx
  ON knowledge_chunks (corpus_id, embedding_model, embedding_revision, audience);

CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw_idx
  ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
