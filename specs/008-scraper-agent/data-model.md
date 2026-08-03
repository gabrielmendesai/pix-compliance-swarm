# Data Model: Scraper Agent (SPEC-008)

Todos os modelos seguem o padrão já estabelecido em `models.py`/`llm_provider.py`:
Pydantic v2 (`extra="forbid"`), identificadores em inglês, docstrings em
português explicando o porquê.

## ScrapeResult (novo modelo de domínio — `output_type` do agente)

Adicionado a `src/pix_compliance/models.py`, junto aos demais modelos de
domínio, e incluído em `MODELOS_PUBLICOS`.

| Campo | Tipo | Validação | Descrição |
|---|---|---|---|
| `documentos` | `list[RawDocument]` | default `[]` | Documentos coletados nesta execução — reaproveita `RawDocument` (já existente: `source_uri`, `content_type`, `bytes_ref`, `hash_conteudo`, `coletado_em`), sem duplicar campos |
| `total_coletado` | `int` | `ge=0` | Quantidade de documentos em `documentos` — campo derivado, mas explícito no schema para facilitar consumo por quem lê o resultado sem recontar a lista |
| `executado_em` | `datetime` | obrigatório | Instante de conclusão da execução do agente |

**Regra de negócio**: `ScrapeResult` MUST NOT conter nenhum campo de
conteúdo estruturado/extraído (artigo, inciso, categoria) — apenas dados de
coleta. Extração de campos é responsabilidade de uma feature futura
(Extractor Agent), conforme Escopo — fora do spec.md.

## ScraperAgentDeps (dependências injetadas via `RunContext`)

Não é um modelo Pydantic — é uma `dataclass` concreta (sem `Protocol`,
Princípio II: não há uma segunda implementação de "dependências do Scraper
Agent" neste projeto), consumida pelas ferramentas do agente através de
`RunContext[ScraperAgentDeps]`.

| Campo | Tipo | Descrição |
|---|---|---|
| `object_store` | `ObjectStore` | Reaproveitado da SPEC-006, usado para confirmar/referenciar a persistência de cada documento coletado pelo servidor MCP |

## ScraperTransportError (exceção tipada, hierarquia própria)

Não é um modelo Pydantic — hierarquia de exceção Python própria deste
módulo, análoga a `ConfigurationError` (SPEC-001) e `BedrockProviderError`
(SPEC-005), mas isolada desta última: representa falha de rede/conexão com
o servidor MCP, uma dependência externa diferente do provider LLM.

| Exceção | Quando é levantada | Mensagem |
|---|---|---|
| `ScraperTransportError` | A política de retry de transporte MCP esgota as tentativas configuradas | Inclui a URL do servidor MCP alvo e o número de tentativas feitas |

**Regra de negócio**: `ScraperTransportError` MUST NUNCA ser confundida com
`BedrockProviderError` (SPEC-005) — são hierarquias de exceção separadas,
cada uma cobrindo uma dependência externa distinta (servidor MCP vs. modelo
LLM), mesmo que ambas apareçam durante a mesma execução do agente.

## Ponto de configuração do modelo (não é `Protocol` — não há seam nesta feature)

```
"bedrock"  → AnthropicModel(settings.bedrock_model_id,
                             provider=AnthropicProvider(anthropic_client=AsyncAnthropicBedrock(...)))
"offline"  → TestModel() / FunctionModel(...)  (biblioteca Pydantic AI, não um double do projeto)
```

Selecionado pela mesma leitura de `settings.llm_provider` já usada por
`get_chat_provider()` (SPEC-005), mas não é um `Protocol` novo do projeto —
`pydantic_ai.models.Model` já é a abstração (de terceiros) que cobre esse
ponto de troca; não se cria uma segunda camada de abstração por cima dela.
