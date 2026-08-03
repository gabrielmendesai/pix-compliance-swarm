"""Vector store sobre PostgreSQL/pgvector (SPEC-006).

`PgVectorStore` é classe concreta, sem `Protocol`, porque este projeto
implementa apenas uma opção de índice vetorial — não há uma segunda
implementação real nem um teste que precise substituí-la (Princípio II da
constituição, YAGNI). A alternativa considerada (OpenSearch Serverless) fica
documentada em prosa em `docs/architecture.md` (ADR-01), nunca como stub de
código morto neste módulo.
"""

from typing import TYPE_CHECKING

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from pix_compliance.config import Settings

MetadataValue = str | int | float | bool


class VectorDimensionError(Exception):
    """Vetor com dimensão diferente da esperada (`settings.embedding_dimension`)
    — rejeitado antes de qualquer escrita, mensagem acionável análoga a
    `ConfigurationError` (SPEC-001)."""


class VectorRecord(BaseModel):
    """Contrato de entrada de `PgVectorStore.upsert`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    embedding: list[float]
    metadata: dict[str, MetadataValue] = {}


class SearchResult(BaseModel):
    """Contrato de saída de `PgVectorStore.similarity_search`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    score: float
    metadata: dict[str, MetadataValue]


class PgVectorStore:
    """Implementação concreta (sem `Protocol`) do vector store sobre
    PostgreSQL/pgvector — única implementação de vector store deste
    projeto. A alternativa considerada (OpenSearch Serverless) fica
    documentada em prosa em `docs/architecture.md` (ADR-01), nunca como
    stub de código morto aqui."""

    def __init__(self, settings: "Settings") -> None:
        self._embedding_dimension = settings.embedding_dimension
        self._conn = psycopg.connect(settings.postgres_dsn, autocommit=True)
        register_vector(self._conn)

    def upsert(self, record: VectorRecord) -> None:
        if len(record.embedding) != self._embedding_dimension:
            raise VectorDimensionError(
                f"dimensão do vetor incompatível: esperado "
                f"{self._embedding_dimension}, recebido {len(record.embedding)}"
            )
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO vector_store (id, embedding, metadata)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata
                """,
                (record.id, Vector(record.embedding), Jsonb(record.metadata)),
            )

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        metadata_filter: dict[str, MetadataValue] | None = None,
    ) -> list[SearchResult]:
        query_vector = Vector(query_embedding)
        where_clause = ""
        params: list[object] = [query_vector]
        if metadata_filter:
            where_clause = "WHERE metadata @> %s"
            params.append(Jsonb(metadata_filter))
        params.extend([query_vector, top_k])

        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, embedding <=> %s AS score, metadata
                FROM vector_store
                {where_clause}
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()

        return [
            SearchResult(id=row[0], score=float(row[1]), metadata=row[2]) for row in rows
        ]
