# Contrato: `src/pix_compliance/agents/orchestrator_agent.py`

Esta feature não expõe uma API HTTP/CLI de terceiros — o "contrato" é a
interface Python que `make run` e o `APScheduler` consomem, ambos sobre o
mesmo handler.

## Função pública: `run_pipeline`

```python
async def run_pipeline(request: PipelineRequest) -> PipelineResult:
    """Executa o pipeline completo: scrape -> extract (sequencial) ->
    {compliance_analyzer, knowledge_builder} (paralelo, asyncio.gather) ->
    conformance_validator -> report_consolidator.

    Constrói PipelineContext uma vez (settings, stores, cliente HTTP,
    correlation_id via bind_run_correlation_id()) e o passa a cada etapa.
    Sobe o mock BCB e o servidor MCP em processo antes de scrape, derruba
    ambos ao final (sucesso ou falha) — research.md, Decisão 2.

    Se o lock em processo já estiver adquirido por outra execução em
    andamento, retorna imediatamente PipelineResult(sucesso=False,
    erro="pipeline já em execução") sem tentar rodar (research.md,
    Decisão 6) — este é o único caminho desta função que não adquire o
    lock antes de checar."""
```

**Pós-condição (execução normal)**: `PipelineResult.etapas` contém um
`EtapaMetric` por etapa efetivamente executada, na ordem em que rodaram;
`sucesso=True` apenas se nenhuma etapa `fatal` falhou.

**Pós-condição (falha fatal)**: A primeira etapa `fatal` que falhar aborta
as etapas seguintes; `PipelineResult.sucesso=False`,
`PipelineResult.erro` contém uma mensagem clara identificando a etapa e a
causa.

**Pós-condição (falha degradável/ignorável)**: A etapa falha é registrada
em `etapas` com `status` correspondente; as etapas seguintes rodam
normalmente; `PipelineResult.sucesso` permanece `True` se nenhuma etapa
`fatal` tiver falhado.

**Pós-condição (lock já adquirido)**: Retorna sem executar nenhuma etapa;
`PipelineResult.etapas == []`.

## Função pública: `start_scheduler`

```python
def start_scheduler(settings: Settings) -> AsyncIOScheduler:
    """Registra run_pipeline como job do AsyncIOScheduler, cron lido de
    settings.orchestrator_schedule_cron — mesmo handler do CLI (FR-008),
    nunca uma segunda implementação do fluxo de disparo. Retorna o
    scheduler já iniciado (chamador decide quando pará-lo)."""
```

## CLI (`make run`)

```bash
python -m pix_compliance.agents.orchestrator_agent
```

Lê `Settings`, monta um `PipelineRequest` (fontes do corpus mock/BCB
configurado), chama `run_pipeline` de forma síncrona (`asyncio.run`), e
imprime o `PipelineResult` resultante — o mesmo `run_pipeline` usado pelo
scheduler.

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. `run_pipeline` sobre o corpus mock completa com `sucesso=True` e um
   `PipelineResult` com `etapas` preenchido (SC-001).
2. Falha injetada numa etapa `degradable` não impede `sucesso=True`; falha
   injetada numa etapa `fatal` produz `sucesso=False` com `erro` claro
   (SC-002).
3. Todos os eventos de log de uma execução carregam o mesmo
   `correlation_id` (SC-003).
4. `PipelineResult.etapas` expõe `duracao_segundos` por etapa (SC-004).
5. Duas chamadas concorrentes de `run_pipeline` — a segunda retorna
   imediatamente com `sucesso=False` e `erro` indicando lock já adquirido,
   sem rodar nenhuma etapa (SC-006).
6. `start_scheduler` com um intervalo curto (segundos, via variável de
   ambiente) dispara `run_pipeline` mais de uma vez automaticamente,
   comprovando o mecanismo (SC-005, verificação do intervalo literal de 1
   minuto documentada em quickstart.md como validação manual).
