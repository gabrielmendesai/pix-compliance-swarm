---

description: "Task list template for feature implementation"
---

# Tasks: Testes e observabilidade (SPEC-017)

**Input**: Design documents from `/specs/017-testes-observabilidade/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/observability.md, quickstart.md

**Tests**: Requeridos pelo Princípio IX da constituição, com a ordem parcialmente invertida
documentada em spec.md/plan.md — o teste que expõe cada lacuna real (encontrada na auditoria de
research.md) é escrito e confirmado como falho antes do ajuste de código de produção
correspondente.

**Organization**: Tarefas agrupadas por user story (spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência entre si)
- **[Story]**: A qual user story esta tarefa pertence (US1, US2, US3)
- Caminhos de arquivo exatos incluídos em cada descrição

## Path Conventions

Projeto único (`src/pix_compliance/`, `mcp_servers/`, `tests/`, `.github/workflows/`) — mesma
estrutura já estabelecida desde a SPEC-001 (ver plan.md, Project Structure).

---

## Phase 1: Setup

**Purpose**: Preparar a dependência de ferramenta necessária ao relatório de cobertura (FR-009),
usada apenas no Polish — sem isso, a etapa de leitura de cobertura não teria a ferramenta
instalada.

- [X] T001 [P] Adicionar `pytest-cov` a `[project.optional-dependencies].dev` em `pyproject.toml` (research.md, Decisão 6).

**Checkpoint**: Dependência de cobertura disponível para instalação via `pip install -e ".[dev]"`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Consolidação de fixtures duplicadas — toca `tests/conftest.py` e dez módulos de
teste ao mesmo tempo; feito antes de qualquer tarefa de user story para evitar conflito com as
novas tarefas de teste que essas mesmas user stories vão adicionar aos mesmos arquivos.

**⚠️ CRITICAL**: Nenhuma tarefa de user story começa antes desta fase completa.

- [X] T002 Consolidar as fixtures `pytest` duplicadas (`_settings`/`settings`, `store`, `_required_env`, `_free_port`) em `tests/conftest.py`, removendo as definições locais redundantes de `tests/test_api.py`, `tests/test_compliance_analyzer_agent.py`, `tests/test_config.py`, `tests/test_conformance.py`, `tests/test_extractor_agent.py`, `tests/test_knowledge_builder_agent.py`, `tests/test_object_store.py`, `tests/test_orchestrator_agent.py`, `tests/test_report_consolidator_agent.py`, `tests/test_vector_store.py` (research.md, Decisão 3; FR-005).
- [X] T003 Rodar `make test` e confirmar que os 194 testes já existentes continuam passando após a consolidação de fixtures — checkpoint de regressão antes de iniciar qualquer user story.

**Checkpoint**: `tests/conftest.py` é a única fonte das fixtures compartilhadas; suíte continua verde.

---

## Phase 3: User Story 1 - Rodar a suíte inteira sem rede e sem credenciais AWS (Priority: P1) 🎯 MVP

**Goal**: `make test` passa integralmente sem rede/credenciais AWS, incluindo um teste ponta a
ponta real do pipeline completo (Orchestrator + todos os agentes + API) — não apenas testes
isolados por agente.

**Independent Test**: Rodar `make test` numa máquina sem `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`
configuradas e confirmar que a suíte inteira passa, incluindo o teste ponta a ponta via `POST /runs`.

### Tests for User Story 1 ⚠️

> **NOTE: Escrever estes testes PRIMEIRO, confirmar que FALHAM antes da implementação**

- [X] T004 [P] [US1] Em `tests/test_api.py`, estender `test_post_runs_dispara_pipeline_e_retorna_resultado_completo` para verificar que `corpo["etapas"]` contém as seis etapas (`scrape`, `extract`, `compliance_analyzer`, `knowledge_builder`, `conformance_validator`, `report_consolidator`) na ordem esperada; rodar e confirmar que FALHA contra o comportamento atual de `_run_pipeline_sync` (só 4 etapas) (research.md, Decisão 1; contracts/observability.md).
- [X] T005 [US1] Confirmar que `tests/test_orchestrator_agent.py::TestPipelineCompleto::test_run_pipeline_completa_com_sucesso_e_etapas_na_ordem_esperada` já passa sem nenhuma alteração — checkpoint de auditoria documentando que a cobertura ponta a ponta via `run_pipeline` já existe (research.md, Decisão 1).

### Implementation for User Story 1

- [X] T006 [US1] Em `src/pix_compliance/api/routes.py`, fazer `post_runs` delegar inteiramente a `run_pipeline` (`src/pix_compliance/agents/orchestrator_agent.py`), com `bootstrap_local_servers=True`, e remover `_run_pipeline_sync` (research.md, Decisão 1; contracts/observability.md).
- [X] T007 [US1] Rodar novamente o teste de T004 e confirmar que agora passa.
- [X] T008 [US1] Rodar `make test` com `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` não definidas e confirmar que a suíte inteira passa (SC-001), conforme quickstart.md Cenário 1.

**Checkpoint**: User Story 1 completa e verificável de forma independente — suíte offline, teste ponta a ponta real via API.

---

## Phase 4: User Story 2 - Confiar no CI sem verificar manualmente (Priority: P1)

**Goal**: Todo push/PR dispara automaticamente lint e a suíte de testes via GitHub Actions, com
resultado confiável sem verificação manual.

**Independent Test**: Dar push numa branch (ou abrir um PR) e observar que o workflow de CI
dispara automaticamente e reporta um status na interface do GitHub.

### Implementation for User Story 2

> Nota: esta user story não tem teste `pytest` correspondente — o "teste" é o próprio workflow rodando com sucesso (Princípio VIII, evidência via execução real de CI).

- [X] T009 [US2] Criar `.github/workflows/ci.yml`, disparado em `push`/`pull_request`, rodando `pip install -e ".[dev]"`, `ruff check .`, `pytest -q` num único job (research.md, Decisão 5; contracts/observability.md).
- [X] T010 [US2] Dar push na branch (ou abrir um PR) e confirmar que a execução do workflow está verde na interface do GitHub Actions (SC-003), conforme quickstart.md Cenário 3. Primeiro push (`16909cb`) revelou dois problemas reais: `services:` ausente (Postgres/MinIO inacessíveis) e `Settings()` falhando na coleta por falta de env vars mínimas — ambos corrigidos em `.github/workflows/ci.yml`; status final do workflow a confirmar manualmente em github.com (`gh` não autenticado neste ambiente).

**Checkpoint**: User Stories 1 e 2 completas e verificáveis de forma independente.

---

## Phase 5: User Story 3 - Auditar uma execução real do pipeline pelos logs (Priority: P2)

**Goal**: Uma única execução do pipeline é seguível do início ao fim pelos logs estruturados,
filtrando por `correlation_id`, com contadores agregados por etapa visíveis.

**Independent Test**: Rodar `make run`, coletar os logs, filtrar por um único `correlation_id`, e
confirmar que todas as etapas aparecem com seus contadores agregados.

### Tests for User Story 3 ⚠️

> **NOTE: Escrever estes testes PRIMEIRO, confirmar que FALHAM antes da implementação**

- [X] T011 [P] [US3] Em `tests/test_models.py`, adicionar um teste confirmando que `EtapaMetric` aceita um campo opcional `contadores: dict[str, int] | None`; rodar e confirmar que FALHA contra o modelo atual (data-model.md).
- [X] T012 [P] [US3] Em `tests/test_scraper_mcp_server.py`, adicionar um teste confirmando que uma chamada de ferramenta (ex. `fetch_normativo`) com `correlation_id` produz linhas de log estruturado (`mcp_tool_chamada`/`mcp_tool_concluida`) carregando esse mesmo id; rodar e confirmar que FALHA contra o servidor atual (nenhum logging existe) (research.md, Decisão 2; contracts/observability.md).
- [X] T013 [US3] Em `tests/test_orchestrator_agent.py`, adicionar um teste confirmando que uma execução do pipeline emite eventos de log `pipeline_etapa_concluida` (via `caplog`/`capsys`) para as seis etapas, todos com o mesmo `correlation_id` e `contadores` não nulo onde aplicável; rodar e confirmar que FALHA contra o `_run_step` atual (contracts/observability.md).

### Implementation for User Story 3

- [X] T014 [P] [US3] Adicionar `contadores: dict[str, int] | None = None` a `EtapaMetric` em `src/pix_compliance/models.py` (data-model.md).
- [X] T015 [US3] Adicionar aceitação de `correlation_id` e logging estruturado (`mcp_tool_chamada`/`mcp_tool_concluida`) às chamadas de ferramenta em `mcp_servers/scraper_sse/server.py` (`list_normativos`, `fetch_normativo`, `detect_changes`), reaproveitando `pix_compliance.logging.configure_logging` (research.md, Decisão 2; contracts/observability.md).
- [X] T016 [US3] Atualizar `_run_step` em `src/pix_compliance/agents/orchestrator_agent.py` para logar `pipeline_etapa_concluida` com `contadores` por etapa (`documentos_coletados`, `regras_extraidas`, `gaps_encontrados`, `tokens_consumidos`, onde aplicável) e para propagar `correlation_id` nas chamadas de ferramenta MCP do scraper (data-model.md; contracts/observability.md).
- [X] T017 [US3] Rodar novamente os testes de T011–T013 e confirmar que passam.
- [X] T018 [US3] Rodar `make run`, capturar os logs, filtrar pelo `correlation_id` da execução, e confirmar que os seis eventos `pipeline_etapa_concluida` aparecem na ordem esperada (quickstart.md Cenário 5) — guardar como evidência.

**Checkpoint**: Todas as user stories completas e verificáveis de forma independente.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Auditoria de cobertura declarada (modelos/guardrails), confirmação de testes de
integração já existentes, e validação final de ponta a ponta.

- [X] T019 [P] Auditar `tests/test_models.py` e `tests/test_guardrails.py` contra `src/pix_compliance/models.py`/`src/pix_compliance/guardrails.py` e adicionar os casos de teste faltantes encontrados — priorizando os pontos onde um erro silencioso é mais caro (dado malformado propagando, PII vazando) (FR-003).
- [X] T020 Instalar `pytest-cov` (via T001) e rodar `pytest --cov=src/pix_compliance --cov-report=term-missing -q`, lendo o relatório com foco declarado em `models.py`/`guardrails.py`, sem meta de porcentagem total (FR-009/SC-004), conforme quickstart.md Cenário 4.
- [X] T021 [P] Rodar os testes de integração contra containers reais (`docker compose up postgres minio -d`, depois `pytest tests/test_object_store.py tests/test_vector_store.py tests/test_no_orphan_abstractions.py tests/test_api.py -q`) e confirmar que continuam passando sem alteração (FR-004).
- [X] T022 Rodar `make test` e `ruff check .` uma última vez sobre o repositório inteiro e confirmar que ambos passam sem erro.
- [X] T023 Validar `quickstart.md` executando os 5 cenários documentados e confirmar que todos correspondem ao resultado esperado.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente.
- **Foundational (Phase 2)**: Depende do Setup — bloqueia todas as user stories (consolidação de fixtures precisa terminar antes de qualquer tarefa de teste de user story tocar os mesmos arquivos).
- **US1 (Phase 3)**: Depende do Foundational. Sem dependência de US2/US3.
- **US2 (Phase 4)**: Depende do Foundational. Independente de US1/US3 (workflow de CI não depende do conteúdo específico dos testes, só de que `ruff`/`pytest` existam como comandos).
- **US3 (Phase 5)**: Depende do Foundational. Independente de US1/US2 (correlation_id/contadores são ortogonais à correção de `POST /runs` e ao CI).
- **Polish (Phase 6)**: Depende de todas as user stories completas.

### Within Each User Story

- Testes (T004/T005, T011–T013) são escritos e confirmados como falhos antes da implementação correspondente (Princípio IX).
- T006 (implementação de US1) depende de T004 já escrito e falho.
- T015/T016 (implementação de US3) dependem de T011–T013 já escritos e falhos.

### Parallel Opportunities

- T001 (Setup) não depende de nada — pode rodar a qualquer momento antes do Polish.
- Dentro de US1: T004 é independente de T005 (arquivos diferentes) — `[P]`.
- Dentro de US3: T011/T012 são independentes entre si (arquivos diferentes) — `[P]`; T014 é independente de T011–T013 (arquivo diferente) — `[P]`.
- US1, US2 e US3 podem ser trabalhadas em paralelo por pessoas diferentes após o Foundational, por serem independentes entre si.
- T019/T021 (Polish, escopos diferentes) podem rodar em paralelo entre si.

---

## Parallel Example: User Story 3

```bash
Task: "Adicionar teste de contadores em EtapaMetric em tests/test_models.py"
Task: "Adicionar teste de logging estruturado com correlation_id em tests/test_scraper_mcp_server.py"
Task: "Adicionar campo contadores a EtapaMetric em src/pix_compliance/models.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup.
2. Completar Phase 2: Foundational (fixtures consolidadas, suíte confirmada verde).
3. Completar Phase 3: User Story 1 — suíte offline + teste ponta a ponta real via API já é o objetivo nominal central da spec, independentemente validável.
4. **PARAR e VALIDAR**: rodar `make test` sem credenciais AWS (quickstart.md Cenário 1).

### Incremental Delivery

1. Setup + Foundational → base pronta (fixtures consolidadas, sem regressão).
2. US1 → validar independentemente (suíte offline, e2e via API, MVP).
3. US2 → validar independentemente (CI verde).
4. US3 → validar independentemente (correlation_id + contadores nos logs).
5. Polish → auditoria de cobertura declarada, regressão de integração, validação final do quickstart.

## Notes

- [P] = arquivos diferentes, sem dependência entre si.
- [Story] mapeia a tarefa à user story correspondente da spec.md.
- Testes de cada user story são escritos e confirmados como falhos antes da implementação
  correspondente (Princípio IX, ordem documentada em plan.md/spec.md).
- Nenhuma tarefa introduz abstração nova — todas estendem infraestrutura já existente
  (`EtapaMetric`, `conftest.py`, `structlog`, `pytest`), conforme FR-011.
