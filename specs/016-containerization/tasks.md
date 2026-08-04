---

description: "Task list template for feature implementation"
---

# Tasks: Conteinerização (SPEC-016)

**Input**: Design documents from `/specs/016-containerization/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/containerization.md, quickstart.md

**Tests**: Requeridos pela spec, adaptados à natureza de infraestrutura declarativa desta feature (Princípio IX) — `scripts/verify_containerization.sh` é o "teste", escrito e confirmado como falho antes de qualquer `Dockerfile`/`docker-compose.yml` existir.

**Organization**: Tarefas agrupadas por user story (spec.md).

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Infraestrutura na raiz do repositório: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `scripts/`; extensão pequena em `src/pix_compliance/agents/orchestrator_agent.py` e `src/pix_compliance/config.py`.

---

## Phase 1: Setup

**Purpose**: Extensões aditivas pequenas necessárias antes de qualquer serviço de container poder funcionar corretamente.

- [x] T001 [P] Adicionar `orchestrator_bootstrap_local_servers: bool = True` a `Settings` (`src/pix_compliance/config.py`) e documentar `ORCHESTRATOR_BOOTSTRAP_LOCAL_SERVERS` em `.env.example` (data-model.md).
- [x] T002 [P] Implementar a flag `--daemon` no bloco `if __name__ == "__main__":` de `src/pix_compliance/agents/orchestrator_agent.py`: com a flag, chama `start_scheduler(settings)` e mantém o processo vivo (`asyncio.Event().wait()`); sem a flag, comportamento inalterado (research.md, Decisão 5).
- [x] T003 [P] Ajustar `run_pipeline` para usar `settings.orchestrator_bootstrap_local_servers` como default de `bootstrap_local_servers` quando o chamador não especifica o parâmetro explicitamente.
- [x] T004 [P] Criar `.dockerignore` (`.venv/`, `__pycache__/`, `.git/`, `tests/`, `docs/`, `*.md` exceto os necessários ao build, `reports/`).

**Checkpoint**: Extensões de `orchestrator_agent.py`/`Settings` prontas; `.dockerignore` no lugar.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: O "teste" desta feature — precisa existir e falhar antes de qualquer Dockerfile/compose ser escrito.

**⚠️ CRITICAL**: Nenhuma tarefa de user story começa antes desta fase completa.

- [x] T005 Escrever `scripts/verify_containerization.sh`: sobe o compose (`docker compose up -d`), faz polling do status de saúde de cada serviço com timeout, confere `GET /docs` no host, confere handshake TCP em `mcp-scraper`, roda o ciclo `down -v && up -d`, sai com código não-zero e mensagem clara em qualquer falha (contracts/containerization.md).
- [x] T006 Confirmar que `scripts/verify_containerization.sh` falha (porque nenhum `Dockerfile`/serviço novo existe ainda) rodando o script — checkpoint explícito do Princípio IX adaptado a esta feature.

**Checkpoint**: Script de verificação criado e confirmado como falho por ausência de implementação.

---

## Phase 3: User Story 1 - Subir o sistema inteiro com um único comando, a partir de um repositório limpo (Priority: P1) 🎯 MVP

**Goal**: `docker compose up -d` a partir de um repositório limpo deixa todos os serviços saudáveis, sem passo manual — incluindo criação do bucket e aplicação da migration.

**Independent Test**: Rodar `docker compose up -d` a partir de um checkout limpo e verificar que todos os serviços reportam `healthy` (ou `exited (0)` para `bootstrap`).

### Implementation for User Story 1

> Nota: esta feature não tem "testes" por user story no sentido `pytest` — o script de verificação (Foundational, T005) já cobre todos os cenários; as tarefas abaixo são de implementação, verificadas rodando o mesmo script ao final de cada fase.

- [x] T007 [US1] Criar `Dockerfile` com estágio `builder` (Python 3.12-slim, `COPY pyproject.toml` antes de `COPY src/`, `RUN --mount=type=cache,target=/root/.cache/pip pip install --no-cache-dir .`, research.md Decisão 2) e três estágios finais (`api`, `mcp-scraper`, `scheduler`), cada um com usuário não-root e `ENTRYPOINT`/`CMD` apropriado (contracts/containerization.md).
- [x] T008 [US1] Implementar `scripts/bootstrap.py`: constrói `S3ObjectStore(settings)` (cria o bucket via `_ensure_bucket()`, idempotente) e aplica `migrations/0001_create_vector_store_schema.sql` via `psycopg` (idempotente, já usa `IF NOT EXISTS`); sai com código não-zero e mensagem clara em caso de falha (research.md, Decisões 3/4; data-model.md).
- [x] T009 [US1] Estender `docker-compose.yml`: adicionar serviços `mock-bcb` (imagem `python:3.12-slim`, `command: python -m http.server 8080 --directory /mock_bcb`, volume `./mock_bcb:/mock_bcb:ro`, healthcheck `curl -f http://localhost:8080/`), `bootstrap` (`build: target: api`, `command: python scripts/bootstrap.py`, `depends_on: postgres, minio: condition: service_healthy`), `mcp-scraper` (`build: target: mcp-scraper`, `depends_on: mock-bcb: condition: service_healthy`, healthcheck TCP), `api` (`build: target: api`, `depends_on: postgres, minio: condition: service_healthy; bootstrap: condition: service_completed_successfully`, healthcheck `GET /health`, porta `8000` publicada), `scheduler` (`build: target: scheduler`, `command: ... --daemon`, `depends_on` análogo à `api` mais `mcp-scraper`/`mock-bcb`, `environment: ORCHESTRATOR_BOOTSTRAP_LOCAL_SERVERS=false`, healthcheck de processo vivo) — todos com `env_file: .env` para credenciais, e `environment:` sobrescrevendo hostnames internos (data-model.md).
- [x] T010 [US1] Rodar `scripts/verify_containerization.sh` (cenários 1 e 2 do quickstart) e confirmar que passa: todos os serviços saudáveis, `/docs` acessível, handshake do `mcp-scraper` bem-sucedido.

