# Implementation Plan: API FastAPI (SPEC-013)

**Branch**: `013-api-fastapi` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-api-fastapi/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Serviço HTTP FastAPI expondo `GET /normativos` (paginado, filtros por
tipo/categoria/período), `GET /compliance` (filtro por severidade),
`GET /search` (RAG via Knowledge Builder, SPEC-012), `GET /health`
(conectividade com storage) e `POST /runs` (execução ad-hoc do pipeline,
orquestrando os agentes já implementados diretamente, sem um Orchestrator
Agent dedicado — ver spec.md, Assumptions). Todo endpoint declara
`response_model` reaproveitando os modelos já congelados da SPEC-002;
exception handlers devolvem erro estruturado com `correlation_id`
(reaproveitando `pix_compliance.logging.bind_run_correlation_id`, SPEC-001);
metadados de OpenAPI completamente preenchidos, com Swagger em `/docs`.
Autenticação fica fora de escopo, documentada em prosa no README.

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `fastapi` e `uvicorn` — **primeira feature do
projeto a de fato introduzi-los** como dependência real em `pyproject.toml`
(já constavam na stack técnica obrigatória da constituição, mas nenhuma
spec anterior os usava; ver research.md, Decisão 5); `httpx` (já
dependência declarada, usado pelo `TestClient` do FastAPI nos testes);
`pix_compliance.object_store`/`vector_store` (SPEC-006), `pix_compliance.
agents.knowledge_builder_agent.search` (SPEC-012), `pix_compliance.logging`
(SPEC-001, `correlation_id`), `pix_compliance.models` (todos os
`response_model`, SPEC-002)

**Storage**: Nenhuma tabela/schema novo. `GET /normativos` lê
`fixtures/normativos.json` diretamente (mesmo arquivo já usado por todo CLI
do projeto); `GET /compliance` lê os `ConformanceReport` JSON já
persistidos localmente pelo Report Consolidator Agent (`reports/*.json`,
SPEC-014) — ver research.md, Decisões 0 e 1, para a justificativa de não
introduzir uma tabela SQL nova para nenhum dos dois.

**Testing**: pytest + `fastapi.testclient.TestClient` (baseado em `httpx`,
já dependência declarada) — sem servidor real escutando em porta, mesmo
padrão de teste em processo já recomendado pelo próprio FastAPI. Arquivo de
teste `tests/test_api.py`, nome exigido explicitamente pela spec.

**Target Platform**: Linux server (container Docker Compose, mesmo alvo do
restante do projeto) — `uvicorn` como servidor ASGI de produção.

**Project Type**: Single project — novo módulo `src/pix_compliance/api/`
(pacote dedicado, não `agents/`, por não ser um agente do enxame — ver
Project Structure)

**Performance Goals**: Sem meta de throughput própria — serviço síncrono de
baixo volume para um desafio técnico, não uma API de produção em escala.

**Constraints**: Todo `response_model` MUST reaproveitar um modelo já
existente da SPEC-002 (FR-006); toda falha MUST devolver corpo estruturado
com `correlation_id`, nunca o corpo cru default do FastAPI (FR-007);
`/docs` MUST ter descrição/exemplo reais em todo endpoint, nunca
placeholders genéricos (FR-008); autenticação MUST NOT ser implementada
(FR-010).

