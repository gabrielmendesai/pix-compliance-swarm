# Contrato: `POST /runs`, logging estruturado, CI (SPEC-017)

Esta feature modifica um contrato de API já existente (`POST /runs`) e
define dois contratos novos que não existiam antes: o comportamento do
workflow de CI e o formato mínimo de log da chamada de ferramenta MCP do
Scraper.

## `POST /runs` — contrato revisado

**Antes desta feature** (SPEC-013/015, comportamento atual): executa uma
implementação inline (`_run_pipeline_sync`) que lê `fixtures/normativos.json`
diretamente e roda apenas 4 das 6 etapas do pipeline
(`compliance_analyzer` → `conformance_validator`/`knowledge_builder` →
`report_consolidator`) — nunca invoca Scraper nem Extractor.

**Depois desta feature**: `POST /runs` delega inteiramente a `run_pipeline`
(`src/pix_compliance/agents/orchestrator_agent.py`, SPEC-015), a mesma
função já usada pelo CLI e pelo scheduler — nenhuma segunda implementação
de orquestração permanece. `_run_pipeline_sync` é removido.

```http
POST /runs
Content-Type: application/json

{"pipeline_id": "run-001", "fontes": ["https://mock-bcb.local/"]}
```

**Pós-condição**: resposta `200` com `PipelineResult` cobrindo as seis
etapas (`scrape`, `extract`, `compliance_analyzer`, `knowledge_builder`,
`conformance_validator`, `report_consolidator`) em `resultado.etapas`,
idêntico em estrutura ao que `run_pipeline` já produz para o CLI/scheduler
— a API deixa de ser um caminho de execução divergente.

**Nota de compatibilidade**: o formato de `PipelineRequest`/`PipelineResult`
(schema JSON) não muda — apenas o comportamento interno. Nenhum cliente
existente da API quebra por essa mudança; o corpo da resposta passa a
refletir as seis etapas reais em vez das quatro anteriores.

## Log estruturado — evento por etapa do pipeline

Emitido uma vez por etapa concluída (sucesso ou falha), dentro do mesmo
`correlation_id` da execução:

```json
{
  "event": "pipeline_etapa_concluida",
  "correlation_id": "…",
  "nome": "compliance_analyzer",
  "status": "sucesso",
  "duracao_segundos": 1.42,
  "contadores": {"regras_extraidas": 12, "tokens_consumidos": 480},
  "level": "info",
  "timestamp": "…"
}
```

**Pós-condição verificável**: filtrando os logs de uma execução por
`correlation_id`, todas as seis etapas aparecem com este evento, na ordem
em que ocorreram (User Story 3, SC-002 combinado com FR-006/FR-007).

## Log estruturado — chamada de ferramenta MCP do Scraper

O servidor MCP (`mcp_servers/scraper_sse/`) recebe o `correlation_id` da
execução como parte da chamada de ferramenta (campo adicional no payload
já existente de `list_normativos`/`detect_changes`/`fetch_normativo`) e
revincula esse valor localmente via
`pix_compliance.logging.bind_run_correlation_id`-equivalente (o mesmo
mecanismo de `contextvars`, não uma segunda implementação), antes de
logar entrada/saída de cada ferramenta:

```json
{"event": "mcp_tool_chamada", "correlation_id": "…", "tool": "fetch_normativo", "level": "info", "timestamp": "…"}
{"event": "mcp_tool_concluida", "correlation_id": "…", "tool": "fetch_normativo", "duracao_segundos": 0.31, "level": "info", "timestamp": "…"}
```

**Pós-condição verificável**: os logs do processo/container `mcp-scraper`
filtrados pelo mesmo `correlation_id` da execução do Orchestrator mostram
as chamadas de ferramenta que ocorreram durante o `scrape` daquela
execução específica.

## CI (GitHub Actions) — `.github/workflows/ci.yml`

**Gatilho**: `push` e `pull_request`, qualquer branch.

**Job único**, passos sequenciais:

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
```

**Pós-condição**: o workflow reporta status verde/vermelho diretamente na
interface do GitHub para cada push/PR (SC-003) — nenhuma credencial AWS é
necessária no ambiente de CI, porque a suíte inteira roda com
`LLM_PROVIDER=offline` (Decisão 0/5, research.md).
