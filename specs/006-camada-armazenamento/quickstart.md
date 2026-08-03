# Quickstart: Camada de armazenamento (SPEC-006)

## Pré-requisitos

- Python 3.11+ e dependências instaladas (`pip install -e ".[dev]"` após esta
  feature adicionar `psycopg[binary]` e `pgvector` a `pyproject.toml` — `boto3`
  já é dependência existente desde a SPEC-005).
- `.env` preenchido a partir de `.env.example`, com `POSTGRES_DSN` e
  `OBJECT_STORAGE_ENDPOINT` válidos (já documentados desde a SPEC-001).
- Docker e Docker Compose instalados para subir `postgres` (imagem
  `pgvector/pgvector:pg16`) e `minio` localmente.

## Cenário 1 — Subir os serviços locais (pré-requisito de SC-003)

```bash
docker compose up postgres minio -d
```

**Resultado esperado**: os dois serviços sobem e ficam prontos para aceitar
conexões (Postgres na porta configurada em `POSTGRES_DSN`, MinIO na porta
configurada em `OBJECT_STORAGE_ENDPOINT`).

## Cenário 2 — Aplicar a migration do schema de vetores

```bash
psql "$POSTGRES_DSN" -f migrations/0001_create_vector_store_schema.sql
```

**Resultado esperado**: a extensão `vector`, a tabela de vetores (coluna
`embedding vector(512)`) e o índice HNSW são criados — sem esse passo, os
testes de `PgVectorStore` (Cenário 4) falham por tabela inexistente,
confirmando o Princípio IX (teste escrito antes de existir implementação ou
schema).

## Cenário 3 — Round-trip do object store (SC-001)

```bash
pytest tests/test_object_store.py -q
```

**Resultado esperado**: upload de um blob de bytes, download em seguida, hash
SHA-256 idêntico ao original — documentado em `contracts/storage.md`,
cenário 1.

## Cenário 4 — Round-trip vetorial com busca por similaridade (SC-002)

```bash
pytest tests/test_vector_store.py -q
```

**Resultado esperado**: upsert de 10 vetores de dimensão 512, busca por
similaridade retorna o resultado esperado, e uma tentativa de `upsert` com
dimensão incorreta é rejeitada com `VectorDimensionError` antes de qualquer
escrita — documentado em `contracts/storage.md`, cenários 3 e 4.

## Cenário 5 — Suíte completa contra os serviços reais (SC-003)

```bash
docker compose up postgres minio -d
psql "$POSTGRES_DSN" -f migrations/0001_create_vector_store_schema.sql
pytest tests/test_object_store.py tests/test_vector_store.py -q
```

**Resultado esperado**: todos os testes de round-trip passam contra os
serviços reais, sem mock do `boto3` nem do driver Postgres.

## Cenário 6 — Confirmar ausência de abstração órfã (SC-004)

```bash
python -c "
import inspect
import pix_compliance.object_store as os_mod
import pix_compliance.vector_store as vs_mod
print('ObjectStore is Protocol:', hasattr(os_mod.ObjectStore, '_is_protocol'))
print('PgVectorStore is concrete class:', inspect.isclass(vs_mod.PgVectorStore))
"
```

**Resultado esperado**: confirma que `ObjectStore` continua sendo o único
`Protocol` desta feature (com `S3ObjectStore` como implementação concreta) e
que `PgVectorStore` é classe concreta, sem interface — nenhum protocolo ou
classe abstrata órfã (sem implementação) introduzido pela feature.

## Checklist de leitura antes de implementar

- [research.md](./research.md) — decisões de cliente S3/MinIO, driver
  Postgres, tipo de índice vetorial (HNSW), migrations em SQL puro, imagem
  Docker do pgvector.
- [data-model.md](./data-model.md) — `VectorRecord`, `SearchResult`,
  exceções tipadas, schema SQL da tabela de vetores, ponto único de
  `Protocol`.
- [contracts/storage.md](./contracts/storage.md) — assinatura das funções
  públicas de `ObjectStore`/`PgVectorStore` e cenários de contrato cobertos
  por teste.

**Lembrete do Princípio IX**: `tests/test_object_store.py` e
`tests/test_vector_store.py` devem ser escritos e confirmados como falhos
(por ausência de implementação) antes de `object_store.py`/`vector_store.py`
existirem — ver ordenação de tarefas em `tasks.md` (gerado por
`/speckit-tasks`).
