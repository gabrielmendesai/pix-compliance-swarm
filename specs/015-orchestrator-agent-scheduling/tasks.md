---

description: "Task list template for feature implementation"
---

# Tasks: Orchestrator Agent (Harness) e agendamento (SPEC-015)

**Input**: Design documents from `/specs/015-orchestrator-agent-scheduling/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/orchestrator.md, quickstart.md

**Tests**: Requeridos pela spec (Princípio IX da constituição — testes escritos e confirmados como falhos antes de qualquer código de implementação, incluindo falha degradável, falha fatal, e disputa de lock).

**Organization**: Tarefas agrupadas por user story (spec.md). Todas convergem para `src/pix_compliance/agents/orchestrator_agent.py` e `tests/test_orchestrator_agent.py` — tarefas que tocam o mesmo arquivo NÃO são marcadas `[P]` entre si.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Projeto único: `src/pix_compliance/agents/`, `tests/`, `docs/` na raiz do repositório.

---

## Phase 1: Setup

**Purpose**: Introduzir `apscheduler` como dependência real (research.md, Decisão 7) e as extensões de contrato aditivas.

- [X] T001 Adicionar `apscheduler>=3.10` a `dependencies` em `pyproject.toml`, rodar `pip install -e ".[dev]"`, confirmar `python -c "import apscheduler; print(apscheduler.__version__)"`.
- [X] T002 Adicionar `EtapaMetric` (Pydantic) e o campo aditivo `PipelineResult.etapas: list[EtapaMetric] = Field(default_factory=list)` em `src/pix_compliance/models.py` (data-model.md) — nenhum campo existente de `PipelineResult` alterado.
- [X] T003 [P] Adicionar `orchestrator_schedule_cron: str` a `Settings` (`src/pix_compliance/config.py`), documentar em `.env.example` (ex. `ORCHESTRATOR_SCHEDULE_CRON=*/1 * * * *`).

**Checkpoint**: Dependência instalada; contrato de `PipelineResult` estendido aditivamente.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestrutura de orquestração compartilhada por todas as user stories — precisa existir antes de qualquer teste de user story.

**⚠️ CRITICAL**: Nenhuma tarefa de user story começa antes desta fase completa.

- [X] T004 [P] Criar `PipelineContext` (`@dataclass`) e `StepPolicy` (`StrEnum`) em `src/pix_compliance/agents/orchestrator_agent.py` (data-model.md).
- [X] T005 Implementar `_run_step(nome, policy, corotina)` em `orchestrator_agent.py`: mede duração, executa a corotina, captura exceção conforme `policy` (relança para `FATAL`; loga e retorna para `DEGRADABLE`/`IGNORABLE`), retorna um `EtapaMetric` (research.md, Decisão 4).
- [X] T006 Criar fixtures em `tests/test_orchestrator_agent.py`: `settings` (env vars via `monkeypatch`, mesmo `REQUIRED_ENV` já usado nos demais testes), reaproveitando `mock_bcb_server` (já existente em `tests/conftest.py`) e o padrão de `running_mcp_server` (mesma lógica de `tests/test_scraper_agent.py`, extraída/reaproveitada aqui) para os testes que precisam do pipeline completo real.
- [X] T007 Escrever `tests/test_orchestrator_agent.py` com os testes das quatro user stories (T010–T012, T017–T019, T023–T025, T030–T034 abaixo) importando `orchestrator_agent` — que ainda não existe — e **confirmar que a suíte falha por `ModuleNotFoundError`/`ImportError`** antes de prosseguir (checkpoint explícito do Princípio IX).

**Checkpoint**: `PipelineContext`/`StepPolicy`/`_run_step` prontos; suíte de teste criada e confirmada como falha.

---

## Phase 3: User Story 1 - Rodar o pipeline completo de ponta a ponta sob demanda (Priority: P1) 🎯 MVP

**Goal**: `run_pipeline` executa scrape→extract sequencial, depois {compliance_analyzer, knowledge_builder} em paralelo, depois conformance_validator, depois report_consolidator — produzindo um `PipelineResult` válido.

**Independent Test**: Rodar `run_pipeline` sobre o corpus mock (mock BCB + MCP subidos em processo) e verificar `PipelineResult.sucesso=True` com `etapas` preenchido.

### Tests for User Story 1 ⚠️

> **NOTE: Escrever estes testes PRIMEIRO, confirmar que FALHAM antes de implementar.**

- [X] T008 [US1] Teste `test_run_pipeline_completa_com_sucesso_e_etapas_na_ordem_esperada` em `tests/test_orchestrator_agent.py`: com `mock_bcb_server`/MCP subidos, `run_pipeline(request)` retorna `sucesso=True`, `etapas` contém uma entrada por etapa (`scrape`, `extract`, `compliance_analyzer`, `knowledge_builder`, `conformance_validator`, `report_consolidator`), com `scrape`/`extract` aparecendo antes de `compliance_analyzer`/`knowledge_builder`, que aparecem antes de `conformance_validator` (Acceptance Scenario 1 da US1, SC-001).
- [X] T009 [US1] Teste `test_compliance_analyzer_e_knowledge_builder_rodam_em_paralelo` em `tests/test_orchestrator_agent.py`: instrumenta (via um contador com `asyncio.Lock`, mesmo padrão já usado em `tests/test_compliance_analyzer_agent.py` para concorrência) as duas etapas para confirmar que ambas estão em execução simultaneamente em algum instante — não apenas que o resultado final está correto (FR-002).
- [X] T010 [US1] Teste `test_extractor_loop_de_reparo_e_acionado_dentro_do_fluxo_maior` em `tests/test_orchestrator_agent.py`: com um `FunctionModel` do Extractor que falha na primeira tentativa e sucede na segunda (mesmo padrão de `tests/test_extractor_agent.py`), `run_pipeline` conclui com sucesso, confirmando que o loop de reparo já existente (SPEC-009) opera normalmente dentro do fluxo maior, sem o Orchestrator reimplementá-lo (Acceptance Scenario 2 da US1, FR-003).
- [X] T011 [US1] Confirmar que T008–T010 falham (por `orchestrator_agent.py` ainda não ter `run_pipeline`) rodando `pytest tests/test_orchestrator_agent.py -k "sucesso or paralelo or loop_de_reparo" -q` — checkpoint explícito do Princípio IX.

### Implementation for User Story 1

- [X] T012 [US1] Implementar `run_pipeline(request: PipelineRequest) -> PipelineResult` em `orchestrator_agent.py`: sobe mock BCB + servidor MCP em processo (research.md, Decisão 2), constrói `PipelineContext` (incluindo `correlation_id` via `bind_run_correlation_id()`), executa `scrape`→`extract` sequencialmente via `_run_step`, depois `compliance_analyzer`/`knowledge_builder` via `asyncio.gather` dentro de `_run_step` cada um, depois `conformance_validator`, depois `report_consolidator` — agregando `PipelineResult` ao final; derruba mock BCB/MCP no `finally`.
- [X] T013 [US1] Rodar `pytest tests/test_orchestrator_agent.py -k "sucesso or paralelo or loop_de_reparo" -q` e confirmar que T008–T010 agora passam.

**Checkpoint**: User Story 1 completa e testável de forma independente — pipeline completo de ponta a ponta.

---

## Phase 4: User Story 2 - Falha em uma etapa é tratada de acordo com sua política (Priority: P1)

**Goal**: Falha numa etapa `degradable` não aborta o pipeline; falha numa etapa `fatal` aborta com mensagem clara.

**Independent Test**: Injetar falha simulada numa etapa degradável e confirmar que o pipeline continua; injetar falha numa etapa fatal e confirmar abort com mensagem clara.

### Tests for User Story 2 ⚠️

- [X] T014 [US2] Teste `test_falha_em_etapa_degradavel_nao_aborta_pipeline` em `tests/test_orchestrator_agent.py`: com uma falha simulada injetada em `knowledge_builder` (etapa `degradable`, ex. via `monkeypatch` fazendo `index_normativos` levantar uma exceção), `run_pipeline` conclui com `sucesso=True`, e o `EtapaMetric` de `knowledge_builder` tem `status="degradada"` (Acceptance Scenario 1 da US2, SC-002).
- [X] T015 [US2] Teste `test_falha_em_etapa_fatal_aborta_pipeline_com_mensagem_clara` em `tests/test_orchestrator_agent.py`: com uma falha simulada injetada em `extract` (etapa `fatal`), `run_pipeline` retorna `sucesso=False`, `erro` menciona a etapa (`"extract"`) e a causa, e as etapas posteriores (`compliance_analyzer` em diante) não aparecem em `etapas` (Acceptance Scenario 2 da US2, SC-002).
- [X] T016 [US2] Confirmar que T014–T015 falham rodando `pytest tests/test_orchestrator_agent.py -k "degradavel or fatal" -q` — checkpoint do Princípio IX.

### Implementation for User Story 2

- [X] T017 [US2] Ajustar `run_pipeline` em `orchestrator_agent.py` para aplicar o mapeamento de política por etapa de data-model.md (`scrape`/`extract`/`compliance_analyzer`/`conformance_validator`/geração local do `report_consolidator` = `fatal`; `knowledge_builder`/publicação HTTP do `report_consolidator` = `degradable`), abortando nas etapas fatais e seguindo nas degradáveis/ignoráveis via `_run_step` (já implementado em T005).
- [X] T018 [US2] Rodar `pytest tests/test_orchestrator_agent.py -k "degradavel or fatal" -q` e confirmar que T014–T015 passam.

**Checkpoint**: User Stories 1 e 2 completas e testáveis de forma independente.

---

## Phase 5: User Story 3 - Toda a execução é rastreável por um único `correlation_id`, com duração por etapa (Priority: P1)

**Goal**: Todo log de uma execução carrega o mesmo `correlation_id`; `PipelineResult.etapas` expõe duração por etapa.

**Independent Test**: Rodar o pipeline completo e verificar que todos os logs carregam o mesmo `correlation_id`, e que `PipelineResult` expõe duração total e por etapa.

### Tests for User Story 3 ⚠️

- [X] T019 [US3] Teste `test_todos_os_logs_de_uma_execucao_carregam_o_mesmo_correlation_id` em `tests/test_orchestrator_agent.py`: com `structlog.testing.capture_logs()` envolvendo uma chamada completa de `run_pipeline`, todos os eventos capturados têm o mesmo valor de `correlation_id`, e esse valor é único por execução (duas chamadas sucessivas produzem `correlation_id` diferentes) (Acceptance Scenario 1 da US3, SC-003).
- [X] T020 [US3] Teste `test_pipeline_result_expõe_duracao_total_e_por_etapa` em `tests/test_orchestrator_agent.py`: `PipelineResult.concluido_em - PipelineResult.iniciado_em` é a duração total; cada item de `PipelineResult.etapas` tem `duracao_segundos >= 0` (Acceptance Scenario 2 da US3, SC-004).
- [X] T021 [US3] Confirmar que T019–T020 falham rodando `pytest tests/test_orchestrator_agent.py -k "correlation_id or duracao_por_etapa" -q` — checkpoint do Princípio IX.

### Implementation for User Story 3

- [X] T022 [US3] Confirmar/ajustar em `orchestrator_agent.py` que `PipelineContext.correlation_id` (já construído em T012 via `bind_run_correlation_id()`) é de fato o mesmo em todos os logs emitidos por `_run_step` e por cada agente chamado (via `structlog.contextvars`, já o mecanismo estabelecido desde a SPEC-001 — nenhuma mudança de agente individual necessária).
- [X] T023 [US3] Rodar `pytest tests/test_orchestrator_agent.py -k "correlation_id or duracao_por_etapa" -q` e confirmar que T019–T020 passam.

**Checkpoint**: User Stories 1, 2 e 3 completas e testáveis de forma independente.

---

## Phase 6: User Story 4 - Disparo periódico via agendamento, sem caminhos de entrada divergentes (Priority: P2)

**Goal**: `start_scheduler` chama exatamente `run_pipeline`; um lock em processo rejeita execuções sobrepostas; o snippet de EventBridge documenta o mesmo entrypoint.

**Independent Test**: Configurar o scheduler com intervalo curto e observar múltiplas execuções automáticas; disparar duas execuções simultâneas e confirmar que a segunda é rejeitada pelo lock.

### Tests for User Story 4 ⚠️

- [X] T024 [P] [US4] Teste `test_duas_execucoes_simultaneas_segunda_e_rejeitada_pelo_lock` em `tests/test_orchestrator_agent.py`: disparar `asyncio.gather(run_pipeline(request), run_pipeline(request))` — exatamente uma das duas chamadas retorna `sucesso=True` com `etapas` preenchido, a outra retorna imediatamente `sucesso=False` com `erro` mencionando lock, e `etapas == []` (Acceptance Scenario 2 da US4, SC-006).
- [X] T025 [P] [US4] Teste `test_scheduler_dispara_run_pipeline_mais_de_uma_vez_automaticamente` em `tests/test_orchestrator_agent.py`: `start_scheduler` com um intervalo curto (segundos, via env var) registrado sobre um `run_pipeline` espiado (contador de chamadas); após aguardar um tempo curto, o contador mostra mais de uma chamada (Acceptance Scenario 1 da US4, SC-005 — mecanismo; o intervalo literal de 1 minuto é validado manualmente em quickstart.md).
- [X] T026 [US4] Teste `test_eventbridge_snippet_referencia_o_mesmo_entrypoint` em `tests/test_orchestrator_agent.py`: `docs/aws/eventbridge-schedule.tf` existe e contém, em texto, uma referência a `orchestrator_agent`/`run_pipeline` (Acceptance Scenario 3 da US4, SC-007).
- [X] T027 [US4] Confirmar que T024–T026 falham rodando `pytest tests/test_orchestrator_agent.py -k "lock or scheduler_dispara or eventbridge" -q` — checkpoint do Princípio IX.

### Implementation for User Story 4

- [X] T028 [US4] Implementar o lock em processo (`asyncio.Lock` em nível de módulo, checagem não bloqueante) em `run_pipeline` — retorno imediato de `PipelineResult(sucesso=False, erro="pipeline já em execução")` quando já adquirido (research.md, Decisão 6).
- [X] T029 [US4] Implementar `start_scheduler(settings) -> AsyncIOScheduler` em `orchestrator_agent.py`: registra `run_pipeline` via `add_job` com cron de `settings.orchestrator_schedule_cron`, retorna o scheduler já iniciado (research.md, Decisão 7).
- [X] T030 [US4] Criar `docs/aws/eventbridge-schedule.tf`: recurso de schedule (`aws_scheduler_schedule` ou `aws_cloudwatch_event_rule`/`aws_cloudwatch_event_target`) comentado, referenciando `orchestrator_agent.run_pipeline` como target conceitual (research.md, Decisão 8) — não aplicado, apenas documentação.
- [X] T031 [US4] Rodar `pytest tests/test_orchestrator_agent.py -k "lock or scheduler_dispara or eventbridge" -q` e confirmar que T024–T026 passam.

**Checkpoint**: Todas as user stories completas e independentemente testáveis.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: CLI, log de evidência, documentação de projeto e validação fim-a-fim.

- [X] T032 Adicionar bloco `if __name__ == "__main__":` (CLI) em `orchestrator_agent.py`, conforme contracts/orchestrator.md — lê `Settings`, monta `PipelineRequest`, chama `run_pipeline` via `asyncio.run`, imprime `PipelineResult`.
- [X] T033 Atualizar o alvo `run` do `Makefile` para invocar `python -m pix_compliance.agents.orchestrator_agent` (hoje aponta para o placeholder `pix_compliance.logging` da SPEC-001).
- [X] T034 Rodar uma execução real do pipeline completo (`make run` ou equivalente) e salvar a saída de log completa em `docs/evidence/pipeline-run.log` (FR-011) — parte do processo de implementação, não uma tarefa avulsa depois.
- [X] T035 [P] Adicionar seção "Orchestrator Agent e agendamento" ao `README.md`, documentando os três padrões de orquestração, a política de falha por etapa, o lock, o scheduler, e a nota de pendência sobre `POST /runs` (SPEC-013) não delegar a este Orchestrator ainda.
- [X] T036 [P] Confirmar `.env.example` documenta `ORCHESTRATOR_SCHEDULE_CRON` (já adicionado em T003).
- [X] T037 Rodar `pytest tests/test_orchestrator_agent.py -q` (suíte completa da feature) e confirmar todos os testes passam.
- [X] T038 Rodar `pytest -q` (regressão completa do projeto) e `ruff check` e confirmar que ambos passam sem erros.
- [X] T039 Validar `quickstart.md` executando os 9 cenários documentados (incluindo a validação manual do intervalo de 1 minuto, cenário 7) e confirmar que todos correspondem ao resultado esperado.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente.
- **Foundational (Phase 2)**: Depende do Setup — bloqueia todas as user stories.
- **US1 (Phase 3)**: Depende do Foundational. Base para US2/US3 (ambas modificam/observam o mesmo `run_pipeline` já funcional).
- **US2 (Phase 4)**: Depende de US1 (`run_pipeline` já orquestra as seis etapas; US2 adiciona a política de falha sobre ele).
- **US3 (Phase 5)**: Depende de US1 (mesma função `run_pipeline`); independente de US2 na prática (observa `correlation_id`/duração, não a política de falha em si).
- **US4 (Phase 6)**: Depende de US1 (precisa de `run_pipeline` funcional para agendar/travar); independente de US2/US3.
- **Polish (Phase 7)**: Depende de todas as user stories completas.

### Within Each User Story

- Testes escritos e confirmados como falhos antes da implementação correspondente (Princípio IX).
- `_run_step`/`PipelineContext`/`StepPolicy` (Foundational) antes de qualquer etapa de `run_pipeline` (US1).
- `run_pipeline` funcional (US1) antes da política de falha (US2), do `correlation_id`/duração (US3, já emergem de T005/T012, mas testados aqui) e do lock/scheduler (US4).

### Parallel Opportunities

- T003/T004 (arquivos distintos) podem rodar em paralelo após T001/T002.
- T024/T025 (US4, testes independentes dentro do mesmo arquivo mas sem dependência de dados entre si) podem ser escritos em paralelo.
- T035/T036 (Polish, arquivos distintos) podem rodar em paralelo entre si.

---

## Parallel Example: Setup

```bash
Task: "Adicionar orchestrator_schedule_cron a Settings em src/pix_compliance/config.py"
Task: "Criar PipelineContext/StepPolicy em src/pix_compliance/agents/orchestrator_agent.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup.
2. Completar Phase 2: Foundational.
3. Completar Phase 3: User Story 1 — pipeline completo de ponta a ponta já é uma entrega independentemente validável (o objetivo nominal central da spec).
4. **PARAR e VALIDAR**: rodar os testes da US1 isoladamente.

### Incremental Delivery

1. Setup + Foundational → base pronta.
2. US1 → validar independentemente (pipeline completo, MVP).
3. US2 → validar independentemente (política de falha por etapa).
4. US3 → validar independentemente (rastreabilidade e métricas).
5. US4 → validar independentemente (agendamento, lock, IaC).
6. Polish → CLI, `make run`, log de evidência real, README, regressão completa, lint.

## Notes

- [P] = arquivos/testes diferentes, sem dependência entre si.
- [Story] mapeia a tarefa à user story correspondente da spec.md.
- Confirmar que os testes falham antes de implementar (Princípio IX) — checkpoints explícitos em T007, T011, T016, T021, T027.
- Rodar `pytest -q` e `ruff check` completos antes de considerar a feature encerrada (T038).
- Reconciliar `POST /runs` (SPEC-013) para delegar a `run_pipeline` **não** é uma tarefa desta lista — pendência registrada (spec.md, Assumptions; quickstart.md) para uma spec/tarefa futura própria.
