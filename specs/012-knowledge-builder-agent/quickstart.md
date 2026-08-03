# Quickstart: Knowledge Builder Agent — indexação e busca semântica (SPEC-012)

## Pré-requisitos

- Dependências instaladas: `pip install -e ".[dev]"` (nenhuma dependência
  nova).
- `docker compose up postgres -d` (SPEC-006), com a migration do vector
  store já aplicada (`migrations/0001_create_vector_store_schema.sql`).
- `fixtures/normativos.json` gerado (`python -m fixtures.generate`,
  SPEC-003).

## Cenário 1 — Reindexar o mesmo corpus não duplica chunks (SC-001)

```bash
pytest tests/test_knowledge_builder_agent.py -k idempotent -q
```

**Resultado esperado**: a contagem de linhas na tabela do `PgVectorStore`
após indexar o corpus mock uma segunda vez é idêntica à contagem após a
primeira indexação — documentado em `contracts/knowledge_builder_agent.md`,
cenário 1.

## Cenário 2 — Busca semântica retorna o normativo correto no topo (SC-002)

```bash
pytest tests/test_knowledge_builder_agent.py -k semantic_search -q
```

**Resultado esperado**: uma consulta por um termo presente em um único
normativo do corpus retorna esse normativo como primeiro item da lista de
resultados.

## Cenário 3 — Filtro por categoria restringe os resultados (SC-003)

```bash
pytest tests/test_knowledge_builder_agent.py -k categoria_filter -q
```

**Resultado esperado**: `search` com `filtros={"categoria": <categoria>}`
retorna apenas resultados de normativos daquela categoria — nunca de outra.

## Cenário 4 — Suíte completa

```bash
pytest tests/test_knowledge_builder_agent.py -q
```

## Cenário 5 — `SKILL.md` segue o formato já estabelecido

```bash
cat skills/knowledge-builder-skill/SKILL.md
```

**Resultado esperado**: descreve responsabilidade, ferramentas, input e
output (`search(SearchQuery) -> list[SearchResult]`), no mesmo formato dos
`SKILL.md` já existentes — incluindo o parágrafo explicando por que o
chunking segue a estrutura do documento (artigo/inciso) e não uma janela
fixa de tokens, e a nota sobre busca híbrida como evolução futura (fora de
escopo).

## Checklist de leitura antes de implementar

- [research.md](./research.md) — por que "chunk = 1 `NormativoItem`" (sem
  subdivisão adicional), por que não há batch real de embeddings, fórmula
  de `chunk_id`, tradução entre os dois `SearchResult`.
- [data-model.md](./data-model.md) — convenção de `chunk_id`, uso de
  `VectorRecord.metadata`, mapeamento `SearchQuery`/`SearchResult`.
- [contracts/knowledge_builder_agent.md](./contracts/knowledge_builder_agent.md) —
  assinatura de `index_normativos`/`search`, CLI, e cenários de contrato
  cobertos por teste.

**Lembrete do Princípio IX**: `tests/test_knowledge_builder_agent.py` deve
ser escrito e confirmado como falho (por ausência de implementação) antes
de `knowledge_builder_agent.py` existir. Ver ordenação de tarefas em
`tasks.md` (gerado por `/speckit-tasks`).
