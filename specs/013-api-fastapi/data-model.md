# Data Model: API FastAPI (SPEC-013)

Esta feature reaproveita integralmente os modelos de domínio já congelados
(SPEC-002) como `response_model`/corpo de request de cada rota. Os únicos
tipos novos são infraestrutura de transporte HTTP (envelope de paginação,
corpo de erro estruturado) — nunca um schema de domínio duplicado ou
paralelo (FR-006).

## Modelos de domínio reaproveitados (já existem — SPEC-002, sem alteração)

| Modelo | Usado por | Papel |
|---|---|---|
| `NormativoItem` | `GET /normativos` | Item individual da listagem paginada |
| `ConformanceItem` | `GET /compliance` | Item individual de gap analysis, com filtro por `severidade` |
| `SearchResult` | `GET /search` | Item individual do resultado de busca semântica |
| `PipelineRequest` | `POST /runs` (corpo da requisição) | `pipeline_id`, `fontes`, `forcar_reprocessamento` |
| `PipelineResult` | `POST /runs` (resposta) | `sucesso`, `report`, `erro`, `iniciado_em`, `concluido_em` |

## Novo (infraestrutura de transporte): `PaginatedResponse`

```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

**Papel**: Envelope de paginação genérico usado por `GET /normativos` (e,
opcionalmente, `GET /compliance` — ver contracts/api.md). Não é um schema de
domínio — `T` é sempre um modelo já existente da SPEC-002 (`NormativoItem`/
`ConformanceItem`); o envelope apenas descreve a página, nunca duplica os
campos do item.

## Novo (infraestrutura de transporte): `ErrorResponse`

```python
class ErrorResponse(BaseModel):
    correlation_id: str
    detail: str
    errors: list[dict] | None = None
```

**Papel**: Corpo estruturado devolvido por todo exception handler desta
feature (FR-007). `correlation_id` vem de
`pix_compliance.logging.bind_run_correlation_id()` (SPEC-001, já
existente); `detail` é uma mensagem legível; `errors` carrega os detalhes
brutos de validação do Pydantic (`RequestValidationError.errors()`) quando
aplicável (422), `None` nos demais casos (404, 500).

## Convenção: persistência local lida por `GET /compliance`

```
reports/<report_id>.json                # ReportOutput (já existente, SPEC-014)
reports/<report_id>.conformance.json     # ConformanceReport completo (NOVO nesta feature)
```

**Regra de negócio**: `POST /runs` grava o `ConformanceReport` completo
produzido pelo Conformance Validator (SPEC-011) em
`reports/<report_id>.conformance.json`, ao lado do `ReportOutput` resumido
já gravado pelo Report Consolidator (SPEC-014) — mesma convenção de nome
determinístico, mesmo diretório. `GET /compliance` agrega os `itens` de
todos os arquivos `*.conformance.json` encontrados em `reports/` (ver
research.md, Decisão 1).

## Parâmetros de consulta (query params) por rota

| Rota | Parâmetros | Tipo | Default |
|---|---|---|---|
| `GET /normativos` | `tipo`, `categoria`, `data_inicio`, `data_fim`, `page`, `page_size` | `str \| None`, `str \| None`, `date \| None`, `date \| None`, `int`, `int` | `None`, `None`, `None`, `None`, `1`, `20` |
| `GET /compliance` | `severidade_min` | `float \| None` | `None` (sem filtro) |
| `GET /search` | `query`, `top_k` | `str`, `int` | (obrigatório), `5` |
