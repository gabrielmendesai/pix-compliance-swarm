# Data Model: Knowledge Builder Agent — indexação e busca semântica (SPEC-012)

Esta feature não introduz nenhum modelo Pydantic novo — reaproveita
integralmente os contratos já existentes (SPEC-002 e SPEC-006). O único
"dado novo" desta spec é a convenção de chunking e a função de tradução
entre os dois `SearchResult` já existentes.

## NormativoItem (já existe — SPEC-002, sem alteração)

Reaproveitado como unidade de indexação. Campos relevantes:

| Campo | Tipo | Uso nesta feature |
|---|---|---|
| `id` | `str` | Usado como `normativo_id` no `chunk_id` e no metadata do chunk |
| `artigo` | `str \| None` | Usado no `chunk_id`; normalizado para `""` quando ausente |
| `inciso` | `str \| None` | Idem |
| `texto` | `str` | Conteúdo vetorizado (embedding) e armazenado como metadado (`trecho` na busca) |
| `categoria` | `CategoriaCompliance` | Preservado como metadado do chunk, usado como filtro em `search()` |

## Convenção: `chunk_id` (não é modelo Pydantic — string determinística)

```
chunk_id = sha256(f"{normativo.id}|{normativo.artigo or ''}|{normativo.inciso or ''}").hexdigest()
```

**Regra de negócio**: o mesmo trio (`id`, `artigo`, `inciso`) sempre produz o
mesmo `chunk_id` — é essa determinística que garante que reindexar o mesmo
corpus faça `PgVectorStore.upsert` substituir (não duplicar) o chunk
correspondente (SC-001).

## VectorRecord (já existe — SPEC-006, sem alteração de contrato; convenção de metadata desta feature)

| Campo | Valor nesta feature |
|---|---|
| `id` | `chunk_id` (ver acima) |
| `embedding` | `EmbeddingsProvider.embed(normativo.texto)` (SPEC-005, Titan V2) |
| `metadata` | `{"normativo_id": normativo.id, "artigo": normativo.artigo or "", "categoria": normativo.categoria.value, "texto": normativo.texto}` |

## SearchQuery / SearchResult (já existem — SPEC-002, sem alteração)

| Campo | Uso nesta feature |
|---|---|
| `SearchQuery.query` | Texto da consulta — vetorizado via o mesmo `EmbeddingsProvider` antes da busca |
| `SearchQuery.top_k` | Propagado diretamente para `PgVectorStore.similarity_search(top_k=...)` |
| `SearchQuery.filtros` | Propagado diretamente para `PgVectorStore.similarity_search(metadata_filter=...)` — ex. `{"categoria": "tarifas"}` |
| `SearchResult.normativo_id` | Extraído de `metadata["normativo_id"]` do resultado interno do `PgVectorStore` |
| `SearchResult.trecho` | Extraído de `metadata["texto"]` do resultado interno |
| `SearchResult.score` | `max(0.0, min(1.0, 1.0 - resultado_interno.score))` — transforma distância de cosseno em similaridade `[0, 1]` (ver research.md, Decisão 4) |

## Funções públicas (contratos internos, ver contracts/)

| Função | Assinatura | Descrição |
|---|---|---|
| `index_normativos` | `(settings, vector_store, normativos: list[NormativoItem]) -> None` | Indexa (upsert idempotente) cada `NormativoItem` como um chunk |
| `search` | `(settings, vector_store, query: SearchQuery) -> list[SearchResult]` | Busca semântica, com filtro por metadados, traduzindo o resultado interno do `PgVectorStore` para o `SearchResult` de domínio |
