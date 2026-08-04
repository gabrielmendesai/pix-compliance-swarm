# Data Model: Testes e observabilidade (SPEC-017)

Esta feature não introduz uma entidade de domínio nova — é uma extensão
aditiva de um modelo já existente, mais dois formatos de saída
(log estruturado, relatório de cobertura) que não são persistidos.

## `EtapaMetric` (extensão aditiva)

`src/pix_compliance/models.py` — já existe desde a SPEC-015. Ganha um
campo opcional para os contadores agregados pedidos por FR-007, sem
quebrar nenhum consumidor existente (campo com default `None`).

| Campo               | Tipo                          | Obrigatório | Observação                                                                 |
|---------------------|--------------------------------|-------------|------------------------------------------------------------------------------|
| `nome`              | `str`                          | sim (já existe) | Nome da etapa (`scrape`, `extract`, ...).                                |
| `duracao_segundos`  | `float` (`ge=0`)               | sim (já existe) | Latência da etapa — já satisfaz parte de FR-007.                         |
| `status`            | `Literal["sucesso","degradada","ignorada","falhou"]` | sim (já existe) | Resultado da política de falha da etapa.                    |
| `contadores`        | `dict[str, int] \| None`       | **novo**, default `None` | Chaves específicas por etapa (ver tabela abaixo); `None` quando a etapa não produz contador aplicável. |

**Chaves de `contadores` por etapa** (preenchidas apenas onde fazem
sentido — nenhuma etapa preenche todas):

| Etapa                   | Chaves possíveis                                      |
|--------------------------|--------------------------------------------------------|
| `scrape`                 | `documentos_coletados`                                 |
| `extract`                | `regras_extraidas` *(nota: `extract` produz `NormativoItem`, não `RegraExtraida` — ver Assumptions)* |
| `compliance_analyzer`     | `regras_extraidas`, `tokens_consumidos`                |
| `conformance_validator`   | `gaps_encontrados`                                      |
| `knowledge_builder`       | `tokens_consumidos` (embeddings)                        |
| `report_consolidator`     | — (tipicamente `None`)                                  |

**Validação**: nenhuma regra nova de validação Pydantic além do tipo —
`contadores` é informativo/observacional, não usado por lógica de decisão
do pipeline (não é lido por nenhuma etapa subsequente).

## Log estruturado de contador agregado (não persistido)

Emitido por `logger.info` dentro de `_run_step`
(`src/pix_compliance/agents/orchestrator_agent.py`) ao final de cada
etapa, carregando o mesmo `correlation_id` já vinculado por
`bind_run_correlation_id()` (via `structlog.contextvars`, Decisão 2 do
research.md) — não é uma nova entidade de dados, é a serialização em log
do mesmo `EtapaMetric.contadores` acima, com uma chave de evento fixa
(`pipeline_etapa_concluida`) para facilitar filtro/agregação por quem lê
os logs.

## Relatório de cobertura (não persistido)

Saída de `pytest-cov` (`--cov-report=term-missing`, Decisão 6 do
research.md) — não é uma entidade de domínio, é a saída padrão da
ferramenta, lida com foco declarado em `src/pix_compliance/models.py` e
`src/pix_compliance/guardrails.py` (FR-009). Nenhum esquema novo de dados
é definido para este relatório — o formato é o já emitido nativamente pelo
`pytest-cov`.
