---

description: "Task list template for feature implementation"
---

# Tasks: Report Consolidator Agent (SPEC-014)

**Input**: Design documents from `/specs/014-report-consolidator-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/report_consolidator_agent.md, quickstart.md

**Tests**: Requeridos pela spec (Princípio IX da constituição — testes escritos e confirmados como falhos antes de qualquer código de implementação, derivados apenas do contrato, incluindo o teste de degradação controlada com API indisponível).

**Organization**: Tarefas agrupadas por user story (spec.md). Todas convergem para o mesmo arquivo de implementação (`report_consolidator_agent.py`) e o mesmo arquivo de teste (`test_report_consolidator_agent.py`), por serem passos pequenos e fortemente relacionados do mesmo fluxo (Princípio III/KISS) — tarefas que tocam o mesmo arquivo NÃO são marcadas `[P]` entre si.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Projeto único: `src/pix_compliance/agents/`, `tests/`, `skills/` na raiz do repositório.

---

## Phase 1: Setup

**Purpose**: Nenhuma dependência nova (`reportlab`/`httpx` já declarados em `pyproject.toml`, SPEC-001; `httpx.MockTransport` já é parte de `httpx` — research.md, Decisão 1).

- [X] T001 Confirmar `reportlab>=4.0` e `httpx>=0.27` instalados (`pip show reportlab httpx`) e `httpx.MockTransport`/`httpx.TransportError`/`httpx.ConnectError` disponíveis na versão instalada (já verificado nesta sessão: `httpx==0.28.1`).

**Checkpoint**: Nenhuma instalação adicional necessária.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestrutura de teste compartilhada por US1/US2/US3 — precisa existir antes de qualquer teste de user story.

**⚠️ CRITICAL**: Nenhuma tarefa de user story começa antes desta fase completa.

- [X] T002 Criar fixtures em `tests/test_report_consolidator_agent.py`: um `ConformanceReport` (com `itens: list[ConformanceItem]` cobrindo ao menos um status de gap e um `severidade` alto), uma `list[NormativoItem]` (reaproveitando o corpus de `fixtures/normativos.json` ou construído inline, como em `tests/test_knowledge_builder_agent.py`) e uma `list[RegraExtraida]` correspondente com mais de uma `categoria` — dados suficientes para exercitar as cinco seções do PDF (FR-002).
- [X] T003 Criar fixture `settings` (env vars via `monkeypatch`, mesmo `REQUIRED_ENV` já usado nos demais testes) e uma fixture de diretório de saída local isolado (`tmp_path`, para não colidir `reports/<report_id>.*` entre execuções de teste).
- [X] T004 Escrever `tests/test_report_consolidator_agent.py` com os testes das três user stories (T007–T009, T012–T013, T016 abaixo) importando `report_consolidator_agent` — que ainda não existe — e **confirmar que a suíte falha por `ModuleNotFoundError`/`ImportError`** antes de prosseguir (checkpoint explícito do Princípio IX).

**Checkpoint**: Fixtures compartilhadas prontas; suíte de teste criada e confirmada como falha por ausência de implementação.

---

## Phase 3: User Story 1 - Gerar o relatório final em JSON e PDF a partir do corpus completo (Priority: P1) 🎯 MVP

**Goal**: `generate_json`/`generate_pdf` produzem os dois artefatos a partir de `ConformanceReport` + `NormativoItem`/`RegraExtraida`; `upload_artifacts` envia ambos ao `ObjectStore`.

**Independent Test**: Rodar `generate_json`/`generate_pdf` sobre o corpus completo de fixtures e verificar que os dois artefatos existem e têm a estrutura esperada.

### Tests for User Story 1 ⚠️

> **NOTE: Escrever estes testes PRIMEIRO, confirmar que FALHAM antes de implementar.**

- [X] T005 [US1] Teste `test_generate_json_produz_report_output_correto` em `tests/test_report_consolidator_agent.py`: `generate_json(report, normativos, regras)` retorna um `ReportOutput` com `total_normativos`/`total_regras`/`total_gaps` corretos, `gerado_em == report.gerado_em`, e grava um arquivo JSON local em `reports/<report_id>.json` (data-model.md, convenção de nome determinístico) (Acceptance Scenario 1 da US1).
- [X] T006 [US1] Teste `test_generate_pdf_contem_cinco_secoes_obrigatorias` em `tests/test_report_consolidator_agent.py`: `generate_pdf(report, normativos, regras, output_path)` grava um PDF válido em `output_path`, e o texto extraído do PDF (via `pdfplumber`, já dependência do projeto desde a SPEC-009) contém marcadores das cinco seções: capa (`report_id`), sumário executivo (`report.resumo`), tabela de normativos (título de ao menos um `NormativoItem`), regras por categoria (`enunciado` de ao menos uma `RegraExtraida`), gap analysis (`regra_id` de ao menos um `ConformanceItem`) (Acceptance Scenario 2 da US1, SC-001).
- [X] T007 [US1] Teste `test_upload_artifacts_envia_json_e_pdf_ao_object_store` em `tests/test_report_consolidator_agent.py`: após `generate_json`/`generate_pdf`, `upload_artifacts(object_store, json_path, pdf_path, report_id)` grava ambos os artefatos no `ObjectStore` (SPEC-006) sob as chaves `reports/<report_id>.json`/`reports/<report_id>.pdf`, recuperáveis via `object_store.download(...)`.
- [X] T008 [US1] Confirmar que T005–T007 falham (por `report_consolidator_agent.py` ainda não existir) rodando `pytest tests/test_report_consolidator_agent.py -k "generate_json or generate_pdf or upload_artifacts" -q` — checkpoint explícito do Princípio IX antes de prosseguir para a implementação.

### Implementation for User Story 1

- [X] T009 [US1] Implementar `generate_json(report, normativos, regras) -> ReportOutput` em `src/pix_compliance/agents/report_consolidator_agent.py`: monta `ReportOutput` (contagens a partir das listas recebidas), grava JSON em `reports/<report_id>.json` (`Path.write_text`, criando o diretório se necessário).
- [X] T010 [US1] Implementar `generate_pdf(report, normativos, regras, output_path)` em `src/pix_compliance/agents/report_consolidator_agent.py` via `reportlab` (`SimpleDocTemplate`/`Table`/`Paragraph`), com as cinco seções obrigatórias (data-model.md).
- [X] T011 [US1] Implementar `upload_artifacts(object_store, json_path, pdf_path, report_id)` em `src/pix_compliance/agents/report_consolidator_agent.py`: lê os bytes dos dois arquivos locais e chama `object_store.upload(...)` para cada um.
- [X] T012 [US1] Rodar `pytest tests/test_report_consolidator_agent.py -k "generate_json or generate_pdf or upload_artifacts" -q` e confirmar que T005–T007 agora passam.

**Checkpoint**: User Story 1 completa e testável de forma independente — JSON/PDF gerados corretamente e enviados ao `ObjectStore`.

---

## Phase 4: User Story 2 - Publicar o resultado consolidado na API FastAPI (Priority: P1)

**Goal**: `publish_to_api` faz uma requisição HTTP para `settings.api_url` — nunca um literal hardcoded — cumprindo o requisito nominal do desafio original.

**Independent Test**: Configurar `settings.api_url`, chamar `publish_to_api` com um `httpx.MockTransport`, e verificar que a requisição foi enviada para essa URL.

### Tests for User Story 2 ⚠️

- [X] T013 [US2] Teste `test_publish_to_api_usa_url_de_settings` em `tests/test_report_consolidator_agent.py`: com um `httpx.Client(base_url=settings.api_url, transport=httpx.MockTransport(handler))`, `publish_to_api(settings, report_output, client=client)` faz uma requisição cuja URL final começa com `settings.api_url` (capturada pelo `handler` do `MockTransport`) (Acceptance Scenario 1 da US2, SC-003).
- [X] T014 [US2] Teste estrutural `test_nenhum_literal_de_url_no_codigo_fonte` em `tests/test_report_consolidator_agent.py`: parse do AST de `src/pix_compliance/agents/report_consolidator_agent.py` confirmando que nenhuma string literal contendo `http://`/`https://` aparece no módulo — mesmo padrão de `tests/test_llm_provider_offline.py::test_no_module_in_src_imports_tests_doubles_at_module_level` (Acceptance Scenario 2 da US2, FR-005).
- [X] T015 [US2] Confirmar que T013–T014 falham (função `publish_to_api` ainda não existe) rodando `pytest tests/test_report_consolidator_agent.py -k "publish_to_api or literal_de_url" -q` — checkpoint do Princípio IX.