**Checkpoint**: User Story 1 completa e verificável de forma independente — subida completa, sem passo manual.

---

## Phase 4: User Story 2 - Reiniciar do zero reproduz o mesmo estado funcional, sem fricção manual (Priority: P1)

**Goal**: `docker compose down -v && docker compose up -d` reproduz o mesmo estado funcional, sem intervenção manual — incluindo recriação do bucket/migration.

**Independent Test**: Rodar `docker compose down -v && docker compose up -d` e confirmar que o sistema volta a ficar saudável, sem nenhum comando manual além dos dois do compose.

### Implementation for User Story 2

- [x] T011 [US2] Confirmar que os volumes nomeados de `postgres`/`minio` em `docker-compose.yml` (já existentes desde a SPEC-006) são de fato removidos por `down -v` e recriados vazios por `up -d` — nenhuma mudança de código esperada aqui, apenas confirmação de que a configuração já existente se comporta como o esperado (FR-004).
- [x] T012 [US2] Rodar `scripts/verify_containerization.sh` (cenário 3 do quickstart: `down -v && up -d` completo) e confirmar que passa — bucket recriado automaticamente pelo serviço `bootstrap`, migration reaplicada, sistema funcional sem intervenção manual.
- [x] T013 [US2] Se o serviço `bootstrap` (T008) falhar ao rodar duas vezes seguidas (ex. erro de "bucket já existe" tratado incorretamente), corrigir `scripts/bootstrap.py` para tolerar esse caso — a idempotência de `_ensure_bucket()` (SPEC-006, `head_bucket`/`create_bucket`) já deveria cobrir isso; esta tarefa existe para confirmar, não para reimplementar.

**Checkpoint**: User Stories 1 e 2 completas e verificáveis de forma independente — subida limpa e reset completo, ambos sem fricção manual.

---

## Phase 5: User Story 3 - Imagens eficientes, com rebuild rápido para mudanças triviais de código (Priority: P2)

**Goal**: Rebuild de uma mudança trivial de código reaproveita o cache de dependências; imagens finais têm tamanho razoável.

**Independent Test**: Alterar uma linha de código, rodar `docker compose build`, e observar que a instalação de dependências não foi reexecutada do zero.

### Implementation for User Story 3

- [x] T014 [US3] Confirmar (via `docker compose build --progress=plain`) que a ordem de `COPY` + o cache mount do `pip` no `Dockerfile` (T007) fazem o rebuild de uma mudança trivial de código reaproveitar o cache do `pip` para as dependências pesadas já baixadas (quickstart.md, cenário 4).
- [x] T015 [US3] Confirmar (via `docker images` / `docker history`) que as imagens finais (`api`, `mcp-scraper`, `scheduler`) não contêm ferramentas de build/dependências de desenvolvimento — apenas o runtime Python e o pacote instalado (FR-010).
- [x] T016 [US3] Atualizar os alvos `up`/`down` do `Makefile` para chamar `docker compose up -d`/`docker compose down` de fato (hoje são placeholders reservados desde a SPEC-001, "conteinerização chega na SPEC-016").

