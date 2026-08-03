# Research: Scraper Agent (SPEC-008)

## 1. Toolset MCP para o `Agent` do Pydantic AI

**Decision**: Usar `pydantic_ai.mcp.MCPToolset(client=f"{mcp_url}/sse")`,
passado em `toolsets=[...]` na construção do `Agent` — o SDK infere o
transporte SSE a partir da URL, sem precisar construir manualmente um
`SSETransport`/`FastMCPClient` explícito para o caso simples.

**Rationale**: A versão instalada de `pydantic-ai-slim` (2.22.0) usa a
biblioteca `fastmcp` (extra `[mcp]`) como cliente MCP por baixo de
`MCPToolset` — testado em spike manual: o servidor MCP da SPEC-007
(`mcp.server.fastmcp.FastMCP`/`sse_app()`) é diretamente compatível como
alvo de conexão de um `MCPToolset`, sem nenhuma alteração no servidor. Isso
confirma que o servidor da SPEC-007 e o cliente usado pelo agente falam o
mesmo protocolo MCP padrão, apesar de virem de pacotes Python distintos
(`mcp` no servidor, `fastmcp` no cliente do agente) — ambos implementam a
mesma especificação.

**Alternatives considered**: Usar o SDK `mcp` de baixo nível diretamente
dentro do agente (o mesmo `mcp.client.sse.sse_client`/`ClientSession` usado
nos testes da SPEC-007) foi descartado — reimplementaria manualmente o loop
de tool-calling que `MCPToolset`/`Agent` já resolvem de forma integrada ao
ciclo de vida do agente (Princípio II, não reinventar o que a biblioteca já
oferece).

## 2. Modelo de chat real: por que não reaproveitar `get_chat_provider()` (SPEC-005)

**Decision**: Construir o modelo do agente diretamente via
`pydantic_ai.models.anthropic.AnthropicModel(settings.bedrock_model_id,
provider=AnthropicProvider(anthropic_client=AsyncAnthropicBedrock(
aws_access_key=..., aws_secret_key=..., aws_region=...)))`, reaproveitando
apenas as credenciais/`model_id` de `Settings` — não a função
`get_chat_provider()`/o `Protocol` `ChatProvider` da SPEC-005.

**Rationale**: `ChatProvider.complete(prompt: str) -> str` (SPEC-005) é uma
interface de texto simples (um prompt entra, um texto sai) — não expõe tool
calling, obrigatório para um `Agent` usar um `MCPToolset` (o modelo precisa
poder decidir "chamar a ferramenta X com estes argumentos" e receber o
resultado de volta na conversa, o que `Agent`/`Model` do Pydantic AI
orquestram nativamente). `AnthropicProvider` aceita um cliente Anthropic
assíncrono customizado (`anthropic_client`) — verificado em spike manual que
`anthropic.AsyncAnthropicBedrock` (variante assíncrona do mesmo
`AnthropicBedrock` já usado em `llm_provider.py`) se encaixa exatamente nesse
parâmetro, preservando a mesma via de autenticação (credenciais explícitas a
partir de `Settings`, nunca resolução implícita) já estabelecida na SPEC-005.

**Alternatives considered**: Adaptar `ChatProvider` para suportar tool
calling foi descartado — mudaria o contrato já congelado e testado da
SPEC-005 para todos os seus consumidores atuais (que não precisam de tool
calling), só para servir este agente; mais simples e menos arriscado
construir o `Model` do Pydantic AI diretamente aqui, reaproveitando apenas a
configuração (não o código do provider).

## 3. Execução determinística em teste ("offline" para agentes)

**Decision**: Usar `pydantic_ai.models.test.TestModel` (ou
`FunctionModel`, quando for necessário controlar precisamente quais
ferramentas o modelo "decide" chamar e com quais argumentos) como o modelo
do agente quando `settings.llm_provider == "offline"`.

**Rationale**: `TestModel`/`FunctionModel` são construções da própria
biblioteca Pydantic AI para testar agentes sem chamada de rede real — o
equivalente, para agentes com tool calling, ao papel que `OfflineProvider`
(SPEC-005, `tests/doubles/`) cumpre para o `ChatProvider` de texto simples.
Não há lógica de negócio própria do projeto a duplicar em `tests/doubles/`
neste caso (o determinismo já vem pronto da biblioteca) — o mesmo padrão de
dispatch por `settings.llm_provider` de `get_chat_provider()` é replicado
aqui, apenas trocando qual objeto de teste é retornado.