### Implementation for User Story 2

- [X] T016 [US2] Implementar `publish_to_api(settings, report_output, client=None)` em `src/pix_compliance/agents/report_consolidator_agent.py`: constrói `httpx.Client(base_url=settings.api_url)` se `client` não for passado, faz `POST` do `report_output.model_dump(mode="json")`, chama `response.raise_for_status()` (sem capturar erros de aplicação nesta tarefa — apenas o caminho feliz).
- [X] T017 [US2] Rodar `pytest tests/test_report_consolidator_agent.py -k "publish_to_api or literal_de_url" -q` e confirmar que T013–T014 passam.

**Checkpoint**: User Stories 1 e 2 funcionam de forma independente — artefatos gerados e publicação HTTP usando exclusivamente a URL de `settings`.

---

## Phase 5: User Story 3 - Degradação controlada quando a API está indisponível (Priority: P1)

**Goal**: Falha de conexão ao publicar não derruba o fluxo nem descarta os artefatos já gerados — apenas loga o erro de forma clara.

**Independent Test**: Simular `httpx.ConnectError` via `httpx.MockTransport` e verificar que nenhuma exceção é levantada, os artefatos locais permanecem, e um log de erro estruturado é emitido.

### Tests for User Story 3 ⚠️

- [X] T018 [US3] Teste `test_publish_to_api_degrada_controladamente_quando_api_indisponivel` em `tests/test_report_consolidator_agent.py`: com um `httpx.MockTransport` cujo `handler` levanta `httpx.ConnectError`, `publish_to_api(settings, report_output, client=client)` retorna normalmente (não levanta exceção), e um log estruturado de erro é emitido (`structlog.testing.capture_logs()`, mesmo padrão já usado em SPEC-004/SPEC-008) contendo o `report_id` (Acceptance Scenario da US3, SC-002).
- [X] T019 [US3] Teste `test_consolidate_and_publish_preserva_artefatos_quando_api_indisponivel` em `tests/test_report_consolidator_agent.py`: `consolidate_and_publish(settings, object_store, report, normativos, regras, client=client_com_erro_de_conexao)` retorna um `ReportOutput` válido, e os arquivos locais (`reports/<report_id>.json`/`.pdf`) e as cópias no `ObjectStore` permanecem intactos após a chamada (edge case de spec.md: trabalho de geração não é perdido).
- [X] T020 [US3] Confirmar que T018–T019 falham (comportamento de degradação ainda não implementado) rodando `pytest tests/test_report_consolidator_agent.py -k "degrada or preserva_artefatos" -q` — checkpoint do Princípio IX.

