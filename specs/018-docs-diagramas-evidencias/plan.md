# Implementation Plan: Documentação, diagramas, skills e evidências (SPEC-018)

**Branch**: `018-docs-diagramas-evidencias` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-docs-diagramas-evidencias/spec.md`

## Summary

Feature inteiramente documental: expandir o README com uma camada de alto nível (visão
geral, arquitetura, instalação, "como executar", seção "Desenvolvimento e ferramentas",
mapeamento explícito dos 11 entregáveis do desafio original) sem descartar o conteúdo
técnico por feature já existente; criar três diagramas Mermaid (container C4, componente do
enxame com os três padrões de orquestração, integrações AWS); auditar os 6 `SKILL.md`
existentes e criar o sétimo (Orchestrator); criar `docs/spec-methodology.md` citando
nominalmente os dois desvios reais do Princípio IX já registrados no histórico de specs
(SPEC-011, SPEC-017); e reorganizar `docs/evidence/` separando o que já existe do que precisa
de coleta manual (screenshot/vídeo, fora de escopo desta spec). Abordagem: nenhum código de
aplicação novo — só arquivos Markdown/Mermaid, e a fonte da verdade dos 11 entregáveis é o
enunciado original do desafio, fornecido pelo usuário durante este planejamento e mapeado
item a item em research.md.

## Technical Context

**Language/Version**: N/A — feature documental, sem código de aplicação (Markdown + Mermaid).

**Primary Dependencies**: Nenhuma nova — Mermaid renderiza nativamente no GitHub, sem
biblioteca/ferramenta adicional.

**Storage**: N/A.

**Testing**: Não há suíte `pytest` para esta feature — verificação é a simulação manual do
Cenário 1 do quickstart (Princípio IX adaptado) e leitura direta dos artefatos
(`contracts/documentation-format.md`).

**Target Platform**: GitHub (renderização de README/diagramas Mermaid na interface web).

**Project Type**: Documental — nenhuma estrutura de projeto de código nova.

**Performance Goals**: N/A.

**Constraints**: README MUST permanecer navegável apesar do crescimento (seção de alto nível
no topo, conteúdo técnico por feature preservado abaixo, não removido) — evitar que a
"porta de entrada" nova fique perdida atrás de 476+ linhas de detalhe técnico já existentes.

**Scale/Scope**: 1 README expandido, 3 diagramas Mermaid, 1 `SKILL.md` novo + 6 auditados,
1 `docs/spec-methodology.md` novo, 1 `docs/evidence/README.md` novo (checklist).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Bedrock é o caminho padrão** — N/A, não afetado (feature documental).
- **II. Abstração exige justificativa concreta (YAGNI)** — PASS. Nenhuma abstração de código;
  o `SKILL.md` do Orchestrator reaproveita a estrutura de seções já validada pelos outros
  seis, em vez de inventar uma nova (research.md, Decisão 4).
- **III. Simplicidade sobre segmentação (KISS)** — PASS. Três diagramas com escopo distinto
  em vez de um genérico confuso (Decisão 3); `docs/evidence/` reorganizado com um único
  arquivo novo de checklist, não uma estrutura de pastas nova.
- **IV. Responsabilidade única por agente (SRP)** — N/A, não afetado.
- **V. Guardrail é ponto único e obrigatório** — N/A, não afetado.
- **VI. Contrato antes de comportamento** — PASS, aplicado ao domínio documental: o formato
  de cada artefato (`SKILL.md`, tabela de mapeamento, diagrama) é definido em
  `contracts/documentation-format.md` antes da escrita do conteúdo real.
- **VII. Comentários e nomenclatura** — PASS. Toda a documentação produzida é em português
  (convenção já usada em todo o projeto), conforme a spec exige explicitamente.
- **VIII. Evidência é entregável, não subproduto** — PASS, central a esta feature: o próprio
  objetivo é produzir os entregáveis de evidência exigidos pelo desafio (com a lacuna manual
  de screenshot/vídeo declarada explicitamente, não escondida).
- **IX. Testes escritos antes da implementação** — PASS, adaptado (spec.md, Assumptions):
  "teste" = simulação do Cenário 1 do quickstart, feita depois do README escrito, antes de
  fechar a spec — mesma lógica de "escrever o contrato antes, confirmar depois" adaptada a
  conteúdo não executável por `pytest`.

**Nenhuma violação a justificar em Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/018-docs-diagramas-evidencias/
├── plan.md                          # Este arquivo
├── research.md                      # Fase 0 — mapeamento dos 11 entregáveis, decisões de formato
├── data-model.md                    # Fase 1 — estrutura de cada artefato documental
├── quickstart.md                    # Fase 1 — cenários de verificação executáveis
├── contracts/
│   └── documentation-format.md      # Fase 1 — formato verificável de cada artefato
└── tasks.md                         # Fase 2 (/speckit-tasks — não criado por este comando)
```

### Source Code (repository root)

```text
README.md                            # Expandido: seção de alto nível nova antes do conteúdo por feature já existente

docs/
├── architecture.md                  # Já existe (ADRs) — pode ganhar referência cruzada aos novos diagramas
├── spec-methodology.md              # NOVO — metodologia SDD, papel do constitution.md/CLAUDE.md, desvios do Princípio IX
└── evidence/
    ├── pipeline-run.log             # Já existe (SPEC-015) — só referenciado, não alterado
    └── README.md                    # NOVO — checklist do que falta coletar manualmente

skills/
├── scraper-skill/SKILL.md               # Auditado, corrigido pontualmente se divergir
├── extractor-skill/SKILL.md             # Auditado, corrigido pontualmente se divergir
├── compliance-analyzer-skill/SKILL.md   # Auditado, corrigido pontualmente se divergir
├── conformance-validator-skill/SKILL.md # Auditado, corrigido pontualmente se divergir
├── knowledge-builder-skill/SKILL.md     # Auditado, corrigido pontualmente se divergir
├── report-consolidator-skill/SKILL.md   # Auditado, corrigido pontualmente se divergir
└── orchestrator-skill/SKILL.md          # NOVO — sétimo agente do enxame (Harness, SPEC-015)
```

**Structure Decision**: Nenhum diretório de código novo — todos os artefatos são
documentação Markdown, seguindo os locais já estabelecidos pelas specs anteriores
(`skills/`, `docs/`) ou o próprio `README.md` na raiz.

## Complexity Tracking

*Sem violações do Constitution Check — seção não aplicável.*
