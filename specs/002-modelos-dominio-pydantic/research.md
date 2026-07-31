# Research: Modelos de domínio Pydantic v2 (SPEC-002)

## 1. Formato de `numero` do normativo

**Decision**: Regex `^\d{1,6}(\.\d{3})*\/\d{4}$`, validando valores como `123/2024` ou
`4.966/2021` (número sequencial, com separador de milhar opcional por ponto, seguido de
`/` e o ano de 4 dígitos).

**Rationale**: Normativos reais do BCB são referenciados como "Resolução BCB nº 123, de
2024" ou, em séries mais antigas, com separador de milhar ("Resolução CMN nº 4.966, de
2021"). O campo `numero` do modelo captura apenas a parte numérica/ano do identificador
(o `tipo` já carrega "Resolução BCB", "Circular" etc. como enum separado), então a regex
não precisa reconhecer o texto do tipo — só o padrão `<número>[.<milhar>]*/<ano>`.

**Alternatives considered**:
- Aceitar qualquer string não vazia (rejeitado: viola FR-014, que exige validação por
  regex de formato, não apenas de não-vacuidade).
- Exigir apenas dígitos sem separador de milhar (rejeitado: normativos anteriores a
  reformas usam numeração com milhar, ex. CMN 4.966).
- Validar o texto completo "Resolução BCB nº 123, de 2024" dentro de `numero`
  (rejeitado: duplicaria informação já presente em `tipo` e tornaria o campo difícil de
  usar em buscas/índices).

## 2. Normalização de espaço em `texto`

**Decision**: `field_validator` que aplica `re.sub(r"\s+", " ", valor.strip())` antes de
checar não-vacuidade.

**Rationale**: FR-011 exige rejeição de texto vazio pós-`strip()` E normalização
(colapso) de espaços internos redundantes — comum em texto extraído de PDF/HTML de
normativos, onde quebras de linha e espaços múltiplos aparecem por artefato de extração,
não por conteúdo real.

**Alternatives considered**: Apenas `strip()` sem colapsar espaços internos (rejeitado:
não atende à Edge Case explícita da spec sobre espaços internos múltiplos/quebras de
linha redundantes).

## 3. Estrutura de módulo (single file vs. um arquivo por modelo)

**Decision**: Um único módulo `src/pix_compliance/models.py` contendo todos os
enums e modelos do vocabulário do sistema.

**Rationale**: Constituição Princípio III (KISS — simplicidade sobre segmentação): os
modelos formam um único vocabulário coeso e fortemente inter-relacionado (ex.
`ConformanceReport` referencia `ConformanceItem`, que referencia `regra_id` de
`RegraExtraida`); segmentar em múltiplos arquivos exigiria imports cruzados sem ganho de
clareza, e o volume total (9 entidades + enums) ainda é revisável em um único arquivo.
Segue o precedente já estabelecido em `src/pix_compliance/config.py` (módulo único,
concreto, sem abstração especulativa).

**Alternatives considered**: Um arquivo por entidade em `src/pix_compliance/models/`
(rejeitado por ora: nenhuma segunda implementação nem teste exige a segmentação — YAGNI,
Princípio II; pode ser revisitado se o módulo crescer muito em specs futuras).

## 4. Persistência de JSON Schema

**Decision**: Script/gerador (`scripts/export_schemas.py` ou teste dedicado) que chama
`Modelo.model_json_schema()` para cada modelo público e grava em
`docs/schemas/<NomeDoModelo>.schema.json`, executado como parte da suíte de testes
(`tests/test_models.py`) para garantir que os artefatos nunca ficam desatualizados em
relação ao código.

**Rationale**: FR-018 exige que os schemas sejam salvos em `docs/schemas/`; gerar os
arquivos a partir de um teste (em vez de um passo manual) garante que SC-002 (100% dos
modelos exportam schema) seja verificável por comando (`pytest`), alinhado ao Princípio
VIII (evidência é entregável, critério de aceite é comando executável).

**Alternatives considered**: Gerar schemas manualmente e commitar sem automação
(rejeitado: viola Princípio VIII — não seria um critério de aceite verificável por
comando, ficaria sujeito a divergência silenciosa entre código e schema commitado).

## 5. StrEnum e coerção case-insensitive

**Decision**: Todos os vocabulários fechados (`TipoNormativo`, `CategoriaCompliance`,
`Obrigatoriedade`, `StatusConformidade`) são `StrEnum` (Python 3.11+); a coerção
case-insensitive é implementada via `field_validator(mode="before")` que faz
`valor.strip().lower()` e busca o membro do enum por valor em minúsculo antes de passar
para o Pydantic validar o tipo.

**Rationale**: FR-016 exige `StrEnum`; FR-013 exige coerção case-insensitive quando a
entrada é string (ex. "Tarifas" → `CategoriaCompliance.TARIFAS`). `StrEnum` nativo do
Python já serializa como string simples em `model_dump(mode="json")`, o que mantém
`ReportOutput`/API sem necessidade de serializadores customizados.

**Alternatives considered**: Usar `Enum` comum com `use_enum_values=True` (rejeitado:
não resolve coerção case-insensitive por si só, e `StrEnum` é requisito explícito do
FR-016).

## 6. Dependências e ferramentas

**Language/Version**: Python 3.11+ (já estabelecido pela SPEC-001/constituição).

**Primary Dependencies**: `pydantic>=2.0` (já em `pyproject.toml`); nenhuma dependência
nova é necessária — `StrEnum` vem da stdlib (`enum.StrEnum`, Python 3.11+).

**Testing**: `pytest>=8.0` (já configurado em `pyproject.toml`, `testpaths = ["tests"]`).

**Storage**: N/A — esta spec não implementa persistência (ver Assumptions do spec.md).

**Target Platform**: Mesmo ambiente do restante do projeto (Docker Compose / Linux
server, Python 3.11+).

**Project Type**: Single project (já estabelecido pela estrutura `src/pix_compliance/`,
`tests/`).

**Performance Goals**: N/A — validação de modelos em memória, sem requisito de
performance específico além do overhead padrão do Pydantic v2 (compilado em Rust,
validação da ordem de microssegundos por instância).

**Constraints**: Nenhuma chamada de rede ou I/O dentro de validadores (Assumption da
spec); todos os validadores são determinísticos e locais.

**Scale/Scope**: 9 entidades principais + 4 enums fechados, todos em um único módulo.
