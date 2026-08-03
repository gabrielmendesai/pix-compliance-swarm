# Servidor MCP do Scraper (transporte SSE)

Expõe a coleta de normativos do site mock do BCB (`mock_bcb/`, SPEC-003)
como um servidor MCP em transporte SSE, com três ferramentas tipadas:
`list_normativos`, `fetch_normativo` e `detect_changes`. Requisito nominal
do desafio original (SPEC-007).

## Pré-requisitos

- Dependências instaladas: `pip install -e ".[dev]"` (inclui `mcp==1.29.0`,
  `httpx`, `beautifulsoup4`).
- `.env` preenchido a partir de `.env.example` na raiz do repositório —
  em particular `BCB_BASE_URL`, `MCP_SCRAPER_HOST`, `MCP_SCRAPER_PORT` e as
  variáveis `OBJECT_STORAGE_*`/`POSTGRES_DSN` já usadas pela SPEC-006.
- Site mock do BCB gerado e servido:
  ```bash
  python -m fixtures.generate       # gera mock_bcb/, se ainda não existir
  (cd mock_bcb && python -m http.server 8080)
  ```
- Object storage disponível (`docker compose up minio -d`), para que
  `fetch_normativo`/`detect_changes` consigam persistir estado.

## Subir o servidor

```bash
python -m mcp_servers.scraper_sse.server
```

O servidor sobe em transporte SSE em `http://<MCP_SCRAPER_HOST>:<MCP_SCRAPER_PORT>`,
com dois endpoints:

- `GET  /sse` — abre a conexão SSE e inicia o handshake MCP
- `POST /messages/` — canal de mensagens JSON-RPC do cliente para o servidor

## Bloco de configuração (pronto para copiar)

```text
Transporte: SSE
URL:        http://127.0.0.1:8100/sse
```

Exemplo de cliente Python (SDK `mcp`):

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://127.0.0.1:8100/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Descobrir as três ferramentas e seus schemas
            tools = await session.list_tools()
            print([t.name for t in tools.tools])

            # list_normativos — sem filtro
            result = await session.call_tool("list_normativos", {"filtros": {}})
            print(result.structuredContent["result"])

            # list_normativos — com filtro por número (substring do id)
            result = await session.call_tool(
                "list_normativos", {"filtros": {"numero": "101-2021"}}
            )
            print(result.structuredContent["result"])

            # fetch_normativo — persiste no ObjectStore, retorna só metadados
            # (hash, chave de persistência) — nunca o conteúdo bruto em si,
            # para que texto de documento nunca volte ao contexto de um LLM
            # sem passar por guard() (Princípio V; ver nota abaixo)
            result = await session.call_tool(
                "fetch_normativo", {"id": "normativo-101-2021-v1"}
            )
            print(result.structuredContent)  # objeto único, sem wrapper "result"

            # detect_changes — desde o início, ou a partir de um timestamp
            result = await session.call_tool("detect_changes", {})
            print(result.structuredContent["result"])

asyncio.run(main())
```

## As três ferramentas

| Ferramenta | Entrada | Saída |
|---|---|---|
| `list_normativos` | `NormativoFilter` (`categoria`, `numero`, ambos opcionais) | `list[NormativoListItem]` |
| `fetch_normativo` | `id: str` | `FetchNormativoResult` (hash, chave no ObjectStore — nunca o conteúdo bruto, ver nota abaixo) |
| `detect_changes` | `since: datetime \| None` | `list[ChangeRecord]` |

Schemas completos (JSON Schema) descobertos via `session.list_tools()` —
gerados automaticamente pelo SDK `mcp` a partir dos modelos Pydantic em
`models.py`, nunca mantidos à mão em dois lugares.

### Nota sobre o filtro de `list_normativos`

O site mock do BCB não expõe metadados estruturados por normativo (apenas
HTML de conteúdo) — por isso o filtro compara por substring
case-insensitive: `numero` contra o identificador (derivado do nome do
arquivo, ex. `normativo-101-2021-v1`), e `categoria` contra o título
coletado (o gerador de fixtures da SPEC-003 embute a categoria como sufixo
do título, ex. "... sobre liquidação").

### Nota sobre `fetch_normativo` nunca retornar o conteúdo bruto

O resultado de uma tool call MCP retorna ao contexto do modelo que chamou a
ferramenta — se `fetch_normativo` devolvesse o texto completo do documento
(que pode conter PII plantada, SPEC-003), esse texto trafegaria a um LLM
consumidor (ex. Scraper Agent, SPEC-008) sem antes atravessar `guard()`
(Princípio V), mesmo que quem chamou a ferramenta não "processe" o conteúdo
semanticamente — a regra do guardrail é sobre qualquer texto que chegue a um
LLM, não sobre texto interpretado deliberadamente. Por isso
`FetchNormativoResult` traz apenas hash e chave de persistência; quem
precisa do conteúdo integral (Extractor Agent, feature futura) lê
diretamente do `ObjectStore` — nesse ponto, `guard()` se aplica antes de
qualquer envio a um LLM.

## Nota de arquitetura: Fetcher vs. Adapter, e a exceção ao Princípio II

A coleta é dividida em duas camadas deliberadamente:

- **`Fetcher`** (`fetcher.py`): genérico e reaproveitável — requisição
  HTTP (`httpx`), retry com backoff (`tenacity`), rate limit, cálculo de
  hash SHA-256. Não sabe nada sobre a estrutura de nenhuma página — funciona
  contra qualquer fonte por URL.
- **`Adapter`** (`Protocol`, `adapters.py`): sabe interpretar a estrutura
  específica do HTML de origem. `MockBcbAdapter` é a única implementação
  concreta hoje.

`Adapter` é a **única interface deste projeto sem uma segunda implementação
concreta** — uma exceção deliberada ao Princípio II da constituição (que
normalmente exige um seam real: duas implementações de fato, ou um teste
que precise substituir a dependência). A justificativa: o cenário de
produção que este `Protocol` antecipa — scraping do `bcb.gov.br` real — é
parte explícita do enunciado do desafio original, mesmo que implementá-lo de
fato esteja fora do escopo de 4 dias desta feature. Sem o `Protocol`, esse
caminho de evolução ficaria implícito; com ele, fica visível no próprio
código.

**Caminho para adicionar um `RealBcbAdapter` no futuro**: implementar a
mesma interface (`list_refs`, `parse_titulo`) interpretando a estrutura real
de `bcb.gov.br` (que difere da estrutura simplificada do site mock), e
trocar apenas `BCB_BASE_URL` para apontar ao domínio real — nenhuma mudança
seria necessária no `Fetcher` (agnóstico à estrutura de página) nem no
`server.py`, que dependem apenas do `Protocol`, não da implementação
concreta.

## Testes

```bash
pytest tests/test_scraper_fetcher.py tests/test_scraper_adapter.py tests/test_scraper_mcp_server.py -q
```

Sobem o servidor real (SSE, via `uvicorn` em thread de teste) e conectam um
cliente MCP real (SDK `mcp`) contra uma cópia efêmera do site mock — sem
mock de protocolo, conforme Princípio VIII da constituição (evidência como
entregável).
