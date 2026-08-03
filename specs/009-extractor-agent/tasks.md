---

description: "Task list template for feature implementation"
---

# Tasks: Extractor Agent (SPEC-009)

**Input**: Design documents from `/specs/009-extractor-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/extractor_agent.md, quickstart.md

**Tests**: Incluídos e obrigatórios — o Princípio IX da constituição exige que os testes sejam escritos e confirmados como falhos antes de qualquer código de implementação, incluindo um teste com `FunctionModel` que força uma falha de validação na primeira tentativa para comprovar o loop de reparo.

**Organization**: Tarefas agrupadas por user story do spec.md, permitindo implementação e teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: A qual user story esta tarefa pertence (US1-US5)
- Caminhos de arquivo exatos incluídos em cada descrição

## Path Conventions

Projeto único: `src/pix_compliance/agents/extractor_agent.py` (novo módulo, mesmo pacote da SPEC-008), `skills/extractor-skill/` (novo), `tests/` na raiz do repositório (conforme `plan.md`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar dependências e esqueleto antes de qualquer código de extração/agente

- [X] T001 Adicionar `pdfplumber` às dependências de `pyproject.toml` (seção `[project.dependencies]`) e sincronizar `requirements.txt` — `beautifulsoup4` já existe desde a SPEC-007
- [X] T002 [P] Criar `skills/extractor-skill/` com um `SKILL.md` placeholder (preenchido de fato na User Story 5)

**Checkpoint**: Dependências instaláveis, esqueleto de skill criado.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contratos de dados e seleção de modelo que TODAS as user stories dependem

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase estar completa

- [X] T003 Definir `ExtractorAgentDeps` (`dataclass`: `object_store: ObjectStore`) em `src/pix_compliance/agents/extractor_agent.py`, conforme `data-model.md`
- [X] T004 [P] Definir as exceções `PdfExtractionError` e `ValidationRepairExhaustedError` em `src/pix_compliance/agents/extractor_agent.py`, conforme `data-model.md`
- [X] T005 Implementar a função privada de seleção de modelo (`_build_model(settings) -> Model`, mesmo padrão de dispatch já estabelecido em `scraper_agent.py`/SPEC-008: `AnthropicModel`/`AsyncAnthropicBedrock` para `"bedrock"`, `TestModel`/`FunctionModel` para `"offline"`) em `src/pix_compliance/agents/extractor_agent.py`

**Checkpoint**: Contratos de dados e seleção de modelo prontos; nenhuma extração/agente ainda.

---

## Phase 3: User Story 1 - Documento bruto vira NormativoItem validado (Priority: P1) 🎯 MVP

**Goal**: Extração determinística (PDF/HTML) seguida de estruturação via LLM produz um `NormativoItem` validado para os documentos mock

**Independent Test**: Rodar o agente contra cada um dos 3+ documentos mock (persistidos no ObjectStore) e verificar que cada um produz um `NormativoItem` válido

### Tests for User Story 1 ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação (Princípio IX)

- [X] T006 [P] [US1] Teste: `extract_pdf_text` sobre cada documento PDF de `fixtures/documents/` (SPEC-003) retorna texto não vazio contendo marcadores esperados (ex. "Art. 1"), em `tests/test_extractor_agent.py`
- [X] T007 [P] [US1] Teste: `extract_html_text` sobre cada documento HTML de `fixtures/documents/` retorna texto não vazio equivalente em conteúdo ao PDF correspondente, em `tests/test_extractor_agent.py`
- [X] T008 [P] [US1] Teste: `run_extractor_agent(...)`, com um `FunctionModel` determinístico retornando dados bem formados, produz um `NormativoItem` válido para cada um dos 3+ documentos mock (PDF e HTML) persistidos no `ObjectStore`, em `tests/test_extractor_agent.py`
- [X] T009 [US1] Rodar `pytest tests/test_extractor_agent.py -k "extract_pdf_text or extract_html_text or mock_documents" -q`, confirmando que os testes FALHAM por ausência de `extractor_agent.py` (nenhuma implementação ainda) — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ModuleNotFoundError`/`ImportError` (16/16 falhando)

