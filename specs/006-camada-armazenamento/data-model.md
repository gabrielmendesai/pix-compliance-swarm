# Data Model: Camada de armazenamento (SPEC-006)

Todos os modelos seguem o padrão já estabelecido em `config.py`/`llm_provider.py`:
Pydantic v2 (`extra="forbid"`) para contratos de dados, identificadores em
inglês, docstrings/comentários em português explicando o porquê.

## Settings.embedding_dimension (extensão de `config.py`)

| Campo | Tipo | Validação | Descrição |
|---|---|---|---|
| `embedding_dimension` | `int` | valor fixo `512` | Dimensão do vetor Titan Text Embeddings V2 (SPEC-005), centralizada aqui e reutilizada tanto na criação do schema (migration) quanto na validação de `PgVectorStore.upsert` |

**Regra de negócio**: este valor não é lido de variável de ambiente — é uma
constante de domínio (a dimensão do modelo de embeddings já escolhido na
SPEC-005), travada em código para que a migration SQL e a validação em tempo
de execução nunca divirjam por configuração incorreta.

## VectorRecord (contrato de entrada de `upsert`)

| Campo | Tipo | Validação | Descrição |
|---|---|---|---|
| `id` | `str` | obrigatório | Identificador único do registro (chave de upsert — mesmo `id` sobrescreve) |
| `embedding` | `list[float]` | `len == settings.embedding_dimension` (512) | Vetor de embedding a persistir |
| `metadata` | `dict[str, str \| int \| float \| bool]` | opcional, default `{}` | Metadados usados como filtro em `similarity_search` |

**Regra de negócio**: se `len(embedding) != settings.embedding_dimension`,
`PgVectorStore.upsert` MUST rejeitar a operação antes de qualquer escrita,
levantando `VectorDimensionError` com a dimensão esperada e a recebida
(Edge Case do spec.md) — nunca deixar o Postgres rejeitar silenciosamente ou
truncar o vetor.

## SearchResult (contrato de saída de `similarity_search`)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | `str` | Identificador do registro encontrado |
| `score` | `float` | Distância/similaridade (cosseno) em relação ao vetor de consulta |
| `metadata` | `dict[str, str \| int \| float \| bool]` | Metadados armazenados junto ao vetor |

## VectorDimensionError / ObjectNotFoundError (exceções tipadas)

Hierarquia análoga a `ConfigurationError` (SPEC-001) e `BedrockProviderError`
(SPEC-005): mensagem acionável em vez de erro cru do driver/SDK subjacente.

| Exceção | Quando é levantada | Mensagem |
|---|---|---|
| `VectorDimensionError` | `PgVectorStore.upsert` recebe vetor com dimensão diferente de `settings.embedding_dimension` | Inclui a dimensão esperada (512) e a recebida |
| `ObjectNotFoundError` | `ObjectStore.download` é chamado para uma chave inexistente no bucket | Inclui a chave buscada, substituindo o erro cru do `boto3`/`botocore` |

## Schema SQL da tabela de vetores (migration `0001_create_vector_store_schema.sql`)

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | `text primary key` | Mesmo `id` de `VectorRecord`, chave de upsert |
| `embedding` | `vector(512)` | Dimensão travada — mesmo valor de `settings.embedding_dimension` |
| `metadata` | `jsonb` | Metadados armazenados como JSON, usados no filtro de `similarity_search` |
| `created_at` | `timestamptz default now()` | Auditoria simples de quando o vetor foi inserido |

Índice: `USING hnsw (embedding vector_cosine_ops)` (ver research.md, Decisão 3).

## Ponto de troca entre implementações (único uso de `Protocol` desta feature)

```
ObjectStore (Protocol)
└── S3ObjectStore (produção — boto3, endpoint_url configurável para MinIO ou S3 real)
```

`PgVectorStore` não participa deste diagrama — é classe concreta, sem
`Protocol`, por ser a única implementação de vector store deste projeto
(Princípio II). Não há um segundo backend de vector store selecionável por
configuração nesta feature.
