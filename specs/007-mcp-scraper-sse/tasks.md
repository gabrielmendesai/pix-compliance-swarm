---

description: "Task list template for feature implementation"
---

# Tasks: Servidor MCP do Scraper com transporte SSE (SPEC-007)

**Input**: Design documents from `/specs/007-mcp-scraper-sse/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/scraper_mcp.md, quickstart.md

**Tests**: Incluídos e obrigatórios — o Princípio IX da constituição exige que os testes do Fetcher, do `MockBcbAdapter` e das três ferramentas MCP sejam escritos e confirmados como falhos antes de qualquer código de implementação correspondente, derivados exclusivamente dos critérios de aceite do spec.md.

**Organization**: Tarefas agrupadas por user story do spec.md, permitindo implementação e teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: A qual user story esta tarefa pertence (US1, US2, US3)
- Caminhos de arquivo exatos incluídos em cada descrição

## Path Conventions

Projeto único: `mcp_servers/scraper_sse/` (novo pacote), `src/pix_compliance/` (config, object store já existentes), `tests/` na raiz do repositório (conforme `plan.md`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar dependências, esqueleto do pacote e configuração de ambiente antes de qualquer código de coleta/servidor

- [X] T001 Adicionar `mcp`, `httpx` e `beautifulsoup4` às dependências de `pyproject.toml` (seção `[project.dependencies]`) e sincronizar `requirements.txt` — `tenacity`/`pydantic` já existem desde a SPEC-005/SPEC-001. `mcp` fixado em `1.29.0` (não `>=`): a série 2.x reestruturou o pacote (FastMCP mudou de módulo) de forma incompatível com a API usada aqui
- [X] T002 [P] Criar o esqueleto do pacote `mcp_servers/scraper_sse/` (`__init__.py`) e um `README.md` inicial (placeholder, preenchido de fato na Polish)
- [X] T003 [P] Adicionar `BCB_BASE_URL`, `MCP_SCRAPER_HOST` e `MCP_SCRAPER_PORT` a `Settings` (`src/pix_compliance/config.py`) e a `.env.example`, com o `BCB_BASE_URL` default apontando para o site mock local (`http://localhost:8080`, servido a partir de `mock_bcb/`)
- [X] T004 [P] Criar um fixture de teste compartilhado (`tests/conftest.py`), reaproveitando o padrão de `tests/test_fixtures.py` (`HTTPServer` da stdlib em porta efêmera, thread daemon), que sobe uma cópia de `mock_bcb/` via `http.server` e expõe a URL base para os testes desta feature — serve uma cópia (`tmp_path`), não o diretório real, para que testes de detecção de mudança possam alterar arquivos sem efeito colateral no repositório

**Checkpoint**: Dependências instaláveis, pacote criado, configuração documentada, fixture de teste do site mock disponível.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contratos, Fetcher e Adapter que TODAS as user stories dependem

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase estar completa

- [X] T005 Definir os modelos Pydantic `NormativoFilter`, `NormativoListItem`, `FetchNormativoResult`, `ChangeRecord` e `NormativoRef` em `mcp_servers/scraper_sse/models.py`, conforme `data-model.md`
- [X] T006 [P] Definir o `Protocol Adapter` (`list_refs() -> list[NormativoRef]`, `parse_titulo(html: str) -> str`) em `mcp_servers/scraper_sse/adapters.py`, com docstring explicando por que é a única exceção do projeto à regra de "interface exige segunda implementação real" (Princípio II) e o caminho de evolução (`RealBcbAdapter` via `BCB_BASE_URL`)

### Tests for Fetcher/Adapter (Foundational) ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação (Princípio IX)

