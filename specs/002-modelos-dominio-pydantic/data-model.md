# Data Model: Modelos de domínio Pydantic v2 (SPEC-002)

Todos os modelos vivem em `src/pix_compliance/models.py` e usam
`model_config = ConfigDict(extra="forbid")` (FR-015). Modelos imutáveis por natureza
semântica usam `frozen=True` (FR-017), marcado explicitamente abaixo.

## Enums (StrEnum, FR-016)

### TipoNormativo
Vocabulário fechado do tipo de ato normativo.
- `RESOLUCAO_BCB` = "Resolução BCB"
- `INSTRUCAO_NORMATIVA` = "Instrução Normativa"
- `CIRCULAR` = "Circular"
- `COMUNICADO` = "Comunicado"

### CategoriaCompliance
As 6 categorias fechadas de compliance (FR-002, Assumptions).
- `PARTICIPANTES` = "participantes"
- `TARIFAS` = "tarifas"
- `LIQUIDACAO` = "liquidação"
- `SEGURANCA` = "segurança"
- `SLA` = "SLA"
- `INTEROPERABILIDADE` = "interoperabilidade"

### Obrigatoriedade
Grau de obrigatoriedade de uma regra extraída.
- `OBRIGATORIO` = "obrigatório"
- `RECOMENDADO` = "recomendado"
- `OPCIONAL` = "opcional"

### StatusConformidade
Vocabulário fechado de status de um `ConformanceItem` (FR-004).
- `CONFORME` = "conforme"
- `NAO_CONFORME` = "não conforme"
- `NOVO` = "novo"
- `ALTERADO` = "alterado"
- `REVOGADO` = "revogado"

Todos os enums acima aceitam coerção case-insensitive quando o valor de entrada é uma
string, via `field_validator(mode="before")` nos modelos que os usam (FR-013,
research.md §5).

## Entidades

### NormativoItem (`frozen=True`)
Item normativo do BCB/PIX já processado.

| Campo | Tipo | Regras |
|---|---|---|
| `id` | `str` (UUID) | obrigatório |
| `titulo` | `str` | não vazio pós-strip, espaços colapsados (FR-011) |
| `tipo` | `TipoNormativo` | enum, coerção case-insensitive |
| `numero` | `str` | regex `^\d{1,6}(\.\d{3})*\/\d{4}$` (FR-014, research.md §1) |
| `artigo` | `str \| None` | opcional |
| `inciso` | `str \| None` | opcional |
| `texto` | `str` | não vazio pós-strip, espaços colapsados (FR-011) |
| `data_publicacao` | `date` | obrigatório |
| `data_vigencia` | `date` | obrigatório; `>= data_publicacao` (FR-009, `model_validator(mode="after")`) |
| `categoria` | `CategoriaCompliance` | enum, coerção case-insensitive |
| `url_origem` | `HttpUrl` | obrigatório |
| `hash_conteudo` | `str` | SHA-256 hex, 64 chars (FR-010) |
| `versao` | `int` | `>= 1` |

**Validação cruzada**: `model_validator(mode="after")` rejeita `data_vigencia <
data_publicacao` (regra de negócio: um normativo não pode entrar em vigor antes de ser
publicado; igualdade no mesmo dia é permitida — Edge Case da spec).

### RegraExtraida
Regra de compliance individual extraída de um `NormativoItem`.

| Campo | Tipo | Regras |
|---|---|---|
| `regra_id` | `str` (UUID) | obrigatório |
| `normativo_id` | `str` (UUID) | referencia `NormativoItem.id` |
| `categoria` | `CategoriaCompliance` | enum, coerção case-insensitive |
| `enunciado` | `str` | não vazio pós-strip, espaços colapsados |
| `obrigatoriedade` | `Obrigatoriedade` | enum |
| `prazo` | `date \| None` | opcional (nem toda regra tem prazo) |
| `atores_afetados` | `list[str]` | não vazia |
| `confianca` | `Annotated[float, Field(ge=0, le=1)]` | FR-012 |

### ConformanceItem
Resultado da avaliação de conformidade de uma `RegraExtraida`.

| Campo | Tipo | Regras |
|---|---|---|
| `regra_id` | `str` (UUID) | referencia `RegraExtraida.regra_id` |
| `status` | `StatusConformidade` | enum |
| `delta` | `str \| None` | descrição da mudança em relação ao estado anterior; opcional |
| `recomendacao` | `str \| None` | opcional |
| `severidade` | `Annotated[float, Field(ge=0, le=1)]` | reaproveita a mesma faixa `[0,1]` que `score`/`confianca` |

