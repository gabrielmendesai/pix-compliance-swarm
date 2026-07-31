---

description: "Task list for SPEC-001 — Fundação do projeto e configuração"
---

# Tasks: Fundação do projeto e configuração (SPEC-001)

**Input**: Design documents from `/specs/001-fundacao-projeto-configuracao/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Incluídas — FR-008 exige configuração funcional de `pytest`, e as
Acceptance Scenarios de US1/US2 são comportamentos verificáveis apenas por teste
automatizado, então os testes fazem parte do escopo entregável, não de um TDD
opcional.

**Organization**: Tarefas agrupadas por user story (spec.md) para permitir
implementação e teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: US1, US2 ou US3, conforme spec.md
- Caminhos de arquivo exatos incluídos em cada descrição

## Path Conventions

Projeto único (backend Python), conforme `plan.md` → Project Structure:
`src/pix_compliance/`, `tests/`, arquivos de configuração na raiz do repositório.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialização do repositório e estrutura básica

- [X] T001 Criar estrutura de diretórios `src/pix_compliance/` e `tests/` na raiz do repositório
- [X] T002 Criar `pyproject.toml` na raiz com metadados do projeto e dependências: `pydantic`, `pydantic-settings`, `structlog`, `ruff`, `pytest`
- [X] T003 [P] Gerar `requirements.txt` na raiz como lock reprodutível a partir das dependências de `pyproject.toml`
- [X] T004 [P] Criar `.gitignore` na raiz cobrindo `.venv/`, `__pycache__/`, `.env`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestrutura compartilhada que TODAS as user stories precisam antes de começar

**⚠️ CRITICAL**: Nenhuma user story começa antes desta fase estar completa

- [X] T005 Criar `Makefile` na raiz com os seis alvos mínimos (`install`, `run`, `test`, `lint`, `up`, `down`) como targets nomeados; `install`/`run`/`test`/`lint` recebem os comandos reais nas fases seguintes, `up`/`down` já recebem o placeholder final (T020)
- [X] T006 [P] Criar `src/pix_compliance/__init__.py` como marcador de pacote

**Checkpoint**: Fundação pronta — user stories podem começar

---

## Phase 3: User Story 1 - Bootstrap do ambiente por um avaliador/desenvolvedor (Priority: P1) 🎯 MVP

**Goal**: Uma pessoa clona o repositório, roda `make install`, carrega `Settings` a
partir de `.env` com sucesso, e recebe erro claro (nunca traceback cru) se faltar
uma variável obrigatória.

**Independent Test**: `cp .env.example .env` com valores válidos →
`python -c "from pix_compliance.config import settings; print(settings.model_dump())"`
imprime sem exceção; removendo `AWS_REGION` de `.env`, o mesmo comando falha com
mensagem acionável citando a variável ausente.

### Tests for User Story 1

- [X] T007 [P] [US1] Escrever `tests/test_config.py` cobrindo: `Settings()` carrega com sucesso a partir de `.env` válido (SC-002); `Settings()` levanta `ConfigurationError` com mensagem citando `AWS_REGION` quando essa variável está ausente (Acceptance Scenario 3)

### Implementation for User Story 1

- [X] T008 [US1] Implementar classe `Settings(BaseSettings)` em `src/pix_compliance/config.py` com todos os campos de `data-model.md` (`llm_provider` default `"bedrock"`, `aws_access_key_id`, `aws_secret_access_key: SecretStr`, `aws_region`, `bedrock_model_id`, `bedrock_embeddings_model_id`, `api_url`, `postgres_dsn`, `object_storage_endpoint`), `model_config = SettingsConfigDict(extra="forbid", env_file=".env", frozen=True)`
- [X] T009 [US1] Implementar exceção `ConfigurationError` e o wrapper de fail-fast em `src/pix_compliance/config.py`: capturar `pydantic.ValidationError` na instanciação de `Settings()` e relançar `ConfigurationError` citando a primeira variável ausente e a instrução "copie .env.example para .env" (FR-004)
- [X] T010 [US1] Instanciar `settings = Settings()` no nível de módulo em `src/pix_compliance/config.py`, para que `from pix_compliance.config import settings` funcione (SC-002)
- [X] T011 [US1] Criar `.env.example` na raiz documentando, com comentário, cada campo de `Settings` (FR-003)
- [X] T012 [US1] Ligar o alvo `install` do `Makefile` para criar o virtualenv e instalar dependências a partir de `pyproject.toml`/`requirements.txt` (FR-001, SC-001)

**Checkpoint**: US1 completa e testável de forma independente — `make install` +
quickstart.md seções 1–3 passam sem depender de US2 ou US3.

---

## Phase 4: User Story 2 - Diagnóstico de execução via logs estruturados (Priority: P2)

**Goal**: Toda execução emite logs JSON com um `correlation_id` único por execução,
estável em todas as linhas daquela execução.

**Independent Test**: Rodar um comando que dispare logging duas vezes e comparar —
cada linha de cada execução é JSON válido; `correlation_id` difere entre as duas
execuções e é idêntico dentro de cada uma.

### Tests for User Story 2

- [X] T013 [P] [US2] Escrever `tests/test_logging.py` cobrindo: linha de log emitida é JSON válido contendo `correlation_id`; duas chamadas de configuração/execução distintas produzem `correlation_id` diferentes, enquanto linhas dentro da mesma execução compartilham o mesmo valor

### Implementation for User Story 2

- [X] T014 [US2] Implementar `src/pix_compliance/logging.py`: configurar `structlog` com processor `JSONRenderer`, e uma função `bind_run_correlation_id()` que gera um `uuid4` e o bind via `structlog.contextvars.bind_contextvars(correlation_id=...)` no início da execução
- [X] T015 [US2] Ligar o alvo `run` do `Makefile` a um entrypoint mínimo (ex.: `python -c "..."` ou `python -m pix_compliance.logging`) que chama `bind_run_correlation_id()` e emite linhas de log de exemplo, demonstrando a propagação do `correlation_id` (FR-005, FR-006)

**Checkpoint**: US2 completa e testável de forma independente — `make run` +
quickstart.md seção 4 passam sem depender de US3.

---

## Phase 5: User Story 3 - Qualidade de código verificável por comando (Priority: P3)

**Goal**: `make lint` e `make test` rodam sem erro de configuração em um
repositório limpo, mesmo sem lógica de agente implementada.

**Independent Test**: Repositório limpo com dependências instaladas → `make lint`
conclui sem erro; `make test` executa a suíte (ainda que mínima) sem falha de
configuração.

### Implementation for User Story 3

- [X] T016 [US3] Configurar seção `[tool.ruff]` em `pyproject.toml` com regras de lint aplicadas a `src/` e `tests/`
- [X] T017 [US3] Configurar seção `[tool.pytest.ini_options]` em `pyproject.toml` (`testpaths = ["tests"]`)
- [X] T018 [US3] Ligar o alvo `lint` do `Makefile` para rodar `ruff check .`
- [X] T019 [US3] Ligar o alvo `test` do `Makefile` para rodar `pytest`
- [X] T020 [US3] Implementar os alvos `up`/`down` do `Makefile` como placeholders que imprimem mensagem apontando para a implementação futura (SPEC-016), sem falhar e sem quebrar os demais alvos (Edge Case da spec)

**Checkpoint**: Todas as três user stories funcionam de forma independente —
`make lint` e `make test` verdes, fechando os critérios de aceite da spec.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificação final dos Success Criteria que atravessam as três stories

- [X] T021 [P] Verificar SC-003: rodar `grep -rn "AKIA" src/` e confirmar saída vazia (nenhum segredo hardcoded)
- [X] T022 Executar a validação completa de `quickstart.md` (seções 1–7) ponta a ponta e registrar a saída como evidência
- [X] T023 [P] Atualizar `Status` de `spec.md` de `Draft` para `done`, registrando eventuais desvios na seção de notas, conforme convenção de SDD do projeto (`Initial Design/BRIEFING.md`, seção 4.2)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: depende de Setup completo — BLOQUEIA todas as user stories
- **User Stories (Phase 3–5)**: todas dependem de Foundational completo
  - US1, US2 e US3 tocam o mesmo `Makefile` (T005/T012/T015/T018–T020) — não são
    paralelizáveis entre si nesse arquivo específico, mas são independentes em todo
    o resto (módulos, testes, `.env.example`, `pyproject.toml`)
  - Ordem recomendada: sequencial por prioridade (US1 → US2 → US3), já que US1 é o
    MVP e as demais adicionam valor incrementalmente
- **Polish (Phase 6)**: depende de todas as user stories desejadas estarem completas

### User Story Dependencies

- **US1 (P1)**: pode começar após Foundational — sem dependência de US2/US3
- **US2 (P2)**: pode começar após Foundational — independente de US1 em código,
  mas compartilha o `Makefile` (edição sequencial recomendada)
- **US3 (P3)**: pode começar após Foundational — depende apenas de US1/US2 já
  terem definido `pyproject.toml`/módulos para o lint ter algo a checar, mas o
  próprio alvo `lint`/`test` é independente em conteúdo

### Within Each User Story

- Testes escritos antes da implementação correspondente (T007 antes de T008–T012;
  T013 antes de T014–T015)
- `config.py`/`logging.py` antes da respectiva ligação no `Makefile`
- Story completa antes de avançar para a próxima prioridade

### Parallel Opportunities

- T003, T004 (Setup) em paralelo
- T006 (Foundational) em paralelo com o restante da fase, após T005
- T007 (teste US1) em paralelo com início de outras stories, se houver mais de uma
  pessoa — mas T008–T012 são sequenciais entre si (mesmo arquivo `config.py`, depois
  `Makefile`)
- T013 (teste US2) em paralelo com T007
- T021, T023 (Polish) em paralelo entre si

---

## Parallel Example: Setup

```bash
Task: "Gerar requirements.txt na raiz a partir de pyproject.toml"
Task: "Criar .gitignore na raiz cobrindo .venv/, __pycache__/, .env"
```

## Parallel Example: Testes de US1 e US2

```bash
Task: "Escrever tests/test_config.py cobrindo fail-fast de Settings"
Task: "Escrever tests/test_logging.py cobrindo JSON + correlation_id"
```

---

## Implementation Strategy

### MVP First (User Story 1 apenas)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (bloqueia todas as stories)
3. Completar Phase 3: User Story 1
4. **PARAR e VALIDAR**: quickstart.md seções 1–3
5. Nesse ponto, `make install` funciona e `Settings` carrega/falha corretamente —
   suficiente para qualquer spec subsequente (002+) começar a programar contra
   `pix_compliance.config.settings`

### Incremental Delivery

1. Setup + Foundational → fundação pronta
2. US1 → validar independentemente → MVP da spec
3. US2 → validar independentemente → observabilidade mínima entregue
4. US3 → validar independentemente → `make lint`/`make test` fecham o ciclo
5. Polish → evidência e fechamento da spec

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente
- Rótulo [Story] mapeia a tarefa à user story correspondente em `spec.md`
- Verificar que os testes falham antes de implementar (T007/T013 antes de
  T008–T012/T014–T015)
- Commit ao final de cada story fechada (mínimo um commit por spec, por convenção
  do projeto)
- Parar em cada checkpoint para validar a story isoladamente antes de seguir
