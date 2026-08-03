# Implementation Plan: Report Consolidator Agent (SPEC-014)

**Branch**: `014-report-consolidator-agent` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-report-consolidator-agent/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Consolida o resultado do pipeline de compliance em dois artefatos (JSON no
formato `ReportOutput`, SPEC-002; PDF via `reportlab` com cinco seções
obrigatórias) e publica esse resultado via cliente HTTP na API FastAPI
(SPEC-013), cumprindo literalmente o requisito da seção 2 do desafio
original ("invocar uma API FastAPI como cliente HTTP para ação final"). A
URL da API vem exclusivamente de `settings.api_url` (campo já existente
desde a SPEC-001), nunca de um literal no código. Quando a publicação HTTP
falha (API indisponível), os artefatos já gerados permanecem persistidos
(localmente e no `ObjectStore`, SPEC-006) e o erro é logado de forma clara
— degradação controlada, não falha total. Como as dependências declaradas
(SPEC-011 Conformance Validator, SPEC-013 API FastAPI) ainda não existem
como código neste repositório, este módulo é projetado e testado contra o
contrato já congelado de `ConformanceReport`/`ReportOutput` (SPEC-002) e um
servidor HTTP mock local, sem depender da implementação real de nenhuma das
duas (ver research.md, Decisão 0).

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `reportlab>=4.0` (PDF, já declarado em
`pyproject.toml`), `httpx>=0.27` (cliente HTTP, já declarado, usado também
transitivamente por MCP/Pydantic AI), `pix_compliance.object_store`
(`ObjectStore`, SPEC-006, reaproveitado sem alteração),
`pix_compliance.models` (`ConformanceReport`, `ReportOutput`, `NormativoItem`,
`RegraExtraida` — já existentes, SPEC-002), `structlog` (log estruturado do
erro de publicação, já usado em todo o projeto)

**Storage**: `ObjectStore` (SPEC-006) para os artefatos binários (JSON/PDF);
disco local (diretório de saída determinístico) como cópia de trabalho e
fallback de degradação controlada quando a publicação HTTP falha — nenhuma
tabela/schema novo

**Testing**: pytest; testes de geração de JSON/PDF rodam localmente sem
dependência externa; teste de publicação HTTP roda contra um servidor mock
local (`pytest-httpserver`-like via `http.server`/`respx`, a decidir em
research.md) em vez da API FastAPI real (SPEC-013 ainda não implementada);
teste de degradação simula erro de conexão (`httpx.ConnectError`) sem
depender de nenhum serviço externo de fato indisponível

**Target Platform**: Linux server (container Docker Compose, mesmo alvo do
restante do projeto)

**Project Type**: Single project — novo módulo
`src/pix_compliance/agents/report_consolidator_agent.py`, no mesmo pacote
`agents/` das specs anteriores

**Performance Goals**: Sem meta de throughput própria — geração de relatório
é uma operação de fim de pipeline, executada uma vez por execução completa,
não em lote/concorrência

**Constraints**: A URL da API MUST vir exclusivamente de `settings.api_url`
— nenhum literal de URL no código-fonte deste agente (FR-005); falha na
publicação HTTP MUST NOT propagar exceção não tratada nem descartar os
artefatos já gerados (FR-006); este agente MUST NOT recategorizar/revalidar
dados de features anteriores (FR-010)