**Scale/Scope**: Um serviço HTTP com 5 rotas, nenhuma entidade de domínio
nova além de um envelope de paginação e um corpo de erro estruturado (ambos
infraestrutura de transporte, não schema de negócio duplicado — ver
data-model.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  N/A direto: esta feature não invoca nenhum LLM diretamente — `GET /search`
  delega ao Knowledge Builder (SPEC-012, já correto quanto a este
  princípio); `POST /runs` delega aos agentes já implementados, cada um já
  correto individualmente.
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS.
  Nenhuma abstração especulativa nova — o envelope de paginação e o corpo
  de erro estruturado são modelos concretos únicos (sem `Protocol`),
  existem porque há uma necessidade real e imediata (FR-006/FR-007), não
  especulação de futuro.
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS.
  `POST /runs` executa o pipeline **sincronamente** dentro do ciclo
  request/response, devolvendo o `PipelineResult` já completo — evita
  introduzir infraestrutura de fila/job assíncrono (Celery, RQ) que não
  existe neste projeto, apenas para um desafio técnico de escopo pequeno
  (ver research.md, Decisão 4 — reversão deliberada de uma suposição
  inicial do spec.md).
- **Princípio IV (Responsabilidade única por agente / SRP)** — N/A direto:
  esta feature não é um agente do enxame — é a camada de transporte HTTP
  que expõe os agentes já existentes; por isso vive em `src/pix_compliance/
  api/`, não em `agents/` (ver Project Structure).
- **Princípio V (Guardrail é ponto único e obrigatório)** — N/A direto: os
  dados servidos por esta feature (normativos, regras, relatórios) já
  passaram por `guard()` nas features que os produziram; esta feature não
  envia texto a nenhum LLM por conta própria — apenas lê e serve dados já
  processados, delega ao Knowledge Builder para busca.
- **Princípio VI (Contrato antes de comportamento)** — PASS. Todo
  `response_model` reaproveita um modelo já congelado (SPEC-002) — nenhuma
  alteração de contrato existente. O corpo de erro estruturado e o
  envelope de paginação são os únicos tipos novos, ambos infraestrutura de
  transporte (não schema de domínio) definidos no Phase 1 (data-model.md).
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês; comentários/docstrings em português explicando decisões não
  óbvias — em particular, por que autenticação foi conscientemente deixada
  fora do escopo, e por que `POST /runs` é síncrono.
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. Todos
  os critérios de aceite são comandos executáveis; `/docs` preenchido é, em
  si, o artefato de evidência formal pedido pelo desafio original
  (screenshot do Swagger).
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, requisito explícito da spec.
  `tests/test_api.py` é escrito e confirmado como falho (rotas ainda não
  existem) antes de qualquer código de rota.

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` confirma que os dois tipos novos
(envelope de paginação, corpo de erro estruturado) são infraestrutura de
transporte, não duplicam nenhum modelo de domínio já existente.
`contracts/api.md` confirma que todas as 5 rotas reaproveitam
`response_model` da SPEC-002 sem exceção. Gates permanecem PASS.

## Project Structure

### Documentation (this feature)

```text
specs/013-api-fastapi/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/pix_compliance/
├── models.py                          # já existe (SPEC-002) — response_model de todo endpoint
├── object_store.py / vector_store.py   # já existem (SPEC-006) — consumidos por /normativos, /compliance, /health
├── logging.py                          # já existe (SPEC-001) — bind_run_correlation_id() reaproveitado
├── agents/
│   ├── knowledge_builder_agent.py        # já existe (SPEC-012) — search() consumido por /search
│   ├── scraper_agent.py, extractor_agent.py, compliance_analyzer_agent.py,
│   │   conformance_validator_agent.py, report_consolidator_agent.py
│   │                                      # já existem — orquestrados diretamente por POST /runs
└── api/
    ├── __init__.py
    ├── app.py                            # NOVO — cria o FastAPI(), metadados OpenAPI, registra routers e exception handlers
    ├── errors.py                          # NOVO — ErrorResponse (corpo de erro estruturado com correlation_id), exception handlers
    ├── pagination.py                      # NOVO — envelope de paginação genérico
    └── routes.py                          # NOVO — os 5 endpoints (normativos, compliance, search, health, runs)

skills/
└── (nenhuma nova — esta feature não é um agente do enxame, não recebe SKILL.md)

tests/
└── test_api.py                          # NOVO — nome exigido explicitamente pela spec; escrito e confirmado falho ANTES do pacote api/ existir (Princípio IX)
```

**Structure Decision**: Projeto único (Option 1), com um pacote novo
`src/pix_compliance/api/` — deliberadamente **fora** de `agents/`, porque
esta feature não é um agente do enxame Pydantic AI (não tem `deps_type`/
`RunContext`/`Agent`), é a camada de transporte HTTP que expõe os agentes
já existentes (Princípio IV, N/A direto). Dividido em `app.py` (bootstrap/
metadados), `errors.py` (corpo de erro + handlers) e `routes.py` (as 5
rotas) por serem responsabilidades pequenas mas distintas o bastante para
não colidir num único arquivo grande (Princípio III) — diferente das specs
de agente anteriores (um único arquivo por agente), aqui há de fato três
preocupações distintas (bootstrap, erro, rotas) que crescem
independentemente conforme mais rotas/handlers forem adicionados no
futuro.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| N/A | N/A | Nenhuma violação identificada nesta feature. |
