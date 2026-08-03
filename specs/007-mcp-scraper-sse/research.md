# Research: Servidor MCP do Scraper com transporte SSE (SPEC-007)

## 1. SDK de servidor MCP com transporte SSE

**Decision**: Usar o SDK oficial `mcp` (pacote `mcp`, com `mcp.server.fastmcp.FastMCP`),
registrando as três ferramentas via decorator `@app.tool()` e servindo via
`app.run(transport="sse")` (ou o equivalente ASGI `app.sse_app()` montado sob
um servidor Uvicorn), com host/porta configuráveis por variável de ambiente.

**Rationale**: É o SDK de referência do protocolo MCP, já com transporte SSE
embutido e um cliente de teste próprio (`mcp.client.sse`) que permite testar
handshake e listagem de ferramentas sem escrever um cliente HTTP/SSE manual —
evita reimplementar o protocolo de baixo nível (Princípio II, não construir o
que uma biblioteca madura já resolve).

**Alternatives considered**: Implementar SSE manualmente sobre FastAPI (que o
projeto já usa para a API REST, SPEC-014) foi descartado — reimplementaria a
camada de protocolo MCP (handshake, formato de mensagens JSON-RPC, listagem
de ferramentas com schema) que o SDK `mcp` já expõe pronta e testada.

## 2. Parser HTML do `MockBcbAdapter`

**Decision**: `beautifulsoup4` com o parser `html.parser` da stdlib (sem
`lxml`), para interpretar `mock_bcb/index.html` (página de listagem) e cada
página individual de normativo em `mock_bcb/normativos/`.

**Rationale**: `beautifulsoup4` é a biblioteca padrão de mercado para parsing
HTML tolerante a estrutura imperfeita em Python; usar o parser `html.parser`
da própria stdlib como backend evita a dependência de extensão C (`lxml`),
que pode exigir toolchain de compilação em algumas plataformas — o HTML do
site mock é simples o suficiente (gerado deterministicamente pela SPEC-003)
para não precisar da robustez adicional do `lxml`.

**Alternatives considered**: Parsing via regex foi descartado — HTML não é
uma linguagem regular, e o projeto já reconhece esse limite explicitamente em
`guardrails.py` (comentário sobre por que regex mais validação é aceitável
para CPF/CNPJ, mas não para estrutura de documento). Um parser de árvore DOM
completo (`lxml` puro, sem BeautifulSoup) foi descartado por exigir uma API
mais verbosa para o mesmo resultado, sem ganho para este projeto.

## 3. Cliente HTTP do Fetcher

**Decision**: `httpx.Client` (síncrono, mesmo padrão do restante do projeto,
que não usa `asyncio` em nenhuma outra camada), com `tenacity` (`retry`,
`wait_exponential`) envolvendo cada requisição para retry com backoff, e um
limitador de taxa simples (intervalo mínimo entre requisições consecutivas à
mesma origem, via `time.monotonic()`) para respeitar rate limit.

**Rationale**: `httpx` é o cliente HTTP padrão de mercado em Python com uma
API mais moderna que `requests` (suporte nativo a HTTP/2, tipagem), e já é
mencionado explicitamente na spec como escolha do usuário. `tenacity` já é
dependência do projeto (SPEC-005, cadeia de fallback do Bedrock) — reaproveitar
em vez de introduzir uma segunda biblioteca de retry.

**Alternatives considered**: `requests` foi descartado por ser a escolha
explícita do usuário ser `httpx`; implementar retry manual com `time.sleep`
em loop foi descartado pelo mesmo raciocínio já registrado em `research.md`
da SPEC-005 (reinventar uma solução que `tenacity` já resolve).

## 4. Persistência do estado de "último hash conhecido"

**Decision**: Um único blob JSON (`{normativo_id: hash_sha256}`), persistido
sob uma chave fixa (`scraper-state/known-hashes.json`) no `ObjectStore`
(SPEC-006) — lido no início de cada chamada a `detect_changes`, comparado
contra os hashes atuais coletados pelo Fetcher, e regravado (sobrescrito) ao
final da chamada com os hashes atualizados.

