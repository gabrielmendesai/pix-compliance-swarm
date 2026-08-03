# Knowledge Builder Skill

Documenta o Knowledge Builder Agent (SPEC-012), implementado em
`src/pix_compliance/agents/knowledge_builder_agent.py`. Segue o mesmo
formato de quatro seções já estabelecido por `skills/scraper-skill/SKILL.md`,
`skills/extractor-skill/SKILL.md` e `skills/compliance-analyzer-skill/SKILL.md`
— embora, diferente desses três, este módulo não instancie
`pydantic_ai.Agent`: não há decisão de LLM aqui, apenas geração
determinística de embeddings e operações de storage.

## Responsabilidade

O Knowledge Builder Agent indexa `NormativoItem` no `PgVectorStore`
(SPEC-006) e serve busca semântica sobre o corpus indexado.

Este agente:

- Trata cada `NormativoItem` como exatamente um chunk de indexação — **não**
  subdivide `.texto` por uma janela fixa de caracteres/tokens. Normativos
  regulatórios já são estruturados por natureza: artigo e inciso já são as
  unidades de sentido do próprio texto legal (campos `artigo`/`inciso`,
  presentes desde a SPEC-002/SPEC-003). Ignorar essa estrutura em favor de
  uma janela fixa destruiria precisão de recuperação sem necessidade real —
  por isso "chunking consciente de estrutura", nesta feature, significa
  simplesmente respeitar a granularidade já nativa do corpus.
- Gera um `chunk_id` determinístico (hash de `normativo_id` + `artigo` +
  `inciso`), usado como chave de upsert idempotente no `PgVectorStore` —
  reindexar o mesmo corpus substitui (nunca duplica) os chunks
  correspondentes.
- Preserva `normativo_id`, `artigo` e `categoria` como metadados de cada
  chunk, permitindo filtro por metadados (ex. restringir a busca a uma
  `categoria` específica) em `search()`.

Este agente **não** faz reranking dos resultados de busca e **não** faz
busca híbrida (léxica + semântica) — ambos fora de escopo desta spec. Busca
híbrida é uma evolução futura possível: combinaria a busca semântica atual
com um índice léxico (full-text search do próprio Postgres, por exemplo)
para consultas onde correspondência exata de termo é mais relevante que
similaridade semântica — mas não há necessidade concreta disso hoje, e
implementá-la agora seria especulação sem justificativa (Princípio II).

## Ferramentas

| Ferramenta | Entrada | Saída | Uso pelo agente |
|---|---|---|---|
| `get_embeddings_provider()` (SPEC-005) | `str` | `list[float]` | Gera o embedding de cada chunk (indexação) e de cada consulta (busca) |
| `PgVectorStore.upsert` (SPEC-006) | `VectorRecord` | — | Grava/atualiza um chunk indexado, usando `chunk_id` como chave |
| `PgVectorStore.similarity_search` (SPEC-006) | embedding, `top_k`, filtro de metadados | `list[SearchResult]` interno | Busca por similaridade de cosseno, com filtro opcional por metadados |

## Input

```python
# Indexação — idempotente, reindexar não duplica chunks
index_normativos(settings, vector_store, normativos)

# Busca semântica, com filtro opcional por metadados
search(settings, vector_store, SearchQuery(query="...", top_k=5, filtros={"categoria": "tarifas"}))
```

Nenhuma dependência via `RunContext` — este módulo recebe `settings` e
`vector_store` diretamente como argumentos de função, sem `deps_type`
(não há `Agent` Pydantic AI envolvido).

## Output

`search(SearchQuery) -> list[SearchResult]` — `SearchResult` de domínio
(modelo já existente, `src/pix_compliance/models.py`, SPEC-002,
`ConfigDict(extra="forbid")`), reaproveitado sem alteração:

| Campo | Tipo | Descrição |
|---|---|---|
| `score` | `Score` (`0..1`) | Similaridade — `1.0 - distância de cosseno`, do resultado interno do `PgVectorStore` |
| `trecho` | `str` | Texto do chunk (`NormativoItem.texto`, armazenado como metadado no momento da indexação) |
| `normativo_id` | `str` | Id do `NormativoItem` de origem do chunk |

`index_normativos` não retorna valor — seu efeito observável é o estado do
`PgVectorStore` (contagem de linhas idêntica entre reindexações do mesmo
corpus).