### Implementation for User Story 1

- [X] T010 [P] [US1] Implementar `extract_pdf_text(data: bytes) -> str` (via `pdfplumber`, caminho feliz — tratamento de corrupção fica para a User Story 4) em `src/pix_compliance/agents/extractor_agent.py`
- [X] T011 [P] [US1] Implementar `extract_html_text(data: bytes) -> str` (via `BeautifulSoup`/`html.parser`) em `src/pix_compliance/agents/extractor_agent.py`
- [X] T012 [US1] Implementar `build_extractor_agent(settings, model=None) -> Agent[ExtractorAgentDeps, NormativoItem]` (`deps_type=ExtractorAgentDeps`, `output_type=NormativoItem`, `retries={"output": 0}`) em `src/pix_compliance/agents/extractor_agent.py` (depende de T003, T005)
- [X] T013 [US1] Implementar `run_extractor_agent(settings, object_store, object_store_key, content_type, model=None) -> NormativoItem` (lê o documento do ObjectStore, despacha extração por `content_type`, chama `agent.run_sync` uma única vez — guardrail e loop de reparo adicionados nas User Stories 2/3) e o CLI (`if __name__ == "__main__":`) em `src/pix_compliance/agents/extractor_agent.py` (depende de T010, T011, T012)
- [X] T014 [US1] Rodar novamente `pytest tests/test_extractor_agent.py -k "extract_pdf_text or extract_html_text or mock_documents" -q` e confirmar que os testes de T006-T008 agora PASSAM — 16/16 passando

**Checkpoint**: User Story 1 completa e testável de forma independente — conversão básica de documento em `NormativoItem` funciona (SC-001).

---

## Phase 4: User Story 2 - Todo texto extraído passa por `guard()` antes do LLM (Priority: P1) 🎯 MVP

**Goal**: `guard()` (SPEC-004) é invocado sobre o texto extraído, para todo documento, antes de qualquer chamada ao LLM

**Independent Test**: Instrumentar/observar a chamada a `guard()` durante o processamento do documento mock com PII plantada, confirmando que ocorre antes de qualquer chamada ao provider de LLM, e que o `NormativoItem` resultante não expõe o valor original da PII

### Tests for User Story 2 ⚠️

> Escrever este teste primeiro; deve FALHAR antes da implementação (Princípio IX)

- [X] T015 [P] [US2] Teste: com o documento mock de PII plantada (`normativo-100-2020-pii`, SPEC-003), `guard()` é invocado (via `monkeypatch`/spy sobre `pix_compliance.agents.extractor_agent.guard`) sobre o texto extraído antes de `agent.run_sync` (comprovado ecoando o prompt recebido pelo `FunctionModel` de volta no campo `texto`), e o resultado contém o texto mascarado, nunca o bruto, em `tests/test_extractor_agent.py`
- [X] T016 [US2] Rodar `pytest tests/test_extractor_agent.py -k guard_is_called -q`, confirmando que o teste FALHA porque `guard()` ainda não está conectado a `run_extractor_agent` — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `AttributeError` (módulo ainda não expõe `guard`)

### Implementation for User Story 2

- [X] T017 [US2] Conectar `guard()` em `run_extractor_agent`: o texto extraído passa por `guard()` antes de compor o prompt enviado ao LLM, usando `texto_mascarado` em ambas as tentativas do loop de reparo (ainda de tentativa única nesta story) em `src/pix_compliance/agents/extractor_agent.py` (depende de T013)
- [X] T018 [US2] Rodar novamente `pytest tests/test_extractor_agent.py -k guard_is_called -q` e confirmar que o teste de T015 agora PASSA — 1/1 passando

**Checkpoint**: User Story 2 completa e testável de forma independente — guardrail obrigatório antes do LLM, verificado por teste.

---

## Phase 5: User Story 3 - Loop de reparo de validação aciona na falha e para na segunda tentativa (Priority: P1) 🎯 MVP

