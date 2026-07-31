# Implementation Plan: Fundação do projeto e configuração (SPEC-001)

**Branch**: `001-fundacao-projeto-configuracao` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-fundacao-projeto-configuracao/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Estabelecer o esqueleto executável do repositório: dependências reprodutíveis via
`pyproject.toml`, um objeto de configurações tipado (`pydantic-settings`) que falha
rápido e com mensagem acionável quando falta uma variável obrigatória, logging
estruturado em JSON com `correlation_id` por execução, e um `Makefile` com os alvos
mínimos (`install`, `run`, `test`, `lint`, `up`, `down`) apoiados por configuração
básica de `pytest` e `ruff`. Nenhuma lógica de agente ou conteinerização entra nesta
spec — é puramente a fundação sobre a qual as specs 002+ programam.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `pydantic` v2, `pydantic-settings` (carregamento tipado de
`.env`/env vars), `structlog` (logging estruturado em JSON com bind de
`correlation_id` via contextvars), `ruff` (lint), `pytest` (testes)

**Storage**: N/A nesta spec — Postgres/pgvector e MinIO são apenas *nomeados* como
variáveis de configuração (DSN, endpoint) que `Settings` deve saber carregar; nenhuma
conexão real é aberta aqui (fica para SPEC-006)

**Testing**: `pytest`, com um teste mínimo cobrindo o fail-fast de `Settings` e o
formato JSON dos logs

**Target Platform**: Linux server (dev local via `make`, produção via Docker em
SPEC-016 — fora de escopo aqui)

**Project Type**: Single project (backend Python) — sem frontend

**Performance Goals**: N/A — spec de fundação, sem caminho de execução com carga

**Constraints**: `make install` até `Settings` carregado em <5 min em máquina limpa
(SC-005); fail-fast nunca deve vazar traceback cru do Pydantic (FR-004)

**Scale/Scope**: Escopo mínimo deliberado — um módulo de config, um módulo de
logging, arquivos de configuração de ferramentas (`pyproject.toml`, `Makefile`,
`.env.example`), sem lógica de domínio

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Aplicação nesta spec | Status |
|---|---|---|
| I. Bedrock é o caminho padrão | `Settings` deve carregar `LLM_PROVIDER` com default `bedrock` e os campos de credencial/modelo Bedrock, mesmo sem nenhum provider ainda implementado (SPEC-005 os consome) | PASS |
| II. Abstração exige justificativa concreta | `Settings` é uma única classe concreta (`pydantic-settings.BaseSettings`), sem interface — não há segunda implementação nem teste que exija substituí-la | PASS |
| III. Simplicidade sobre segmentação | Config e logging vivem em módulos separados e pequenos (`config.py`, `logging.py`) porque são duas responsabilidades genuinamente distintas, não uma segmentação artificial | PASS |
| IV. Responsabilidade única por agente | N/A — nenhum agente nesta spec (fora de escopo por FR-010) | N/A |
| V. Guardrail é ponto único | N/A — nenhum texto trafega para LLM ou storage nesta spec | N/A |
| VI. Contrato antes de comportamento | `Settings` é o único "contrato" desta spec; é definido e testado antes de qualquer spec que o consuma | PASS |
| VII. Comentários e nomenclatura | Identificadores em inglês, docstrings/comentários em português, aplicado a `config.py` e `logging.py` | PASS |
| VIII. Evidência é entregável | Critérios de aceite desta spec são todos comandos (`make install`, `make lint`, `python -c ...`, `grep`) — nenhum julgamento subjetivo | PASS |

Nenhuma violação a justificar em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml          # dependências, metadados do projeto, config de ruff/pytest
requirements.txt        # lock reprodutível gerado a partir do pyproject (pip)
.env.example             # todas as variáveis de ambiente, comentadas
Makefile                 # install, run, test, lint, up, down

src/
└── pix_compliance/
    ├── __init__.py
    ├── config.py         # Settings (pydantic-settings), fail-fast com mensagem acionável
    └── logging.py         # setup de structlog em JSON + correlation_id por execução

tests/
└── test_config.py         # fail-fast em var obrigatória ausente; Settings carrega com .env válido
└── test_logging.py         # linha de log é JSON válido; correlation_id estável na execução
```

**Structure Decision**: Projeto único (backend Python), conforme a estrutura de
repositório definida no briefing (`Initial Design/BRIEFING.md`, seção 3.3). Apenas os
diretórios que esta spec de fato entrega são criados agora (`src/pix_compliance/`,
`tests/`); os demais diretórios do layout final (`agents/`, `providers/`, `storage/`,
`mcp_servers/`, `fixtures/`, `docker/`, etc.) pertencem a specs posteriores e não são
criados vazios aqui, para não sugerir estrutura não implementada.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Nenhuma violação — todos os gates da Constitution Check passaram ou são N/A para o
escopo desta spec.
