# Implementation Plan: Orchestrator Agent (Harness) e agendamento (SPEC-015)

**Branch**: `015-orchestrator-agent-scheduling` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-orchestrator-agent-scheduling/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Um único módulo (`orchestrator_agent.py`) que coordena os seis agentes já
implementados de ponta a ponta — Scraper → Extractor (sequencial), depois
{Compliance Analyzer, Knowledge Builder} em paralelo (`asyncio.gather`),
depois Conformance Validator, depois Report Consolidator — com política de
falha por etapa (fatal/degradável/ignorável), um contexto compartilhado
(`PipelineContext`: settings, stores, cliente HTTP, `correlation_id` único
por execução), e um `PipelineResult` (SPEC-002) estendido aditivamente com
métricas por etapa. O mesmo handler (`run_pipeline`) é chamado tanto pelo
disparo ad-hoc via CLI (`make run`) quanto pelo `APScheduler` (cron
configurável por variável de ambiente) — nunca dois caminhos de entrada
divergentes — protegido por um lock em processo que rejeita execuções
sobrepostas. Um snippet de IaC do EventBridge (Terraform) documenta o
caminho de produção sem implementá-lo. O módulo é um harness de
orquestração puro (sem `pydantic_ai.Agent` próprio) — a "delegação
agente-para-agente via chamada de ferramenta" (FR-007) é satisfeita
apontando para o mecanismo de tool-calling MCP já existente no Scraper
Agent (SPEC-007/008), não uma nova construção.

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `apscheduler>=3.10` — **primeira introdução real**
como dependência (já constava na stack técnica obrigatória da constituição,
nenhuma spec anterior a usou, mesma situação do FastAPI na SPEC-013); todos
os seis módulos de agente já existentes (`scraper_agent`, `extractor_agent`,
`compliance_analyzer_agent`, `conformance_validator_agent`,
`knowledge_builder_agent`, `report_consolidator_agent`); `pix_compliance.
object_store`/`vector_store` (SPEC-006); `pix_compliance.logging`
(`bind_run_correlation_id`, SPEC-001); `mcp_servers.scraper_sse` (para
subir o servidor MCP em processo, mesmo padrão de
`tests/test_scraper_agent.py::running_mcp_server`)

**Storage**: Nenhuma tabela/schema novo. O log de evidência de uma execução
completa é salvo em `docs/evidence/pipeline-run.log` (FR-011) — arquivo de
texto, não um mecanismo de persistência estruturada.

**Testing**: pytest, `LLM_PROVIDER=offline` com `FunctionModel`/`TestModel`
por etapa (mesmo padrão já usado em cada agente individualmente); testes de
falha injetada usam um `model`/dependência substituída para simular erro em
uma etapa específica; teste de lock dispara duas chamadas de `run_pipeline`
concorrentes (`asyncio.gather`) e verifica que a segunda é rejeitada; teste
de scheduler usa um intervalo curto (segundos, via a mesma variável de
ambiente configurável) em vez do intervalo literal de "1 minuto" do SC-005
— esse cenário específico é verificado manualmente via `quickstart.md`, não
esperado num teste automatizado (mesmo padrão já usado para o Swagger da
SPEC-013).

**Target Platform**: Linux server (container Docker Compose, mesmo alvo do
restante do projeto); scheduler roda no mesmo processo Python de longa
duração (não um processo separado).

**Project Type**: Single project — novo módulo
`src/pix_compliance/agents/orchestrator_agent.py`

**Performance Goals**: Sem meta de throughput própria — uma execução
completa do pipeline por vez (o próprio lock, FR-010, garante isso).

**Constraints**: `PipelineResult` (SPEC-002) MUST ser estendido apenas
aditivamente (novo campo, nenhum campo existente alterado — Princípio VI);
o mesmo handler MUST ser chamado tanto pelo CLI quanto pelo scheduler
(FR-008); nenhuma execução distribuída, fila de mensageria, ou deploy real
na AWS (FR-012).

**Scale/Scope**: Um módulo de orquestração, um novo modelo Pydantic
aditivo (`EtapaMetric`), um snippet de IaC, um log de evidência.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  N/A direto: este módulo não invoca LLM diretamente — delega a cada
  agente já implementado, cada um já correto quanto a este princípio.
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS.
  Nenhuma abstração especulativa nova — `PipelineContext` é uma classe
  concreta (não `Protocol`), existe porque há uma necessidade real e
  imediata (compartilhar dependências entre as seis chamadas de agente na
  mesma execução), não especulação de futuro. O lock é em processo
  (`asyncio.Lock`), não uma solução distribuída — execução distribuída está
  explicitamente fora de escopo (FR-012).
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS. Este é
  o próprio racional já citado na constituição: orquestração e agendamento
  vivem juntos no mesmo módulo, porque ambos giram em torno do mesmo
  entrypoint (`run_pipeline`).