**Rationale**: O `ObjectStore` já existe e já é dependência desta feature
(para persistir o documento bruto de `fetch_normativo`); reaproveitar a mesma
primitiva para um pequeno blob de estado evita introduzir um banco de dados
ou arquivo local dedicado só para isso (Princípio III, KISS) — o volume de
estado (um hash por normativo, dezenas de registros no corpus fictício) não
justifica uma tabela relacional própria.

**Alternatives considered**: Uma tabela dedicada no Postgres (reaproveitando
a conexão já usada por `PgVectorStore`) foi considerada e descartada — o
estado não é vetorial nem se beneficia de índice de similaridade; um blob
JSON no object store já resolve com uma primitiva mais simples e já testada
(SPEC-006). Um arquivo local no disco do processo do servidor foi descartado
por não sobreviver a reinício de container sem um volume adicional dedicado
— o object store já é persistente entre reinícios via docker-compose.

## 5. Fixture de teste servindo `mock_bcb/` via HTTP

**Decision**: Reaproveitar o mesmo padrão já usado em
`tests/test_fixtures.py::test_mock_bcb_serve_pagina_de_listagem_via_http_server`
— um `http.server.HTTPServer` da stdlib, servindo `mock_bcb/` em uma porta
efêmera (`("127.0.0.1", 0)`), rodando em thread daemon durante a duração do
teste, com `BCB_BASE_URL` apontando para essa porta.

**Rationale**: Já é o padrão estabelecido no projeto para servir o site mock
em teste (SPEC-003); reaproveitar evita duas formas diferentes de subir o
mesmo servidor de arquivo estático no repositório.

**Alternatives considered**: Rodar `mock_bcb/` como um serviço adicional em
`docker-compose.yml` foi considerado e descartado para os testes desta
feature — adicionaria uma dependência de Docker aos testes de Fetcher/Adapter
que não precisam dela, quando um `http.server` em thread já é suficiente e
mais rápido de rodar em CI.

## 6. Cliente MCP de teste para verificar handshake e listagem de ferramentas

**Decision**: Usar o cliente de teste do próprio SDK `mcp`
(`mcp.client.sse.sse_client` + `mcp.ClientSession`), conectando ao servidor
SSE subido em processo/thread separado durante o teste, chamando
`session.list_tools()` e comparando os nomes/schemas das três ferramentas.

**Rationale**: É o cliente de referência do mesmo SDK usado no servidor —
qualquer divergência de comportamento entre o "que o servidor expõe" e "o que
um cliente MCP externo consegue descobrir" fica coberta pelo próprio SDK,
sem reimplementar um cliente SSE/JSON-RPC ad-hoc só para teste.

**Alternatives considered**: Testar apenas as funções Python das três
ferramentas diretamente (sem subir o servidor SSE de fato) foi descartado
para os critérios SC-001/SC-002 — testaria a lógica de negócio, mas não o
requisito nominal do desafio (handshake MCP via SSE, descoberta de
ferramentas), que é justamente o que esta spec precisa comprovar.

## Resumo de dependências novas

| Pacote | Uso | Justificativa |
|---|---|---|
| `mcp` | Servidor e cliente MCP, transporte SSE embutido | SDK oficial do protocolo, evita reimplementar handshake/JSON-RPC |
| `httpx` | Cliente HTTP do Fetcher | Escolha explícita do usuário na spec; API moderna, síncrona |
| `beautifulsoup4` | Parser HTML do `MockBcbAdapter` | Padrão de mercado para parsing tolerante; `html.parser` da stdlib evita dependência de `lxml` |

`tenacity` e `pydantic` já são dependências existentes (SPEC-005/SPEC-001) e
são reaproveitadas sem alteração. `ObjectStore`/`S3ObjectStore` (SPEC-006)
são reaproveitados sem alteração de contrato.

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
