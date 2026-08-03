# Data Model: Orchestrator Agent (Harness) e agendamento (SPEC-015)

## Extensão aditiva: `PipelineResult` (SPEC-002)

`PipelineResult` já existe (`src/pix_compliance/models.py`) — ganha um
único campo novo, `etapas`, sem alteração de nenhum campo existente
(Princípio VI):

| Campo | Tipo | Status |
|---|---|---|
| `pipeline_id` | `str` | já existe |
| `sucesso` | `bool` | já existe |
| `report` | `ReportOutput \| None` | já existe |
| `erro` | `str \| None` | já existe |
| `iniciado_em` | `datetime` | já existe |
| `concluido_em` | `datetime` | já existe |
| `etapas` | `list[EtapaMetric]` | **NOVO** — `Field(default_factory=list)`, aditivo |

**Regra de negócio**: `concluido_em - iniciado_em` já é a duração total
(SC-004, "duração total") — não duplicada em `etapas`. `etapas` cobre a
duração *por etapa* e, contando itens por `status`, a *contagem por etapa*
pedida pela spec — um único campo cobre as duas exigências (research.md,
Decisão 5).

## Novo: `EtapaMetric` (Pydantic, SPEC-002 — módulo `models.py`)

```python
class EtapaMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str
    duracao_segundos: float = Field(ge=0)
    status: Literal["sucesso", "degradada", "ignorada", "falhou"]
```

| Campo | Descrição |
|---|---|
| `nome` | Identificador da etapa (ex. `"scrape"`, `"extract"`, `"compliance_analyzer"`, `"knowledge_builder"`, `"conformance_validator"`, `"report_consolidator"`) |
| `duracao_segundos` | Duração medida da etapa, sempre registrada mesmo quando a etapa falha |
| `status` | `sucesso` (concluiu sem erro), `degradada` (falhou mas política permitiu seguir), `ignorada` (falhou, política `ignorable`, sem impacto no resultado), `falhou` (etapa fatal que abortou o pipeline) |

## Novo (infraestrutura de orquestração, não modelo Pydantic público): `PipelineContext`

```python
@dataclass
class PipelineContext:
    settings: Settings
    object_store: ObjectStore
    vector_store: PgVectorStore
    http_client: httpx.Client
    correlation_id: str
```

**Papel**: Dependências compartilhadas por todas as etapas de uma execução
— construído uma vez no início de `run_pipeline()`, nunca reconstruído
etapa a etapa (mesma instância de `object_store`/`vector_store`/
`http_client` em toda a execução). `correlation_id` é o mesmo retornado por
`bind_run_correlation_id()` (SPEC-001) no início da execução — todo log
emitido por qualquer etapa, através de qualquer agente, carrega esse mesmo
valor (SC-003).

## Novo (infraestrutura de orquestração, não modelo Pydantic público): `StepPolicy`

```python
class StepPolicy(StrEnum):
    FATAL = "fatal"
    DEGRADABLE = "degradable"
    IGNORABLE = "ignorable"
```

**Mapeamento por etapa** (decisão de implementação, detalhada em
`contracts/orchestrator.md`):

| Etapa | Política | Justificativa |
|---|---|---|
| `scrape` | `fatal` | Sem documento coletado, nada mais no pipeline tem o que processar |
| `extract` | `fatal` | Sem `NormativoItem` estruturado, as etapas seguintes não têm entrada válida |
| `compliance_analyzer` | `fatal` | `RegraExtraida` é entrada obrigatória do Conformance Validator e do relatório final |
| `knowledge_builder` | `degradable` | Indexação para busca é um recurso adicional — sua falha não invalida o gap analysis nem o relatório |
| `conformance_validator` | `fatal` | Sem gap analysis, não há `ConformanceReport` para o Report Consolidator consumir |
| `report_consolidator` (geração local) | `fatal` | Sem os artefatos gerados, não há nada a reportar |
| `report_consolidator` (publicação HTTP) | `degradable` | Comportamento já estabelecido na SPEC-014 — falha de publicação não invalida o trabalho já persistido |

## Diagrama de fluxo

```
scrape (fatal)
  └─▶ extract (fatal)
        └─▶ [ compliance_analyzer (fatal) ‖ knowledge_builder (degradable) ]  (asyncio.gather)
              └─▶ conformance_validator (fatal)
                    └─▶ report_consolidator (fatal na geração; degradable na publicação HTTP)
```
