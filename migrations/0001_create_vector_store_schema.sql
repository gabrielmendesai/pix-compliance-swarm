-- SPEC-006: schema do vector store (PgVectorStore).
--
-- Dimensão do vetor (512) travada em src/pix_compliance/config.py
-- (EMBEDDING_DIMENSION) — mantenha os dois em sincronia caso o modelo de
-- embeddings mude no futuro (decisão da SPEC-005: Titan Text Embeddings V2).
--
-- Índice HNSW escolhido em vez de IVFFlat por não exigir um parâmetro de
-- calibração (número de listas) dependente de volume de dados ainda
-- desconhecido neste projeto (ver research.md, Decisão 3).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS vector_store (
    id TEXT PRIMARY KEY,
    embedding VECTOR(512) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS vector_store_embedding_hnsw_idx
    ON vector_store
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS vector_store_metadata_gin_idx
    ON vector_store
    USING gin (metadata);
