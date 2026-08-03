# Quickstart: Orchestrator Agent (Harness) e agendamento (SPEC-015)

## Pré-requisitos

- Dependências instaladas, incluindo `apscheduler` (research.md, Decisão 7):
  `pip install -e ".[dev]"`.
- `docker compose up postgres minio -d` (SPEC-006) — `ObjectStore`/
  `PgVectorStore` reais.
- `fixtures/normativos.json`/`mock_bcb/` já existem (SPEC-003) — o mock BCB
  HTTP e o servidor MCP são subidos automaticamente pelo próprio
  `run_pipeline` (research.md, Decisão 2), não precisam ser iniciados à mão.

## Cenário 1 — Execução completa via `make run` (SC-001)

```bash
make run
```

**Resultado esperado**: o pipeline completo roda de ponta a ponta e um
`PipelineResult` válido é impresso ao final, com `sucesso=True` e `etapas`
preenchido — documentado em `contracts/orchestrator.md`, cenário 1.

## Cenário 2 — Falha degradável não aborta; falha fatal aborta (SC-002)

```bash
pytest tests/test_orchestrator_agent.py -k "degradavel or fatal" -q
```

**Resultado esperado**: o teste com falha injetada numa etapa `degradable`
(ex. `knowledge_builder`) conclui com `sucesso=True`; o teste com falha
injetada numa etapa `fatal` (ex. `extract`) conclui com `sucesso=False` e
uma mensagem de erro identificando a etapa — cenário 2 do contrato.

## Cenário 3 — `correlation_id` único correlaciona toda a execução (SC-003)

```bash
pytest tests/test_orchestrator_agent.py -k correlation_id -q
```

**Resultado esperado**: todos os eventos de log capturados durante uma
execução completa carregam o mesmo `correlation_id` — cenário 3 do
contrato.

## Cenário 4 — Duração por etapa no `PipelineResult` (SC-004)

```bash
pytest tests/test_orchestrator_agent.py -k duracao_por_etapa -q
```

**Resultado esperado**: `PipelineResult.etapas` tem um `EtapaMetric` por
etapa executada, cada um com `duracao_segundos >= 0` — cenário 4 do
contrato.

## Cenário 5 — Lock rejeita execuções sobrepostas (SC-006)

```bash
pytest tests/test_orchestrator_agent.py -k lock -q
```

**Resultado esperado**: duas chamadas concorrentes de `run_pipeline`
resultam em exatamente uma execução completa e uma rejeição imediata
(`sucesso=False`, `erro` mencionando lock) — cenário 5 do contrato.

## Cenário 6 — Scheduler dispara automaticamente (mecanismo, SC-005 parcial)

```bash
pytest tests/test_orchestrator_agent.py -k scheduler -q
```

**Resultado esperado**: com um intervalo curto (segundos) configurado via
variável de ambiente, `start_scheduler` dispara `run_pipeline` mais de uma
vez automaticamente dentro da janela do teste — cenário 6 do contrato.

## Cenário 7 — Validação manual do intervalo literal de 1 minuto (SC-005 completo)

```bash
ORCHESTRATOR_SCHEDULE_CRON="*/1 * * * *" python -c "
from pix_compliance.agents.orchestrator_agent import start_scheduler
from pix_compliance.config import settings
start_scheduler(settings)
import time; time.sleep(150)
"
```

**Resultado esperado**: inspecionando os logs, duas execuções completas
automáticas aparecem dentro dos ~150 segundos de espera — validação manual
do cenário exato descrito em SC-005 (research.md: intervalos curtos em
segundos são usados nos testes automatizados; o intervalo literal de 1
minuto é verificado manualmente aqui, mesmo padrão já usado para o Swagger
da SPEC-013).

## Cenário 8 — Snippet de EventBridge consistente com o handler local

```bash
cat docs/aws/eventbridge-schedule.tf
```

**Resultado esperado**: a regra de schedule e o target referenciam,
em comentário, o mesmo entrypoint (`orchestrator_agent.run_pipeline`) usado
pelo `APScheduler`/CLI — cenário 7 do contrato.

## Cenário 9 — Log de evidência de uma execução real

```bash
cat docs/evidence/pipeline-run.log
```

**Resultado esperado**: log completo (JSON por linha, `structlog`) de uma
execução real do pipeline, do início (`scrape`) ao fim
(`report_consolidator`), gerado durante a implementação desta feature
(FR-011) — não uma tarefa avulsa posterior.

## Checklist de leitura antes de implementar

- [research.md](./research.md) — por que o Orchestrator não é um
  `pydantic_ai.Agent`, por que FR-007 aponta para o MCP do Scraper (não
  uma nova delegação), por que `make run` sobe mock BCB/MCP em processo,
  por que `PipelineContext` não é literalmente o `RunContext` do Pydantic
  AI, o design do lock e do scheduler, e por que o IaC é Terraform.
- [data-model.md](./data-model.md) — extensão aditiva de `PipelineResult`,
  `EtapaMetric`, `PipelineContext`, `StepPolicy` e o mapeamento de política
  por etapa.
- [contracts/orchestrator.md](./contracts/orchestrator.md) —
  `run_pipeline`/`start_scheduler`, CLI, e cenários de contrato cobertos
  por teste.

**Lembrete do Princípio IX**: `tests/test_orchestrator_agent.py` deve ser
escrito e confirmado como falho (por ausência de implementação) antes de
`orchestrator_agent.py` existir — incluindo os testes de falha
degradável/fatal e de disputa de lock. Ver ordenação de tarefas em
`tasks.md` (gerado por `/speckit-tasks`).

## Pendência registrada (fora de escopo desta spec)

Reconciliar `POST /runs` (SPEC-013, `src/pix_compliance/api/routes.py::
_run_pipeline_sync`) para delegar a `run_pipeline` desta feature, em vez de
manter uma segunda implementação inline do mesmo fluxo, fica para uma
spec/tarefa futura (ver spec.md, Assumptions).
