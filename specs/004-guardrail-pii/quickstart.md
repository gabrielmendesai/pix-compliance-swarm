# Quickstart: Validando o guardrail de PII (SPEC-004)

## Pré-requisitos

- Ambiente do projeto instalado (`.venv`); nenhuma dependência nova é
  necessária para esta spec (research.md §8).
- SPEC-002 já implementada (`NormativoItem` e o padrão de modelos Pydantic
  disponíveis).
- SPEC-001 já implementada (`pix_compliance.logging.configure_logging`
  disponível).

## Setup

```bash
pip install -e ".[dev]"
```

## Cenário 1 — CPF válido é mascarado, inválido não é (User Story 1)

```python
from pix_compliance.guardrails import guard

resultado = guard("Contato: CPF 123.456.789-09.")  # dígito verificador válido
assert "123.456.789-09" not in resultado.texto_mascarado
assert "123.***.***-09" in resultado.texto_mascarado

resultado_invalido = guard("Contato: CPF 123.456.789-00.")  # dígito inválido
assert "123.456.789-00" in resultado_invalido.texto_mascarado  # não mascarado
```

**Verificação**: `pytest tests/test_guardrails.py -q -k cpf`

## Cenário 2 — Sequência de 11 dígitos aleatória não gera falso positivo

```python
resultado = guard("Código de rastreio: 12345678901.")
assert resultado.relatorios == []  # nenhum CPF detectado
```

**Verificação**: `pytest tests/test_guardrails.py -q -k falso_positivo`

## Cenário 3 — Ponto único de aplicação (`call_with_guard`) (User Story 2)

```python
from pix_compliance.guardrails import call_with_guard

recebido = {}

def funcao_exemplo(texto: str) -> None:
    recebido["texto"] = texto

call_with_guard(funcao_exemplo, "CPF 123.456.789-09 no corpo do texto.")
assert "123.456.789-09" not in recebido["texto"]
```

**Verificação**: `pytest tests/test_guardrails.py -q -k call_with_guard`

## Cenário 4 — Log estruturado audita sem vazar o valor (User Story 3)

```python
import json
import structlog
from pix_compliance.logging import configure_logging
from pix_compliance.guardrails import guard

configure_logging()
# capturar stdout do teste via `capsys` (ver tests/test_logging.py para o padrão)
guard("CPF 123.456.789-09 e e-mail joao@exemplo.com no mesmo texto.")
# cada linha de log JSON deve conter "tipo"/"ocorrencias", nunca
# "123.456.789-09" ou "joao@exemplo.com"
```

**Verificação**: `pytest tests/test_guardrails.py -q -k log`

## Cenário 5 — Correção de fixture bloqueante (FR-012)

```bash
grep -oE "[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}" fixtures/documents/normativo-100-2020-pii.html
python -c "
from pix_compliance.guardrails import guard
import pathlib
texto = pathlib.Path('fixtures/documents/normativo-100-2020-pii.html').read_text(encoding='utf-8')
resultado = guard(texto)
print([r.tipo for r in resultado.relatorios])
"
```

**Resultado esperado**: o CNPJ corrigido no fixture aparece na lista de
tipos detectados (`cnpj` presente em `resultado.relatorios`), confirmando
que a fixture volta a demonstrar corretamente o guardrail de ponta a ponta.

## Rodar toda a suíte de testes desta feature

```bash
pytest tests/test_guardrails.py -q
```

## Lint

```bash
ruff check src/pix_compliance/guardrails.py tests/test_guardrails.py
```
