# Implementation Plan: Testes e observabilidade (SPEC-017)

**Branch**: `017-testes-observabilidade` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-testes-observabilidade/spec.md`

## Summary

Consolidação, não construção: auditar a suíte de testes já existente
(escrita spec a spec desde SPEC-001, seguindo o Princípio IX), confirmar
que ela já roda offline, e fechar as lacunas reais encontradas — um teste
ponta a ponta que amarre Orchestrator + todos os agentes + API (hoje
inexistente porque `POST /runs` não delega a `run_pipeline`), fixtures
`pytest` duplicadas entre módulos de teste, propagação de `correlation_id`
até o servidor MCP do Scraper (hoje sem logging algum), contadores
agregados por etapa do pipeline, e um workflow de CI em GitHub Actions.
Abordagem técnica: nenhuma ferramenta nova fora do stack já estabelecido
(`pytest`+`pytest-cov`, `structlog`, GitHub Actions), extensão aditiva de
`EtapaMetric` em vez de um tipo de métrica novo, e remoção da
implementação de pipeline duplicada em `api/routes.py` em favor de
`run_pipeline` já existente — simplificação, não nova abstração.

## Technical Context

**Language/Version**: Python 3.11+ (já fixado em `pyproject.toml`).

**Primary Dependencies**: `pytest` (já presente); `pytest-cov` (novo, dev-only,
Decisão 6 do research.md); `structlog` (já presente, reaproveitado sem
mudança de mecanismo); GitHub Actions (`actions/checkout`, `actions/setup-python`,
sem dependência de terceiros adicional).

**Storage**: N/A para esta feature — os testes de integração já existentes
contra `postgres`/`minio` reais (SPEC-006) não mudam de mecanismo, apenas
são confirmados/mantidos.

**Testing**: `pytest` (já estabelecido); `pytest-cov` para o relatório de
cobertura (FR-009); nenhum framework de teste novo introduzido.

**Target Platform**: Mesmo alvo do restante do projeto — execução local
(dev), CI (Linux runner do GitHub Actions), containers (SPEC-016).

**Project Type**: Single project (mesma estrutura já estabelecida desde a
SPEC-001) — esta feature não adiciona um segundo projeto/pacote.

**Performance Goals**: N/A — explicitamente fora de escopo (FR-010, sem
testes de carga/performance).

**Constraints**: A suíte completa (`make test`) MUST continuar rodando sem
rede e sem credenciais AWS (FR-001); o workflow de CI MUST rodar sem
nenhum secret AWS configurado, pela mesma razão.

**Scale/Scope**: Consolidação sobre ~194 testes já existentes (16 módulos
de teste) e 7 agentes/módulos de pipeline já implementados (SPEC-001 a
SPEC-016) — sem introdução de escopo de aplicação novo.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Bedrock é o caminho padrão, nunca um fallback silencioso** — PASS.
  Esta feature reforça isso: audita que `LLM_PROVIDER=offline` permanece
  isolado em `tests/doubles/` e nunca é caminho de produção; nenhum código
  de `src/` passa a depender dele.
- **II. Abstração exige justificativa concreta (YAGNI)** — PASS. Nenhuma
  interface/`Protocol` nova. A única mudança estrutural é a remoção de uma
  implementação duplicada (`_run_pipeline_sync`) em favor da já existente
  (`run_pipeline`) — reduz abstração/duplicação, não adiciona.
- **III. Simplicidade sobre segmentação (KISS)** — PASS. Fixtures
  consolidadas no único `conftest.py` já existente (não um pacote novo de
  fixtures); CI como um único workflow/job (não múltiplos workflows);
  `EtapaMetric` estendido (não um tipo de métrica paralelo).
- **IV. Responsabilidade única por agente (SRP)** — PASS, não afetado:
  nenhum agente novo, nenhum agente existente ganha uma segunda
  responsabilidade.
- **V. Guardrail é ponto único e obrigatório** — PASS. A auditoria de
  cobertura de `guardrails.py` (FR-003/FR-009) reforça este princípio em
  vez de contorná-lo; nenhuma mudança ao próprio guardrail é necessária a
  priori (só cobertura de teste, a confirmar na auditoria de
  implementação).
- **VI. Contrato antes de comportamento** — PASS. A mudança de contrato de
  `POST /runs` (delegar a `run_pipeline`) é documentada em
  `contracts/observability.md` antes de qualquer código ser alterado,
  seguindo o mesmo padrão das specs anteriores.
- **VII. Comentários e nomenclatura** — PASS. Aplicado nos artefatos desta
  spec (identificadores em inglês no código a escrever, comentários em
  português); reforçado explicitamente pela spec de origem (justificar por
  que cobertura prioriza modelos/guardrails).
- **VIII. Evidência é entregável, não subproduto** — PASS. Todos os
  critérios de aceite (SC-001 a SC-004) já são comandos executáveis,
  mantidos como fornecidos.
- **IX. Testes escritos antes da implementação, a partir do contrato,
  nunca do código** — PASS, com a ordem explicitamente invertida e
  documentada na própria spec (Assumptions): auditar primeiro (o que já
  existe), depois escrever os testes que faltam (incluindo os que devem
  falhar contra o `POST /runs` atual antes da correção), só então ajustar
  código de produção. `tasks.md` deve refletir essa ordem por user story.

**Nenhuma violação a justificar em Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/017-testes-observabilidade/
├── plan.md              # Este arquivo
├── research.md          # Fase 0 — auditoria e decisões
├── data-model.md         # Fase 1 — extensão de EtapaMetric, formatos de log/cobertura
├── quickstart.md         # Fase 1 — cenários de validação executáveis
├── contracts/
│   └── observability.md  # Fase 1 — contrato revisado de POST /runs, eventos de log, CI
└── tasks.md               # Fase 2 (/speckit-tasks — não criado por este comando)
```