**Goal**: Falha de validação Pydantic na primeira tentativa aciona uma segunda tentativa com a mensagem de erro do Pydantic; o loop nunca excede duas tentativas

**Independent Test**: Com um `FunctionModel` que retorna dado inválido na primeira chamada e válido na segunda, confirmar que a segunda tentativa recebe a mensagem de erro Pydantic da primeira, que o `NormativoItem` final é válido, e que nenhuma terceira tentativa é feita

### Tests for User Story 3 ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação (Princípio IX)

- [X] T019 [P] [US3] Teste: `FunctionModel` retorna dado inválido na 1ª chamada e válido na 2ª — `run_extractor_agent` produz um `NormativoItem` válido, a 2ª chamada ao modelo inclui a mensagem de erro Pydantic da 1ª, e o log estruturado registra as duas tentativas (`tentativa`, `motivo`, `sucesso`), em `tests/test_extractor_agent.py`
- [X] T020 [P] [US3] Teste: `FunctionModel` retorna dado inválido nas duas chamadas — `run_extractor_agent` levanta `ValidationRepairExhaustedError`, e o modelo é chamado exatamente duas vezes, nunca uma terceira, em `tests/test_extractor_agent.py`
- [X] T021 [US3] Rodar `pytest tests/test_extractor_agent.py -k validation_repair -q`, confirmando que os testes FALHAM porque o loop de reparo ainda não está implementado (`run_extractor_agent` ainda faz apenas uma tentativa) — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `UnexpectedModelBehavior` propagada crua (sem loop de reparo/exceção tipada ainda)

### Implementation for User Story 3

- [X] T022 [US3] Implementar o loop de reparo de validação em `run_extractor_agent`: tentativa 1 via `agent.run_sync`; em `UnexpectedModelBehavior` (validação Pydantic falhou), log estruturado (`tentativa=1`, `motivo=<erro>`, `sucesso=False`) e tentativa 2 com um novo prompt incluindo a mensagem de erro Pydantic; em sucesso, log (`sucesso=True`) e retorno; em nova falha, log e `raise ValidationRepairExhaustedError` — nunca uma terceira tentativa, em `src/pix_compliance/agents/extractor_agent.py` (depende de T017)
- [X] T023 [US3] Rodar novamente `pytest tests/test_extractor_agent.py -k validation_repair -q` e confirmar que os testes de T019-T020 agora PASSAM — 2/2 passando

**Checkpoint**: User Story 3 completa e testável de forma independente — loop de reparo de validação demonstrável e instrumentado (SC-003).

---

## Phase 6: User Story 4 - PDF corrompido produz erro tratado e tipado (Priority: P2)

**Goal**: Um PDF malformado/corrompido levanta uma exceção própria do projeto, tipada — nunca a exceção crua de `pdfplumber`, nunca uma falha não controlada

**Independent Test**: Submeter um PDF deliberadamente corrompido/malformado a `extract_pdf_text` e verificar que `PdfExtractionError` é levantada

### Tests for User Story 4 ⚠️

> Escrever este teste primeiro; deve FALHAR antes da implementação (Princípio IX)

- [X] T024 [P] [US4] Teste: `extract_pdf_text` sobre bytes de um PDF corrompido/malformado (literal de bytes inválido no próprio teste) levanta `PdfExtractionError`, nunca a exceção crua de `pdfplumber`, em `tests/test_extractor_agent.py`
- [X] T025 [US4] Rodar `pytest tests/test_extractor_agent.py -k corrupted_pdf -q`, confirmando que o teste FALHA porque `extract_pdf_text` ainda propaga a exceção crua de `pdfplumber` (sem tratamento) — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `pdfplumber.utils.exceptions.PdfminerException` propagada crua

### Implementation for User Story 4

