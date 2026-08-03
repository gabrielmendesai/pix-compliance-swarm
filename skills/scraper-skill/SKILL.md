# Scraper Skill

Documenta o Scraper Agent (SPEC-008) — o primeiro agente do enxame,
implementado em `src/pix_compliance/agents/scraper_agent.py`. Este arquivo
estabelece o formato que os seis agentes seguintes do enxame devem seguir:
Responsabilidade, Ferramentas, Input e Output.

## Responsabilidade

O Scraper Agent decide **o quê** coletar do site do BCB (via as ferramentas
MCP `list_normativos` e `detect_changes`) e coleta cada normativo decidido
via `fetch_normativo` — sempre através do protocolo MCP, nunca por import
direto de função do servidor. Este agente **não** contém:

- Lógica de parsing de HTML ou interpretação de estrutura de página — isso
  já vive no servidor MCP do Scraper (`mcp_servers/scraper_sse/`, SPEC-007).
- Lógica de extração de campos estruturados do documento bruto (artigo,
  inciso, categoria) — isso é responsabilidade de uma feature futura
  (Extractor Agent).

Um agente, uma responsabilidade (Princípio IV da constituição): decidir o
que coletar e orquestrar a coleta via ferramentas já existentes, nada além
disso.

## Ferramentas

Todas as ferramentas são expostas pelo servidor MCP do Scraper (SPEC-007,
transporte SSE) e conectadas ao agente via `MCPToolset` (Pydantic AI) — o
agente nunca as chama por import direto:

| Ferramenta | Entrada | Saída | Uso pelo agente |
|---|---|---|---|
| `list_normativos` | `NormativoFilter` (`categoria`, `numero`, opcionais) | `list[NormativoListItem]` | Descobre quais normativos existem no site mock |
| `fetch_normativo` | `id: str` | `FetchNormativoResult` (hash, chave no ObjectStore — nunca o conteúdo bruto, ver nota da SPEC-007) | Coleta um normativo específico, já persistido no ObjectStore pelo servidor |
| `detect_changes` | `since: datetime \| None` | `list[ChangeRecord]` | Descobre o que é novo/alterado desde a última coleta |

## Input

Nenhum parâmetro de usuário direto — o Scraper Agent lê toda a configuração
necessária de `Settings` (`BCB_BASE_URL`, `MCP_SCRAPER_HOST`/`MCP_SCRAPER_PORT`,
credenciais Bedrock/object storage), já validada e centralizada desde a
SPEC-001. A execução é disparada via:

```bash
python -m pix_compliance.agents.scraper_agent
```

Dependências injetadas via `RunContext[ScraperAgentDeps]`:

| Campo | Tipo | Descrição |
|---|---|---|
| `object_store` | `ObjectStore` | Reaproveitado da SPEC-006, usado para confirmar/referenciar a persistência de cada documento coletado |

## Output

`ScrapeResult` (modelo Pydantic, `src/pix_compliance/models.py`,
`ConfigDict(extra="forbid")`):

| Campo | Tipo | Descrição |
|---|---|---|
| `documentos` | `list[RawDocument]` | Documentos coletados nesta execução (reaproveita `RawDocument`, já existente) |
| `total_coletado` | `int` | Quantidade de documentos em `documentos` |
| `executado_em` | `datetime` | Instante de conclusão da execução |

`ScrapeResult` **nunca** contém campo de conteúdo estruturado/extraído
(artigo, inciso, categoria) — apenas dados de coleta.

## Tratamento de erro de dependência externa

Falha de conexão com o servidor MCP (rede caiu, servidor derrubado durante a
execução) aciona uma política de retry com backoff própria deste agente
(`tenacity`, `_is_mcp_transport_failure`), distinta e independente da cadeia
de fallback de `model_id` do Bedrock (SPEC-005) — são duas dependências
externas diferentes (servidor MCP vs. modelo LLM). Ao esgotar as tentativas,
o agente levanta `ScraperTransportError` (`scraper_agent.py`), nunca a
exceção crua do cliente MCP subjacente.

## Padrão para os seis agentes seguintes

Todo agente novo do enxame deve documentar, neste mesmo formato de quatro
seções (Responsabilidade, Ferramentas, Input, Output), em
`skills/<nome-do-agente>-skill/SKILL.md`:

1. **Responsabilidade**: o que o agente decide/faz, e o que explicitamente
   não faz (delegado a outra camada/feature).
2. **Ferramentas**: tabela de ferramentas disponíveis (MCP ou não), com
   entrada/saída e uso pelo agente.
3. **Input**: como o agente é invocado e quais dependências recebe via
   `RunContext`/`deps_type`.
4. **Output**: o modelo Pydantic de saída (`output_type`), com a tabela de
   campos.
