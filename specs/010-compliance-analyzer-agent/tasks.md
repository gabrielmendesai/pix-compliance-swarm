---

description: "Task list template for feature implementation"
---

# Tasks: Compliance Analyzer Agent (SPEC-010)

**Input**: Design documents from `/specs/010-compliance-analyzer-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/compliance_analyzer_agent.md, quickstart.md

**Tests**: Incluídos e obrigatórios — o Princípio IX da constituição exige que os testes sejam escritos e confirmados como falhos antes de qualquer código de implementação, incluindo um teste que comprove por instrumentação (não apenas pelo resultado final) que o semáforo de concorrência nunca excede o limite configurado.

**Organization**: Tarefas agrupadas por user story do spec.md, permitindo implementação e teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: A qual user story esta tarefa pertence (US1-US5)
- Caminhos de arquivo exatos incluídos em cada descrição

## Path Conventions

Projeto único: `src/pix_compliance/agents/compliance_analyzer_agent.py` (novo módulo, mesmo pacote das SPEC-008/009), `skills/compliance-analyzer-skill/` (novo), `tests/` na raiz do repositório (conforme `plan.md`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar configuração e esqueleto antes de qualquer código do agente

- [X] T001 [P] Adicionar `compliance_analyzer_max_concurrency: int` e `compliance_analyzer_confidence_threshold: float` a `Settings` (`src/pix_compliance/config.py`) e a `.env.example` (com default documentado, ex. `3` e `0.7`) — REQUIRED_ENV de todos os testes existentes atualizado com as duas novas variáveis
- [X] T002 [P] Criar `skills/compliance-analyzer-skill/` com um `SKILL.md` placeholder (preenchido de fato na User Story 5)

**Checkpoint**: Configuração e esqueleto prontos.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contratos de dados e seleção de modelo que TODAS as user stories dependem

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase estar completa

- [X] T003 Adicionar o campo `revisao_humana_necessaria: bool = False` a `RegraExtraida` em `src/pix_compliance/models.py`, sem alterar nenhum campo já existente, conforme `data-model.md`
- [X] T004 [P] Teste: `RegraExtraida` com o novo campo valida e serializa corretamente (default `False`, round-trip, e rejeita campo extra) em `tests/test_models.py` (estendido `TestRegraExtraida` já existente)
- [X] T005 Rodar `pytest tests/test_models.py -q` (inclui `TestJsonSchemaExport`, que atualiza `docs/schemas/RegraExtraida.schema.json` automaticamente) e confirmar ausência de divergência de schema — 33/33 passando
- [X] T006 [P] Definir `ComplianceAnalyzerAgentDeps` (`dataclass` vazia, mantida por consistência estrutural com os demais agentes — este agente não tem dependência externa própria) em `src/pix_compliance/agents/compliance_analyzer_agent.py`, conforme `data-model.md`
- [X] T007 Implementar a função privada de seleção de modelo (`_build_model(settings) -> Model`, mesmo padrão de dispatch já estabelecido em `scraper_agent.py`/`extractor_agent.py`) em `src/pix_compliance/agents/compliance_analyzer_agent.py`

**Checkpoint**: Contratos de dados e seleção de modelo prontos; nenhuma lógica de categorização ainda.

---

## Phase 3: User Story 1 - Regras são categorizadas corretamente nas seis dimensões de compliance (Priority: P1) 🎯 MVP

**Goal**: O agente categoriza corretamente regras de `NormativoItem` em cada uma das seis dimensões, com um system prompt que define operacionalmente cada categoria

**Independent Test**: Para cada uma das seis categorias, processar ao menos um `NormativoItem`/fixture representativo e verificar que a `RegraExtraida` produzida tem o campo `categoria` correto

### Tests for User Story 1 ⚠️

> Escrever este teste primeiro; deve FALHAR antes da implementação (Princípio IX)

- [X] T008 [P] [US1] Teste: para cada uma das seis categorias (`participantes`, `tarifas`, `liquidação`, `segurança`, `SLA`, `interoperabilidade`), um `NormativoItem` representativo carregado de `fixtures/normativos.json` (SPEC-003), processado via `analyze_normativo` com um `FunctionModel` determinístico retornando a categoria esperada, produz uma `RegraExtraida` com `categoria` correta, em `tests/test_compliance_analyzer_agent.py` — validado por spike manual que o output tool de `Agent(output_type=list[Model])` espera `args={"response": [...]}`
- [X] T009 [US1] Rodar `pytest tests/test_compliance_analyzer_agent.py -k six_categories -q`, confirmando que o teste FALHA por ausência de `compliance_analyzer_agent.py`/`analyze_normativo` (nenhuma implementação ainda) — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ImportError` (6/6 falhando)