### ConformanceReport
Agregado de uma execução do pipeline de conformidade.

| Campo | Tipo | Regras |
|---|---|---|
| `report_id` | `str` (UUID) | obrigatório |
| `gerado_em` | `datetime` | obrigatório |
| `itens` | `list[ConformanceItem]` | pode ser vazia (execução sem regras avaliadas) |
| `resumo` | `str` | não vazio pós-strip |
| `criticidade_maxima` | `StatusConformidade \| None` | derivável de `itens`, mas mantido como campo explícito para consumo direto por relatórios/API |

### SearchQuery
Contrato de entrada de busca semântica.

| Campo | Tipo | Regras |
|---|---|---|
| `query` | `str` | não vazia pós-strip |
| `top_k` | `int` | `>= 1` |
| `filtros` | `dict[str, str] \| None` | opcional |

### SearchResult
Contrato de saída de busca semântica.

| Campo | Tipo | Regras |
|---|---|---|
| `score` | `Annotated[float, Field(ge=0, le=1)]` | FR-012 |
| `trecho` | `str` | não vazio pós-strip |
| `normativo_id` | `str` (UUID) | referencia `NormativoItem.id` |

### ReportOutput
Metadados de saída de um relatório de conformidade gerado.

| Campo | Tipo | Regras |
|---|---|---|
| `json_path` | `str` | caminho do arquivo JSON gerado |
| `pdf_path` | `str` | caminho do arquivo PDF gerado |
| `total_normativos` | `int` | `>= 0` |
| `total_regras` | `int` | `>= 0` |
| `total_gaps` | `int` | `>= 0` |
| `gerado_em` | `datetime` | obrigatório |

### PipelineRequest
Entrada do agente orquestrador.

| Campo | Tipo | Regras |
|---|---|---|
| `pipeline_id` | `str` (UUID) | obrigatório |
| `fontes` | `list[HttpUrl]` | não vazia — URLs de origem a coletar |
| `forcar_reprocessamento` | `bool` | default `False` |

### PipelineResult
Saída do agente orquestrador.

| Campo | Tipo | Regras |
|---|---|---|
| `pipeline_id` | `str` (UUID) | referencia `PipelineRequest.pipeline_id` |
| `sucesso` | `bool` | obrigatório |
| `report` | `ReportOutput \| None` | presente quando `sucesso=True` |
| `erro` | `str \| None` | presente quando `sucesso=False` |
| `iniciado_em` | `datetime` | obrigatório |
| `concluido_em` | `datetime` | obrigatório |

### RawDocument
Documento ainda não processado, capturado da fonte original.

| Campo | Tipo | Regras |
|---|---|---|
| `source_uri` | `HttpUrl` | obrigatório |
| `content_type` | `str` | ex. `"text/html"`, `"application/pdf"` |
| `bytes_ref` | `str` | referência (chave/path) ao conteúdo bruto armazenado, não o conteúdo em si |
| `hash_conteudo` | `str` | SHA-256 hex, 64 chars (FR-010) |
| `coletado_em` | `datetime` | obrigatório |

## Relacionamentos

```
RawDocument --(processado em)--> NormativoItem --(extrai)--> RegraExtraida
RegraExtraida --(avaliada em)--> ConformanceItem --(agregado em)--> ConformanceReport
ConformanceReport --(insumo de)--> ReportOutput
SearchQuery --(produz)--> SearchResult --(referencia)--> NormativoItem
PipelineRequest --(processado em)--> PipelineResult --(contém)--> ReportOutput
```

## Validadores compartilhados (reuso)

Para evitar duplicação entre modelos (Princípio III/KISS), os seguintes validadores são
implementados uma vez como funções módulo-privadas e reaproveitados via
`field_validator`/`Annotated`:

- `_normalizar_texto(valor: str) -> str`: aplica `strip()` + colapso de espaços,
  rejeita string vazia resultante (FR-011). Usado por `titulo`, `texto`, `enunciado`,
  `resumo`, `trecho`, `query`.
- `_validar_hash_sha256(valor: str) -> str`: valida regex hex de 64 chars (FR-010).
  Usado por `NormativoItem.hash_conteudo` e `RawDocument.hash_conteudo`.
- Tipo anotado `Score = Annotated[float, Field(ge=0, le=1)]` (FR-012). Usado por
  `RegraExtraida.confianca`, `ConformanceItem.severidade`, `SearchResult.score`.
