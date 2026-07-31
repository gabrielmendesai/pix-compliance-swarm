# Research: Fundação do projeto e configuração (SPEC-001)

Nenhum item do Technical Context ficou marcado como `NEEDS CLARIFICATION` — o
briefing (`Initial Design/BRIEFING.md`) e a constituição já fixam a stack. As decisões
abaixo cobrem as escolhas de implementação que a spec deixa em aberto dentro dessa
stack fixada.

## 1. Biblioteca de logging estruturado

**Decision**: `structlog`, configurado para emitir JSON via
`structlog.processors.JSONRenderer`, com `correlation_id` injetado por um
`contextvars`-based processor (`structlog.contextvars.bind_contextvars`).

**Rationale**: `structlog` integra nativamente com `contextvars`, o que permite
setar o `correlation_id` uma vez no entrypoint de cada execução (CLI, comando do
Makefile) e tê-lo propagado automaticamente para todo log emitido durante aquela
execução — inclusive por código chamado indiretamente — sem passar o valor
explicitamente por toda a call chain. Isso é exatamente o requisito de FR-006
("`correlation_id` único por execução e presente em toda linha de log daquela
execução").

**Alternatives considered**:
- `logging` padrão + `python-json-logger`: exigiria propagar `correlation_id`
  manualmente via `LoggerAdapter` ou `Filter` customizado em cada chamada — mais
  código e mais fácil de esquecer em um novo módulo futuro.
- `loguru`: JSON estruturado é possível mas o padrão de contexto por execução é menos
  direto que `contextvars` nativo do `structlog`; ecossistema do projeto (Pydantic,
  FastAPI futuro) já é compatível com `structlog` sem fricção.

## 2. Geração e propagação de `correlation_id`

**Decision**: `uuid4()` gerado uma vez no ponto de entrada de cada execução
(cada alvo do `Makefile` que roda um comando Python), bindado via
`structlog.contextvars.bind_contextvars(correlation_id=...)` logo no início.

**Rationale**: UUID4 é suficientemente único sem depender de coordenação externa
(sequência de banco, timestamp+hostname). Bind único no entrypoint satisfaz FR-006
sem exigir que cada módulo saiba gerar ou receber o id.

**Alternatives considered**: ULID (ordenável por tempo) — rejeitado por YAGNI: nada
nesta spec precisa de ordenação lexicográfica de execuções; UUID4 já resolve o
requisito literal.

## 3. Mensagem de erro fail-fast em `Settings`

**Decision**: `pydantic-settings.BaseSettings` com validação padrão do Pydantic
capturada no ponto de instanciação (import-time, em `config.py`, que instancia
`settings = Settings()` no nível de módulo); em caso de `ValidationError`, capturar a
exceção e relançar uma exceção tipada do projeto (`ConfigurationError`) com mensagem
que nomeia a primeira variável ausente e a instrução de copiar `.env.example` para
`.env`, conforme literal da spec ("falta AWS_REGION; copie .env.example para .env").

**Rationale**: Atende FR-004 (nunca vazar traceback cru do Pydantic) e ao Edge Case
de múltiplas variáveis ausentes (reporta ao menos a primeira, sem exigir múltiplas
rodadas) com o menor código possível — sem construir um sistema de coleta e
formatação de todos os erros de uma vez, o que seria mais robusto mas não é exigido
por nenhum critério de aceite (YAGNI).

**Alternatives considered**: Deixar o `ValidationError` do Pydantic vazar direto —
rejeitado, viola FR-004 explicitamente. Construir um formatter que lista *todas* as
variáveis ausentes de uma vez — considerado, mas o Edge Case da spec só exige "pelo
menos a primeira de forma clara"; a superfície mínima que satisfaz o critério é
preferível (Princípio III, KISS).

## 4. Gerenciamento de dependências: `pyproject.toml` vs `requirements.txt`

**Decision**: `pyproject.toml` como fonte de verdade (PEP 621, `[project.dependencies]`),
com `requirements.txt` gerado/mantido como lock reprodutível simples via
`pip freeze` ou `pip-compile`, conforme FR-001 que cita ambos.

**Rationale**: `pyproject.toml` é o padrão moderno do ecossistema Python e já é
necessário para configurar `ruff` e `pytest` no mesmo arquivo
(`[tool.ruff]`, `[tool.pytest.ini_options]`), reduzindo o número de arquivos de
configuração soltos na raiz.

**Alternatives considered**: Poetry/PDM — rejeitado por adicionar uma ferramenta de
build extra sem necessidade declarada na stack do briefing, que já assume `pip` via
`make install`.

## 5. Escopo dos alvos `up`/`down` do `Makefile`

**Decision**: `up`/`down` existem no `Makefile` desta spec como placeholders que
imprimem uma mensagem indicando que a implementação real chega na SPEC-016
(conteinerização), sem executar `docker compose` ainda.

**Rationale**: FR-010 exclui Docker explicitamente desta spec; o Edge Case da spec
exige que os alvos existam sem quebrar os demais. Um placeholder textual é a menor
implementação que satisfaz as duas condições simultaneamente.

**Alternatives considered**: Omitir os alvos até a SPEC-016 — rejeitado, viola FR-007
que exige os seis alvos mínimos já nesta spec.