### Implementation for User Story 1

- [X] T010 [US1] Implementar `build_compliance_analyzer_agent(settings, model=None) -> Agent[ComplianceAnalyzerAgentDeps, list[RegraExtraida]]` com o system prompt definindo operacionalmente cada uma das seis categorias (foco nos pares ambíguos, ex. participantes vs. interoperabilidade, conforme `research.md`) em `src/pix_compliance/agents/compliance_analyzer_agent.py` (depende de T006, T007)
- [X] T011 [US1] Implementar `analyze_normativo(settings, normativo, model=None) -> list[RegraExtraida]` (async — monta o prompt a partir do texto do `NormativoItem`, chama `agent.run`, retorna a lista produzida; guardrail e recomputação de `revisao_humana_necessaria` adicionados nas User Stories 2/4) em `src/pix_compliance/agents/compliance_analyzer_agent.py` (depende de T010)
- [X] T012 [US1] Rodar novamente `pytest tests/test_compliance_analyzer_agent.py -k six_categories -q` e confirmar que o teste de T008 agora PASSA — 6/6 passando

**Checkpoint**: User Story 1 completa e testável de forma independente — categorização nas seis dimensões funciona (SC-001).

---

## Phase 4: User Story 2 - Regras com baixa confiança são sinalizadas explicitamente (Priority: P1) 🎯 MVP

**Goal**: Toda `RegraExtraida` com `confianca` abaixo do limiar configurado tem `revisao_humana_necessaria=True`, calculado deterministicamente pelo código do agente (não pelo LLM)

**Independent Test**: Processar uma regra cuja `confianca` retornada pelo modelo fique abaixo do limiar configurado, e verificar que `revisao_humana_necessaria=True` na saída — e o inverso para confiança igual/acima do limiar

### Tests for User Story 2 ⚠️

> Escrever este teste primeiro; deve FALHAR antes da implementação (Princípio IX)

- [X] T013 [P] [US2] Teste: `analyze_normativo`, com um `FunctionModel` que devolve `revisao_humana_necessaria` deliberadamente errado (sempre `False`), produz `RegraExtraida.revisao_humana_necessaria=True` quando `confianca` fica abaixo do limiar configurado; `False` quando igual/acima — comprovando que o agente recalcula, não confia no LLM, em `tests/test_compliance_analyzer_agent.py`
- [X] T014 [US2] Rodar `pytest tests/test_compliance_analyzer_agent.py -k confidence -q`, confirmando que o teste de baixa confiança FALHA porque `analyze_normativo` ainda não recalcula `revisao_humana_necessaria` a partir de `confianca` e do limiar — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `AssertionError` (flag `False` em vez de `True`)

### Implementation for User Story 2

- [X] T015 [US2] Em `analyze_normativo`, após receber a saída do agente, recalcular deterministicamente `revisao_humana_necessaria = (confianca < settings.compliance_analyzer_confidence_threshold)` para cada `RegraExtraida` (via `model_copy(update=...)`, nunca confiando em o LLM ter feito essa comparação corretamente) em `src/pix_compliance/agents/compliance_analyzer_agent.py` (depende de T011)
- [X] T016 [US2] Rodar novamente `pytest tests/test_compliance_analyzer_agent.py -k confidence -q` e confirmar que o teste de T013 agora PASSA — 2/2 passando