- [X] T007 [P] Teste: `Fetcher.get(url)` contra o site mock (via fixture de T004) retorna conteúdo e hash SHA-256 corretos; com uma falha transitória simulada, aplica retry com backoff antes de suceder; e respeita rate limit entre requisições consecutivas, em `tests/test_scraper_fetcher.py`
- [X] T008 [P] Teste: `MockBcbAdapter.list_refs()` retorna o conjunto correto de `NormativoRef` a partir de `mock_bcb/index.html`; `parse_titulo()` extrai o título correto de uma página conhecida do site mock, em `tests/test_scraper_adapter.py`
- [X] T009 Rodar `pytest tests/test_scraper_fetcher.py tests/test_scraper_adapter.py -q`, confirmando que os testes FALHAM por ausência de `Fetcher`/`MockBcbAdapter` (nenhuma implementação ainda) — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ModuleNotFoundError`/`ImportError`

### Implementation for Fetcher/Adapter (Foundational)

- [X] T010 [P] Implementar `Fetcher` (via `httpx`, retry/backoff com `tenacity`, rate limit por intervalo mínimo entre requisições, cálculo de hash SHA-256), agnóstico à estrutura de página, em `mcp_servers/scraper_sse/fetcher.py` (depende de T005)
- [X] T011 [P] Implementar `MockBcbAdapter` (via `beautifulsoup4`/`html.parser`, interpretando `mock_bcb/index.html` e as páginas individuais em `mock_bcb/normativos/`) em `mcp_servers/scraper_sse/adapters.py` (depende de T006)
- [X] T012 Implementar `mcp_servers/scraper_sse/state.py` (`load_known_hashes()`/`save_known_hashes(hashes)`, lendo/escrevendo o blob `scraper-state/known-hashes.json` via `ObjectStore`/`S3ObjectStore`, SPEC-006) (depende de T005)
- [X] T013 Rodar novamente `pytest tests/test_scraper_fetcher.py tests/test_scraper_adapter.py -q` e confirmar que os testes de T007-T008 agora PASSAM — 5/5 passando (um teste ajustado para comparar bytes crus em vez de texto normalizado por `Path.read_text`, divergência de CRLF vs. decodificação `httpx`, não um bug do Fetcher)

**Checkpoint**: Fetcher, Adapter e estado de hashes prontos; nenhum servidor MCP ainda.

---

## Phase 3: User Story 1 - Cliente MCP descobre e lista as ferramentas do servidor (Priority: P1) 🎯 MVP

**Goal**: O servidor MCP sobe em transporte SSE, completa o handshake, e um cliente MCP consegue listar as três ferramentas com seus schemas de entrada/saída

**Independent Test**: Subir o servidor e conectar um cliente MCP (SDK `mcp`) que completa o handshake e solicita a listagem de ferramentas, verificando que as três aparecem com schemas Pydantic serializados

### Tests for User Story 1 ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação (Princípio IX)

- [X] T014 [P] [US1] Teste: cliente MCP (via `mcp.client.sse.sse_client`/`ClientSession`) conecta ao servidor subido em thread de teste (uvicorn + `app.sse_app()`), completa o handshake, e `list_tools()` retorna as três ferramentas (`list_normativos`, `fetch_normativo`, `detect_changes`) com `inputSchema`/`outputSchema` correspondentes aos modelos de `data-model.md`, em `tests/test_scraper_mcp_server.py`
- [X] T015 [US1] Rodar `pytest tests/test_scraper_mcp_server.py -k list_tools -q`, confirmando que o teste FALHA por ausência de `server.py` (nenhum servidor MCP ainda) — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ModuleNotFoundError`

### Implementation for User Story 1

- [X] T016 [US1] Implementar `mcp_servers/scraper_sse/server.py`: `FastMCP` app, registrando as três ferramentas (`list_normativos`, `fetch_normativo`, `detect_changes`) com os schemas Pydantic de `models.py`, servido via transporte SSE em host/porta de `Settings` (`MCP_SCRAPER_HOST`/`MCP_SCRAPER_PORT`) (depende de T005, T010, T011, T012)
- [X] T017 [US1] Rodar novamente `pytest tests/test_scraper_mcp_server.py -k list_tools -q` e confirmar que o teste de T014 agora PASSA

**Checkpoint**: User Story 1 completa e testável de forma independente — handshake SSE e listagem de ferramentas funcionam (SC-001, SC-002).

---

## Phase 4: User Story 2 - Detecção de normativo novo ou alterado por hash (Priority: P1) 🎯 MVP

**Goal**: `detect_changes(since)` retorna vazio quando nada muda entre duas chamadas, e retorna o item alterado depois que um fixture do site mock é modificado

**Independent Test**: Chamar `detect_changes` duas vezes contra o site mock inalterado (esperando lista vazia nas duas), depois alterar um fixture e chamar `detect_changes` novamente (esperando o item alterado na resposta)

### Tests for User Story 2 ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação (Princípio IX)