### Implementation for User Story 3

- [X] T021 [US3] Ajustar `publish_to_api` em `src/pix_compliance/agents/report_consolidator_agent.py`: capturar `httpx.TransportError` ao redor da chamada de rede, logar erro estruturado (`structlog`, incluindo `report_id`) e retornar sem levantar — nunca capturar exceções de `response.raise_for_status()` da mesma forma (research.md, Decisão 4).
- [X] T022 [US3] Implementar `consolidate_and_publish(settings, object_store, report, normativos, regras, client=None) -> ReportOutput` em `src/pix_compliance/agents/report_consolidator_agent.py`, orquestrando nesta ordem: `generate_json` → `generate_pdf` → `upload_artifacts` → `publish_to_api` (a falha de `publish_to_api` não interrompe o retorno do `ReportOutput`, por já não levantar).
- [X] T023 [US3] Rodar `pytest tests/test_report_consolidator_agent.py -k "degrada or preserva_artefatos" -q` e confirmar que T018–T019 passam.

**Checkpoint**: Todas as user stories completas e independentemente testáveis — geração, publicação e degradação controlada.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: CLI, skill, documentação de projeto e validação fim-a-fim.

- [X] T024 Criar `skills/report-consolidator-skill/SKILL.md` seguindo o formato de quatro seções já usado por `skills/knowledge-builder-skill/SKILL.md` — incluindo uma menção explícita de que este agente cumpre o requisito literal da seção 2 do desafio original ("invocar uma API FastAPI como cliente HTTP para ação final"), conforme exigido por FR-007.
- [X] T025 [P] Teste `test_skill_md_menciona_requisito_do_desafio` em `tests/test_report_consolidator_agent.py`: `skills/report-consolidator-skill/SKILL.md` existe, segue o formato de quatro seções, e menciona explicitamente "API FastAPI" e "cliente HTTP".
- [X] T026 Adicionar bloco `if __name__ == "__main__":` (CLI) em `src/pix_compliance/agents/report_consolidator_agent.py`, conforme contracts/report_consolidator_agent.md.
- [X] T027 [P] Adicionar seção "Report Consolidator Agent" ao `README.md`, documentando explicitamente a conexão entre este agente e o requisito literal do desafio original (mesma exigência das Notas de implementação da spec).
- [X] T028 [P] Confirmar que nenhuma variável de ambiente nova é necessária em `.env.example` — `settings.api_url` já existe desde a SPEC-001 (research.md).
- [X] T029 Rodar `pytest tests/test_report_consolidator_agent.py -q` (suíte completa da feature) e confirmar todos os testes passam.
- [X] T030 Rodar `pytest -q` (regressão completa do projeto) e `ruff check` e confirmar que ambos passam sem erros.
- [X] T031 Validar `quickstart.md` executando os 6 cenários documentados e confirmar que todos correspondem ao resultado esperado.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente.
- **Foundational (Phase 2)**: Depende do Setup — bloqueia todas as user stories.
- **US1 (Phase 3)**: Depende do Foundational. Conceitualmente independente de US2/US3.
- **US2 (Phase 4)**: Depende do Foundational; não depende de US1 (`publish_to_api` recebe um `ReportOutput` construído diretamente no teste, sem precisar de `generate_json` real).
- **US3 (Phase 5)**: Depende de US2 (`publish_to_api` já existir) — adiciona o tratamento de erro à mesma função, e `consolidate_and_publish` (T022) depende de US1 (`generate_json`/`generate_pdf`/`upload_artifacts`) e US2 (`publish_to_api`) já implementadas.
- **Polish (Phase 6)**: Depende de todas as user stories completas.

