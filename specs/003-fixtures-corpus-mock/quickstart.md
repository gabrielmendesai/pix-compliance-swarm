# Quickstart: Validando o corpus mock (SPEC-003)

## Pré-requisitos

- Ambiente do projeto instalado (`.venv`), incluindo a nova dependência
  `reportlab` (adicionar a `pyproject.toml`/`requirements.txt` na
  implementação).
- SPEC-002 já implementada (`src/pix_compliance/models.py` disponível e
  instalado via `pip install -e .`).

## Setup

```bash
pip install -e ".[dev]"
```

## Cenário 1 — Gerar o corpus (User Story 1)

```bash
python -m fixtures.generate
jq 'length' fixtures/normativos.json
```

**Resultado esperado**: comando termina com código 0; `jq` imprime um número
`>= 50`.

## Cenário 2 — Idempotência (SC-001)

```bash
python -m fixtures.generate
sha256sum fixtures/normativos.json > /tmp/run1.sha256
python -m fixtures.generate
sha256sum -c /tmp/run1.sha256
```

**Resultado esperado**: `sha256sum -c` reporta `OK` — o arquivo é
byte-idêntico entre as duas execuções. O mesmo vale para os arquivos em
`fixtures/documents/` e `mock_bcb/`.

## Cenário 3 — Validação contra `NormativoItem` (SC-003)

```python
import json
from pix_compliance.models import NormativoItem

registros = json.load(open("fixtures/normativos.json", encoding="utf-8"))
for registro in registros:
    NormativoItem.model_validate(registro)  # não deve lançar ValidationError
print(f"{len(registros)} registros validados com sucesso")
```

**Verificação via teste**: `pytest tests/test_fixtures.py -q -k validacao`

## Cenário 4 — Fixture de PII para o guardrail (User Story 2)

```bash
grep -rE '[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}' fixtures/documents/
grep -rE '[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}' fixtures/documents/
```

**Resultado esperado**: ao menos um CPF e um CNPJ aparecem em algum documento;
`fixtures/EXPECTED_DELTAS.md`/comentários do gerador indicam qual é
sintaticamente válido e qual é inválido (para orientar os testes da futura
feature de guardrail).

## Cenário 5 — Par de versões com delta conhecido (User Story 3)

```bash
cat fixtures/EXPECTED_DELTAS.md
```

Em seguida, para o par citado, localizar os dois registros correspondentes em
`fixtures/normativos.json` (mesmo `numero`, `versao` distinta) e confirmar que
a única diferença de campo é a listada no documento.

**Verificação via teste**: `pytest tests/test_fixtures.py -q -k delta`

## Cenário 6 — Site mock do BCB (User Story 4)

```bash
cd mock_bcb
python -m http.server 8080 &
curl -s http://localhost:8080/ | grep -o '<a href="[^"]*"' | head
kill %1
```

**Resultado esperado**: a página de listagem responde HTTP 200 e contém pelo
menos um link `<a href="...">` por documento gerado em
`fixtures/documents/*.html`.

## Rodar toda a suíte de testes desta feature

```bash
pytest tests/test_fixtures.py -q
```

## Lint

```bash
ruff check fixtures/ tests/test_fixtures.py
```
