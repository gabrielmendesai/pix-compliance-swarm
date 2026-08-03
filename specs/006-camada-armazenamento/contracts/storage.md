# Contrato: `src/pix_compliance/object_store.py` e `src/pix_compliance/vector_store.py`

Esta feature não expõe uma API HTTP/CLI própria — o "contrato" é a interface
Python que os agentes/pipelines do enxame (specs futuras) consomem para
persistir e recuperar artefatos binários e vetores de embedding. Documentado
aqui em vez de OpenAPI/JSON Schema porque o consumidor é código Python
interno, não um cliente externo.

## Protocol `ObjectStore`

```python
class ObjectStore(Protocol):
    def upload(self, key: str, data: bytes) -> None:
        """Grava `data` sob `key` no bucket configurado. Sobrescreve se a
        chave já existir."""

    def download(self, key: str) -> bytes:
        """Retorna os bytes gravados sob `key`. Levanta ObjectNotFoundError
        se a chave não existir — nunca propaga o erro cru do boto3/botocore."""
```

**Implementação concreta**: `S3ObjectStore`, via `boto3.client("s3",
endpoint_url=settings.object_storage_endpoint)` — a mesma classe serve MinIO
local (endpoint local) e S3 real (endpoint AWS ou omitido), por ser esse o
seam real que justifica o `Protocol` (Princípio II, comentado explicitamente
no código conforme exigido pela spec).

**Pré-condição do chamador**: todo texto gravado via `upload` que se origina
de conteúdo livre (não binário fixo) MUST já ter atravessado
`pix_compliance.guardrails.guard()` (SPEC-004) antes desta chamada — esta
camada não reaplica o guardrail, apenas persiste o que recebe (Princípio V).

## Classe concreta `PgVectorStore` (sem `Protocol`)

```python
class PgVectorStore:
    def upsert(self, record: VectorRecord) -> None:
        """Insere ou atualiza (por record.id) um vetor com metadados.
        Levanta VectorDimensionError se len(record.embedding) !=
        settings.embedding_dimension, antes de qualquer escrita."""

    def similarity_search(
        self, query_embedding: list[float], top_k: int = 5,
        metadata_filter: dict[str, str | int | float | bool] | None = None,
    ) -> list[SearchResult]:
        """Retorna os top_k vetores mais similares (distância de cosseno) a
        query_embedding, restritos por metadata_filter quando fornecido.
        Retorna lista vazia se nenhum vetor satisfizer o filtro."""
```

**Por que classe concreta, sem interface**: única implementação de vector
store deste projeto — a alternativa (OpenSearch Serverless) fica documentada
em prosa em `docs/architecture.md` (ADR-01), nunca como stub de código morto
(Princípio II, comentado explicitamente no código).

## Exceções expostas (ver data-model.md para detalhe completo)

```python
class ObjectNotFoundError(Exception): ...
class VectorDimensionError(Exception): ...
```

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. `S3ObjectStore.upload(key, data)` seguido de `download(key)` → bytes
   idênticos (hash SHA-256 igual) ao original (SC-001).
2. `S3ObjectStore.download("chave-inexistente")` → `ObjectNotFoundError`.
3. `PgVectorStore.upsert` com 10 `VectorRecord` de dimensão 512, seguido de
   `similarity_search` com um vetor de consulta conhecido → retorna o
   resultado esperado, dado o conjunto de teste (SC-002).
4. `PgVectorStore.upsert` com um vetor de dimensão diferente de 512 →
   `VectorDimensionError`, nenhuma escrita realizada.
5. `PgVectorStore.similarity_search` com `metadata_filter` que não corresponde
   a nenhum vetor armazenado → lista vazia, sem erro.
6. Ambos os testes acima rodando contra `docker compose up postgres minio`
   (SC-003), sem mock do driver Postgres nem do `boto3`.