**Scale/Scope**: Um módulo de consolidação/publicação, nenhuma entidade de
domínio nova (reaproveita `ConformanceReport`/`ReportOutput`/`NormativoItem`/
`RegraExtraida` já existentes), uma skill (`SKILL.md`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  N/A direto: esta feature não invoca nenhum LLM (chat ou embeddings) — é
  puramente consolidação de dados já produzidos e publicação HTTP/storage.
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS.
  Nenhuma abstração nova: `ObjectStore` (SPEC-006) já é `Protocol` por razão
  própria e preexistente; o cliente HTTP usa `httpx` diretamente, sem
  `Protocol` especulativo (FR não pede uma segunda implementação de cliente
  HTTP).
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS. Geração
  de JSON, geração de PDF, upload ao `ObjectStore` e publicação HTTP vivem no
  mesmo módulo — passos pequenos e fortemente relacionados do mesmo fluxo
  ("consolidar e publicar").
- **Princípio IV (Responsabilidade única por agente / SRP)** — PASS. Este
  agente consolida e publica; não recategoriza nem revalida dados já
  produzidos pelo Compliance Analyzer/Conformance Validator (FR-010).
- **Princípio V (Guardrail é ponto único e obrigatório)** — N/A direto: o
  texto que compõe o relatório (enunciados de regras, resumos) já passou por
  `guard()` em features anteriores (Extractor/Compliance Analyzer/
  Conformance Validator) antes de chegar aqui; esta feature não envia texto
  a nenhum LLM — apenas grava/publica dados já estruturados e já
  sanitizados.
- **Princípio VI (Contrato antes de comportamento)** — PASS. `ConformanceReport`/
  `ReportOutput` (SPEC-002) já existem e são o contrato de entrada/saída
  desta feature; a Fase 1 (`data-model.md`) documenta apenas a composição
  desses contratos com `NormativoItem`/`RegraExtraida` (necessários para as
  seções do PDF), sem alterar nenhum modelo já congelado.
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês; comentários/docstrings em português explicando o porquê da
  degradação controlada e por que a URL nunca é hardcoded.
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. Todos
  os critérios de aceite são comandos executáveis (JSON/PDF gerados
  corretamente, degradação controlada com log claro, ausência de literal de
  URL verificável por inspeção/teste estrutural).
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, requisito explícito da spec,
  incluindo o teste de degradação controlada (API indisponível, mock de
  erro de conexão).

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` confirma que nenhum modelo Pydantic
novo é introduzido — apenas a composição de `ConformanceReport`/
`NormativoItem`/`RegraExtraida` já existentes como entrada da função de
consolidação. `contracts/report_consolidator_agent.md` confirma que o
cliente HTTP usa `httpx` diretamente, sem abstração nova. Gates permanecem
PASS.

## Project Structure

### Documentation (this feature)

```text
specs/014-report-consolidator-agent/
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
├── models.py                          # já existe (SPEC-002) — ConformanceReport, ReportOutput, NormativoItem, RegraExtraida reaproveitados
├── object_store.py                     # já existe (SPEC-006) — ObjectStore reaproveitado
├── config.py                           # já existe (SPEC-001) — Settings.api_url reaproveitado
└── agents/
    ├── scraper_agent.py                  # já existe (SPEC-008)
    ├── extractor_agent.py                 # já existe (SPEC-009)
    ├── compliance_analyzer_agent.py         # já existe (SPEC-010)
    ├── knowledge_builder_agent.py           # já existe (SPEC-012)
    └── report_consolidator_agent.py          # NOVO — generate_json(), generate_pdf(), publish_to_api(), consolidate_and_publish(), CLI

skills/
├── scraper-skill/SKILL.md                # já existe
├── extractor-skill/SKILL.md               # já existe
├── compliance-analyzer-skill/SKILL.md       # já existe
├── knowledge-builder-skill/SKILL.md         # já existe
└── report-consolidator-skill/
    └── SKILL.md                            # NOVO — mesmo formato de 4 seções, com nota explícita sobre o requisito literal do desafio

tests/
└── test_report_consolidator_agent.py       # NOVO — escrito e confirmado falho ANTES de report_consolidator_agent.py (Princípio IX), incluindo teste de degradação controlada
```

**Structure Decision**: Projeto único (Option 1). `report_consolidator_agent.py`
vive no mesmo pacote `src/pix_compliance/agents/` das specs anteriores, por
consistência organizacional do enxame — não instancia `pydantic_ai.Agent`
(mesma situação da SPEC-012, Knowledge Builder): não há decisão de LLM
envolvida, apenas geração de artefatos determinísticos e I/O (arquivo local,
`ObjectStore`, HTTP). Geração de JSON, geração de PDF, upload e publicação
HTTP vivem no mesmo arquivo por serem passos pequenos e fortemente
relacionados do mesmo fluxo (Princípio III) — não se cria um submódulo
`pdf_renderer.py` separado para a montagem do PDF, dado o volume de lógica
(cinco seções simples sobre dados já estruturados).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| N/A | N/A | Nenhuma violação identificada nesta feature. |
