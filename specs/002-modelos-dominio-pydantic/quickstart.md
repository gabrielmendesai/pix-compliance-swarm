# Quickstart: Validando os modelos de domínio (SPEC-002)

## Pré-requisitos

- Python 3.11+ com o ambiente do projeto instalado (`.venv` já presente no repo).
- Dependências já cobertas por `pyproject.toml` (`pydantic>=2.0`); nenhuma dependência
  nova é necessária para esta spec.

## Setup

```bash
pip install -e ".[dev]"
```

## Rodar a suíte de testes dos modelos

```bash
pytest tests/test_models.py -q
```

**Resultado esperado (SC-001)**: todos os testes passam, cobrindo:
- Caminho feliz de cada um dos 10 modelos (`NormativoItem`, `RegraExtraida`,
  `ConformanceItem`, `ConformanceReport`, `SearchQuery`, `SearchResult`, `ReportOutput`,
  `PipelineRequest`, `PipelineResult`, `RawDocument`).
- Pelo menos um caso de rejeição por validador não trivial em cada modelo que os possui
  (`data_vigencia < data_publicacao`, `hash_conteudo` malformado, `texto`/`enunciado`
  vazio, `categoria` fora do vocabulário, `confianca`/`score`/`severidade` fora de
  `[0,1]`, `numero` fora do formato regex, campo extra não declarado).

## Cenário 1 — NormativoItem válido e inválido (User Story 1)

```python
from datetime import date
from pix_compliance.models import NormativoItem, TipoNormativo, CategoriaCompliance

valido = NormativoItem(
    id="...", titulo="Resolução sobre tarifas PIX", tipo=TipoNormativo.RESOLUCAO_BCB,
    numero="123/2024", texto="Texto do normativo.",
    data_publicacao=date(2024, 1, 1), data_vigencia=date(2024, 1, 1),
    categoria=CategoriaCompliance.TARIFAS, url_origem="https://bcb.gov.br/x",
    hash_conteudo="a" * 64, versao=1,
)  # sucesso

# data_vigencia anterior a data_publicacao -> ValidationError
NormativoItem(..., data_publicacao=date(2024, 6, 1), data_vigencia=date(2024, 1, 1))
```

**Verificação**: `pytest tests/test_models.py -q -k normativo` passa.

## Cenário 2 — ConformanceReport agregando ConformanceItem (User Story 2)

```python
from pix_compliance.models import ConformanceItem, ConformanceReport, StatusConformidade

item = ConformanceItem(regra_id="...", status=StatusConformidade.CONFORME, severidade=0.9)
report = ConformanceReport(report_id="...", gerado_em=..., itens=[item], resumo="ok",
                            criticidade_maxima=StatusConformidade.CONFORME)
```

**Verificação**: `pytest tests/test_models.py -q -k conformance` passa;
`severidade=1.5` deve levantar `ValidationError`.

## Cenário 3 — Round-trip serialização/API (User Story 3)

```python
from pix_compliance.models import PipelineRequest

req = PipelineRequest(pipeline_id="...", fontes=["https://bcb.gov.br/normativos"])
dump = req.model_dump()
assert PipelineRequest.model_validate(dump) == req

# campo extra -> ValidationError (extra="forbid")
PipelineRequest.model_validate({**dump, "foo": "bar"})
```

**Verificação**: `pytest tests/test_models.py -q -k "extra or roundtrip"` passa.

## Verificar contrato de JSON Schema (SC-002)

```bash
pytest tests/test_models.py -q -k schema
ls docs/schemas/
```

**Resultado esperado**: um arquivo `.schema.json` por modelo listado em
`contracts/schemas-contract.md`, gerado a partir de `model_json_schema()`.

## Lint

```bash
ruff check src/pix_compliance/models.py tests/test_models.py
```