### Source Code (repository root)

```text
src/pix_compliance/
├── models.py                          # EtapaMetric ganha campo `contadores` (aditivo)
├── logging.py                          # sem mudança de mecanismo (contextvars mantido)
├── agents/
│   └── orchestrator_agent.py           # _run_step passa a logar contadores agregados por etapa
└── api/
    └── routes.py                       # POST /runs passa a delegar a run_pipeline; _run_pipeline_sync removido

mcp_servers/scraper_sse/
└── server.py (ou equivalente)          # ganha logging estruturado mínimo + aceita correlation_id

tests/
├── conftest.py                         # recebe as fixtures consolidadas (_settings, store, _required_env, _free_port)
├── test_orchestrator_agent.py          # já cobre Orchestrator + 6 agentes via run_pipeline (confirmado na auditoria)
├── test_api.py                         # ganha teste de POST /runs cobrindo as 6 etapas (hoje cobre só 4)
├── test_models.py                      # ganha cobertura do campo `contadores` de EtapaMetric
├── test_guardrails.py                  # revisado/complementado (FR-003)
├── test_logging.py                     # ganha teste de propagação de correlation_id ponta a ponta
└── test_scraper_mcp_server.py          # ganha teste de logging estruturado + correlation_id no servidor MCP

.github/workflows/
└── ci.yml                              # novo — lint + suíte a cada push/PR

pyproject.toml                          # pytest-cov adicionado a [project.optional-dependencies].dev
Makefile                                # sem mudança de contrato (make test/make lint já existem)
```

**Structure Decision**: Mesma estrutura de projeto único já estabelecida
desde a SPEC-001 (`src/pix_compliance/`, `tests/`, `mcp_servers/`) — esta
feature não introduz um diretório de topo novo além de `.github/workflows/`
(padrão do GitHub Actions, não uma escolha arquitetural do projeto).

## Complexity Tracking

*Sem violações do Constitution Check — seção não aplicável.*
