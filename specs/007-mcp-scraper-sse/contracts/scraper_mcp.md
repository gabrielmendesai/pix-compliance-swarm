# Contrato: `mcp_servers/scraper_sse/server.py`

Esta feature expõe um servidor MCP real (transporte SSE) — o "contrato" aqui
é tanto o protocolo MCP em si (handshake, listagem de ferramentas) quanto o
schema Pydantic de cada ferramenta, documentado abaixo. O consumidor é
qualquer cliente MCP compatível (o Scraper Agent de uma feature futura, ou
um cliente de inspeção externo/avaliador).

## Handshake e transporte

```text
GET /sse            → abre a conexão SSE, inicia o handshake MCP
POST /messages       → canal de mensagens JSON-RPC do cliente para o servidor
```

Host e porta configuráveis por variável de ambiente (`MCP_SCRAPER_HOST`,
`MCP_SCRAPER_PORT`). Ver README do pacote para o bloco de configuração
pronto para copiar.

## Ferramenta `list_normativos`

```python
def list_normativos(filtros: NormativoFilter) -> list[NormativoListItem]:
    """Lista os normativos disponíveis no site mock do BCB, opcionalmente
    filtrados por categoria/número. Não faz download do conteúdo completo —
    apenas a página de listagem (via Adapter.list_refs())."""
```

## Ferramenta `fetch_normativo`

```python
def fetch_normativo(id: str) -> FetchNormativoResult:
    """Coleta o conteúdo bruto de um normativo específico (via Fetcher +
    Adapter) e persiste uma cópia no ObjectStore (SPEC-006), retornando
    apenas metadados de confirmação (hash SHA-256, chave de persistência) —
    NUNCA o conteúdo bruto em si (adendo pós-implementação: o resultado de
    uma tool call MCP retorna ao contexto do modelo chamador; devolver o
    texto completo faria PII eventualmente plantada no documento, SPEC-003,
    trafegar a um LLM sem passar por guard(), Princípio V — ver data-model.md
    para o detalhe completo). Levanta um erro MCP claro se `id` não
    corresponder a nenhum normativo conhecido."""
```

## Ferramenta `detect_changes`

```python
def detect_changes(since: datetime | None = None) -> list[ChangeRecord]:
    """Coleta o conteúdo atual de todos os normativos listados, compara o
    hash SHA-256 de cada um contra o último hash conhecido (persistido em
    scraper-state/known-hashes.json no ObjectStore), e retorna os que são
    novos ou mudaram. Atualiza o estado de hashes conhecidos ao final da
    chamada. Se `since` for fornecido, filtra apenas mudanças detectadas a
    partir desse instante."""
```

## Protocol `Adapter` (exceção documentada ao Princípio II)

```python
class Adapter(Protocol):
    def list_refs(self) -> list[NormativoRef]:
        """Interpreta a página de listagem da fonte e retorna as referências
        (id, url) de cada normativo."""

    def parse_titulo(self, html: str) -> str:
        """Extrai o título de uma página individual de normativo."""
```

**Nota de arquitetura**: `Adapter` é a única interface deste projeto sem uma
segunda implementação concreta hoje (`MockBcbAdapter` é a única). Ver
docstring completa em `adapters.py` e a seção correspondente no README do
pacote para a justificativa (cenário de produção do desafio original) e o
caminho de evolução (`RealBcbAdapter`, trocando apenas `BCB_BASE_URL`).

## Classe concreta `Fetcher` (sem `Protocol`)

```python
class Fetcher:
    def get(self, url: str) -> FetchedContent:
        """Requisição HTTP com retry/backoff e rate limit, retornando o
        conteúdo bruto e o hash SHA-256 calculado. Não sabe nada sobre a
        estrutura da página — funciona contra qualquer URL."""
```

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. Cliente MCP conecta via SSE, completa o handshake, e lista as três
   ferramentas com seus schemas de entrada/saída (SC-001, SC-002).
2. `list_normativos({})` sem filtro retorna todos os normativos do site mock;
   com filtro, retorna apenas o subconjunto correspondente.
3. `fetch_normativo(id)` para um `id` conhecido retorna metadados de
   confirmação (hash, chave de persistência — nunca o conteúdo bruto), e uma
   cópia idêntica ao fixture de origem é persistida no `ObjectStore`.
4. `fetch_normativo(id)` para um `id` inexistente retorna um erro MCP claro.
5. `detect_changes()` chamado duas vezes seguidas sem alteração no site mock
   retorna lista vazia nas duas vezes; após alterar um fixture, retorna o
   item alterado (SC-003).
