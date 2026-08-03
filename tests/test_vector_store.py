"""Testes de round-trip do vector store (SPEC-006, US2).

Escritos antes de `PgVectorStore` existir (Princípio IX da constituição) —
rodam contra o Postgres/pgvector real subido via `docker compose up postgres`
com a migration 0001 já aplicada, sem mock do driver (a spec exige que a
busca por similaridade funcione contra o serviço de fato).
"""

import uuid

import pytest

REQUIRED_ENV = {
    "AWS_ACCESS_KEY_ID": "AKIAFAKEEXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "fake-secret",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "anthropic.claude-3-fake",
    "BEDROCK_EMBEDDINGS_MODEL_ID": "amazon.titan-embed-fake",
    "API_URL": "http://localhost:8000",
    "POSTGRES_DSN": "postgresql://pix:pix@localhost:5432/pix_compliance",
    "OBJECT_STORAGE_ENDPOINT": "http://localhost:9000",
    "OBJECT_STORAGE_ACCESS_KEY": "minioadmin",
    "OBJECT_STORAGE_SECRET_KEY": "minioadmin",
    "OBJECT_STORAGE_BUCKET": "pix-compliance-test",
    "BCB_BASE_URL": "http://localhost:8080",
    "MCP_SCRAPER_HOST": "127.0.0.1",
    "MCP_SCRAPER_PORT": "8100",
    "COMPLIANCE_ANALYZER_MAX_CONCURRENCY": "3",
    "COMPLIANCE_ANALYZER_CONFIDENCE_THRESHOLD": "0.7",
}

DIMENSION = 512


def _settings(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    from pix_compliance.config import Settings

    return Settings(_env_file=None)


def _unit_vector(dim: int, hot_index: int) -> list[float]:
    """Vetor com 1.0 em `hot_index` e 0.0 nas demais posições — vetores
    ortogonais entre si, permitindo prever com exatidão qual é o mais
    similar a uma dada consulta na busca por distância de cosseno."""
    vector = [0.0] * dim
    vector[hot_index] = 1.0
    return vector


@pytest.fixture
def store(monkeypatch):
    from pix_compliance.vector_store import PgVectorStore

    return PgVectorStore(_settings(monkeypatch))


@pytest.fixture
def run_id() -> str:
    # Prefixo único por execução de teste, para não colidir com linhas de
    # outras execuções na mesma tabela compartilhada (banco de desenvolvimento).
    return uuid.uuid4().hex[:8]


def test_upsert_and_similarity_search_returns_expected_nearest(store, run_id) -> None:
    from pix_compliance.vector_store import VectorRecord

    records = [
        VectorRecord(
            id=f"{run_id}-vec-{i}",
            embedding=_unit_vector(DIMENSION, i),
            metadata={"run": run_id, "index": i},
        )
        for i in range(10)
    ]
    for record in records:
        store.upsert(record)

    query = _unit_vector(DIMENSION, 3)
    results = store.similarity_search(query, top_k=1, metadata_filter={"run": run_id})

    assert len(results) == 1
    assert results[0].id == f"{run_id}-vec-3"


def test_similarity_search_respects_metadata_filter(store, run_id) -> None:
    from pix_compliance.vector_store import VectorRecord

    store.upsert(
        VectorRecord(
            id=f"{run_id}-a",
            embedding=_unit_vector(DIMENSION, 0),
            metadata={"run": run_id, "grupo": "a"},
        )
    )
    store.upsert(
        VectorRecord(
            id=f"{run_id}-b",
            embedding=_unit_vector(DIMENSION, 0),
            metadata={"run": run_id, "grupo": "b"},
        )
    )

    results = store.similarity_search(
        _unit_vector(DIMENSION, 0),
        top_k=10,
        metadata_filter={"run": run_id, "grupo": "b"},
    )

    assert {result.id for result in results} == {f"{run_id}-b"}


def test_upsert_rejects_wrong_dimension_before_any_write(store, run_id) -> None:
    from pix_compliance.vector_store import VectorDimensionError, VectorRecord

    record = VectorRecord(id=f"{run_id}-bad", embedding=[0.0] * (DIMENSION - 1), metadata={})

    with pytest.raises(VectorDimensionError):
        store.upsert(record)

    results = store.similarity_search(
        _unit_vector(DIMENSION, 0), top_k=10, metadata_filter={"run": run_id}
    )
    assert all(result.id != f"{run_id}-bad" for result in results)


def test_similarity_search_with_no_matching_metadata_returns_empty_list(store, run_id) -> None:
    from pix_compliance.vector_store import VectorRecord

    store.upsert(
        VectorRecord(
            id=f"{run_id}-only",
            embedding=_unit_vector(DIMENSION, 0),
            metadata={"run": run_id},
        )
    )

    results = store.similarity_search(
        _unit_vector(DIMENSION, 0),
        top_k=10,
        metadata_filter={"run": run_id, "grupo": "inexistente"},
    )

    assert results == []
