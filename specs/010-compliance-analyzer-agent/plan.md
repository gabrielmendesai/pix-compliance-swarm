# Implementation Plan: Compliance Analyzer Agent (SPEC-010)

**Branch**: `010-compliance-analyzer-agent` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-compliance-analyzer-agent/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Terceiro agente Pydantic AI do enxame, reaproveitando o mesmo padrão
estrutural das SPEC-008/009 (`deps_type`, `RunContext`, `output_type`,
tratamento de erro tipado, dispatch de modelo por `settings.llm_provider`).
Recebe `NormativoItem` já validados (SPEC-009) e categoriza cada regra de
compliance neles contida em uma das seis dimensões do desafio original
(participantes, tarifas, liquidação, segurança, SLA, interoperabilidade),
com um system prompt que define operacionalmente cada categoria para reduzir
ambiguidade. Processa lotes de `NormativoItem` concorrentemente, com um
`asyncio.Semaphore` limitando o número de chamadas simultâneas ao LLM a um
valor configurável (`Settings`) — validado por instrumentação, não apenas
pelo resultado final. Cada `RegraExtraida` produzida carrega um score de
confiança (`Score`, já existente) e um novo campo booleano explícito
(`revisao_humana_necessaria`) quando o score cai abaixo de um limiar
configurável. `guard()` (SPEC-004) é reaplicado sobre o texto de entrada
antes de qualquer chamada ao LLM deste agente — redundância deliberada de
defesa em profundidade, não custo desnecessário.

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `pydantic-ai-slim` (`Agent`, `RunContext`,
`AnthropicModel`/`AnthropicProvider`/`AsyncAnthropicBedrock`, `TestModel`/
`FunctionModel` para teste — mesmo padrão de `_build_model` já estabelecido
em `scraper_agent.py`/`extractor_agent.py`), `asyncio` (stdlib —
`Semaphore`/`gather` para o processamento em lote concorrente, sem
dependência nova), `pix_compliance.guardrails.guard()` (SPEC-004),
`structlog` (log estruturado)

**Storage**: Nenhuma persistência própria desta feature — consome
`NormativoItem` já em memória (produzidos pelo Extractor Agent, SPEC-009) e
devolve `list[RegraExtraida]` em memória; a persistência de regras extraídas
fica para uma feature futura, se necessária

**Testing**: pytest, com `FunctionModel` determinístico (nunca uma chamada
real ao Bedrock), incluindo um teste que usa um `FunctionModel` assíncrono
com `asyncio.sleep` e um contador de chamadas em andamento (protegido por
`asyncio.Lock`) para comprovar, por instrumentação, que o pico de
concorrência nunca excede o limite configurado — validado em spike manual
(não apenas o resultado final do lote)

**Target Platform**: Linux server (container Docker Compose, mesmo alvo do
restante do projeto)

**Project Type**: Single project — novo módulo
`src/pix_compliance/agents/compliance_analyzer_agent.py`, no mesmo pacote
`agents/` das SPEC-008/009

**Performance Goals**: O limite de concorrência prioriza custo/rate-limit do
Bedrock sobre velocidade máxima de processamento do lote — não há meta de
throughput própria além de "nunca exceder o limite configurado"

**Constraints**: O limite de concorrência de chamadas ao LLM é configurável
via `Settings` (não fixo no código); o limiar de confiança para sinalização
de revisão humana também é configurável; `guard()` é reaplicado sem exceção,
mesmo com entrada supostamente já limpa; este agente não compara versões
nem gera relatório (Princípio IV)

