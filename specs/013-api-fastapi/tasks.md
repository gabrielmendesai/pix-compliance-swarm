---

description: "Task list template for feature implementation"
---

# Tasks: API FastAPI (SPEC-013)

**Input**: Design documents from `/specs/013-api-fastapi/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Requeridos pela spec (Princípio IX da constituição — `tests/test_api.py` escrito e confirmado como falho antes de qualquer código de rota).

**Organization**: Tarefas agrupadas por user story (spec.md). Todas convergem para o pacote `src/pix_compliance/api/` e o arquivo de teste `tests/test_api.py` (nome exigido explicitamente pela spec).

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Projeto único: `src/pix_compliance/api/`, `tests/` na raiz do repositório.

---

## Phase 1: Setup

**Purpose**: Introduzir `fastapi`/`uvicorn` como dependências reais pela primeira vez no projeto (research.md, Decisão 5).

- [X] T001 Adicionar `fastapi>=0.115` e `uvicorn[standard]>=0.30` a `dependencies` em `pyproject.toml`, rodar `pip install -e ".[dev]"`, e confirmar `python -c "import fastapi; print(fastapi.__version__)"`.
- [X] T002 [P] Criar `src/pix_compliance/api/__init__.py` (vazio, apenas marca o pacote).

**Checkpoint**: `fastapi`/`uvicorn` instalados e importáveis.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestrutura de transporte compartilhada por todas as user stories — precisa existir antes de qualquer rota.

**⚠️ CRITICAL**: Nenhuma tarefa de user story começa antes desta fase completa.

- [X] T003 [P] Implementar `ErrorResponse` (Pydantic) em `src/pix_compliance/api/errors.py` (data-model.md) e os três exception handlers (`RequestValidationError` → 422, `ObjectNotFoundError`/404, `Exception` → 500), cada um chamando `bind_run_correlation_id()` (SPEC-001) e incluindo o `correlation_id` no corpo (research.md, Decisão 3).
- [X] T004 [P] Implementar `PaginatedResponse[T]` (Pydantic `Generic`) em `src/pix_compliance/api/pagination.py` (data-model.md).
- [X] T005 Criar `src/pix_compliance/api/app.py` com `FastAPI(title=..., description=..., version=..., openapi_tags=[...])` (metadados completos, FR-008) e registro dos exception handlers de T003 — ainda sem nenhuma rota registrada.
- [X] T006 Criar fixtures em `tests/test_api.py`: `client` (`TestClient(app)`, `fastapi.testclient`), `settings` (env vars via `monkeypatch`, mesmo `REQUIRED_ENV` já usado nos demais testes).
- [X] T007 Escrever `tests/test_api.py` com os testes das três user stories (T010–T014, T018–T021, T025–T028 abaixo) importando `pix_compliance.api.app` — cujas rotas ainda não existem — e **confirmar que a suíte falha** (rotas retornam 404 do próprio FastAPI, ou `ImportError` se `app.py` ainda não existir) antes de prosseguir (checkpoint explícito do Princípio IX).

**Checkpoint**: `app.py` com metadados OpenAPI e exception handlers prontos, mas sem rotas; suíte de teste criada e confirmada como falha.

---

## Phase 3: User Story 1 - Consultar normativos, compliance e busca semântica via HTTP (Priority: P1) 🎯 MVP

**Goal**: `GET /normativos`, `GET /compliance` e `GET /search` retornam dados corretos, paginados/filtrados, no formato `response_model` esperado.

**Independent Test**: Chamar cada um dos três endpoints com dados já persistidos e verificar que a resposta corresponde ao `response_model` esperado.

### Tests for User Story 1 ⚠️

> **NOTE: Escrever estes testes PRIMEIRO, confirmar que FALHAM antes de implementar.**

- [X] T008 [US1] Teste `test_get_normativos_pagina_e_filtra_por_tipo_e_categoria` em `tests/test_api.py`: `GET /normativos?tipo=...&categoria=...&page=1&page_size=5` retorna 200 com `PaginatedResponse[NormativoItem]`, apenas itens que casam com os filtros (Acceptance Scenario 1 da US1).
- [X] T009 [US1] Teste `test_get_normativos_sem_filtro_retorna_primeira_pagina` em `tests/test_api.py`: `GET /normativos` sem parâmetros retorna 200 com a primeira página, sem erro (Edge Case de spec.md).
- [X] T010 [US1] Teste `test_get_normativos_data_invalida_retorna_422` em `tests/test_api.py`: `GET /normativos?data_inicio=nao-e-uma-data` retorna 422 com `ErrorResponse`.
- [X] T011 [US1] Teste `test_get_compliance_filtra_por_severidade` em `tests/test_api.py`: com um `reports/<id>.conformance.json` de fixture já gravado (setup do teste), `GET /compliance?severidade_min=0.7` retorna apenas itens com `severidade >= 0.7` (Acceptance Scenario 2 da US1).
- [X] T012 [US1] Teste `test_get_compliance_sem_relatorios_retorna_vazio` em `tests/test_api.py`: sem nenhum `reports/*.conformance.json` presente, `GET /compliance` retorna 200 com lista vazia, não erro.
- [X] T013 [US1] Teste `test_get_search_retorna_resultados_do_knowledge_builder` em `tests/test_api.py`: com o índice de busca populado (mesma fixture de corpus de `tests/test_knowledge_builder_agent.py`), `GET /search?query=...&top_k=3` retorna 200 com `list[SearchResult]`, no máximo 3 itens (Acceptance Scenario 3 da US1).
- [X] T014 [US1] Teste `test_get_search_sem_query_retorna_422` em `tests/test_api.py`: `GET /search` sem `query` retorna 422 com `ErrorResponse`.
- [X] T015 [US1] Confirmar que T008–T014 falham (rotas ainda não existem) rodando `pytest tests/test_api.py -k "normativos or compliance or search" -q` — checkpoint explícito do Princípio IX.

### Implementation for User Story 1

- [X] T016 [US1] Implementar `GET /normativos` em `src/pix_compliance/api/routes.py`: lê `fixtures/normativos.json`, filtra por `tipo`/`categoria`/período, pagina, retorna `PaginatedResponse[NormativoItem]` (research.md, Decisão 0).
- [X] T017 [US1] Implementar `GET /compliance` em `src/pix_compliance/api/routes.py`: agrega `itens` de todos os `reports/*.conformance.json`, filtra por `severidade_min` (research.md, Decisão 1).
- [X] T018 [US1] Implementar `GET /search` em `src/pix_compliance/api/routes.py`: delega a `knowledge_builder_agent.search(settings, vector_store, SearchQuery(...))` (SPEC-012), retorna `list[SearchResult]`.
- [X] T019 [US1] Registrar o `router` de T016–T018 em `app.py` (T005).
- [X] T020 [US1] Rodar `pytest tests/test_api.py -k "normativos or compliance or search" -q` e confirmar que T008–T014 agora passam.

**Checkpoint**: User Story 1 completa e testável de forma independente.

---

## Phase 4: User Story 2 - Verificar a saúde do serviço e disparar uma execução ad-hoc (Priority: P1)

**Goal**: `GET /health` reporta conectividade por dependência sem lançar erro; `POST /runs` orquestra o pipeline sincronamente e persiste o `ConformanceReport` completo.

**Independent Test**: Chamar `GET /health` com dependências disponíveis/indisponíveis; chamar `POST /runs` e verificar que uma execução é de fato disparada.

### Tests for User Story 2 ⚠️

- [X] T021 [US2] Teste `test_get_health_reporta_ok_quando_dependencias_disponiveis` em `tests/test_api.py`: com `ObjectStore`/`PgVectorStore` acessíveis, `GET /health` retorna 200 com `status="ok"` (Acceptance Scenario 1 da US2).
- [X] T022 [US2] Teste `test_get_health_reporta_degradado_sem_lancar_erro` em `tests/test_api.py`: com `POSTGRES_DSN` apontando para um host inexistente (via `monkeypatch`), `GET /health` retorna 200 com `status="degraded"` e a dependência falha identificada — nunca 500 (Acceptance Scenario 2 da US2, research.md Decisão 2).
- [X] T023 [US2] Teste `test_post_runs_dispara_pipeline_e_retorna_resultado_completo` em `tests/test_api.py`: `POST /runs` com um `PipelineRequest` válido retorna 200 com `PipelineResult` (`sucesso`/`concluido_em` preenchidos) — execução síncrona (Acceptance Scenario 3 da US2, research.md Decisão 4).
- [X] T024 [US2] Teste `test_post_runs_corpo_invalido_retorna_422` em `tests/test_api.py`: `POST /runs` com `fontes=[]` (viola `Field(min_length=1)` de `PipelineRequest`) retorna 422 com `ErrorResponse`.
- [X] T025 [US2] Confirmar que T021–T024 falham rodando `pytest tests/test_api.py -k "health or post_runs" -q` — checkpoint do Princípio IX.

### Implementation for User Story 2

- [X] T026 [US2] Implementar `GET /health` em `src/pix_compliance/api/routes.py`: tenta instanciar `S3ObjectStore`/`PgVectorStore`, captura exceção por dependência, monta o corpo `{"status": ..., "dependencies": {...}}` (research.md, Decisão 2).
- [X] T027 [US2] Implementar `POST /runs` em `src/pix_compliance/api/routes.py`: orquestra sincronamente Scraper → Extractor → Compliance Analyzer → Conformance Validator → Knowledge Builder → Report Consolidator sobre `PipelineRequest.fontes`, grava `reports/<report_id>.conformance.json` (data-model.md), captura erro de qualquer etapa em `PipelineResult.sucesso=False`/`erro=...` em vez de propagar exceção.
- [X] T028 [US2] Registrar as rotas de T026–T027 em `app.py`.
- [X] T029 [US2] Rodar `pytest tests/test_api.py -k "health or post_runs" -q` e confirmar que T021–T024 passam.

**Checkpoint**: User Stories 1 e 2 completas e testáveis de forma independente.

---

## Phase 5: User Story 3 - Erros são estruturados e a documentação é substantiva, não genérica (Priority: P1)

**Goal**: Toda falha retorna `ErrorResponse` com `correlation_id`; `/docs` renderiza com descrição/exemplo reais em todas as rotas.

**Independent Test**: Enviar uma requisição inválida a qualquer endpoint e verificar o formato estruturado; abrir `/docs` e verificar ausência de placeholders genéricos.

### Tests for User Story 3 ⚠️

- [X] T030 [US3] Teste `test_erro_422_estruturado_com_correlation_id` em `tests/test_api.py`: qualquer requisição malformada (ex. `GET /search` sem `query`) retorna corpo `ErrorResponse` com `correlation_id` não vazio — não o corpo cru `{"detail": [...]}` do FastAPI (Acceptance Scenario 1 da US3, SC-003).
- [X] T031 [US3] Teste `test_erro_404_estruturado` em `tests/test_api.py`: uma rota que busca recurso inexistente (se aplicável, ex. filtro que não casa com nada em uma rota de detalhe) retorna `ErrorResponse` estruturado.
- [X] T032 [US3] Teste `test_docs_endpoint_responde_200` em `tests/test_api.py`: `GET /docs` retorna 200.
- [X] T033 [US3] Teste `test_openapi_schema_tem_descricao_e_exemplo_em_toda_rota` em `tests/test_api.py`: `GET /openapi.json` — para cada uma das 5 rotas, `summary`/`description` não vazios e ao menos um exemplo de resposta presente no schema (Acceptance Scenario 2 da US3, SC-001).
- [X] T034 [US3] Confirmar que T030–T033 falham rodando `pytest tests/test_api.py -k "erro_422_estruturado or erro_404 or docs_endpoint or openapi_schema" -q` — checkpoint do Princípio IX.

### Implementation for User Story 3

- [X] T035 [US3] Preencher `summary`/`description`/`responses` (com exemplo) em cada rota de `routes.py` (T016–T018, T026–T027) via os parâmetros nativos do FastAPI (`@router.get(..., summary=..., description=..., responses={...})`), conforme FR-008.
- [X] T036 [US3] Rodar `pytest tests/test_api.py -k "erro_422_estruturado or erro_404 or docs_endpoint or openapi_schema" -q` e confirmar que T030–T033 passam.

**Checkpoint**: Todas as user stories completas e independentemente testáveis.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentação de projeto e validação fim-a-fim.

- [X] T037 [P] Adicionar seção "API FastAPI" ao `README.md`, documentando as 5 rotas, o comando `uvicorn pix_compliance.api.app:app`, e a decisão consciente de deixar autenticação fora de escopo (FR-010, não uma lacuna esquecida).
- [X] T038 [P] Confirmar/adicionar variáveis de ambiente relevantes em `.env.example`, se alguma nova for necessária para rodar a API (ex. host/porta do `uvicorn`, se configurável via `Settings` — decisão de implementação).
- [X] T039 Rodar `pytest tests/test_api.py -q` (suíte completa da feature, SC-002) e confirmar todos os testes passam.
- [X] T040 Rodar `pytest -q` (regressão completa do projeto) e `ruff check` e confirmar que ambos passam sem erros.
- [X] T041 Validar `quickstart.md` executando os 4 cenários documentados e confirmar que todos correspondem ao resultado esperado.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente.
- **Foundational (Phase 2)**: Depende do Setup — bloqueia todas as user stories.
- **US1 (Phase 3)**: Depende do Foundational. Conceitualmente independente de US2/US3.
- **US2 (Phase 4)**: Depende do Foundational; independente de US1 (rotas distintas), embora `POST /runs` (T027) reaproveite `reports/<report_id>.conformance.json`, a mesma convenção que `GET /compliance` (US1) lê — a ordem entre as duas fases não importa para a implementação, mas o teste de `GET /compliance` (T011) precisa de um arquivo de fixture gravado diretamente no teste, não necessariamente de `POST /runs` já implementado.
- **US3 (Phase 5)**: Depende de US1 e US2 já terem as rotas registradas em `app.py` (T019/T028) — os testes de "descrição/exemplo em toda rota" (T033) precisam das 5 rotas existentes para inspecionar.
- **Polish (Phase 6)**: Depende de todas as user stories completas.

### Within Each User Story

- Testes escritos e confirmados como falhos antes da implementação correspondente (Princípio IX).
- Rotas de leitura (T016–T018) antes do registro em `app.py` (T019).
- `GET /health`/`POST /runs` (T026–T027) antes do registro em `app.py` (T028).
- Enriquecimento de OpenAPI (T035) depende de todas as rotas já existirem (US1 e US2 completas).

### Parallel Opportunities

- T002/T003/T004 (arquivos distintos) podem rodar em paralelo após T001.
- T037/T038 (Polish, arquivos distintos) podem rodar em paralelo entre si.
- Dentro de cada user story, as tarefas tocam o mesmo arquivo de teste/rota e por isso NÃO são marcadas `[P]` entre si.

---

## Parallel Example: Foundational

```bash
Task: "Implementar ErrorResponse e exception handlers em src/pix_compliance/api/errors.py"
Task: "Implementar PaginatedResponse em src/pix_compliance/api/pagination.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup (`fastapi`/`uvicorn` instalados).
2. Completar Phase 2: Foundational (`app.py`, `errors.py`, `pagination.py`).
3. Completar Phase 3: User Story 1 — os três endpoints de consulta já são uma entrega independentemente validável.
4. **PARAR e VALIDAR**: rodar os testes da US1 isoladamente.

### Incremental Delivery

1. Setup + Foundational → base pronta.
2. US1 → validar independentemente (consultas via HTTP).
3. US2 → validar independentemente (`/health`, `/runs`).
4. US3 → validar independentemente (erros estruturados, `/docs` substantivo).
5. Polish → README (com a nota de escopo de autenticação), regressão completa, lint.

## Notes

- [P] = arquivos diferentes, sem dependência entre si.
- [Story] mapeia a tarefa à user story correspondente da spec.md.
- Confirmar que os testes falham antes de implementar (Princípio IX) — checkpoints explícitos em T007, T015, T025, T034.
- Rodar `pytest -q` e `ruff check` completos antes de considerar a feature encerrada (T040).
