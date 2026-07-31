# Implementation Plan: Camada de guardrail e PII (SPEC-004)

**Branch**: `004-guardrail-pii` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-guardrail-pii/spec.md`

## Summary

Implementar, em um único módulo `src/pix_compliance/guardrails.py`, detectores
de CPF, CNPJ, e-mail, telefone e chave PIX aleatória — com validação real de
dígito verificador para CPF/CNPJ, não apenas regex — mascaramento que
preserva o formato original, um modelo `PIIReport` por tipo detectado, e uma
função única `guard(text: str) -> GuardedText` como ponto obrigatório de
aplicação para qualquer texto destinado a um LLM ou a uma escrita de
storage. Inclui verificação de tamanho de texto, detecção sintática de
padrões de injeção de prompt, e log estruturado (JSON, via `structlog` já
configurado pela SPEC-001) que nunca expõe o valor original detectado.
Bloqueante: correção do CNPJ com dígito verificador inválido plantado na
fixture de PII da SPEC-003.

## Technical Context

**Language/Version**: Python 3.11+ (mesmo ambiente do restante do projeto)

**Primary Dependencies**: Nenhuma dependência nova — `re`/`uuid` da stdlib,
`pydantic>=2.0` e `structlog>=24.0` já presentes em `pyproject.toml`
(research.md §8)

**Storage**: N/A — nenhuma persistência nesta feature

**Testing**: `pytest>=8.0` (`tests/test_guardrails.py`), usando `capsys` para
inspecionar log JSON (mesmo padrão de `tests/test_logging.py` da SPEC-001)

**Target Platform**: Mesmo ambiente do restante do projeto

**Project Type**: Módulo de biblioteca interna, consumido por agentes
futuros (SPEC-005+), não um serviço próprio

**Performance Goals**: N/A — varredura de regex sobre texto de até 100.000
caracteres é da ordem de milissegundos

**Constraints**: `guard()` nunca loga o valor original detectado;
reimplementação local do dígito verificador em vez de importar de
`fixtures/` (research.md §1); nenhuma classe/interface nova sem segunda
implementação real que a justifique

**Scale/Scope**: 5 detectores de PII, 1 enum (`TipoPII`), 2 modelos
(`PIIReport`, `GuardedText`), 1 exceção (`GuardrailInputError`), 2 funções
públicas (`guard`, `call_with_guard`), tudo em um único módulo, mais a
correção de 1 fixture de SPEC-003

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação |
|---|---|
| I. Bedrock como padrão | N/A direto — esta feature não invoca LLM algum; o enforcement é testado contra uma função de exemplo (Assumption do spec.md), a integração real com Bedrock fica para SPEC-005 |
| II. Abstração exige justificativa (YAGNI) | ✅ Nenhuma interface/Protocol/hierarquia de classes; `guardrails.py` é um módulo de funções; dígito verificador reimplementado localmente em vez de compartilhado especulativamente com `fixtures/` (research.md §1) |
| III. Simplicidade sobre segmentação (KISS) | ✅ Um único módulo `guardrails.py`; `call_with_guard` é uma função de ordem superior, não um decorator/classe (research.md §7) |
| IV. SRP por agente | N/A — esta spec não define agentes, apenas o guardrail que agentes futuros deverão usar |
| V. Guardrail é ponto único e obrigatório | ✅ É exatamente o objetivo desta spec: `guard()` como único caminho permitido; novos detectores se adicionam dentro deste módulo sem alterar nenhum agente consumidor (Princípio V, texto literal da constituição) |
| VI. Contrato antes de comportamento | ✅ `PIIReport`/`GuardedText` seguem o mesmo padrão Pydantic (`ConfigDict(extra="forbid")`, `StrEnum`) já congelado em SPEC-002 |
| VII. Comentários e nomenclatura | ✅ Identificadores em inglês; comentários/docstrings em português explicando o porquê (dígito verificador vs. regex ingênuo, mascaramento preserva formato, ponto único de aplicação) — exigido explicitamente pelo spec.md |
| VIII. Evidência como entregável | ✅ SC-001 a SC-003 são comandos/inspeções executáveis (`pytest tests/test_guardrails.py -q`, inspeção de log) |

**Resultado**: Nenhuma violação. Nenhuma entrada necessária em Complexity
Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/004-guardrail-pii/
├── plan.md              # This file (/speckit-plan command output)
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── guardrails-contract.md
└── tasks.md              # Phase 2 output (/speckit-tasks command — not created here)
```

### Source Code (repository root)

```text
src/
└── pix_compliance/
    ├── config.py            # já existente (SPEC-001)
    ├── logging.py           # já existente (SPEC-001) — reutilizado por guard()
    ├── models.py            # já existente (SPEC-002) — padrão seguido por PIIReport/GuardedText
    └── guardrails.py        # NOVO — detectores, mascaramento, PIIReport, GuardedText,
                              # GuardrailInputError, guard(), call_with_guard()

tests/
└── test_guardrails.py       # NOVO — cobre detecção/mascaramento por tipo, dígito
                              # verificador, ausência de falso positivo, call_with_guard,
                              # e inspeção de log sem vazamento do valor original

fixtures/documents/
└── normativo-100-2020-pii.{html,pdf}   # CORRIGIDO — CNPJ com dígito verificador válido
mock_bcb/normativos/
└── normativo-100-2020-pii.html          # CORRIGIDO — espelho do HTML acima
```

**Structure Decision**: Módulo único `src/pix_compliance/guardrails.py`,
seguindo o mesmo padrão de organização de `config.py`/`models.py` (SPEC-001/
SPEC-002) — nenhum novo diretório de nível superior. A correção de fixture
(FR-012) é feita regenerando `fixtures/documents/normativo-100-2020-pii.*` e
seu espelho em `mock_bcb/normativos/` via `python -m fixtures.generate`,
após ajustar o CNPJ hardcoded em `fixtures/generate.py`/`fixtures/pii.py` —
não uma edição manual dos arquivos gerados (mantém a garantia de idempotência
e regeneração determinística já estabelecida pela SPEC-003).

## Complexity Tracking

*Nenhuma violação de Constitution Check — seção não aplicável.*
