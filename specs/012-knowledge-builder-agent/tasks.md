---

description: "Task list template for feature implementation"
---

# Tasks: Knowledge Builder Agent — indexação e busca semântica (SPEC-012)

**Input**: Design documents from `/specs/012-knowledge-builder-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/knowledge_builder_agent.md, quickstart.md

**Tests**: Requeridos pela spec (Princípio IX da constituição — testes escritos e confirmados como falhos antes de qualquer código de implementação, derivados apenas do contrato).

**Organization**: Tarefas agrupadas por user story (spec.md). US1/US2/US3 convergem para o mesmo arquivo de implementação (`knowledge_builder_agent.py`) e o mesmo arquivo de teste (`test_knowledge_builder_agent.py`), por serem passos pequenos e fortemente relacionados do mesmo fluxo (Princípio III/KISS) — tarefas que tocam o mesmo arquivo NÃO são marcadas `[P]` entre si.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Projeto único: `src/pix_compliance/agents/`, `tests/`, `skills/` na raiz do repositório.

---

## Phase 1: Setup

**Purpose**: Nenhuma dependência nova (research.md, "Resumo de dependências novas"); infraestrutura já existe (SPEC-005/006). Único item de setup é o fix compartilhado do double offline, pré-requisito para todos os testes desta feature.

- [X] T001 Corrigir `OfflineEmbeddingsProvider` em `tests/doubles/offline_provider.py` para produzir vetores de `EMBEDDING_DIMENSION` (512) em vez de 8, via expansão determinística de blocos SHA-256 — já aplicado nesta sessão (ver research.md, Decisão 0); confirmar com `python -m pytest tests/test_llm_provider_offline.py -q`.

**Checkpoint**: Double offline compatível com `PgVectorStore` (vetor 512 dimensões).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestrutura de teste compartilhada por US1/US2/US3 — precisa existir antes de qualquer teste de user story.

**⚠️ CRITICAL**: Nenhuma tarefa de user story começa antes desta fase completa.

- [X] T002 Criar fixture de corpus mock com pelo menos 2 categorias e ao menos um `NormativoItem` sem `artigo`/`inciso` preenchidos (edge case da spec), reaproveitando `fixtures/normativos.json` (SPEC-003) ou uma lista `list[NormativoItem]` construída inline em `tests/test_knowledge_builder_agent.py`.
- [X] T003 Criar fixture pytest que garante `PgVectorStore` real (Postgres via `docker compose up postgres`, SPEC-006) com a tabela vazia antes de cada teste (`DELETE FROM` ou schema limpo), em `tests/test_knowledge_builder_agent.py` ou `tests/conftest.py`, seguindo o padrão já estabelecido em `tests/test_vector_store.py` (SPEC-006).
- [X] T004 Escrever `tests/test_knowledge_builder_agent.py` com os testes das três user stories (T007, T012, T016 abaixo) importando `knowledge_builder_agent` — que ainda não existe — e **confirmar que a suíte falha por `ModuleNotFoundError`/`ImportError`** antes de prosseguir (checkpoint explícito do Princípio IX).

**Checkpoint**: Fixtures compartilhadas prontas; suíte de teste criada e confirmada como falha por ausência de implementação.

---

## Phase 3: User Story 1 - Indexar o corpus é idempotente, sem duplicar chunks (Priority: P1) 🎯 MVP

**Goal**: `index_normativos` grava um chunk por `NormativoItem` (ou por artigo/inciso) no `PgVectorStore`, com `chunk_id` determinístico; reindexar não duplica.

**Independent Test**: Indexar o corpus mock duas vezes seguidas; contagem de linhas na tabela idêntica antes/depois da segunda indexação.

### Tests for User Story 1 ⚠️

> **NOTE: Escrever estes testes PRIMEIRO, confirmar que FALHAM antes de implementar.**

- [X] T005 [US1] Teste `test_chunk_id_e_deterministico` em `tests/test_knowledge_builder_agent.py`: mesmo trio (`normativo_id`, `artigo`, `inciso`) sempre produz o mesmo `_chunk_id`; trios diferentes produzem ids diferentes; `artigo`/`inciso` ausentes (`None`) produzem um id determinístico e distinto de qualquer valor preenchido.
- [X] T006 [US1] Teste `test_index_normativos_indexa_corpus_preservando_metadados` em `tests/test_knowledge_builder_agent.py`: após `index_normativos`, a contagem de linhas na tabela do `PgVectorStore` é igual ao número de `NormativoItem` do corpus mock, e cada linha carrega `normativo_id`/`artigo`/`categoria` corretos em `metadata` (Acceptance Scenario 1 da US1).
- [X] T007 [US1] Teste `test_index_normativos_e_idempotente` em `tests/test_knowledge_builder_agent.py`: chamar `index_normativos` duas vezes seguidas com o mesmo corpus; contagem de linhas na tabela idêntica antes/depois da segunda chamada (SC-001, Acceptance Scenario 2 da US1).
- [X] T008 [US1] Confirmar que T005–T007 falham (por `knowledge_builder_agent.py` ainda não existir) rodando `pytest tests/test_knowledge_builder_agent.py -k "chunk_id or index_normativos" -q` — checkpoint explícito do Princípio IX antes de prosseguir para a implementação.

### Implementation for User Story 1

- [X] T009 [US1] Implementar `_chunk_id(normativo_id, artigo, inciso) -> str` em `src/pix_compliance/agents/knowledge_builder_agent.py` (hash SHA-256 do trio, normalizando `None` para `""` — ver data-model.md).
- [X] T010 [US1] Implementar `index_normativos(settings, vector_store, normativos) -> None` em `src/pix_compliance/agents/knowledge_builder_agent.py`: para cada `NormativoItem`, gera embedding via `get_embeddings_provider()` (SPEC-005), monta `VectorRecord` (`id=_chunk_id(...)`, `metadata` com `normativo_id`/`artigo`/`categoria`/`texto`), chama `vector_store.upsert(...)` (depende de T009).
- [X] T011 [US1] Rodar `pytest tests/test_knowledge_builder_agent.py -k "chunk_id or index_normativos" -q` e confirmar que T005–T007 agora passam.

**Checkpoint**: User Story 1 completa e testável de forma independente — indexação idempotente com metadados corretos.

---

## Phase 4: User Story 2 - Busca semântica retorna o normativo correto no topo (Priority: P1)

**Goal**: `search(SearchQuery) -> list[SearchResult]` traduz o resultado do `PgVectorStore.similarity_search` para o `SearchResult` de domínio, ordenado por similaridade.

**Independent Test**: Indexar o corpus mock; `search(SearchQuery(query=<texto do normativo alvo>))` retorna esse normativo como primeiro item.

### Tests for User Story 2 ⚠️

- [X] T012 [US2] Teste `test_search_retorna_normativo_correto_no_topo` em `tests/test_knowledge_builder_agent.py`: após `index_normativos` do corpus mock, `search(SearchQuery(query=<texto idêntico ao de um NormativoItem específico>))` retorna esse `normativo_id` como primeiro item de `list[SearchResult]` — consulta usa texto idêntico ao indexado por causa da ausência de sinal semântico real do `OfflineEmbeddingsProvider` (ver research.md, Decisão 0); documentar esse motivo como comentário no teste (SC-002, Acceptance Scenario da US2).
- [X] T013 [US2] Confirmar que T012 falha (função `search` ainda não existe) rodando `pytest tests/test_knowledge_builder_agent.py -k semantic_search -q` — checkpoint do Princípio IX.

### Implementation for User Story 2

- [X] T014 [US2] Implementar `search(settings, vector_store, query: SearchQuery) -> list[SearchResult]` em `src/pix_compliance/agents/knowledge_builder_agent.py`: vetoriza `query.query` via `get_embeddings_provider()`, chama `vector_store.similarity_search(embedding, top_k=query.top_k, metadata_filter=query.filtros)`, traduz cada resultado interno para `SearchResult` de domínio (`score = max(0.0, min(1.0, 1.0 - resultado.score))`, `trecho = metadata["texto"]`, `normativo_id = metadata["normativo_id"]` — ver data-model.md).
- [X] T015 [US2] Rodar `pytest tests/test_knowledge_builder_agent.py -k semantic_search -q` e confirmar que T012 passa.

**Checkpoint**: User Stories 1 e 2 funcionam de forma independente — indexação idempotente e busca semântica retornando o resultado correto no topo.

---

## Phase 5: User Story 3 - Filtro por categoria restringe corretamente os resultados (Priority: P1)

**Goal**: `search` com `filtros={"categoria": ...}` restringe os resultados exclusivamente a normativos daquela categoria.

**Independent Test**: Mesma consulta, com e sem filtro por categoria; a versão filtrada é um subconjunto estrito da versão sem filtro, todos da categoria especificada.

### Tests for User Story 3 ⚠️

- [X] T016 [US3] Teste `test_search_com_filtro_categoria_restringe_resultados` em `tests/test_knowledge_builder_agent.py`: corpus mock com ao menos duas categorias indexado; `search` com `filtros={"categoria": <valor>}` retorna somente `SearchResult` cujo `normativo_id` corresponde a normativos daquela categoria; a mesma consulta sem filtro inclui resultados de outra categoria (Acceptance Scenarios 1 e 2 da US3).
- [X] T017 [US3] Confirmar que T016 falha rodando `pytest tests/test_knowledge_builder_agent.py -k categoria_filter -q` antes de qualquer ajuste em `search` — checkpoint do Princípio IX (T014 já propaga `query.filtros` para `similarity_search`; este passo confirma que o comportamento fim-a-fim ainda não estava coberto por teste).

### Implementation for User Story 3

- [X] T018 [US3] Rodar `pytest tests/test_knowledge_builder_agent.py -k categoria_filter -q` — se `search` (T014) já propaga `metadata_filter` corretamente, o teste passa sem alteração de código; caso contrário, ajustar `search` em `src/pix_compliance/agents/knowledge_builder_agent.py` até passar.

**Checkpoint**: User Stories 1, 2 e 3 completas e testáveis de forma independente.

---

## Phase 6: User Story 4 - Documentação da skill segue o formato já estabelecido (Priority: P2)

**Goal**: `skills/knowledge-builder-skill/SKILL.md` documenta responsabilidade, ferramentas, input e output, no formato já usado pelas skills anteriores.

**Independent Test**: Verificar que o arquivo existe e contém as quatro seções exigidas.

### Tests for User Story 4 ⚠️

- [X] T019 [P] [US4] Teste `test_skill_md_segue_formato_estabelecido` em `tests/test_knowledge_builder_agent.py`: `skills/knowledge-builder-skill/SKILL.md` existe e contém as seções de responsabilidade/ferramentas/input/output, incluindo a assinatura `search(SearchQuery) -> list[SearchResult]` (Acceptance Scenario da US4).
- [X] T020 [P] [US4] Confirmar que T019 falha (arquivo ainda não existe) rodando `pytest tests/test_knowledge_builder_agent.py -k skill_md -q`.

### Implementation for User Story 4

- [X] T021 [US4] Criar `skills/knowledge-builder-skill/SKILL.md` seguindo o formato de quatro seções já usado por `skills/compliance-analyzer-skill/SKILL.md` — incluindo o parágrafo sobre chunking por artigo/inciso (não janela fixa de tokens) e a nota sobre busca híbrida como evolução futura fora de escopo.
- [X] T022 [P] [US4] Rodar `pytest tests/test_knowledge_builder_agent.py -k skill_md -q` e confirmar que T019 passa.

**Checkpoint**: Todas as user stories completas e independentemente testáveis.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: CLI, documentação de projeto e validação fim-a-fim.

- [X] T023 Adicionar bloco `if __name__ == "__main__":` (CLI) em `src/pix_compliance/agents/knowledge_builder_agent.py`: lê `Settings`, carrega o corpus do caminho passado via argv, executa `index_normativos`, imprime a contagem de chunks indexados (ver contracts/knowledge_builder_agent.md).
- [X] T024 [P] Adicionar seção "Knowledge Builder Agent" ao `README.md`, incluindo o parágrafo (exigido pela spec, Assumptions) explicando por que o chunking segue a estrutura do documento (artigo/inciso) e não uma janela fixa de tokens, e a nota sobre busca híbrida como evolução futura (nunca como stub de código).
- [X] T025 [P] Adicionar/confirmar variáveis de ambiente relevantes em `.env.example`, se alguma nova for necessária (nenhuma nova dependência esperada — confirmar contra research.md).
- [X] T026 Rodar `pytest tests/test_knowledge_builder_agent.py -q` (suíte completa da feature) e confirmar todos os testes passam.
- [X] T027 Rodar `pytest -q` (regressão completa do projeto) e `ruff check` e confirmar que ambos passam sem erros.
- [X] T028 Validar `quickstart.md` executando os 5 cenários documentados (`-k idempotent`, `-k semantic_search`, `-k categoria_filter`, suíte completa, `cat skills/knowledge-builder-skill/SKILL.md`) e confirmar que todos correspondem ao resultado esperado.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente (já aplicado nesta sessão).
- **Foundational (Phase 2)**: Depende do Setup — bloqueia todas as user stories.
- **US1 (Phase 3)**: Depende do Foundational. Bloqueia US2/US3 na prática (mesmo arquivo `knowledge_builder_agent.py`, e US2/US3 exercitam `search` sobre dados já indexados por `index_normativos`), embora conceitualmente independente.
- **US2 (Phase 4)**: Depende de US1 estar implementada (usa `index_normativos` para popular o corpus antes de testar `search`).
- **US3 (Phase 5)**: Depende de US2 (`search` já implementado); adiciona apenas cobertura de teste do filtro, sem necessariamente exigir código novo.
- **US4 (Phase 6)**: Independente de US1/US2/US3 — pode ser feita em paralelo a qualquer momento após o Foundational.
- **Polish (Phase 7)**: Depende de todas as user stories desejadas estarem completas.

### Within Each User Story

- Testes escritos e confirmados como falhos antes da implementação correspondente (Princípio IX).
- `_chunk_id` antes de `index_normativos` (T009 antes de T010).
- `index_normativos` antes de `search` (US1 antes de US2, já que US2 indexa o corpus antes de buscar).

### Parallel Opportunities

- T019/T020/T021/T022 (US4) podem rodar em paralelo às demais phases após o Foundational, por não tocarem `knowledge_builder_agent.py`.
- T024/T025 (Polish, arquivos distintos) podem rodar em paralelo entre si.
- Dentro de US1/US2/US3, as tarefas tocam o mesmo arquivo de teste/implementação e por isso NÃO são marcadas `[P]` entre si.

---

## Parallel Example: User Story 4 (independente das demais)

```bash
Task: "Teste test_skill_md_segue_formato_estabelecido em tests/test_knowledge_builder_agent.py"
Task: "Criar skills/knowledge-builder-skill/SKILL.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup (já feito).
2. Completar Phase 2: Foundational.
3. Completar Phase 3: User Story 1 — indexação idempotente já é uma entrega independentemente validável.
4. **PARAR e VALIDAR**: rodar os testes da US1 isoladamente.

### Incremental Delivery

1. Setup + Foundational → base pronta.
2. US1 → validar independentemente (MVP).
3. US2 → validar independentemente (busca semântica).
4. US3 → validar independentemente (filtro por categoria).
5. US4 → documentação da skill (pode ser feita a qualquer momento após o Foundational).
6. Polish → CLI, README, regressão completa, lint.

## Notes

- [P] = arquivos diferentes, sem dependência entre si.
- [Story] mapeia a tarefa à user story correspondente da spec.md.
- Confirmar que os testes falham antes de implementar (Princípio IX) — checkpoints explícitos em T004, T008, T013, T017, T020.
- Rodar `pytest -q` e `ruff check` completos antes de considerar a feature encerrada (T027).