**Alternatives considered**: Escrever um double próprio (`FunctionModel`
customizado vivendo em `tests/doubles/`) que simula explicitamente a decisão
de chamar `list_normativos`→`fetch_normativo` foi considerado — mantido como
opção para os testes que precisam de determinismo fino sobre a sequência de
chamadas (ex. User Story 1), usando `FunctionModel` com uma função de decisão
escrita no próprio arquivo de teste; `TestModel` simples (que chama
ferramentas com argumentos arbitrários válidos) é suficiente para os testes
que só precisam confirmar que o toolset está corretamente conectado.

## 4. Retry de transporte MCP (distinto do fallback de LLM)

**Decision**: Envolver a chamada de execução do agente (`agent.run_sync(...)`/
`agent.run(...)`) em um decorator/laço `tenacity.Retrying` próprio deste
módulo, capturando exceções de transporte (a serem confirmadas
empiricamente no momento de escrever os testes — candidatas: exceções de
`httpx`/`anyio`/`fastmcp` relacionadas a conexão recusada ou fechada), com
backoff exponencial; ao esgotar tentativas, levantar `ScraperTransportError`
(exceção própria do projeto).

**Rationale**: A spec exige explicitamente que este retry seja distinto do
retry de fallback de `model_id` (`FallbackChainConfig`/`Retrying` já usado em
`llm_provider.py`) — são duas causas de falha diferentes (rede/conexão com
um processo externo vs. disponibilidade de um modelo LLM) que não devem
compartilhar a mesma configuração nem a mesma exceção-base, para que o
diagnóstico de operação continue claro (qual das duas dependências externas
falhou). `tenacity` já é dependência do projeto — reaproveitada, não uma
segunda biblioteca de retry.

**Alternatives considered**: Confiar apenas na reconexão automática interna
do `MCPToolset`/cliente `fastmcp` (se houver) foi considerado insuficiente
isoladamente — a spec pede uma exceção tipada e própria do projeto ao
esgotar tentativas, o que exige uma camada de tratamento explícita neste
módulo, não apenas confiar em um comportamento implícito da biblioteca
cliente.

## 5. Fixture de teste do servidor MCP (reaproveitando SPEC-007)

**Decision**: Reaproveitar o mesmo padrão de fixture já usado em
`tests/test_scraper_mcp_server.py` (`running_server`: thread + `uvicorn` +
`app.sse_app()`, subindo/derrubando o servidor MCP real da SPEC-007
programaticamente), com a extensão de que um teste específico desta feature
(User Story 2) derruba o servidor **no meio** da execução do agente (não
apenas antes de iniciar), para exercitar de fato a política de retry de
transporte.

**Rationale**: É exatamente o requisito explícito da spec — testes que não
dependem de um terminal separado rodando o servidor manualmente, permitindo
rodar a suíte inteira com um único comando (`pytest`). Reaproveitar o padrão
já validado na SPEC-007 evita reinventar a mesma fixture com uma segunda
forma de subir/derrubar o mesmo tipo de servidor.

**Alternatives considered**: Mockar o `MCPToolset`/cliente MCP inteiramente
(sem subir um servidor real) foi descartado para os testes de aceite
principais (SC-001/SC-002) — a spec exige demonstrar o comportamento contra
o protocolo MCP real, incluindo a falha de conexão real ao derrubar o
processo do servidor, não uma simulação de exceção.

## Resumo de dependências novas

| Pacote | Uso | Justificativa |
|---|---|---|
| `pydantic-ai-slim[mcp]` | `Agent`, `MCPToolset`, `AnthropicModel`, `TestModel` | Extra `[mcp]` traz o cliente `fastmcp`, necessário para `MCPToolset` conectar ao servidor SSE da SPEC-007 |

`anthropic` (`AsyncAnthropicBedrock`), `tenacity` e `pydantic` já são
dependências existentes (SPEC-005/SPEC-001) e são reaproveitadas sem
alteração. `ObjectStore`/`S3ObjectStore` (SPEC-006) é reaproveitado sem
alteração de contrato.

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
