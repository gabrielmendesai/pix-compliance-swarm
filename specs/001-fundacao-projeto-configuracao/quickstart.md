# Quickstart: Fundação do projeto e configuração (SPEC-001)

Guia de validação ponta a ponta desta spec. Cada seção corresponde a um Success
Criterion de `spec.md`.

## Pré-requisitos

- Python 3.11+ e `make` disponíveis no `PATH`.
- Repositório clonado, sem ambiente virtual `.venv` previamente criado ("ambiente
  limpo", conforme a seção Assumptions da spec).

## 1. Instalação reprodutível (SC-001)

```bash
make install
```

Esperado: comando conclui sem erro; ambiente virtual criado e dependências de
`pyproject.toml` instaladas.

## 2. Configuração carregada com sucesso (SC-002, SC-005)

```bash
cp .env.example .env
# edite .env com valores válidos (mesmo que fictícios) para todas as variáveis
python -c "from pix_compliance.config import settings; print(settings.model_dump())"
```

Esperado: dicionário com todos os campos de `Settings` (ver `data-model.md`) impresso
sem exceção. Do clone ao sucesso deste comando, seguindo só `.env.example` e o
`Makefile` — sem ler `config.py` — deve levar menos de 5 minutos.

## 3. Fail-fast com variável ausente (Acceptance Scenario 3, Edge Cases)

```bash
cp .env.example .env
# remova ou comente a linha AWS_REGION em .env
python -c "from pix_compliance.config import settings"
```

Esperado: falha imediata com mensagem acionável citando `AWS_REGION` e a instrução
de copiar `.env.example` para `.env` — nunca um traceback cru de `pydantic.ValidationError`.

Repita apagando todo o `.env` (renomeie ou remova o arquivo, sem variáveis
exportadas no shell): mesmo comportamento — falha com mensagem clara, sem defaults
inseguros.

## 4. Logs estruturados com `correlation_id` (User Story 2)

```bash
make run    # ou qualquer alvo do Makefile que dispare um log
```

Esperado: cada linha de saída é um objeto JSON válido contendo `correlation_id`.
Rode o mesmo comando duas vezes e compare — `correlation_id` difere entre as duas
execuções, mas é idêntico em todas as linhas de uma mesma execução:

```bash
make run 2>&1 | jq -r '.correlation_id' | sort -u
# deve imprimir exatamente 1 valor por execução
```

## 5. Nenhum segredo hardcoded (SC-003)

```bash
grep -rn "AKIA" src/
```

Esperado: nenhuma ocorrência (saída vazia, exit code 1 do grep).

## 6. Qualidade de código verificável por comando (User Story 3)

```bash
make lint
make test
```

Esperado: `make lint` roda sem erros; `make test` executa a suíte (`test_config.py`,
`test_logging.py`) sem falhas de configuração.

## 7. Alvos `up`/`down` não quebram o restante (Edge Cases)

```bash
make up
make down
```

Esperado: ambos executam sem erro (placeholder documentado apontando para a
implementação futura da SPEC-016), sem impedir a execução dos demais alvos do
`Makefile`.
