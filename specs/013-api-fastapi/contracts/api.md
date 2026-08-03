# Contrato: `src/pix_compliance/api/` (SPEC-013)

Esta é a primeira feature do projeto cujo contrato é uma API HTTP externa
de verdade — documentado aqui como rotas REST, não como assinatura de
função Python.

## `GET /normativos`

**Query params**: `tipo?: str`, `categoria?: str`, `data_inicio?: date`,
`data_fim?: date`, `page: int = 1`, `page_size: int = 20`.

**Response 200**: `PaginatedResponse[NormativoItem]`.

**Response 422**: `ErrorResponse` — parâmetro de query malformado (ex.
`data_inicio` não é uma data válida).

**Comportamento**: Lê `fixtures/normativos.json` (research.md, Decisão 0),
filtra por `tipo`/`categoria` (igualdade) e por período (`data_publicacao`
dentro de `[data_inicio, data_fim]`, quando informados), pagina o resultado
filtrado.

## `GET /compliance`

**Query params**: `severidade_min?: float`.

**Response 200**: `PaginatedResponse[ConformanceItem]` (ou `list[ConformanceItem]`
diretamente — decisão de implementação, ver tasks.md).

**Response 422**: `ErrorResponse` — `severidade_min` fora do intervalo
`[0, 1]`.

**Comportamento**: Agrega `itens` de todos os `reports/*.conformance.json`
já persistidos (research.md, Decisão 1), filtra por `severidade >=
severidade_min` quando informado.

## `GET /search`

**Query params**: `query: str` (obrigatório), `top_k: int = 5`.

**Response 200**: `list[SearchResult]`.

**Response 422**: `ErrorResponse` — `query` ausente/vazio, ou `top_k <= 0`.

**Comportamento**: Delega a `knowledge_builder_agent.search(settings,
vector_store, SearchQuery(query=query, top_k=top_k))` (SPEC-012), sem
lógica adicional.

## `GET /health`

**Query params**: nenhum.

**Response 200**: corpo estruturado (`{"status": "ok" | "degraded",
"dependencies": {"object_store": "ok" | "falhou: ...", "vector_store": "ok"
| "falhou: ..."}}`) — não reaproveita um modelo de domínio da SPEC-002
(nenhum modelo de "saúde do sistema" existe lá), mas também não introduz um
segundo schema de negócio: é puramente infraestrutura de observabilidade.

**Comportamento**: Tenta instanciar `S3ObjectStore(settings)` e
`PgVectorStore(settings)`, captura exceção por dependência (research.md,
Decisão 2), nunca retorna 500 por conta própria de uma dependência
indisponível — o status geral é `"degraded"` quando qualquer dependência
falha, `"ok"` quando todas respondem.

## `POST /runs`

**Request body**: `PipelineRequest`.

**Response 200**: `PipelineResult` — sempre já completo (execução síncrona,
research.md, Decisão 4).

**Response 422**: `ErrorResponse` — corpo malformado (ex. `fontes` vazio,
violando `Field(min_length=1)` já existente em `PipelineRequest`).

**Comportamento**: Orquestra, nesta ordem, os agentes já implementados
correspondentes às `fontes` informadas: Scraper → Extractor → Compliance
Analyzer → Conformance Validator → Knowledge Builder (indexação) → Report
Consolidator. Grava `reports/<report_id>.conformance.json` (data-model.md)
antes de retornar. Erros de qualquer etapa são capturados e refletidos em
`PipelineResult.sucesso=False`/`erro=<mensagem>`, não uma exceção não
tratada (edge case de spec.md).

## Exception handlers globais

| Exceção | Status | Corpo |
|---|---|---|
| `RequestValidationError` (FastAPI/Pydantic) | 422 | `ErrorResponse` com `errors` preenchido a partir de `exc.errors()` |
| `ObjectNotFoundError` (SPEC-006) / recurso não encontrado | 404 | `ErrorResponse` |
| `Exception` (qualquer erro não tratado) | 500 | `ErrorResponse`, sem vazar traceback no corpo (mensagem genérica + `correlation_id` para correlacionar com o log estruturado) |

## Metadados de OpenAPI

`FastAPI(title=..., description=..., version=..., openapi_tags=[...])` —
título, descrição e versão do projeto preenchidos; cada rota declara
`summary`, `description` e `responses` com exemplo de corpo (FR-008); `/docs`
(Swagger UI) e `/redoc` disponíveis nos caminhos default do FastAPI.

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. Cada uma das 5 rotas retorna 200 com um corpo que valida contra seu
   `response_model` quando a requisição é bem formada (SC-002).
2. Cada rota retorna 422 com `ErrorResponse` (incluindo `correlation_id`)
   quando a requisição é malformada — nunca o corpo cru do FastAPI (SC-002,
   SC-003).
3. Uma rota que busca um recurso inexistente retorna 404 com `ErrorResponse`
   (SC-002).
4. `/docs` responde 200 e contém a descrição/exemplo preenchidos de cada
   rota, não os placeholders genéricos do FastAPI (SC-001).