### Within Each User Story

- Testes escritos e confirmados como falhos antes da implementação correspondente (Princípio IX).
- `generate_json`/`generate_pdf` (T009/T010) antes de `upload_artifacts` (T011), que depende dos arquivos locais existirem.
- `publish_to_api` caminho feliz (T016, US2) antes do tratamento de erro (T021, US3) na mesma função.
- `consolidate_and_publish` (T022) depende de todas as funções das três user stories já existirem.

### Parallel Opportunities

- T025/T027/T028 (Polish, arquivos/verificações distintos) podem rodar em paralelo entre si.
- Dentro de US1/US2/US3, as tarefas tocam o mesmo arquivo de teste/implementação e por isso NÃO são marcadas `[P]` entre si.

---

## Parallel Example: Polish

```bash
Task: "Teste test_skill_md_menciona_requisito_do_desafio em tests/test_report_consolidator_agent.py"
Task: "Adicionar seção Report Consolidator Agent ao README.md"
Task: "Confirmar que nenhuma variável de ambiente nova é necessária em .env.example"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup (já verificado).
2. Completar Phase 2: Foundational.
3. Completar Phase 3: User Story 1 — JSON/PDF gerados corretamente já é uma entrega independentemente validável.
4. **PARAR e VALIDAR**: rodar os testes da US1 isoladamente.

### Incremental Delivery

1. Setup + Foundational → base pronta.
2. US1 → validar independentemente (MVP: geração de artefatos).
3. US2 → validar independentemente (publicação HTTP usando `settings.api_url`).
4. US3 → validar independentemente (degradação controlada) — depende de US2 já existir.
5. Polish → CLI, `SKILL.md`, README, regressão completa, lint.

## Notes

- [P] = arquivos/verificações diferentes, sem dependência entre si.
- [Story] mapeia a tarefa à user story correspondente da spec.md.
- Confirmar que os testes falham antes de implementar (Princípio IX) — checkpoints explícitos em T004, T008, T015, T020.
- Rodar `pytest -q` e `ruff check` completos antes de considerar a feature encerrada (T030).