- **Princípio IV (Responsabilidade única por agente / SRP)** — N/A direto
  para este módulo especificamente: ele não decide entre múltiplos papéis
  de domínio (extrair vs. categorizar) — sua única responsabilidade é
  orquestrar; cada agente chamado mantém sua própria responsabilidade
  única, inalterada.
- **Princípio V (Guardrail é ponto único e obrigatório)** — N/A direto: o
  texto que trafega para cada LLM já passa por `guard()` dentro do agente
  correspondente (Extractor, Compliance Analyzer, Conformance Validator);
  este módulo não compõe nenhum prompt por conta própria.
- **Princípio VI (Contrato antes de comportamento)** — PASS, com uma
  extensão aditiva explícita e documentada: `PipelineResult` (SPEC-002)
  ganha um novo campo `etapas: list[EtapaMetric]` — nenhum campo existente
  é removido ou redefinido (ver data-model.md).
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês; comentários/docstrings em português explicando o porquê de cada
  escolha de padrão de orquestração (sequencial vs. paralelo), não "porque
  sim".
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. O log
  completo de uma execução real é salvo em `docs/evidence/pipeline-run.log`
  como parte do processo de implementação (FR-011), não uma tarefa avulsa
  depois.
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, requisito explícito da spec,
  incluindo os testes de falha degradável/fatal e de disputa de lock.

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` confirma que `EtapaMetric`/a
extensão de `PipelineResult` são as únicas mudanças de contrato, ambas
aditivas. `contracts/orchestrator.md` confirma que nenhuma abstração nova
além de `PipelineContext` (classe concreta) é introduzida. Gates
permanecem PASS.

## Project Structure

### Documentation (this feature)

```text
specs/015-orchestrator-agent-scheduling/
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
├── models.py                          # já existe (SPEC-002) — PipelineRequest/PipelineResult; PipelineResult ganha campo aditivo `etapas` nesta feature; EtapaMetric NOVO
├── logging.py                          # já existe (SPEC-001) — bind_run_correlation_id() reaproveitado
├── object_store.py / vector_store.py   # já existem (SPEC-006)
└── agents/
    ├── scraper_agent.py, extractor_agent.py, compliance_analyzer_agent.py,
    │   conformance_validator_agent.py, knowledge_builder_agent.py,
    │   report_consolidator_agent.py       # já existem — orquestrados, não alterados
    └── orchestrator_agent.py               # NOVO — PipelineContext, StepPolicy, run_pipeline(), start_scheduler(), lock, CLI

mcp_servers/scraper_sse/                 # já existe (SPEC-007) — servidor MCP subido em processo pelo Orchestrator (mesmo padrão do fixture de teste), não alterado

docs/
├── evidence/
│   └── pipeline-run.log                # NOVO — log completo de uma execução real, gerado durante a implementação (FR-011)
└── aws/
    └── eventbridge-schedule.tf          # NOVO — snippet de IaC (Terraform), documentando o caminho de produção sem implementá-lo

Makefile                                 # `run` atualizado para invocar orchestrator_agent (hoje aponta para pix_compliance.logging, placeholder da SPEC-001)

tests/
└── test_orchestrator_agent.py           # NOVO — escrito e confirmado falho ANTES de orchestrator_agent.py (Princípio IX)
```

**Structure Decision**: Projeto único (Option 1). `orchestrator_agent.py`
vive no mesmo pacote `src/pix_compliance/agents/` dos seis agentes que
orquestra, por consistência organizacional — mas não instancia
`pydantic_ai.Agent`: não há julgamento de LLM na decisão de "qual etapa
rodar quando" (isso é fluxo de controle determinístico), mesma situação já
estabelecida para Knowledge Builder (SPEC-012) e Report Consolidator
(SPEC-014). Orquestração e agendamento vivem no mesmo arquivo (não dois
módulos separados) por serem, como a própria constituição já registra,
"duas responsabilidades pequenas e fortemente relacionadas" girando em
torno do mesmo entrypoint (Princípio III).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| N/A | N/A | Nenhuma violação identificada nesta feature. |
