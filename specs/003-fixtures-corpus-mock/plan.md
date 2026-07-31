# Implementation Plan: Fixtures e corpus mock (SPEC-003)

**Branch**: `003-fixtures-corpus-mock` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-fixtures-corpus-mock/spec.md`

## Summary

Produzir, via um gerador determinístico (`python -m fixtures.generate`), o
corpus de dados fictícios exigido pelo desafio: ≥50 registros
`NormativoItem`-compatíveis em `fixtures/normativos.json` (incluindo ≥2 pares
de versões com delta documentado em `fixtures/EXPECTED_DELTAS.md`), ≥3
documentos PDF e ≥3 HTML em `fixtures/documents/` com estrutura de
artigo/inciso (um deles com CPF/CNPJ fictícios plantados), e um site mock
estático do BCB em `mock_bcb/` com página de listagem. Toda a geração é
byte-idêntica entre execuções (seed fixa local, PDF em modo `invariant`,
nenhuma dependência de timestamp/aleatoriedade não controlada).

## Technical Context

**Language/Version**: Python 3.11+ (mesmo ambiente do restante do projeto)

**Primary Dependencies**: `reportlab` (nova — geração de PDF determinística
via `Canvas(invariant=1)`, research.md §1); `pydantic>=2.0` (já presente, via
`NormativoItem`); HTML gerado com f-strings da stdlib, sem motor de template
novo (research.md §2); CPF/CNPJ gerados por função própria, sem `Faker`
(research.md §3)

**Storage**: N/A — saída são arquivos estáticos em disco (JSON, PDF, HTML,
Markdown), sem banco de dados

**Testing**: `pytest>=8.0` (`tests/test_fixtures.py`)

**Target Platform**: Mesmo ambiente do restante do projeto (Python 3.11+,
Docker Compose); site mock servido localmente via `python -m http.server`
(stdlib), sem servidor dedicado

**Project Type**: Script de geração de dados (CLI standalone via `python -m
fixtures.generate`), não um serviço da aplicação

**Performance Goals**: N/A — geração de ~50 registros JSON + ~6-8 documentos
é operação de segundos

**Constraints**: Determinismo estrito — duas execuções sucessivas produzem
bytes idênticos em todos os artefatos (SC-001, research.md §1 e §4); nenhuma
chamada de rede; nenhuma dependência de binário externo de SO

**Scale/Scope**: 50+ registros de normativo, ≥3 PDF, ≥3 HTML, 1 site mock, 1
arquivo de deltas esperados

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação |
|---|---|
| I. Bedrock como padrão | N/A — esta spec não invoca LLM/provider (script de geração de dados determinístico e local) |
| II. Abstração exige justificativa (YAGNI) | ✅ Nenhuma interface/Protocol criada; CPF/CNPJ e HTML gerados com código direto (funções), não abstrações especulativas; `reportlab` é a única dependência nova, justificada por uma necessidade concreta (modo `invariant` para idempotência, research.md §1) |
| III. Simplicidade sobre segmentação (KISS) | ✅ Um único pacote `fixtures/` com poucos módulos coesos (geração de normativos, documentos, site mock); HTML via f-strings em vez de motor de template novo (research.md §2) |
| IV. SRP por agente | N/A — esta spec não define agentes do enxame, apenas dados de fixture que agentes futuros consumirão |
| V. Guardrail único de PII | N/A direto — esta spec **produz** a fixture de PII para testar o guardrail futuro, mas não implementa nem invoca o guardrail em si; nenhum dado desta feature trafega para um LLM |
| VI. Contrato antes de comportamento | ✅ Reaproveita `NormativoItem` já congelado (SPEC-002) como fonte de verdade de schema; nenhum formato de dado paralelo é criado (Decisão de reconciliação de schema do spec.md) |
| VII. Comentários e nomenclatura | ✅ Identificadores em inglês; comentários/docstrings em português; comentário explicando por que determinismo importa (reprodutibilidade da avaliação, não só conveniência — research.md §4) |
| VIII. Evidência como entregável | ✅ SC-001 a SC-004 são todos comandos executáveis (`python -m fixtures.generate`, `jq`, validação via `NormativoItem`, `python -m http.server`) |

**Resultado**: Nenhuma violação. Nenhuma entrada necessária em Complexity
Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/003-fixtures-corpus-mock/
├── plan.md              # This file (/speckit-plan command output)
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── fixtures-contract.md
└── tasks.md              # Phase 2 output (/speckit-tasks command — not created here)
```

### Source Code (repository root)

```text
fixtures/                       # NOVO — pacote de geração de dados (fora de src/, ver research.md §5)
├── __init__.py
├── generate.py                # Entry point: `python -m fixtures.generate`
├── pii.py                     # Geração de CPF/CNPJ fictícios (válido + inválido)
├── normativos.json            # GERADO — corpus de ≥50 NormativoItem
├── EXPECTED_DELTAS.md          # GERADO — deltas documentados dos pares de versão
└── documents/                  # GERADO — ≥3 PDF + ≥3 HTML com estrutura de artigo/inciso

mock_bcb/                       # GERADO — site mock estático do BCB
└── index.html                  # Página de listagem linkando fixtures/documents/*.html

tests/
└── test_fixtures.py            # NOVO — idempotência, contagem mínima, validação contra
                                 # NormativoItem, PII plantada, pares de versão, site mock
```

**Structure Decision**: Pacote `fixtures/` na raiz do repositório (não em
`src/`), pois é um gerador de dados de desenvolvimento/avaliação, não parte
do pacote de produção instalável `pix_compliance` (research.md §5).
`mock_bcb/` e os artefatos gerados dentro de `fixtures/` (`normativos.json`,
`documents/`, `EXPECTED_DELTAS.md`) são saída do gerador, não código-fonte —
regenerados a cada execução, mas versionados no repositório para servir de
fixture estável a outras specs.

## Complexity Tracking

*Nenhuma violação de Constitution Check — seção não aplicável.*
