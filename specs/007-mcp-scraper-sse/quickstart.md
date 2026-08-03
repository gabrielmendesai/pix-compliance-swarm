# Quickstart: Servidor MCP do Scraper com transporte SSE (SPEC-007)

## Pré-requisitos

- Python 3.11+ e dependências instaladas (`pip install -e ".[dev]"` após esta
  feature adicionar `mcp`, `httpx` e `beautifulsoup4` a `pyproject.toml`).
- `.env` preenchido a partir de `.env.example`, com `BCB_BASE_URL`,
  `MCP_SCRAPER_HOST`/`MCP_SCRAPER_PORT` e as variáveis de `OBJECT_STORAGE_*`
  já existentes desde a SPEC-006.
- Site mock do BCB gerado (`python -m fixtures.generate`, SPEC-003) e servido
  localmente (`python -m http.server` a partir de `mock_bcb/`, ou o mesmo em
  thread durante os testes).
- `docker compose up minio -d` (SPEC-006), para que `fetch_normativo` consiga
  persistir o documento bruto coletado.

## Cenário 1 — Subir o site mock e o servidor MCP

```bash
(cd mock_bcb && python -m http.server 8080) &
BCB_BASE_URL=http://localhost:8080 python -m mcp_servers.scraper_sse.server
```

**Resultado esperado**: o servidor MCP sobe em transporte SSE, na porta
configurada por `MCP_SCRAPER_PORT` (default documentado no README do
pacote).

## Cenário 2 — Handshake e listagem de ferramentas (SC-001, SC-002)

```bash
python -c "
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client('http://localhost:<porta>/sse') as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([t.name for t in tools.tools])

asyncio.run(main())
"
```

**Resultado esperado**: `['list_normativos', 'fetch_normativo',
'detect_changes']`, cada uma com `inputSchema`/`outputSchema` visíveis no
objeto retornado.

## Cenário 3 — Detecção de mudança determinística (SC-003)

```bash
pytest tests/test_scraper_mcp_server.py -k detect_changes -q
```

**Resultado esperado**: duas chamadas consecutivas a `detect_changes` sem
alteração no site mock retornam lista vazia nas duas; após o teste alterar um
fixture (via `fixtures.generate` ou escrita direta em `mock_bcb/`), uma nova
chamada retorna o item alterado — documentado em `contracts/scraper_mcp.md`,
cenário 5.

## Cenário 4 — Buscar e listar normativos individuais

```bash
pytest tests/test_scraper_fetcher.py tests/test_scraper_adapter.py -q
```

**Resultado esperado**: `Fetcher` coleta conteúdo com retry/backoff e
calcula hash corretamente; `MockBcbAdapter` interpreta a listagem e cada
página individual do site mock, extraindo `id`/`titulo`/`url` corretamente —
documentado em `contracts/scraper_mcp.md`, cenários 2 e 3.

## Cenário 5 — Validar a documentação de integração por um terceiro (SC-004)

```bash
cat mcp_servers/scraper_sse/README.md
```

**Resultado esperado**: o README contém um bloco de configuração pronto para
copiar (URL do servidor, transporte SSE, exemplo de chamada a cada uma das
três ferramentas) suficiente para configurar e chamar o servidor sem
contexto adicional — este é o próprio critério de aceite SC-004, verificado
por leitura humana (não há comando automatizável para "suficiência de
documentação para um terceiro").

## Checklist de leitura antes de implementar

- [research.md](./research.md) — decisões de SDK MCP/SSE, parser HTML,
  cliente HTTP do Fetcher, persistência de estado de hash no `ObjectStore`,
  fixture de teste do site mock.
- [data-model.md](./data-model.md) — `NormativoFilter`, `NormativoListItem`,
  `FetchNormativoResult`, `ChangeRecord`, estado `known-hashes.json`, e a
  única exceção do projeto ao Princípio II (`Adapter`).
- [contracts/scraper_mcp.md](./contracts/scraper_mcp.md) — assinatura das
  três ferramentas MCP, do `Protocol` `Adapter` e da classe `Fetcher`, e
  cenários de contrato cobertos por teste.

**Lembrete do Princípio IX**: `tests/test_scraper_fetcher.py`,
`tests/test_scraper_adapter.py` e `tests/test_scraper_mcp_server.py` devem
ser escritos e confirmados como falhos (por ausência de implementação) antes
de `fetcher.py`/`adapters.py`/`server.py` existirem — ver ordenação de
tarefas em `tasks.md` (gerado por `/speckit-tasks`).