**Checkpoint**: Todas as user stories completas e verificáveis de forma independente.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentação de projeto e validação fim-a-fim.

- [x] T017 [P] Adicionar seção "Conteinerização" ao `README.md`, documentando os serviços do compose, o script de bootstrap, e como rodar `docker compose up -d`/`scripts/verify_containerization.sh`.
- [x] T018 [P] Confirmar que `.env.example` documenta `ORCHESTRATOR_BOOTSTRAP_LOCAL_SERVERS` (já adicionado em T001) e que os valores de exemplo continuam corretos para execução local (fora de container).
- [x] T019 Rodar `scripts/verify_containerization.sh` (suíte completa, todos os cenários) e confirmar que passa integralmente.
- [x] T020 Rodar `pytest -q` (regressão completa do projeto — a pequena extensão de `orchestrator_agent.py`/`Settings` não deve quebrar nada já existente) e `ruff check` e confirmar que ambos passam sem erros.
- [x] T021 Validar `quickstart.md` executando os 4 cenários documentados e confirmar que todos correspondem ao resultado esperado.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente.
- **Foundational (Phase 2)**: Depende do Setup — bloqueia todas as user stories (o script de verificação precisa das flags/config de T001-T003 para funcionar corretamente uma vez que os serviços existirem).
- **US1 (Phase 3)**: Depende do Foundational. Base para US2/US3 (ambas verificam propriedades do mesmo `Dockerfile`/compose já funcional).
- **US2 (Phase 4)**: Depende de US1 (precisa do sistema já subindo com sucesso para testar o ciclo de reset).
- **US3 (Phase 5)**: Depende de US1 (precisa do `Dockerfile` já existir para inspecionar cache/tamanho de imagem); independente de US2.
- **Polish (Phase 6)**: Depende de todas as user stories completas.

### Within Each User Story

- `Dockerfile` (T007) antes de `docker-compose.yml` (T009), que depende dele via `build.target`.
- `scripts/bootstrap.py` (T008) antes do serviço `bootstrap` no compose (T009) poder funcionar.
- Verificação via `scripts/verify_containerization.sh` acontece ao final de cada user story, não apenas no Polish.

### Parallel Opportunities

- T001/T002/T003/T004 (Setup, arquivos distintos) podem rodar em paralelo.
- T017/T018 (Polish, arquivos distintos) podem rodar em paralelo entre si.
- T014/T015 (US3, verificações independentes) podem rodar em paralelo.

---

## Parallel Example: Setup

```bash
Task: "Adicionar orchestrator_bootstrap_local_servers a Settings em src/pix_compliance/config.py"
Task: "Implementar flag --daemon em src/pix_compliance/agents/orchestrator_agent.py"
Task: "Criar .dockerignore"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup.
2. Completar Phase 2: Foundational (script de verificação escrito e confirmado falho).
3. Completar Phase 3: User Story 1 — subida completa sem passo manual já é o objetivo nominal central da spec, independentemente validável.
4. **PARAR e VALIDAR**: rodar `scripts/verify_containerization.sh` (cenários 1-2).

### Incremental Delivery

1. Setup + Foundational → base pronta (script de verificação como "teste" confirmado falho).
2. US1 → validar independentemente (subida completa, MVP).
3. US2 → validar independentemente (reset completo, sem fricção).
4. US3 → validar independentemente (eficiência de imagem/cache).
5. Polish → README, regressão completa do projeto, lint.

## Notes

- [P] = arquivos diferentes, sem dependência entre si.
- [Story] mapeia a tarefa à user story correspondente da spec.md.
- Confirmar que `scripts/verify_containerization.sh` falha antes de implementar (Princípio IX adaptado) — checkpoint explícito em T006.
- Rodar `pytest -q` e `ruff check` completos (regressão do projeto Python já existente) antes de considerar a feature encerrada (T020) — mesmo esta feature sendo majoritariamente infraestrutura, a pequena extensão de código (`orchestrator_agent.py`/`Settings`) precisa continuar passando na suíte já existente.