**Checkpoint**: User Story 2 completa e testável de forma independente — sinalização de revisão humana determinística (SC-002).

---

## Phase 5: User Story 3 - Processamento em lote nunca excede o limite de concorrência configurado (Priority: P1) 🎯 MVP

**Goal**: `analyze_batch` processa múltiplos `NormativoItem` concorrentemente, sem nunca exceder `settings.compliance_analyzer_max_concurrency` chamadas simultâneas ao LLM

**Independent Test**: Processar um lote maior que o limite configurado, instrumentando o número de chamadas em andamento a cada instante, e confirmar que o pico nunca excede o limite

### Tests for User Story 3 ⚠️

> Escrever este teste primeiro; deve FALHAR antes da implementação (Princípio IX)

- [X] T017 [P] [US3] Teste: `analyze_batch` sobre um lote de `NormativoItem` maior que `settings.compliance_analyzer_max_concurrency`, usando um `FunctionModel` assíncrono com `asyncio.sleep` e um contador de chamadas em andamento protegido por `asyncio.Lock`, confirma que o pico de concorrência nunca excede o limite configurado (comprovado por instrumentação, não apenas pelo resultado final) em `tests/test_compliance_analyzer_agent.py`
- [X] T018 [US3] Rodar `pytest tests/test_compliance_analyzer_agent.py -k concurrency -q`, confirmando que o teste FALHA por ausência de `analyze_batch` (nenhuma implementação ainda) — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ImportError`

### Implementation for User Story 3

- [X] T019 [US3] Implementar `analyze_batch(settings, normativos, model=None) -> list[RegraExtraida]` (`asyncio.Semaphore(settings.compliance_analyzer_max_concurrency)` adquirido antes de cada `analyze_normativo`, orquestrado via `asyncio.gather`) em `src/pix_compliance/agents/compliance_analyzer_agent.py` (depende de T011, T015)
- [X] T020 [US3] Rodar novamente `pytest tests/test_compliance_analyzer_agent.py -k concurrency -q` e confirmar que o teste de T017 agora PASSA — 1/1 passando

**Checkpoint**: User Story 3 completa e testável de forma independente — limite de concorrência genuinamente respeitado (SC-003).

---

## Phase 6: User Story 4 - Guardrail é reaplicado antes de qualquer chamada ao LLM (Priority: P2)

**Goal**: `guard()` (SPEC-004) é invocado sobre o texto do `NormativoItem` antes de qualquer chamada ao LLM deste agente, mesmo com entrada supostamente já limpa

**Independent Test**: Instrumentar/observar a chamada a `guard()` durante o processamento de um `NormativoItem`, confirmando que ocorre antes de qualquer chamada ao LLM deste agente

### Tests for User Story 4 ⚠️

> Escrever este teste primeiro; deve FALHAR antes da implementação (Princípio IX)

- [X] T021 [P] [US4] Teste: `guard()` é invocado (via `monkeypatch`/spy sobre `pix_compliance.agents.compliance_analyzer_agent.guard`) sobre o texto do `NormativoItem` antes de `agent.run`, em `tests/test_compliance_analyzer_agent.py`
- [X] T022 [US4] Rodar `pytest tests/test_compliance_analyzer_agent.py -k guard_is_called -q`, confirmando que o teste FALHA porque `guard()` ainda não está conectado a `analyze_normativo` — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `AssertionError` (`chamadas == []`)

### Implementation for User Story 4

- [X] T023 [US4] Conectar `guard()` em `analyze_normativo`: o texto do `NormativoItem` passa por `guard()` antes de compor o prompt enviado ao LLM — reaplicação deliberada, independentemente de o texto já ter passado pelo guardrail no Extractor Agent (SPEC-009) em `src/pix_compliance/agents/compliance_analyzer_agent.py` (depende de T011)
- [X] T024 [US4] Rodar novamente `pytest tests/test_compliance_analyzer_agent.py -k guard_is_called -q` e confirmar que o teste de T021 agora PASSA — 1/1 passando

**Checkpoint**: User Story 4 completa e testável de forma independente — defesa em profundidade do guardrail confirmada.

---

## Phase 7: User Story 5 - Documentação da skill segue o formato já estabelecido (Priority: P2)

**Goal**: `skills/compliance-analyzer-skill/SKILL.md` documenta responsabilidade, ferramentas, input e output, no mesmo formato dos `SKILL.md` já existentes

**Independent Test**: Verificar que `skills/compliance-analyzer-skill/SKILL.md` existe e contém as mesmas quatro seções exigidas

### Tests for User Story 5 ⚠️

> Escrever este teste primeiro; deve FALHAR antes da implementação (Princípio IX)

- [X] T025 [P] [US5] Teste: `skills/compliance-analyzer-skill/SKILL.md` existe e contém as seções "Responsabilidade", "Ferramentas", "Input" e "Output" (mesmo padrão de verificação já usado para os `SKILL.md` das SPEC-008/009), em `tests/test_compliance_analyzer_agent.py`
- [X] T026 [US5] Rodar `pytest tests/test_compliance_analyzer_agent.py -k skill_md -q`, confirmando que o teste FALHA porque `SKILL.md` ainda é o placeholder de T002 — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `AssertionError` (seção "Responsabilidade" ausente)

### Implementation for User Story 5

- [X] T027 [US5] Escrever `skills/compliance-analyzer-skill/SKILL.md` completo: responsabilidade (categoriza regras nas 6 dimensões; não compara versões nem gera relatório), ferramentas (system prompt de categorização, `guard()`, semáforo de concorrência), input (`NormativoItem`/lote) e output (`list[RegraExtraida]`), no mesmo formato dos `SKILL.md` já existentes
- [X] T028 [US5] Rodar novamente `pytest tests/test_compliance_analyzer_agent.py -k skill_md -q` e confirmar que o teste de T025 agora PASSA — 1/1 passando

**Checkpoint**: Todas as cinco user stories completas e testáveis de forma independente (SC-001, SC-002, SC-003).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Validação final que atravessa todas as user stories

- [X] T029 [P] Rodar `ruff check src tests` e corrigir eventuais violações introduzidas por esta feature — limpo, sem violações
- [X] T030 Rodar `pytest -q` como checagem final de regressão de toda a suíte do projeto (não apenas os testes desta feature) — 142/142 passando
- [X] T031 [P] Atualizar README com uma nota sobre o Compliance Analyzer Agent (terceiro agente do enxame, categorização nas 6 dimensões, concorrência limitada por semáforo, sinalização de revisão humana, guardrail redundante) — CLI (`__main__`) também adicionado a `compliance_analyzer_agent.py`, documentado no README (não previsto como tarefa dedicada, mas exigido pelo contrato em `contracts/compliance_analyzer_agent.md`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: Depende da Setup — BLOQUEIA todas as user stories
- **User Stories (Phase 3-7)**: Todas dependem da conclusão da Foundational
  - US1 (P1) depende apenas da Foundational — nenhuma dependência de outra story
  - US2 (P1) depende da Foundational e de US1 (recalcula um campo sobre a saída já existente de `analyze_normativo`)
  - US3 (P1) depende da Foundational, de US1 e de US2 (`analyze_batch` orquestra `analyze_normativo` já completo, incluindo a recomputação de `revisao_humana_necessaria`)
  - US4 (P2) depende da Foundational e de US1 (adiciona `guard()` à função já existente); independente de US2/US3
  - US5 (P2) depende apenas da Foundational — independente de US1-US4
- **Polish (Phase 8)**: Depende de todas as user stories desejadas estarem completas

### User Story Dependencies

- **US1 (P1)**: Depende apenas da Foundational — cria `build_compliance_analyzer_agent`/`analyze_normativo`
- **US2 (P1)**: Depende da Foundational e de US1 (adiciona recomputação determinística sobre a saída já existente)
- **US3 (P1)**: Depende da Foundational, de US1 e de US2 (`analyze_batch` reaproveita `analyze_normativo` já completo)
- **US4 (P2)**: Depende da Foundational e de US1; independente de US2/US3
- **US5 (P2)**: Depende apenas da Foundational — independente de US1-US4

### Within Each User Story

- Testes escritos e confirmados como FALHANDO (passo explícito, Princípio IX) antes da implementação correspondente
- Categorização básica (US1) antes de sinalização de revisão (US2) antes de concorrência em lote (US3) — cada uma adiciona uma camada à mesma função `analyze_normativo`/`analyze_batch`
- Guardrail (US4) e documentação (US5) são incrementos independentes sobre a Foundational/US1

### Parallel Opportunities

- T001/T002 (Setup) em paralelo — arquivos diferentes
- T004/T006 (Foundational) em paralelo — arquivos diferentes
- US4 (Phase 6) e US5 (Phase 7) podem ser trabalhadas em paralelo por desenvolvedores diferentes, assim que US1 estiver completa

---

## Parallel Example: Foundational

```bash
# Tarefas independentes da Foundational em paralelo:
Task: "Teste RegraExtraida com revisao_humana_necessaria em tests/test_models.py"
Task: "Definir ComplianceAnalyzerAgentDeps em src/pix_compliance/agents/compliance_analyzer_agent.py"
```

## Parallel Example: User Story 4 + User Story 5

```bash
# US4 (guardrail) e US5 (documentação) em paralelo, após US1:
Task: "Conectar guard() em analyze_normativo em src/pix_compliance/agents/compliance_analyzer_agent.py"
Task: "Escrever skills/compliance-analyzer-skill/SKILL.md completo"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 + 3)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (CRÍTICO — bloqueia todas as stories)
3. Completar Phase 3: User Story 1 (categorização nas 6 dimensões)
4. Completar Phase 4: User Story 2 (sinalização de revisão humana)
5. Completar Phase 5: User Story 3 (concorrência limitada por semáforo)
6. **PARAR e VALIDAR**: rodar os Cenários 1, 2 e 3 de `quickstart.md`
7. Este é o MVP real desta feature — as três garantias P1 que cumprem o objetivo nominal (categorização correta, sinalização acionável, concorrência segura)