- [X] T026 [US4] Envolver a chamada a `pdfplumber` dentro de `extract_pdf_text` em um bloco `try/except Exception`, convertendo qualquer falha em `PdfExtractionError` com mensagem clara (`from exc`) em `src/pix_compliance/agents/extractor_agent.py` (depende de T004, T010)
- [X] T027 [US4] Rodar novamente `pytest tests/test_extractor_agent.py -k corrupted_pdf -q` e confirmar que o teste de T024 agora PASSA — 1/1 passando

**Checkpoint**: User Story 4 completa e testável de forma independente — PDF corrompido tratado (SC-002).

---

## Phase 7: User Story 5 - Documentação da skill segue o formato já estabelecido (Priority: P2)

**Goal**: `skills/extractor-skill/SKILL.md` documenta responsabilidade, ferramentas, input e output, no mesmo formato de `skills/scraper-skill/SKILL.md`

**Independent Test**: Verificar que `skills/extractor-skill/SKILL.md` existe e contém as mesmas quatro seções exigidas

### Tests for User Story 5 ⚠️

> Escrever este teste primeiro; deve FALHAR antes da implementação (Princípio IX)

- [X] T028 [P] [US5] Teste: `skills/extractor-skill/SKILL.md` existe e contém as seções "Responsabilidade", "Ferramentas", "Input" e "Output" (mesmo padrão de verificação já usado para `scraper-skill/SKILL.md`, SPEC-008), em `tests/test_extractor_agent.py`
- [X] T029 [US5] Rodar `pytest tests/test_extractor_agent.py -k skill_md -q`, confirmando que o teste FALHA porque `SKILL.md` ainda é o placeholder de T002 — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `AssertionError` (seção "Responsabilidade" ausente)

### Implementation for User Story 5

- [X] T030 [US5] Escrever `skills/extractor-skill/SKILL.md` completo: responsabilidade (estrutura documento em `NormativoItem`; não categoriza regras nem compara versões), ferramentas (extração determinística de PDF/HTML, `guard()`, LLM apenas para campos ambíguos), input (`object_store_key`, `content_type`) e output (`NormativoItem`), no mesmo formato de `scraper-skill/SKILL.md`
- [X] T031 [US5] Rodar novamente `pytest tests/test_extractor_agent.py -k skill_md -q` e confirmar que o teste de T028 agora PASSA — 1/1 passando

**Checkpoint**: Todas as cinco user stories completas e testáveis de forma independente (SC-001, SC-002, SC-003).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Validação final que atravessa todas as user stories

- [X] T032 [P] Rodar `ruff check src tests` e corrigir eventuais violações introduzidas por esta feature — limpo, sem violações
- [X] T033 Rodar `pytest -q` como checagem final de regressão de toda a suíte do projeto (não apenas os testes desta feature) — 128/128 passando
- [X] T034 [P] Atualizar README com uma nota sobre o Extractor Agent (segundo agente do enxame, extração determinística + LLM apenas para campos ambíguos, guardrail obrigatório, loop de reparo de validação)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: Depende da Setup — BLOQUEIA todas as user stories
- **User Stories (Phase 3-7)**: Todas dependem da conclusão da Foundational
  - US1 (P1) depende apenas da Foundational — nenhuma dependência de outra story
  - US2 (P1) depende da Foundational e de US1 (adiciona `guard()` ao `run_extractor_agent` já existente)
  - US3 (P1) depende da Foundational e de US2 (o loop de reparo envolve a mesma chamada ao LLM que já usa texto mascarado)
  - US4 (P2) depende da Foundational e de US1 (`extract_pdf_text` já existe; esta story adiciona o tratamento de corrupção)
  - US5 (P2) depende apenas da Foundational — documentação, independente de US1-US4
- **Polish (Phase 8)**: Depende de todas as user stories desejadas estarem completas

### User Story Dependencies

