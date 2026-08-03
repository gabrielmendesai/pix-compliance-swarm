---

description: "Task list template for feature implementation"
---

# Tasks: Scraper Agent (SPEC-008)

**Input**: Design documents from `/specs/008-scraper-agent/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/scraper_agent.md, quickstart.md

**Tests**: Incluídos e obrigatórios — o Princípio IX da constituição exige que os testes deste agente sejam escritos e confirmados como falhos antes de qualquer código de implementação, incluindo uma fixture de `pytest` que sobe e derruba o servidor MCP da SPEC-007 programaticamente.

**Organization**: Tarefas agrupadas por user story do spec.md, permitindo implementação e teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: A qual user story esta tarefa pertence (US1, US2, US3)
- Caminhos de arquivo exatos incluídos em cada descrição

## Path Conventions

Projeto único: `src/pix_compliance/agents/` (novo pacote), `src/pix_compliance/models.py` (já existente), `skills/scraper-skill/` (novo), `tests/` na raiz do repositório (conforme `plan.md`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar dependências e esqueleto dos pacotes antes de qualquer código do agente

- [X] T001 Adicionar `pydantic-ai-slim[mcp]` (extra `mcp`, traz o cliente `fastmcp` exigido por `MCPToolset`) às dependências de `pyproject.toml` (substituindo/complementando `pydantic-ai-slim[bedrock]` já existente) e sincronizar `requirements.txt` — combinado como `pydantic-ai-slim[bedrock,mcp]`
- [X] T002 [P] Criar o esqueleto do pacote `src/pix_compliance/agents/` (`__init__.py`) — primeiro agente do enxame, pacote reaproveitado pelos seis seguintes
- [X] T003 [P] Criar `skills/scraper-skill/` com um `SKILL.md` placeholder (preenchido de fato na User Story 3)

**Checkpoint**: Dependências instaláveis, pacotes criados.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contratos de dados e seleção de modelo que TODAS as user stories dependem

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase estar completa

- [X] T004 Adicionar o modelo Pydantic `ScrapeResult` (`documentos: list[RawDocument]`, `total_coletado: int`, `executado_em: datetime`; `ConfigDict(extra="forbid")`) a `src/pix_compliance/models.py`, e incluí-lo na tupla `MODELOS_PUBLICOS`, conforme `data-model.md`
- [X] T005 [P] Teste: `ScrapeResult` valida e serializa corretamente (round-trip `model_dump`/`model_validate`, e rejeita campo extra) em `tests/test_models.py` (nova classe `TestScrapeResult`, mesmo padrão das demais classes do arquivo)
- [X] T006 Rodar `pytest tests/test_models.py -q` (inclui `TestJsonSchemaExport`, que gera/atualiza `docs/schemas/ScrapeResult.schema.json` automaticamente) e confirmar ausência de divergência de schema — 30/30 passando, `docs/schemas/ScrapeResult.schema.json` gerado
- [X] T007 [P] Definir `ScraperAgentDeps` (`dataclass`: `object_store: ObjectStore`) e a hierarquia de exceção `ScraperTransportError` em `src/pix_compliance/agents/scraper_agent.py`, conforme `data-model.md`
- [X] T008 Implementar a função privada de seleção de modelo (`_build_model(settings) -> Model`: `AnthropicModel(settings.bedrock_model_id, provider=AnthropicProvider(anthropic_client=AsyncAnthropicBedrock(...)))` para `settings.llm_provider == "bedrock"`, `TestModel()` para `"offline"`) em `src/pix_compliance/agents/scraper_agent.py` (depende de T007)

**Checkpoint**: Contratos de dados e seleção de modelo prontos; nenhum `Agent`/toolset MCP ainda.

---

## Phase 3: User Story 1 - Agente coleta o corpus do site mock via MCP e devolve resultado validado (Priority: P1) 🎯 MVP

**Goal**: Execução via CLI conecta ao servidor MCP como toolset, decide o que coletar, e devolve um `ScrapeResult` validado, sem lógica de parsing/extração no próprio agente

**Independent Test**: Subir o servidor MCP da SPEC-007 (fixture programática) contra o site mock, executar o agente via CLI, e verificar que o `ScrapeResult` devolvido é válido e reflete os documentos do site mock

### Tests for User Story 1 ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação (Princípio IX)

- [X] T009 [P] [US1] Criar a fixture `running_mcp_server` em `tests/test_scraper_agent.py`, reaproveitando o padrão de `tests/test_scraper_mcp_server.py` (thread + `uvicorn` + `app.sse_app()`, subindo/derrubando o servidor MCP real da SPEC-007 contra uma cópia efêmera do site mock via `mock_bcb_server`) — expõe `.shutdown()` para a User Story 2 derrubar o servidor sob demanda
- [X] T010 [P] [US1] Teste: `run_scraper_agent(...)` com o servidor MCP rodando (`FunctionModel` determinístico decidindo chamar `list_normativos`→`fetch_normativo` para cada item) retorna um `ScrapeResult` válido, com `documentos` refletindo os 4 normativos do site mock e nenhum campo de conteúdo estruturado/extraído, em `tests/test_scraper_agent.py` — validado por spike manual (`agent_spike.py`, descartado) confirmando que `MCPToolset`/`FunctionModel` orquestram corretamente as três ferramentas MCP reais da SPEC-007
- [X] T011 [US1] Rodar `pytest tests/test_scraper_agent.py -k valid_result -q`, confirmando que o teste FALHA por ausência de `scraper_agent.py`/`run_scraper_agent` (nenhuma implementação ainda) — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ImportError`

