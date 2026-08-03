# Implementation Plan: Knowledge Builder Agent — indexação e busca semântica (SPEC-012)

**Branch**: `012-knowledge-builder-agent` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-knowledge-builder-agent/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Indexa `NormativoItem` no `PgVectorStore` (SPEC-006) e serve busca semântica
via `search(SearchQuery) -> list[SearchResult]` (SPEC-002, reaproveitados
sem alteração). Diferente das SPEC-008/009/010, esta feature **não** é um
`Agent` Pydantic AI com decisão via LLM — não há raciocínio de modelo
envolvido, apenas geração determinística de embeddings (Titan V2, SPEC-005)
e operações de storage (SPEC-006); vive no mesmo pacote `agents/` por
consistência organizacional do enxame, mas internamente é um módulo de
indexação/busca puro. Cada `NormativoItem` do corpus já corresponde a
exatamente um artigo/inciso (granularidade herdada da SPEC-002/003) —
"chunking consciente de estrutura" significa, portanto, tratar cada
`NormativoItem` como um chunk único (não subdividir `.texto` internamente),
com um `chunk_id` determinístico (hash de `normativo_id`+`artigo`+`inciso`)
usado como chave de upsert idempotente no `PgVectorStore`.

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `pix_compliance.object_store`/`vector_store`
(SPEC-006, `PgVectorStore`/`VectorRecord`/`SearchResult` internos,
reaproveitados sem alteração), `pix_compliance.llm_provider`
(`get_embeddings_provider()`, SPEC-005, Titan V2), `pix_compliance.models`
(`NormativoItem`, `SearchQuery`, `SearchResult` de domínio — já existentes,
SPEC-002), `hashlib` (stdlib, `chunk_id` determinístico)

**Storage**: `PgVectorStore` (SPEC-006) — nenhuma tabela nova, nenhuma
alteração de schema; esta feature é consumidora do vector store já
existente

**Testing**: pytest, contra o `PgVectorStore` real (SPEC-006,
`docker compose up postgres`) e o corpus mock (`fixtures/normativos.json`,
SPEC-003) — sem mock do banco, consistente com o padrão já estabelecido na
SPEC-006; `LLM_PROVIDER=offline` para os embeddings em teste (o
`OfflineEmbeddingsProvider` já existente, SPEC-005, é determinístico:
mesmo texto sempre produz o mesmo vetor, o que já é suficiente para provar
idempotência de upsert e correção de busca por similaridade sem chamada
real ao Bedrock)

**Target Platform**: Linux server (container Docker Compose, mesmo alvo do
restante do projeto)

**Project Type**: Single project — novo módulo
`src/pix_compliance/agents/knowledge_builder_agent.py`, no mesmo pacote
`agents/` das SPEC-008/009/010 (por consistência organizacional, embora não
use `Agent`/`deps_type`/`RunContext` — não há decisão de LLM nesta feature)

**Performance Goals**: Sem meta de throughput própria; embeddings são
gerados um por chunk (a API Titan V2 já configurada, via `invoke_model`
clássico, não suporta múltiplos textos por chamada — ver research.md)

**Constraints**: Reindexar o mesmo corpus MUST NOT duplicar linhas no
`PgVectorStore` (upsert idempotente via `chunk_id` determinístico); esta
feature MUST NOT introduzir uma segunda abstração de vector store além de
`PgVectorStore` já existente; reranking e busca híbrida ficam fora de
escopo (busca híbrida documentada em prosa no README, nunca como stub)

