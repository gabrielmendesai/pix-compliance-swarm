# Quickstart: Scraper Agent (SPEC-008)

## Pré-requisitos

- Dependências instaladas: `pip install -e ".[dev]"` (adiciona
  `pydantic-ai-slim[mcp]` — traz o cliente `fastmcp` necessário para
  `MCPToolset`).
- `.env` preenchido a partir de `.env.example`, incluindo `BCB_BASE_URL`,
  `MCP_SCRAPER_HOST`/`MCP_SCRAPER_PORT` (SPEC-007) e as credenciais
  Bedrock/object storage já existentes.
- Site mock do BCB gerado e servido (`python -m fixtures.generate`,
  `python -m http.server 8080` a partir de `mock_bcb/`).
- Servidor MCP do Scraper rodando (`python -m mcp_servers.scraper_sse.server`,
  SPEC-007).
- `docker compose up postgres minio -d` (SPEC-006).

## Cenário 1 — Execução via CLI coleta o corpus e devolve `ScrapeResult` (SC-001)

```bash
python -m pix_compliance.agents.scraper_agent
```

**Resultado esperado**: o agente conecta ao servidor MCP, decide o que
coletar (`list_normativos`/`detect_changes`), coleta cada normativo via
`fetch_normativo`, e imprime um `ScrapeResult` válido (JSON) — sem nenhum
campo de conteúdo estruturado/extraído.

## Cenário 2 — Queda do servidor MCP durante a execução produz erro tipado (SC-002)

```bash
pytest tests/test_scraper_agent.py -k transport_error -q
```

**Resultado esperado**: o teste sobe o servidor MCP via fixture programática,
inicia a execução do agente, derruba o servidor no meio da execução, e
confirma que `run_scraper_agent(...)` levanta `ScraperTransportError` (após
a política de retry se esgotar) — nunca um traceback cru do cliente MCP
subjacente. Documentado em `contracts/scraper_agent.md`, cenário 2.

## Cenário 3 — Suíte completa do agente (execução de ponta a ponta)

```bash
pytest tests/test_scraper_agent.py -q
```

**Resultado esperado**: todos os testes passam, incluindo a execução
completa contra o servidor MCP real (subido/derrubado programaticamente pela
fixture de teste) e `TestModel`/`FunctionModel` no lugar de uma chamada real
ao Bedrock (`LLM_PROVIDER=offline`).

## Cenário 4 — `SKILL.md` documenta o padrão para os seis agentes seguintes (SC-003)

```bash
cat skills/scraper-skill/SKILL.md
```

**Resultado esperado**: o arquivo descreve responsabilidade, ferramentas
disponíveis (MCP), input e output (`ScrapeResult`) do Scraper Agent — este é
o próprio critério de aceite SC-003, verificado por leitura humana (não há
comando automatizável para "adequação de formato para reutilização futura").

## Checklist de leitura antes de implementar

- [research.md](./research.md) — decisões de `MCPToolset`, construção do
  modelo real (`AnthropicModel`/`AsyncAnthropicBedrock`, não
  `get_chat_provider()`), `TestModel`/`FunctionModel` para teste
  determinístico, retry de transporte MCP distinto do fallback de LLM,
  fixture de servidor MCP reaproveitada da SPEC-007.
- [data-model.md](./data-model.md) — `ScrapeResult` (reaproveitando
  `RawDocument`), `ScraperAgentDeps`, `ScraperTransportError`.
- [contracts/scraper_agent.md](./contracts/scraper_agent.md) — assinatura de
  `build_scraper_agent`/`run_scraper_agent`, CLI, e cenários de contrato
  cobertos por teste.

**Lembrete do Princípio IX**: `tests/test_scraper_agent.py` deve ser escrito
e confirmado como falho (por ausência de implementação) antes de
`scraper_agent.py` existir — incluindo a fixture programática do servidor
MCP, reaproveitando o padrão de `tests/test_scraper_mcp_server.py`
(SPEC-007). Ver ordenação de tarefas em `tasks.md` (gerado por
`/speckit-tasks`).