### Implementation for User Story 1

- [X] T012 [US1] Implementar `build_scraper_agent(settings, mcp_url, model=None) -> Agent[ScraperAgentDeps, ScrapeResult]` (constrói `MCPToolset(client=f"{mcp_url}/sse", read_timeout=5.0, init_timeout=5.0)`, `deps_type=ScraperAgentDeps`, `output_type=ScrapeResult`, modelo via `_build_model` ou override) em `src/pix_compliance/agents/scraper_agent.py` (depende de T004, T007, T008) — parâmetro `model` opcional adicionado ao contrato original para permitir injeção de `FunctionModel`/`TestModel` determinístico em teste, sem depender de `settings.llm_provider`
- [X] T013 [US1] Implementar `run_scraper_agent(settings, mcp_url, object_store, model=None) -> ScrapeResult` (executa `agent.run_sync(...)`) e o entrypoint CLI (`if __name__ == "__main__":`, imprime `ScrapeResult` como JSON) em `src/pix_compliance/agents/scraper_agent.py` (depende de T012)
- [X] T014 [US1] Rodar novamente `pytest tests/test_scraper_agent.py -k valid_result -q` e confirmar que o teste de T010 agora PASSA — 1/1 passando, `ScrapeResult` com 4 documentos refletindo o site mock

**Checkpoint**: User Story 1 completa e testável de forma independente — execução de ponta a ponta via MCP funciona (SC-001).

---

## Phase 4: User Story 2 - Falha de conexão com o servidor MCP produz erro tipado e claro (Priority: P1) 🎯 MVP

**Goal**: Derrubar o servidor MCP durante a execução aciona retry com backoff (distinto do fallback de `model_id` da SPEC-005) e, ao esgotar tentativas, propaga `ScraperTransportError` — nunca um traceback cru

**Independent Test**: Subir o servidor MCP via fixture, iniciar a execução do agente, derrubar o servidor programaticamente no meio da execução, e verificar que o agente levanta `ScraperTransportError`, tipada e com mensagem acionável

### Tests for User Story 2 ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação (Princípio IX)