**Scale/Scope**: Um agente, um novo campo em `RegraExtraida`
(`revisao_humana_necessaria`), dois novos campos de configuração em
`Settings`, uma skill (`SKILL.md`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  PASS. Mesmo padrão de `_build_model` das SPEC-008/009: `AnthropicModel`/
  `AsyncAnthropicBedrock` em produção, `TestModel`/`FunctionModel` (da
  própria biblioteca Pydantic AI) apenas em teste, via `settings.llm_provider`.
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS.
  Nenhuma abstração nova: o limite de concorrência é um `asyncio.Semaphore`
  simples (construção da stdlib, não uma abstração própria do projeto); não
  há `Protocol` novo — não há uma segunda implementação de "como categorizar
  regras" neste projeto.
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS. System
  prompt, seleção de modelo, orquestração de lote com semáforo e a chamada
  ao guardrail vivem no mesmo módulo — responsabilidades pequenas e
  fortemente relacionadas (todas resolvem "como este agente categoriza um
  lote de `NormativoItem`"), sem segmentação prematura.
- **Princípio IV (Responsabilidade única por agente / SRP)** — PASS, é o
  próprio objetivo estrutural desta feature: o agente categoriza regras nas
  seis dimensões; não compara versões nem gera relatório (FR-008, FR-009) —
  essas responsabilidades pertencem a agentes futuros.
- **Princípio V (Guardrail é ponto único e obrigatório)** — PASS, reforçado
  por esta feature: `guard()` é reaplicado aqui mesmo com entrada
  supostamente já limpa (vinda do Extractor Agent, SPEC-009) — o ponto de
  aplicação obrigatório vale para todo caminho que toca um LLM, não apenas o
  primeiro da cadeia.
- **Princípio VI (Contrato antes de comportamento)** — PASS. O novo campo
  `revisao_humana_necessaria` em `RegraExtraida` e os novos campos de
  `Settings` são definidos na Fase 1 (`data-model.md`) antes de qualquer
  lógica do agente.
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês (`ComplianceAnalyzerAgentDeps`, `max_concurrent_llm_calls`);
  comentários/docstrings em português explicando o porquê — em particular,
  por que existe um limite de concorrência (custo e rate limit do Bedrock,
  não só performance) e por que o guardrail é reaplicado aqui.
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. Todos
  os critérios de aceite são comandos executáveis (cobertura das 6
  categorias, sinalização de baixa confiança, teste de concorrência por
  instrumentação).
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, requisito explícito da spec. Testes
  de categorização por categoria, sinalização de revisão humana, limite de
  concorrência (por instrumentação, não apenas resultado final) e
  reaplicação do guardrail são escritos e confirmados como falhos antes de
  `compliance_analyzer_agent.py` existir.

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` e `contracts/compliance_analyzer_agent.md`
confirmam que nenhuma abstração nova (`Protocol`) foi introduzida; o
`asyncio.Semaphore` é usado diretamente (stdlib), sem encapsulamento
especulativo; `RegraExtraida` ganha exatamente um campo novo
(`revisao_humana_necessaria`), sem alterar os já existentes. Gates
permanecem PASS.

## Project Structure

### Documentation (this feature)

```text
specs/010-compliance-analyzer-agent/
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
├── models.py                          # ATUALIZADO — RegraExtraida ganha revisao_humana_necessaria: bool
├── config.py                           # ATUALIZADO — compliance_analyzer_max_concurrency, compliance_analyzer_confidence_threshold
├── guardrails.py                        # já existe (SPEC-004) — guard() reaproveitado sem alteração
└── agents/
    ├── scraper_agent.py                  # já existe (SPEC-008)
    ├── extractor_agent.py                 # já existe (SPEC-009)
    └── compliance_analyzer_agent.py        # NOVO — ComplianceAnalyzerAgentDeps, build_compliance_analyzer_agent(),
                                            #        analyze_normativo(), analyze_batch() (semáforo), CLI

skills/
├── scraper-skill/SKILL.md               # já existe
├── extractor-skill/SKILL.md              # já existe
└── compliance-analyzer-skill/
    └── SKILL.md                           # NOVO — mesmo formato de 4 seções

tests/
└── test_compliance_analyzer_agent.py      # NOVO — escrito e confirmado falho ANTES de compliance_analyzer_agent.py (Princípio IX)
```

**Structure Decision**: Projeto único (Option 1). `compliance_analyzer_agent.py`
vive no mesmo pacote `src/pix_compliance/agents/` das SPEC-008/009 — mesmo
nível de responsabilidade (um agente por módulo). O processamento em lote
concorrente (`analyze_batch`, com semáforo) vive no mesmo arquivo do agente
individual (`analyze_normativo`), por serem passos do mesmo fluxo
("categorizar um ou mais `NormativoItem`"), não módulos separados —
segmentar isso fragmentaria visualmente uma responsabilidade única
(Princípio III).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| N/A | N/A | Nenhuma violação identificada nesta feature. |
