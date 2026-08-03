# Implementation Plan: Conformance Validator Agent (SPEC-011)

**Branch**: `011-conformance-validator-agent` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-conformance-validator-agent/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Compara semanticamente conjuntos de `RegraExtraida` (SPEC-002, produzidos
pelo Compliance Analyzer, SPEC-010) entre a versão atual e a versão anterior
imediata do mesmo normativo (agrupadas por `NormativoItem.numero`, ordenadas
por `versao`), classificando cada regra em `novo`, `alterado`, `revogado` ou
`conforme` (`StatusConformidade`, SPEC-002 — ver spec.md, Assumptions, para
o mapeamento do termo "inalterado" da spec original), com `delta`
legível, `recomendacao` acionável e `severidade` por item. Reaproveita o
mesmo padrão estrutural de agente Pydantic AI das SPEC-008/009/010
(`deps_type`, `RunContext`, `output_type`, `guard()` antes de qualquer
chamada ao LLM). Quando não há versão anterior de um normativo, a
classificação é `novo` para todas as suas regras, resolvida
deterministicamente em código, **sem** chamada ao LLM (não há nada a
comparar). Produz `ConformanceReport` (SPEC-002) agregando os itens de todo
o corpus processado.

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `pydantic_ai.Agent` (mesmo padrão SPEC-008/009/010),
`pix_compliance.guardrails.guard()` (SPEC-004, reaplicado sobre o texto de
cada regra antes de compor o prompt), `pix_compliance.models`
(`RegraExtraida`, `NormativoItem`, `ConformanceItem`, `ConformanceReport`,
`StatusConformidade` — já existentes, SPEC-002), `pix_compliance.llm_provider`
(dispatch bedrock/offline já estabelecido, SPEC-005)

**Storage**: N/A — esta feature não persiste nada por conta própria; recebe
dados já produzidos por features anteriores e devolve um `ConformanceReport`
em memória, para o Report Consolidator (SPEC-014, revisão futura fora de
escopo) consumir

**Testing**: pytest, com `LLM_PROVIDER=offline` e `FunctionModel` (Pydantic
AI) cujas funções de decisão leem o conteúdo real das `RegraExtraida`
recebidas no prompt e retornam a classificação/deltas correspondentes aos
três pares documentados em `fixtures/EXPECTED_DELTAS.md` — mesmo padrão já
usado em SPEC-010 (prova a orquestração do agente contra um resultado
conhecido de antemão, não a qualidade de julgamento de um LLM real, que
está fora do escopo de um teste automatizado determinístico; ver
research.md, Decisão 1). Arquivo de teste nomeado `tests/test_conformance.py`
por exigência explícita da spec (não o padrão `test_<feature>_agent.py`).

**Target Platform**: Linux server (container Docker Compose, mesmo alvo do
restante do projeto)

**Project Type**: Single project — novo módulo
`src/pix_compliance/agents/conformance_validator_agent.py`, no mesmo pacote
`agents/` das specs anteriores

**Performance Goals**: Sem meta de throughput própria — mesmo padrão de
processamento em lote já usado no Compliance Analyzer (SPEC-010,
`asyncio.Semaphore`), reaproveitado aqui para limitar chamadas simultâneas
ao LLM durante a comparação de múltiplos pares de normativos

**Constraints**: A comparação MUST ser semântica (pelo significado da
regra), não um diff textual bruto (FR-001); um normativo sem versão
anterior MUST resultar em `novo` para suas regras, sem exceção (FR-006); os
três pares já existentes em `fixtures/normativos.json` MUST produzir
exatamente os deltas documentados em `fixtures/EXPECTED_DELTAS.md` (FR-010)

