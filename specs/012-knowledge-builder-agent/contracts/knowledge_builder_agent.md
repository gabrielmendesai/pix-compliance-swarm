# Contrato: `src/pix_compliance/agents/knowledge_builder_agent.py`

Esta feature não expõe uma API HTTP/CLI de terceiros — o "contrato" é a
interface Python que o CLI deste projeto (e, no futuro, o orquestrador do
enxame ou uma API de consulta) consome.

## Função interna: `_chunk_id`

```python
def _chunk_id(normativo_id: str, artigo: str | None, inciso: str | None) -> str:
    """chunk_id determinístico — mesmo trio sempre produz o mesmo hash,
    garantindo upsert idempotente (ver research.md, Decisão 3)."""
```

## Função pública: `index_normativos`

```python
def index_normativos(
    settings: Settings, vector_store: PgVectorStore, normativos: list[NormativoItem]
) -> None:
    """Indexa cada NormativoItem como um chunk (1:1 — ver research.md,
    Decisão 1), gerando embedding via EmbeddingsProvider (SPEC-005) e
    fazendo upsert no PgVectorStore (SPEC-006) com chunk_id determinístico.
    Reindexar o mesmo corpus substitui (nunca duplica) os chunks
    correspondentes."""
```

**Pós-condição de idempotência**: chamar `index_normativos` duas vezes
seguidas com o mesmo `normativos` MUST resultar na mesma contagem de linhas
na tabela do `PgVectorStore` após a segunda chamada.

## Função pública: `search`

```python
def search(
    settings: Settings, vector_store: PgVectorStore, query: SearchQuery
) -> list[SearchResult]:
    """Busca semântica: vetoriza query.query via o mesmo EmbeddingsProvider,
    chama PgVectorStore.similarity_search (top_k=query.top_k,
    metadata_filter=query.filtros), e traduz cada resultado interno para o
    SearchResult de domínio (SPEC-002) — ver data-model.md para a fórmula
    de conversão de score."""
```

**Pós-condição de ordenação**: o primeiro item de `list[SearchResult]` MUST
ser o de maior `score` (mais similar à consulta) — consistente com a
ordenação já garantida por `PgVectorStore.similarity_search`.

## CLI

```bash
python -m pix_compliance.agents.knowledge_builder_agent fixtures/normativos.json
```

Lê `Settings`, carrega o corpus do caminho fornecido, executa
`index_normativos`, e imprime a contagem de chunks indexados.

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. Indexar o corpus mock duas vezes seguidas não altera a contagem de linhas
   na tabela do `PgVectorStore` entre a primeira e a segunda execução
   (SC-001).
2. `search(SearchQuery(query=<termo específico de um normativo>))` retorna
   esse normativo como primeiro item de `list[SearchResult]` (SC-002).
3. `search` com `filtros={"categoria": <categoria>}` retorna apenas
   resultados cujo `normativo_id` corresponde a normativos daquela categoria
   (SC-003).