- **US1 (P1)**: Depende apenas da Foundational — cria `extract_pdf_text`/`extract_html_text`/`build_extractor_agent`/`run_extractor_agent` (caminho feliz, tentativa única, sem guardrail)
- **US2 (P1)**: Depende da Foundational e de US1 (adiciona `guard()` à função já existente)
- **US3 (P1)**: Depende da Foundational e de US2 (adiciona o loop de reparo sobre a mesma chamada ao LLM já usando texto mascarado)
- **US4 (P2)**: Depende da Foundational e de US1 (`extract_pdf_text` já existe); independente de US2/US3
- **US5 (P2)**: Depende apenas da Foundational — independente de US1-US4

### Within Each User Story

- Testes escritos e confirmados como FALHANDO (passo explícito, Princípio IX) antes da implementação correspondente
- Extração determinística (US1) antes de guardrail (US2) antes de loop de reparo (US3) — cada uma adiciona uma camada à mesma função `run_extractor_agent`
- Tratamento de corrupção de PDF (US4) e documentação (US5) são incrementos independentes sobre a Foundational/US1

### Parallel Opportunities

- T002 (Setup) pode rodar em paralelo com T001
- T003/T004 (Foundational) em paralelo — arquivos/definições independentes
- T006/T007/T008 (testes da US1) em paralelo entre si
- T010/T011 (implementação de extração PDF/HTML da US1) em paralelo entre si
- US4 (Phase 6) e US5 (Phase 7) podem ser trabalhadas em paralelo por desenvolvedores diferentes, assim que US1 estiver completa

---

## Parallel Example: User Story 1

```bash
# Testes da User Story 1 em paralelo:
Task: "Teste extract_pdf_text sobre fixtures/documents/*.pdf em tests/test_extractor_agent.py"
Task: "Teste extract_html_text sobre fixtures/documents/*.html em tests/test_extractor_agent.py"
Task: "Teste run_extractor_agent com FunctionModel bem formado produz NormativoItem válido em tests/test_extractor_agent.py"
```

## Parallel Example: User Story 3

```bash
# Testes da User Story 3 em paralelo:
Task: "Teste FunctionModel inválido→válido comprova loop de reparo em 2 tentativas"
Task: "Teste FunctionModel inválido nas duas chamadas levanta ValidationRepairExhaustedError, nunca 3ª tentativa"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 + 3)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (CRÍTICO — bloqueia todas as stories)
3. Completar Phase 3: User Story 1 (extração + estruturação básica)
4. Completar Phase 4: User Story 2 (guardrail obrigatório)
5. Completar Phase 5: User Story 3 (loop de reparo de validação)
6. **PARAR e VALIDAR**: rodar os Cenários 1, 3 e 4 de `quickstart.md`
7. Este é o MVP real desta feature — as três garantias P1 que tornam a conversão de documento em `NormativoItem` completa, segura (guardrail) e resiliente (loop de reparo)

### Incremental Delivery

1. Setup + Foundational → contratos de dados e seleção de modelo prontos
2. US1 → conversão básica de documento → validar com Cenário 1 de `quickstart.md`
3. US2 → guardrail obrigatório → validar com Cenário 3 de `quickstart.md`
4. US3 → loop de reparo de validação → validar com Cenário 4 de `quickstart.md`
5. US4 → PDF corrompido tratado → validar com Cenário 2 de `quickstart.md`
6. US5 → `SKILL.md` → validar com Cenário 6 de `quickstart.md`
7. Polish → lint, regressão completa, README

---

## Notes

- [P] = arquivos diferentes ou casos de teste independentes, sem dependência bloqueante
- [Story] mapeia cada tarefa à user story correspondente do spec.md
- Testes devem ser escritos e confirmados como falhando antes da implementação correspondente (Princípio IX) — cada story inclui um passo explícito de execução e confirmação de falha antes da tarefa de implementação
- Commitar após cada tarefa ou grupo lógico de tarefas
- Parar em cada checkpoint para validar a story de forma independente
- Evitar: tarefas vagas, conflito de mesmo arquivo sem necessidade, dependências entre stories que quebrem a independência (US2/US3 dependem de US1 por necessidade real — a mesma função `run_extractor_agent` recebe camadas sucessivas —, não por acoplamento evitável; US4/US5 são deliberadamente independentes entre si)