- [X] T015 [P] [US2] Teste: com o servidor MCP derrubado (via `running_mcp_server.shutdown()`) no meio da execução — depois de `list_normativos` responder, antes de `fetch_normativo` — `run_scraper_agent(...)` levanta `ScraperTransportError` (mensagem incluindo a URL do servidor MCP) após a política de retry se esgotar, em `tests/test_scraper_agent.py`. Confirmado por spike manual (`agent_spike2.py`, descartado) que a exceção real observável é `anyio.ClosedResourceError` (com uma tentativa de reconexão interna do cliente MCP surgindo como `httpx.ConnectError` no log) — o retry deste módulo deve capturar essa combinação
- [X] T016 [US2] Rodar `pytest tests/test_scraper_agent.py -k transport_error -q`, confirmando que o teste FALHA porque a política de retry/exceção tipada ainda não está implementada — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ImportError` (mesmo motivo de T011 — `run_scraper_agent` ainda não existia neste ponto)

### Implementation for User Story 2

- [X] T017 [US2] Envolver a chamada de `agent.run_sync(...)` dentro de `run_scraper_agent` em um laço `tenacity.Retrying` próprio (`retry_if_exception(_is_mcp_transport_failure)`, 3 tentativas, backoff exponencial curto), levantando `ScraperTransportError` (com URL e número de tentativas) ao esgotar, em `src/pix_compliance/agents/scraper_agent.py` (depende de T013) — `_is_mcp_transport_failure` inspeciona tipo e `__cause__` porque a exceção observável variou entre spikes (`anyio.ClosedResourceError` direto, ou `RuntimeError("Client failed to connect: ...")` do `fastmcp` envolvendo um `httpx`/`httpcore.ConnectError`)
- [X] T018 [US2] Rodar novamente `pytest tests/test_scraper_agent.py -k drops_mid_run -q` e confirmar que o teste de T015 agora PASSA — 1/1 passando (nome do teste corrigido de "transport_error" para "drops_mid_run" ao escrever o arquivo real)

**Checkpoint**: User Story 2 completa e testável de forma independente — falha de transporte MCP produz erro tipado (SC-002).

---

## Phase 5: User Story 3 - Documentação da skill estabelece o formato para os demais seis agentes (Priority: P2)

**Goal**: `skills/scraper-skill/SKILL.md` descreve responsabilidade, ferramentas, input e output do Scraper Agent, em formato replicável

**Independent Test**: Verificar que `skills/scraper-skill/SKILL.md` existe e contém as quatro seções exigidas (responsabilidade, ferramentas, input, output), sem depender de nenhuma execução do agente

### Tests for User Story 3 ⚠️

> Escrever este teste primeiro; deve FALHAR antes da implementação (Princípio IX)

- [X] T019 [P] [US3] Teste: `skills/scraper-skill/SKILL.md` existe e contém as seções "Responsabilidade", "Ferramentas", "Input" e "Output" (verificação de presença de cabeçalhos, não de conteúdo semântico), em `tests/test_scraper_agent.py`
- [X] T020 [US3] Rodar `pytest tests/test_scraper_agent.py -k skill_md -q`, confirmando que o teste FALHA porque `SKILL.md` ainda é o placeholder de T003 — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `AssertionError` (seção "Responsabilidade" ausente)

### Implementation for User Story 3

- [X] T021 [US3] Escrever `skills/scraper-skill/SKILL.md` completo: responsabilidade (decide o quê coletar, delega a coleta ao servidor MCP), ferramentas disponíveis (`list_normativos`, `fetch_normativo`, `detect_changes` via MCP), input (nenhum parâmetro de usuário — lê `Settings`) e output (`ScrapeResult`), estabelecendo o formato para os seis agentes seguintes
- [X] T022 [US3] Rodar novamente `pytest tests/test_scraper_agent.py -k skill_md -q` e confirmar que o teste de T019 agora PASSA — 1/1 passando

**Checkpoint**: Todas as três user stories completas e testáveis de forma independente (SC-003).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validação final que atravessa todas as user stories

- [X] T023 [P] Rodar `ruff check src tests` e corrigir eventuais violações introduzidas por esta feature — 7 violações (ordenação de imports, alias `datetime.UTC`) corrigidas via `--fix`; limpo
- [X] T024 Rodar `pytest -q` como checagem final de regressão de toda a suíte do projeto (não apenas os testes desta feature) — 107/107 passando
- [X] T025 [P] Atualizar README com uma nota sobre o Scraper Agent ser o primeiro agente do enxame e o padrão estrutural (`deps_type`, `RunContext`, `output_type`, tratamento de erro de dependência externa) que os seis agentes seguintes reutilizam

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: Depende da Setup — BLOQUEIA todas as user stories
- **User Stories (Phase 3-5)**: Todas dependem da conclusão da Foundational
  - US1 (P1) depende apenas da Foundational — nenhuma dependência de outra story
  - US2 (P1) depende da Foundational e de US1 (envolve `run_scraper_agent` já existente com a política de retry)
  - US3 (P2) depende apenas da Foundational — independente de US1/US2 (documentação, sem dependência de código funcional além de `SKILL.md` descrever um agente já existente em intenção)
- **Polish (Phase 6)**: Depende de todas as user stories desejadas estarem completas

### User Story Dependencies

- **US1 (P1)**: Depende apenas da Foundational — cria `build_scraper_agent`/`run_scraper_agent`
- **US2 (P1)**: Depende da Foundational e de US1 (adiciona a política de retry à função já existente)
- **US3 (P2)**: Depende apenas da Foundational — pode ser escrita em paralelo a US1/US2 por outro desenvolvedor, já que descreve o agente em termos de contrato (já definido em `contracts/scraper_agent.md`), não de implementação interna

### Within Each User Story

- Testes escritos e confirmados como FALHANDO (passo explícito, Princípio IX) antes da implementação correspondente
- Modelos/exceções/seleção de modelo (Foundational) antes de qualquer lógica do agente
- `build_scraper_agent` (US1) antes da política de retry (US2), que envolve a mesma função

### Parallel Opportunities

- T002 e T003 (Setup) em paralelo — arquivos diferentes
- T005 e T007 (Foundational) em paralelo — arquivos diferentes
- T009/T010 (US1, mesmo arquivo, mas fixture e teste independentes) podem ser escritos em paralelo por desenvolvedores diferentes, com atenção a conflito de merge
- US3 (Phase 5) pode ser trabalhada em paralelo a US1/US2 por outro desenvolvedor, assim que a Foundational estiver completa

---

## Parallel Example: Foundational

```bash
# Tarefas independentes da Foundational em paralelo:
Task: "Teste ScrapeResult valida e serializa corretamente em tests/test_models.py"
Task: "Definir ScraperAgentDeps e ScraperTransportError em src/pix_compliance/agents/scraper_agent.py"
```

## Parallel Example: User Story 1 + User Story 3

```bash
# US1 (funcionalidade) e US3 (documentação) em paralelo, após a Foundational:
Task: "Implementar build_scraper_agent/run_scraper_agent em src/pix_compliance/agents/scraper_agent.py"
Task: "Escrever skills/scraper-skill/SKILL.md completo"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (CRÍTICO — bloqueia todas as stories)
3. Completar Phase 3: User Story 1 (execução de ponta a ponta via MCP)
4. Completar Phase 4: User Story 2 (erro tipado de transporte MCP)
5. **PARAR e VALIDAR**: rodar os Cenários 1 e 2 de `quickstart.md`
6. Este é o MVP real desta feature — as duas garantias P1 que estabelecem o padrão estrutural para os seis agentes seguintes

### Incremental Delivery

1. Setup + Foundational → contratos de dados e seleção de modelo prontos
2. US1 → execução de ponta a ponta via MCP → validar com Cenário 1 de `quickstart.md`
3. US2 → erro tipado de transporte MCP → validar com Cenário 2 de `quickstart.md`
4. US3 → `SKILL.md` → validar com Cenário 4 de `quickstart.md`
5. Polish → lint, regressão completa, README

---

## Notes

- [P] = arquivos diferentes ou casos de teste independentes, sem dependência bloqueante
- [Story] mapeia cada tarefa à user story correspondente do spec.md
- Testes devem ser escritos e confirmados como falhando antes da implementação correspondente (Princípio IX) — cada story inclui um passo explícito de execução e confirmação de falha antes da tarefa de implementação
- Commitar após cada tarefa ou grupo lógico de tarefas
- Parar em cada checkpoint para validar a story de forma independente
- Evitar: tarefas vagas, conflito de mesmo arquivo sem necessidade, dependências entre stories que quebrem a independência (US2 depende de US1 por necessidade real de código, não por acoplamento evitável; US3 é deliberadamente independente)
