---

description: "Task list template for feature implementation"
---

# Tasks: Conformance Validator Agent (SPEC-011)

**Input**: Design documents from `/specs/011-conformance-validator-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/conformance_validator_agent.md, quickstart.md

**Tests**: Requeridos pela spec (Princípio IX da constituição — testes escritos e confirmados como falhos antes de qualquer código de implementação, derivados apenas do contrato).

**Organization**: Tarefas agrupadas por user story (spec.md). Todas convergem para o mesmo arquivo de implementação (`conformance_validator_agent.py`) e o mesmo arquivo de teste (`test_conformance.py`, nome exigido explicitamente pela spec), por serem passos pequenos e fortemente relacionados do mesmo fluxo (Princípio III/KISS) — tarefas que tocam o mesmo arquivo NÃO são marcadas `[P]` entre si.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Projeto único: `src/pix_compliance/agents/`, `tests/`, `skills/` na raiz do repositório.

---

## Phase 1: Setup

**Purpose**: Nenhuma dependência nova (research.md, "Resumo de dependências novas").

- [X] T001 Confirmar `fixtures/normativos.json` e `fixtures/EXPECTED_DELTAS.md` presentes e consistentes entre si (`python -c "import json; json.load(open('fixtures/normativos.json'))"`), sem necessidade de regeneração.

**Checkpoint**: Nenhuma ação adicional necessária.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestrutura de teste compartilhada por US1/US2 — precisa existir antes de qualquer teste de user story.

**⚠️ CRITICAL**: Nenhuma tarefa de user story começa antes desta fase completa.

- [X] T002 Criar fixtures em `tests/test_conformance.py`: `settings` (env vars via `monkeypatch`, `LLM_PROVIDER=offline`, mesmo `REQUIRED_ENV` já usado nos demais testes) e, para cada um dos três pares documentados em `fixtures/EXPECTED_DELTAS.md` (100/2020, 101/2021, 102/2022), duas `RegraExtraida` (versão anterior e versão atual) cujo `enunciado` reflita fielmente o conteúdo real de `fixtures/normativos.json` para aquele par (prazo "90 dias" → "180 dias" para os pares 1 e 2; revogação do Inciso II para o par 3) — dados suficientes para o `FunctionModel` de cada teste reconhecer o par pelo conteúdo real (research.md, Decisão 1).
- [X] T003 Escrever `tests/test_conformance.py` com os testes das duas user stories P1 (T006–T009, T013 abaixo) importando `conformance_validator_agent` — que ainda não existe — e **confirmar que a suíte falha por `ModuleNotFoundError`/`ImportError`** antes de prosseguir (checkpoint explícito do Princípio IX).

**Checkpoint**: Fixtures compartilhadas prontas; suíte de teste criada e confirmada como falha por ausência de implementação.

---

## Phase 3: User Story 1 - Classificar corretamente os deltas entre versões conhecidas de um normativo (Priority: P1) 🎯 MVP

**Goal**: `compare_regras` classifica corretamente `alterado`/`revogado` para os três pares documentados, com `delta`/`recomendacao`/`severidade`; `build_conformance_report` agrega tudo com `resumo`/`criticidade_maxima` consistentes.

**Independent Test**: Rodar `compare_regras` sobre cada um dos três pares de `fixtures/EXPECTED_DELTAS.md` e comparar o `status`/`delta` produzido com o documentado.

### Tests for User Story 1 ⚠️

> **NOTE: Escrever estes testes PRIMEIRO, confirmar que FALHAM antes de implementar.**

- [X] T004 [US1] Teste `test_par_100_2020_produz_status_alterado` em `tests/test_conformance.py`: com um `FunctionModel` cuja função de decisão reconhece "90 dias"/"180 dias" no prompt e retorna `status=alterado` com `delta` mencionando a extensão de prazo, `compare_regras(settings, [regra_anterior], [regra_atual], model=function_model)` retorna `status == StatusConformidade.ALTERADO` (Acceptance Scenario 1 da US1).
- [X] T005 [US1] Teste `test_par_101_2021_produz_status_alterado` em `tests/test_conformance.py`: mesmo padrão do T004, para o segundo par documentado como `alterado`.
- [X] T006 [US1] Teste `test_par_102_2022_produz_status_revogado` em `tests/test_conformance.py`: com um `FunctionModel` que reconhece a menção a "revogado"/"Inciso II" no prompt e retorna `status=revogado`, `compare_regras(...)` retorna `status == StatusConformidade.REVOGADO` (Acceptance Scenario 2 da US1).
- [X] T007 [US1] Teste `test_item_alterado_ou_revogado_tem_recomendacao_e_severidade` em `tests/test_conformance.py`: para os `ConformanceItem` retornados nos três pares acima, `recomendacao is not None` e `0.0 <= severidade <= 1.0` (Acceptance Scenario 3 da US1).
- [X] T008 [US1] Teste `test_build_conformance_report_agrega_resumo_e_criticidade_consistentes` em `tests/test_conformance.py`: `build_conformance_report` sobre um corpus pequeno contendo os três pares (mais um caso `novo`, US2) produz um `ConformanceReport` cujo `criticidade_maxima` corresponde ao status de maior severidade presente em `itens`, e cujo `resumo` menciona as contagens reais por status (data-model.md).
- [X] T009 [US1] Confirmar que T004–T008 falham (por `conformance_validator_agent.py` ainda não existir) rodando `pytest tests/test_conformance.py -k "alterado or revogado or agrega_resumo" -q` — checkpoint explícito do Princípio IX antes de prosseguir para a implementação.

### Implementation for User Story 1

- [X] T010 [US1] Implementar `compare_regras(settings, regras_anteriores, regras_atuais, model=None)` em `src/pix_compliance/agents/conformance_validator_agent.py` — caminho com `regras_anteriores` não `None`: monta o `Agent` (mesmo padrão `_build_model(settings)` do Compliance Analyzer, SPEC-010), aplica `guard()` sobre o `enunciado` de cada regra antes do prompt, invoca com `output_type=list[ConformanceItem]`.
- [X] T011 [US1] Implementar `build_conformance_report(settings, report_id, normativos, regras_por_normativo, model=None)` em `src/pix_compliance/agents/conformance_validator_agent.py`: agrupa `NormativoItem` por `numero`, ordena por `versao`, chama `compare_regras` por grupo (atual + anterior imediato, ou `None`), agrega `itens`, calcula `resumo`/`criticidade_maxima` em código (data-model.md, research.md Decisão 3).
- [X] T012 [US1] Rodar `pytest tests/test_conformance.py -k "alterado or revogado or agrega_resumo" -q` e confirmar que T004–T008 agora passam.

**Checkpoint**: User Story 1 completa e testável de forma independente — os três pares documentados classificados corretamente, relatório agregado consistente.

---

## Phase 4: User Story 2 - Normativo sem versão anterior é tratado como coleção inicial, não como erro (Priority: P1)

**Goal**: `compare_regras(settings, None, regras_atuais)` classifica tudo como `novo`, deterministicamente, sem chamar o LLM.

**Independent Test**: Rodar `compare_regras` com `regras_anteriores=None` e verificar `status == novo` para todas as regras, sem exceção.

### Tests for User Story 2 ⚠️

- [X] T013 [US2] Teste `test_compare_regras_sem_versao_anterior_produz_status_novo` em `tests/test_conformance.py`: `compare_regras(settings, None, regras_atuais)` retorna `len(resultado) == len(regras_atuais)`, todos com `status == StatusConformidade.NOVO`, `delta is None`, `recomendacao is None`, sem levantar exceção (Acceptance Scenario da US2, SC-002).
- [X] T014 [US2] Teste `test_compare_regras_sem_versao_anterior_nao_chama_llm` em `tests/test_conformance.py`: passar um `model` cujo `FunctionModel` levanta `AssertionError` se invocado; `compare_regras(settings, None, regras_atuais, model=model_que_falha_se_chamado)` não levanta (prova que o caminho `novo` é 100% determinístico em código, research.md Decisão 4).
- [X] T015 [US2] Confirmar que T013–T014 falham (comportamento ainda não implementado) rodando `pytest tests/test_conformance.py -k sem_versao_anterior -q` — checkpoint do Princípio IX.

### Implementation for User Story 2

- [X] T016 [US2] Implementar o caminho `regras_anteriores is None` em `compare_regras` (`src/pix_compliance/agents/conformance_validator_agent.py`): retorno antecipado com `ConformanceItem(status=novo, delta=None, recomendacao=None, severidade=0.0)` por regra, sem instanciar/chamar o `Agent`.
- [X] T017 [US2] Rodar `pytest tests/test_conformance.py -k sem_versao_anterior -q` e confirmar que T013–T014 passam.

**Checkpoint**: User Stories 1 e 2 completas e testáveis de forma independente.

---

## Phase 5: User Story 3 - Documentação da skill segue o formato já estabelecido (Priority: P2)

**Goal**: `skills/conformance-validator-skill/SKILL.md` documenta responsabilidade, ferramentas, input e output, no formato já usado pelas skills anteriores.

**Independent Test**: Verificar que o arquivo existe e contém as quatro seções exigidas.

### Tests for User Story 3 ⚠️

- [X] T018 [P] [US3] Teste `test_skill_md_segue_formato_estabelecido` em `tests/test_conformance.py`: `skills/conformance-validator-skill/SKILL.md` existe e contém as seções de responsabilidade/ferramentas/input/output (Acceptance Scenario da US3).
- [X] T019 [P] [US3] Confirmar que T018 falha (arquivo ainda não existe) rodando `pytest tests/test_conformance.py -k skill_md -q`.

### Implementation for User Story 3

- [X] T020 [US3] Criar `skills/conformance-validator-skill/SKILL.md` seguindo o formato de quatro seções já usado por `skills/compliance-analyzer-skill/SKILL.md` — incluindo o porquê do diff ser semântico e por que "sem versão anterior" não é um erro.
- [X] T021 [P] [US3] Rodar `pytest tests/test_conformance.py -k skill_md -q` e confirmar que T018 passa.

**Checkpoint**: Todas as user stories completas e independentemente testáveis.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: CLI, documentação de projeto e validação fim-a-fim.

- [X] T022 Adicionar bloco `if __name__ == "__main__":` (CLI) em `src/pix_compliance/agents/conformance_validator_agent.py`, conforme contracts/conformance_validator_agent.md.
- [X] T023 [P] Adicionar seção "Conformance Validator Agent" ao `README.md`, incluindo nota explícita sobre a pendência de revisão do `report_consolidator_agent.py` (SPEC-014) para consumir o `ConformanceReport` real produzido por esta feature (fora do escopo desta spec, mas registrada como ação de acompanhamento).
- [X] T024 [P] Confirmar que nenhuma variável de ambiente nova é necessária em `.env.example` (research.md: nenhuma dependência nova).
- [X] T025 Rodar `pytest tests/test_conformance.py -q` (suíte completa da feature, SC-003) e confirmar todos os testes passam.
- [X] T026 Rodar `pytest -q` (regressão completa do projeto) e `ruff check` e confirmar que ambos passam sem erros.
- [X] T027 Validar `quickstart.md` executando os 4 cenários documentados e confirmar que todos correspondem ao resultado esperado.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente.
- **Foundational (Phase 2)**: Depende do Setup — bloqueia todas as user stories.
- **US1 (Phase 3)**: Depende do Foundational. Conceitualmente independente de US2/US3.
- **US2 (Phase 4)**: Depende do Foundational; independente de US1 (o caminho `None` de `compare_regras` não depende do caminho via LLM já implementado).
- **US3 (Phase 5)**: Independente de US1/US2 — pode ser feita em paralelo a qualquer momento após o Foundational.
- **Polish (Phase 6)**: Depende de todas as user stories completas.

### Within Each User Story

- Testes escritos e confirmados como falhos antes da implementação correspondente (Princípio IX).
- `compare_regras` (caminho via LLM, T010) antes de `build_conformance_report` (T011), que depende de `compare_regras` já existir.
- O caminho `None` de `compare_regras` (T016, US2) é uma ramificação da mesma função implementada em T010 (US1) — a ordem entre as duas fases pode ser invertida sem problema, já que são `if`/`else` independentes dentro da mesma função.

### Parallel Opportunities

- T018/T019/T021 (US3) podem rodar em paralelo às demais phases após o Foundational.
- T023/T024 (Polish, arquivos/verificações distintos) podem rodar em paralelo entre si.
- Dentro de US1/US2, as tarefas tocam o mesmo arquivo de teste/implementação e por isso NÃO são marcadas `[P]` entre si.

---

## Parallel Example: User Story 3 (independente das demais)

```bash
Task: "Teste test_skill_md_segue_formato_estabelecido em tests/test_conformance.py"
Task: "Criar skills/conformance-validator-skill/SKILL.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup.
2. Completar Phase 2: Foundational.
3. Completar Phase 3: User Story 1 — classificação correta dos três pares documentados já é o critério de aceite mais forte da spec, independentemente validável.
4. **PARAR e VALIDAR**: rodar os testes da US1 isoladamente.

### Incremental Delivery

1. Setup + Foundational → base pronta.
2. US1 → validar independentemente (MVP: classificação correta contra `EXPECTED_DELTAS.md`).
3. US2 → validar independentemente (sem versão anterior → `novo`).
4. US3 → documentação da skill (pode ser feita a qualquer momento após o Foundational).
5. Polish → CLI, README (com a nota de pendência do Report Consolidator), regressão completa, lint.

## Notes

- [P] = arquivos/verificações diferentes, sem dependência entre si.
- [Story] mapeia a tarefa à user story correspondente da spec.md.
- Confirmar que os testes falham antes de implementar (Princípio IX) — checkpoints explícitos em T003, T009, T015, T019.
- Rodar `pytest -q` e `ruff check` completos antes de considerar a feature encerrada (T026).
- A revisão de `report_consolidator_agent.py` (SPEC-014) para consumir o `ConformanceReport` real **não** é uma tarefa desta lista — é uma pendência registrada (spec.md, Assumptions; quickstart.md) para uma spec/tarefa futura própria.