**Scale/Scope**: Um módulo de comparação/classificação, nenhuma entidade de
domínio nova (reaproveita `RegraExtraida`/`ConformanceItem`/
`ConformanceReport`/`StatusConformidade` já existentes), uma skill
(`SKILL.md`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  PASS. Reaproveita o mesmo dispatch `_build_model(settings)` já
  estabelecido em `compliance_analyzer_agent.py` (SPEC-010) — `TestModel`/
  `FunctionModel` apenas em teste, `AnthropicModel`/`AnthropicProvider` com
  `AsyncAnthropicBedrock` em produção.
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS.
  Nenhuma abstração nova — a classificação "sem versão anterior" é resolvida
  com um `if` simples em código, não uma segunda estratégia de comparação
  abstraída atrás de uma interface.
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS.
  Agrupamento por `numero`/`versao`, comparação semântica via LLM, e
  montagem do `ConformanceReport` vivem no mesmo módulo — passos pequenos e
  fortemente relacionados do mesmo fluxo ("comparar e classificar").
- **Princípio IV (Responsabilidade única por agente / SRP)** — PASS. Este
  agente compara e classifica; não gera PDF (SPEC-014) nem publica em API
  (SPEC-014) — FR-008/FR-009.
- **Princípio V (Guardrail é ponto único e obrigatório)** — PASS.
  `guard()` é reaplicado sobre o `enunciado` de cada `RegraExtraida` antes
  de compor o prompt enviado ao LLM — mesma redundância deliberada de
  defesa em profundidade já documentada no Compliance Analyzer (SPEC-010).
- **Princípio VI (Contrato antes de comportamento)** — PASS. `RegraExtraida`/
  `ConformanceItem`/`ConformanceReport`/`StatusConformidade` (SPEC-002) já
  existem e são o contrato de entrada/saída desta feature, sem alteração —
  ver spec.md, Assumptions, para o mapeamento explícito "inalterado" →
  `conforme` (nenhum membro novo adicionado ao enum já congelado).
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês; comentários/docstrings em português explicando o porquê do diff
  ser semântico (não textual bruto) e por que um normativo sem versão
  anterior é `novo`, não um erro.
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. Todos
  os critérios de aceite são comandos executáveis, incluindo a comparação
  exata contra `fixtures/EXPECTED_DELTAS.md` (o critério mais forte já
  produzido no projeto até aqui, por ter resultado esperado documentado de
  antemão).
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, requisito explícito da spec. Testes
  para os três pares documentados e para o caso "sem versão anterior" são
  escritos e confirmados como falhos antes de
  `conformance_validator_agent.py` existir.

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` confirma que nenhum modelo Pydantic
novo é introduzido — apenas a convenção de agrupamento por `numero`/`versao`
e a fórmula determinística de `resumo`/`criticidade_maxima` do
`ConformanceReport` (calculadas em código, não pelo LLM, para manter esses
dois campos agregados sempre consistentes com os itens reais, sem depender
de o LLM "somar corretamente"). `contracts/conformance_validator_agent.md`
confirma que nenhuma abstração nova é introduzida. Gates permanecem PASS.

## Project Structure

### Documentation (this feature)

```text
specs/011-conformance-validator-agent/
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
├── models.py                          # já existe (SPEC-002) — RegraExtraida, ConformanceItem, ConformanceReport, StatusConformidade reaproveitados
├── guardrails.py                       # já existe (SPEC-004) — guard() reaproveitado
├── llm_provider.py                     # já existe (SPEC-005) — dispatch bedrock/offline reaproveitado
└── agents/
    ├── scraper_agent.py                  # já existe (SPEC-008)
    ├── extractor_agent.py                 # já existe (SPEC-009)
    ├── compliance_analyzer_agent.py         # já existe (SPEC-010) — mesmo padrão de agente reaproveitado
    ├── knowledge_builder_agent.py           # já existe (SPEC-012)
    ├── report_consolidator_agent.py          # já existe (SPEC-014) — revisão futura fora de escopo desta spec
    └── conformance_validator_agent.py         # NOVO — compare_regras(), build_conformance_report(), CLI

skills/
├── scraper-skill/SKILL.md                # já existe
├── extractor-skill/SKILL.md               # já existe
├── compliance-analyzer-skill/SKILL.md       # já existe
├── knowledge-builder-skill/SKILL.md         # já existe
├── report-consolidator-skill/SKILL.md       # já existe
└── conformance-validator-skill/
    └── SKILL.md                            # NOVO — mesmo formato de 4 seções

tests/
└── test_conformance.py                   # NOVO — nome exigido explicitamente pela spec; escrito e confirmado falho ANTES de conformance_validator_agent.py (Princípio IX)
```

**Structure Decision**: Projeto único (Option 1). `conformance_validator_agent.py`
vive no mesmo pacote `src/pix_compliance/agents/` das specs anteriores, por
consistência organizacional do enxame, e reaproveita integralmente o padrão
`Agent`/`deps_type`/`RunContext`/`output_type` já estabelecido em
`compliance_analyzer_agent.py` (SPEC-010) — mesmo tipo de tarefa (julgamento
via LLM a partir de texto estruturado). Agrupamento de versões,
classificação, e montagem do relatório vivem no mesmo arquivo por serem
passos pequenos e fortemente relacionados do mesmo fluxo (Princípio III) —
não se cria um submódulo `version_matcher.py` separado para o agrupamento
por `numero`/`versao`, dado o volume de lógica (poucas linhas de
`itertools.groupby`/ordenação).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| N/A | N/A | Nenhuma violação identificada nesta feature. |
