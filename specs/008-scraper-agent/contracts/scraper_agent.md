# Contrato: `src/pix_compliance/agents/scraper_agent.py`

Esta feature não expõe uma API HTTP/CLI de terceiros — o "contrato" é a
interface Python que o CLI deste projeto (e, no futuro, o orquestrador do
enxame) consome. Documentado aqui em vez de OpenAPI/JSON Schema porque o
consumidor é código Python interno ou um operador via terminal, não um
cliente HTTP externo.

## Função pública: `build_scraper_agent`

```python
def build_scraper_agent(settings: Settings, mcp_url: str) -> Agent[ScraperAgentDeps, ScrapeResult]:
    """Monta o Agent com deps_type=ScraperAgentDeps, output_type=ScrapeResult,
    e o toolset MCP (MCPToolset) apontando para mcp_url. O modelo é
    selecionado por settings.llm_provider: AnthropicModel/AnthropicProvider
    (AsyncAnthropicBedrock) em produção, TestModel/FunctionModel em teste."""
```

## Função pública: `run_scraper_agent`

```python
def run_scraper_agent(
    settings: Settings, mcp_url: str, object_store: ObjectStore
) -> ScrapeResult:
    """Executa o Scraper Agent de ponta a ponta (run_sync), envolto pela
    política de retry de transporte MCP (tenacity, distinta do fallback de
    model_id da SPEC-005). Levanta ScraperTransportError se as tentativas de
    retry se esgotarem por falha de conexão com o servidor MCP."""
```

**Pré-condição**: o servidor MCP do Scraper (SPEC-007) já deve estar
respondendo em `mcp_url` (transporte SSE) antes da chamada.

**Pós-condição em sucesso**: retorna um `ScrapeResult` validado, sem nenhum
campo de conteúdo estruturado/extraído.

**Pós-condição em falha de transporte**: levanta `ScraperTransportError`,
com a URL do servidor MCP e o número de tentativas feitas na mensagem —
nunca a exceção crua do cliente MCP/`httpx`/`anyio` subjacente.

## `ScraperAgentDeps` (ver data-model.md)

```python
@dataclass
class ScraperAgentDeps:
    object_store: ObjectStore
```

## Exceção exposta (ver data-model.md para detalhe completo)

```python
class ScraperTransportError(Exception): ...
```

## CLI

```bash
python -m pix_compliance.agents.scraper_agent
```

Lê configuração de `Settings` (incluindo `bcb_base_url`,
`mcp_scraper_host`/`mcp_scraper_port` já existentes desde a SPEC-007),
executa `run_scraper_agent(...)`, e imprime o `ScrapeResult` (JSON) na saída
padrão — este é o comando verificado pelo critério de aceite SC-001.

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. `run_scraper_agent(...)` com o servidor MCP rodando e apontando para o
   site mock do BCB → `ScrapeResult` válido, refletindo os documentos do
   site mock (SC-001).
2. `run_scraper_agent(...)` com o servidor MCP derrubado durante a execução
   → `ScraperTransportError`, após a política de retry se esgotar (SC-002).
3. `skills/scraper-skill/SKILL.md` existe e descreve responsabilidade,
   ferramentas, input e output (SC-003).