### Incremental Delivery

1. Setup + Foundational → configuração e contratos de dados prontos
2. US1 → categorização nas 6 dimensões → validar com Cenário 1 de `quickstart.md`
3. US2 → sinalização de revisão humana → validar com Cenário 2 de `quickstart.md`
4. US3 → concorrência limitada → validar com Cenário 3 de `quickstart.md`
5. US4 → guardrail redundante → validar com Cenário 4 de `quickstart.md`
6. US5 → `SKILL.md` → validar com Cenário 6 de `quickstart.md`
7. Polish → lint, regressão completa, README

---

## Notes

- [P] = arquivos diferentes ou casos de teste independentes, sem dependência bloqueante
- [Story] mapeia cada tarefa à user story correspondente do spec.md
- Testes devem ser escritos e confirmados como falhando antes da implementação correspondente (Princípio IX) — cada story inclui um passo explícito de execução e confirmação de falha antes da tarefa de implementação
- Commitar após cada tarefa ou grupo lógico de tarefas
- Parar em cada checkpoint para validar a story de forma independente
- Evitar: tarefas vagas, conflito de mesmo arquivo sem necessidade, dependências entre stories que quebrem a independência (US2/US3 dependem de US1 por necessidade real de código, não por acoplamento evitável; US4/US5 são deliberadamente independentes entre si)
