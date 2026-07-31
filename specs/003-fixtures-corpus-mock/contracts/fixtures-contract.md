# Contract: Corpus de fixtures e site mock

Esta feature não expõe uma API HTTP própria da aplicação (o `mock_bcb/` é
servido ad-hoc via `python -m http.server` da stdlib, não um serviço
gerenciado pelo enxame). O "contrato externo" verificável é o conjunto de
artefatos de arquivo que outras specs (guardrail, Conformance Validator,
scraping/MCP) consumirão como dado de teste fixo.

## Contrato de CLI

`python -m fixtures.generate`

- **Entrada**: nenhum argumento obrigatório (seed é constante interna, não
  configurável via CLI nesta versão — ver Assumptions do spec.md).
- **Saída (efeitos colaterais em disco)**:
  - `fixtures/normativos.json` — criado ou sobrescrito
  - `fixtures/documents/*.pdf`, `*.html` — criados ou sobrescritos
  - `fixtures/EXPECTED_DELTAS.md` — criado ou sobrescrito
  - `mock_bcb/index.html` (e demais arquivos do site mock) — criados ou
    sobrescritos
- **Código de saída**: `0` em sucesso; não-zero se qualquer registro gerado
  falhar a validação contra `NormativoItem` antes de escrever os arquivos
  (falha rápida, sem deixar corpus parcialmente inválido em disco).
- **Idempotência**: chamar o comando duas vezes em sequência produz bytes
  idênticos em todos os arquivos gerados (SC-001).

## Contrato de dados: `fixtures/normativos.json`

- Formato: array JSON de objetos.
- Cada objeto MUST validar via `NormativoItem.model_validate(objeto)`
  (importado de `src/pix_compliance/models.py`) sem lançar `ValidationError`.
- `len(json.load(...)) >= 50` (SC-002, verificável também via
  `jq 'length' fixtures/normativos.json`).
- Pelo menos 2 pares de objetos compartilham o mesmo normativo lógico com
  `versao` distinta (ver data-model.md).

## Contrato de dados: `fixtures/EXPECTED_DELTAS.md`

- Formato: Markdown com uma seção por par de versões (ver data-model.md).
- Cada seção MUST ser resolvível programaticamente o suficiente para um teste
  automatizado localizar os dois registros correspondentes em
  `normativos.json` pelo `numero`/`versao` citados e comparar os campos
  listados.

## Contrato do site mock: `mock_bcb/`

- `mock_bcb/index.html` MUST retornar HTTP 200 quando requisitado via
  `python -m http.server` a partir de `mock_bcb/` (verificado por
  `GET /index.html` ou `GET /`).
- O HTML da página de listagem MUST conter pelo menos um elemento `<a href>`
  por documento gerado em `fixtures/documents/*.html`.

## Verificação

Comando executável que prova o contrato (Princípio VIII — evidência como
entregável):

```bash
python -m fixtures.generate
python -m fixtures.generate  # segunda execução — deve ser idêntica
jq 'length' fixtures/normativos.json
pytest tests/test_fixtures.py -q
```
