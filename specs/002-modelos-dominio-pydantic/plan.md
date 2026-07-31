# Implementation Plan: Modelos de domínio Pydantic v2 (SPEC-002)

**Branch**: `002-modelos-dominio-pydantic` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-modelos-dominio-pydantic/spec.md`

## Summary

Congelar, em um único módulo `src/pix_compliance/models.py`, o vocabulário de tipos
Pydantic v2 usado por todo o enxame (`NormativoItem`, `RegraExtraida`,
`ConformanceReport`/`ConformanceItem`, `SearchQuery`/`SearchResult`, `ReportOutput`,
`PipelineRequest`/`PipelineResult`, `RawDocument`), com validação obrigatória via
`field_validator`/`model_validator`, `extra="forbid"` em todos os modelos, enums como
`StrEnum` e `frozen=True` nas entidades semanticamente imutáveis. O contrato externo
verificável é o conjunto de JSON Schemas exportados via `model_json_schema()` e
persistidos em `docs/schemas/`, provado por `pytest tests/test_models.py`.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib `enum.StrEnum`)

**Primary Dependencies**: `pydantic>=2.0` (já presente em `pyproject.toml`); nenhuma
dependência nova

**Storage**: N/A — apenas modelos de dados, sem persistência (Assumption do spec.md)

**Testing**: `pytest>=8.0` (`tests/test_models.py`, `testpaths = ["tests"]` já
configurado)

**Target Platform**: Mesmo ambiente do restante do projeto (Python 3.11+, Docker
Compose)

**Project Type**: Single project (`src/pix_compliance/`, `tests/`)

**Performance Goals**: N/A — validação em memória, sem requisito de throughput
específico além do overhead padrão do Pydantic v2

**Constraints**: Nenhum I/O ou chamada de rede dentro de validadores; toda validação é
determinística e local (Assumption do spec.md)

**Scale/Scope**: 10 modelos públicos + 4 enums `StrEnum`, em um único módulo

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação |
|---|---|
| I. Bedrock como padrão | N/A — esta spec não invoca LLM/provider (Assumption do spec.md) |
| II. Abstração exige justificativa (YAGNI) | ✅ Nenhuma interface/Protocol criada; modelos são classes Pydantic concretas |
| III. Simplicidade sobre segmentação (KISS) | ✅ Módulo único `models.py`, justificado em research.md §3; segue precedente de `config.py` |
| IV. SRP por agente | N/A — esta spec não define agentes, apenas os contratos de dados que eles consumirão (Princípio VI) |
| V. Guardrail único de PII | N/A — nenhum texto trafega para LLM/persistência nesta spec |
| VI. Contrato antes de comportamento | ✅ É exatamente o objetivo desta spec: congelar os modelos antes de qualquer lógica de agente |
| VII. Comentários e nomenclatura | ✅ Identificadores em inglês; vocabulário BCB/PIX (normativo, inciso, vigência, enunciado, atores_afetados) preservado em português (FR-021); todo validador não trivial recebe comentário de razão de negócio (FR-020); docstring de módulo explicando o papel de cada modelo (FR-019) |
| VIII. Evidência como entregável | ✅ SC-001/SC-002/SC-003 são todos comandos executáveis (`pytest`, inspeção de `docs/schemas/`) |

**Resultado**: Nenhuma violação. Nenhuma entrada necessária em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-modelos-dominio-pydantic/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── schemas-contract.md
└── tasks.md              # Phase 2 output (/speckit-tasks command — not created here)
```

### Source Code (repository root)

```text
src/
└── pix_compliance/
    ├── __init__.py
    ├── config.py          # já existente (SPEC-001)
    ├── logging.py         # já existente (SPEC-001)
    └── models.py          # NOVO — todos os modelos e enums desta spec

tests/
└── test_models.py         # NOVO — cobre os 10 modelos + geração/drift-check de schemas

docs/
└── schemas/               # NOVO — JSON Schemas gerados (FR-018, SC-002)
    ├── NormativoItem.schema.json
    ├── RegraExtraida.schema.json
    ├── ConformanceItem.schema.json
    ├── ConformanceReport.schema.json
    ├── SearchQuery.schema.json
    ├── SearchResult.schema.json
    ├── ReportOutput.schema.json
    ├── PipelineRequest.schema.json
    ├── PipelineResult.schema.json
    └── RawDocument.schema.json
```

**Structure Decision**: Projeto single (Option 1), seguindo a estrutura já estabelecida
por SPEC-001 (`src/pix_compliance/`, `tests/`). Nenhum novo diretório de nível superior
além de `docs/schemas/`, que é um artefato de saída (contrato), não código-fonte.

## Complexity Tracking

*Nenhuma violação de Constitution Check — seção não aplicável.*