- [X] T018 [P] [US2] Teste: `detect_changes()` chamado duas vezes seguidas via cliente MCP, sem nenhuma alteração no site mock entre as chamadas, retorna lista vazia nas duas, em `tests/test_scraper_mcp_server.py`
- [X] T019 [P] [US2] Teste: após alterar o conteúdo de um fixture do site mock (escrita direta na cópia efêmera servida por `mock_bcb_server`), uma nova chamada a `detect_changes()` retorna um `ChangeRecord` para o item alterado, com `hash_anterior` e `hash_atual` corretos, em `tests/test_scraper_mcp_server.py`
- [X] T020 [P] [US2] Teste: `detect_changes()` na primeira chamada (nenhum estado de hash conhecido persistido ainda) trata todo o conteúdo atual do site mock como novo, com `hash_anterior=None`, em `tests/test_scraper_mcp_server.py`
- [X] T021 [US2] Rodar `pytest tests/test_scraper_mcp_server.py -k detect_changes -q`, confirmando que os testes FALHAM porque `detect_changes` ainda não está implementado em `server.py` — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ModuleNotFoundError` (todo o `server.py` ainda não existia neste ponto)

### Implementation for User Story 2

- [X] T022 [US2] Implementar a lógica de `detect_changes` em `mcp_servers/scraper_sse/server.py` (coleta todos os normativos via `Fetcher`/`MockBcbAdapter`, compara hash contra `state.load_known_hashes()`, monta `ChangeRecord[]`, filtra por `since` quando fornecido, e persiste o novo estado via `state.save_known_hashes()`) (depende de T016)
- [X] T023 [US2] Rodar novamente `pytest tests/test_scraper_mcp_server.py -k detect_changes -q` e confirmar que os testes de T018-T020 agora PASSAM — 3/3 passando (o teste de "primeira chamada" exigiu zerar o estado de hashes conhecidos no fixture `running_server`, já que o bucket MinIO de teste é real e persiste entre execuções)

**Checkpoint**: User Story 2 completa e testável de forma independente — detecção de mudança por hash funciona de ponta a ponta (SC-003).

---

## Phase 5: User Story 3 - Buscar e listar normativos individuais via MCP (Priority: P2)

**Goal**: `list_normativos(filtros)` lista os normativos do site mock (com ou sem filtro), e `fetch_normativo(id)` retorna o conteúdo bruto de um normativo específico, persistindo uma cópia no `ObjectStore`

**Independent Test**: Chamar `list_normativos` sem filtro (esperando a lista completa) e com um filtro que restrinja o resultado, e chamar `fetch_normativo(id)` para um `id` conhecido, verificando que o conteúdo bruto corresponde ao fixture de origem e que uma cópia foi persistida no `ObjectStore`

### Tests for User Story 3 ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação (Princípio IX)

- [X] T024 [P] [US3] Teste: `list_normativos({})` sem filtro, via cliente MCP, retorna todos os normativos do site mock, em `tests/test_scraper_mcp_server.py`
- [X] T025 [P] [US3] Teste: `list_normativos(filtro)` com um filtro (`numero`, substring do identificador) restringe corretamente o conjunto de normativos retornado, em `tests/test_scraper_mcp_server.py`
- [X] T026 [P] [US3] Teste: `fetch_normativo(id)` para um `id` conhecido retorna conteúdo bruto correspondente ao fixture de origem, com uma cópia persistida no `ObjectStore` sob a chave retornada em `object_store_key`, em `tests/test_scraper_mcp_server.py`
- [X] T027 [P] [US3] Teste: `fetch_normativo(id)` para um `id` inexistente retorna um erro MCP claro (`isError=True`, não uma exceção crua propagada ao cliente), em `tests/test_scraper_mcp_server.py`
- [X] T028 [US3] Rodar `pytest tests/test_scraper_mcp_server.py -k "list_normativos or fetch_normativo" -q`, confirmando que os testes FALHAM porque essas ferramentas ainda não estão implementadas em `server.py` — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ModuleNotFoundError` (todo o `server.py` ainda não existia neste ponto)

### Implementation for User Story 3

- [X] T029 [US3] Implementar a lógica de `list_normativos` (via `MockBcbAdapter.list_refs()` + filtro por `numero`/`categoria`, substring case-insensitive contra id/título — únicos dados estruturados disponíveis a partir do HTML coletado) e `fetch_normativo` (via `Fetcher.get()` + persistência no `ObjectStore`/`S3ObjectStore`, `NormativoNotFoundError` para `id` inexistente, convertida pelo SDK `mcp` em resultado `isError=True`) em `mcp_servers/scraper_sse/server.py` (depende de T016)
- [X] T030 [US3] Rodar novamente `pytest tests/test_scraper_mcp_server.py -k "list_normativos or fetch_normativo" -q` e confirmar que os testes de T024-T027 agora PASSAM — 4/4 passando

**Checkpoint**: Todas as três ferramentas MCP funcionais e testáveis de forma independente.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentação e validação final que atravessa todas as user stories

- [X] T031 [P] Escrever `mcp_servers/scraper_sse/README.md` com um bloco de configuração pronto para copiar (URL do servidor, transporte SSE, exemplo de chamada a cada uma das três ferramentas) e a nota de arquitetura sobre `Adapter` ser a única exceção do projeto ao Princípio II, com o caminho de evolução (`RealBcbAdapter`) (SC-004)
- [X] T032 [P] Rodar `ruff check src tests mcp_servers` e corrigir eventuais violações introduzidas por esta feature — 1 violação de ordenação de imports corrigida via `--fix` em `tests/test_scraper_mcp_server.py`; limpo
- [X] T033 Rodar `pytest -q` como checagem final de regressão de toda a suíte do projeto (não apenas os testes desta feature) — 100/100 passando
- [ ] T034 Roteirizar e gravar, no vídeo de evidência final do projeto, o trecho mostrando o handshake SSE e a listagem das três ferramentas com seus schemas — passo manual, não automatizável, pendente de gravação pelo usuário

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: Depende da Setup — BLOQUEIA todas as user stories
- **User Stories (Phase 3-5)**: Todas dependem da conclusão da Foundational
  - US1 (P1) depende apenas da Foundational — nenhuma dependência de outra story
  - US2 (P1) depende da Foundational e de US1 (usa o `server.py` já criado em T016 para adicionar a lógica de `detect_changes`)
  - US3 (P2) depende da Foundational e de US1 (mesma razão de US2); independente de US2