**Scale/Scope**: Um módulo de indexação/busca, nenhuma entidade de domínio
nova (reaproveita `NormativoItem`/`SearchQuery`/`SearchResult` já
existentes), uma skill (`SKILL.md`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  PASS. Reaproveita `get_embeddings_provider()` (SPEC-005) sem alteração —
  já resolve o dispatch `bedrock`/`offline` via `settings.llm_provider`.
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS,
  é o próprio objetivo estrutural desta feature: nenhuma abstração nova é
  introduzida; `PgVectorStore` (SPEC-006) permanece a única implementação de
  vector store, sem `Protocol` especulativo (FR-010).
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS. Chunking
  (trivial — 1 `NormativoItem` = 1 chunk, dada a granularidade já existente),
  geração de embedding, upsert e busca vivem no mesmo módulo — passos
  pequenos e fortemente relacionados do mesmo fluxo ("indexar e buscar").
- **Princípio IV (Responsabilidade única por agente / SRP)** — PASS. Esta
  feature indexa e busca; não reranqueia, não faz busca híbrida (FR-008/
  FR-009), não decide sobre conteúdo (não há LLM de raciocínio aqui).
- **Princípio V (Guardrail é ponto único e obrigatório)** — N/A direto: o
  texto indexado (`NormativoItem.texto`) já passou por `guard()` em
  features anteriores (Extractor/Compliance Analyzer) antes de chegar aqui;
  esta feature não envia texto a nenhum LLM de chat/estruturação — apenas
  ao provider de embeddings (que não interpreta/gera texto livre a partir
  do input, apenas vetoriza), fora do escopo do guardrail de conteúdo
  gerado por chat.
- **Princípio VI (Contrato antes de comportamento)** — PASS. `SearchQuery`/
  `SearchResult` (SPEC-002) e `VectorRecord`/`SearchResult` internos do
  `PgVectorStore` (SPEC-006) já existem; a Fase 1 (`data-model.md`) define
  apenas a função de tradução entre os dois, sem novo modelo Pydantic.
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês; comentários/docstrings em português explicando o porquê — em
  particular, por que o chunking segue a estrutura do documento (artigo/
  inciso) e não um tamanho fixo de tokens.
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. Todos
  os critérios de aceite são comandos executáveis (contagem de linhas
  idêntica após reindexação, busca retornando o normativo certo no topo,
  filtro por categoria restringindo resultados).
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, requisito explícito da spec. Testes
  de idempotência de indexação, busca semântica correta e filtro por
  categoria são escritos e confirmados como falhos antes de
  `knowledge_builder_agent.py` existir.

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` e
`contracts/knowledge_builder_agent.md` confirmam que nenhum modelo Pydantic
novo foi introduzido (reaproveitamento total de `NormativoItem`/
`SearchQuery`/`SearchResult`/`VectorRecord`), e que `PgVectorStore`
permanece a única implementação de vector store, sem abstração adicional.
Gates permanecem PASS.

## Project Structure

### Documentation (this feature)

```text
specs/012-knowledge-builder-agent/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/pix_compliance/
├── models.py                        # já existe (SPEC-002) — NormativoItem, SearchQuery, SearchResult reaproveitados
├── vector_store.py                   # já existe (SPEC-006) — PgVectorStore, VectorRecord, SearchResult (interno) reaproveitados
├── llm_provider.py                   # já existe (SPEC-005) — get_embeddings_provider() reaproveitado
└── agents/
    ├── scraper_agent.py                # já existe (SPEC-008)
    ├── extractor_agent.py               # já existe (SPEC-009)
    ├── compliance_analyzer_agent.py       # já existe (SPEC-010)
    └── knowledge_builder_agent.py          # NOVO — _chunk_id(), index_normativos(), search(), CLI

skills/
├── scraper-skill/SKILL.md              # já existe
├── extractor-skill/SKILL.md             # já existe
├── compliance-analyzer-skill/SKILL.md     # já existe
└── knowledge-builder-skill/
    └── SKILL.md                          # NOVO — mesmo formato de 4 seções

tests/
└── test_knowledge_builder_agent.py       # NOVO — escrito e confirmado falho ANTES de knowledge_builder_agent.py (Princípio IX)
```

**Structure Decision**: Projeto único (Option 1). `knowledge_builder_agent.py`
vive no mesmo pacote `src/pix_compliance/agents/` das SPEC-008/009/010, por
consistência organizacional do enxame (mesmo diretório, mesmo padrão de
nomenclatura de skill), ainda que esta feature não instancie
`pydantic_ai.Agent` internamente — não há decisão via LLM aqui, apenas
geração determinística de embeddings e operações de storage. `_chunk_id`,
`index_normativos` e `search` vivem no mesmo arquivo por serem passos
pequenos e fortemente relacionados do mesmo fluxo (Princípio III) — não se
cria um submódulo `chunking.py` separado para uma função de poucas linhas
(1 `NormativoItem` = 1 chunk, dada a granularidade já existente no modelo).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| N/A | N/A | Nenhuma violação identificada nesta feature. |