- **Polish (Phase 6)**: Depende de todas as user stories estarem completas

### User Story Dependencies

- **US1 (P1)**: Depende apenas da Foundational (Fetcher, Adapter, state) — cria o servidor MCP com as três ferramentas registradas
- **US2 (P1)**: Depende da Foundational e de US1 (adiciona a lógica de `detect_changes` ao `server.py` já existente)
- **US3 (P2)**: Depende da Foundational e de US1 (adiciona a lógica de `list_normativos`/`fetch_normativo` ao `server.py` já existente); independente de US2

### Within Each User Story

- Testes escritos e confirmados como FALHANDO (passo explícito, Princípio IX) antes da implementação correspondente
- Fetcher/Adapter/state (Foundational) antes de qualquer ferramenta MCP
- `server.py` com as três ferramentas registradas (US1) antes das lógicas específicas de US2/US3

### Parallel Opportunities

- T002, T003 e T004 (Setup) em paralelo — arquivos diferentes
- T006 (Foundational, `adapters.py`) em paralelo com T005 (`models.py`)
- T007/T008 (testes de Fetcher/Adapter) em paralelo entre si
- T010/T011 (implementação de Fetcher/Adapter) em paralelo entre si; T012 (`state.py`) em paralelo com ambos
- Após US1 (T016/T017) estar completa, US2 e US3 podem ser trabalhadas em paralelo por desenvolvedores diferentes (cada uma adiciona lógica a ferramentas distintas do mesmo `server.py` — atenção a conflito de merge no mesmo arquivo)
- Testes marcados `[P]` dentro de cada story rodam em paralelo entre si

---

## Parallel Example: Foundational (Fetcher/Adapter)

```bash
# Testes de Fetcher/Adapter em paralelo:
Task: "Teste Fetcher.get() com retry/backoff e hash correto em tests/test_scraper_fetcher.py"
Task: "Teste MockBcbAdapter.list_refs()/parse_titulo() em tests/test_scraper_adapter.py"
```

## Parallel Example: User Story 2

```bash
# Testes da User Story 2 em paralelo:
Task: "Teste detect_changes() duas vezes sem mudança retorna vazio em tests/test_scraper_mcp_server.py"
Task: "Teste detect_changes() após alteração de fixture retorna item alterado em tests/test_scraper_mcp_server.py"
Task: "Teste detect_changes() na primeira chamada trata tudo como novo em tests/test_scraper_mcp_server.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (CRÍTICO — bloqueia todas as stories)
3. Completar Phase 3: User Story 1 (handshake + listagem de ferramentas)
4. Completar Phase 4: User Story 2 (detecção de mudança por hash)
5. **PARAR e VALIDAR**: rodar os Cenários 2 e 3 de `quickstart.md`
6. Este é o MVP real desta feature — as duas garantias P1 que comprovam o requisito nominal do desafio (servidor MCP via SSE) e o valor central da coleta (saber o que mudou)

### Incremental Delivery

1. Setup + Foundational → Fetcher/Adapter/state prontos e testados
2. US1 → servidor MCP com handshake e discovery → validar com Cenário 2 de `quickstart.md`
3. US2 → detecção de mudança → validar com Cenário 3 de `quickstart.md`
4. US3 → busca/listagem individual → validar com Cenário 4 de `quickstart.md`
5. Polish → README de integração, lint, regressão completa, evidência em vídeo

---

## Notes

- [P] = arquivos diferentes ou casos de teste independentes, sem dependência bloqueante
- [Story] mapeia cada tarefa à user story correspondente do spec.md
- Testes devem ser escritos e confirmados como falhando antes da implementação correspondente (Princípio IX) — cada story inclui um passo explícito de execução e confirmação de falha antes da tarefa de implementação
- Commitar após cada tarefa ou grupo lógico de tarefas
- Parar em cada checkpoint para validar a story de forma independente
- Evitar: tarefas vagas, conflito de mesmo arquivo sem necessidade, dependências entre stories que quebrem a independência (US2/US3 dependem de US1 por necessidade real — o `server.py` precisa existir antes de receber lógica adicional —, não por acoplamento evitável)
