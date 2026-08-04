# Orchestrator Skill

Documenta o Orchestrator Agent (Harness) e agendamento (SPEC-015), implementado em
`src/pix_compliance/agents/orchestrator_agent.py`. Segue o mesmo formato de quatro seções já
estabelecido pelos `SKILL.md` anteriores — embora, como o Knowledge Builder (SPEC-012) e o
Report Consolidator (SPEC-014), este módulo não instancie `pydantic_ai.Agent`: não há
julgamento de LLM na decisão de "qual etapa roda quando" (fluxo de controle determinístico).
É o sétimo agente do enxame — o "harness" que coordena os seis demais, não um consumidor de
LLM próprio.

## Responsabilidade

O Orchestrator Agent coordena os seis agentes já implementados de ponta a ponta:

```
scrape -> extract -> [ compliance_analyzer || knowledge_builder ] -> conformance_validator -> report_consolidator
```

Este agente:

- Decide **quando** cada etapa roda e com qual política de falha (`fatal`, `degradável`,
  `ignorável`) — nunca decide **o quê** cada etapa faz (isso é responsabilidade exclusiva do
  agente correspondente).
- Aplica os três padrões de orquestração avaliados pelo desafio original, cada um por um
  motivo real: `scrape → extract` é **sequencial** (o Extractor depende do documento já
  coletado); `compliance_analyzer`/`knowledge_builder` rodam em **paralelo**
  (`asyncio.gather`, sem depender um do resultado do outro); o **loop com condição** já
  existente no Extractor (reparo de validação, SPEC-009) é reaproveitado dentro do fluxo
  maior, não reimplementado por este agente.
- Garante que nunca duas execuções rodem sobrepostas no mesmo processo (`asyncio.Lock`).
- Registra `EtapaMetric` (duração, status, contadores agregados — SPEC-017) por etapa
  executada, e vincula um `correlation_id` único a todos os logs de uma mesma execução.
- Sobe, opcionalmente, cópias efêmeras do mock BCB e do servidor MCP do Scraper em processo
  (`bootstrap_local_servers`), em portas escolhidas dinamicamente pelo sistema operacional
  (SPEC-017) — usado por `make run`/testes; em Docker, esses dois já são containers próprios.

Este agente **não** contém nenhuma lógica de domínio (parsing, categorização, comparação de
versões, geração de relatório) — cada uma dessas responsabilidades já vive em um dos seis
agentes delegados (Princípio IV, um agente/uma responsabilidade).

## Ferramentas

Diferente dos demais agentes (que chamam ferramentas MCP ou funções determinísticas), este
"harness" delega a etapa inteira a outro agente do enxame — a tabela abaixo lista essa
delegação, não ferramentas no sentido de `@agent.tool`:

| Etapa delegada | Agente | Padrão de orquestração |
|---|---|---|
| `scrape` | Scraper Agent (`run_scraper_agent`, SPEC-008) | Sequencial (bloqueia `extract`) |
| `extract` | Extractor Agent (`run_extractor_agent`, SPEC-009) | Sequencial; contém o loop de reparo de validação internamente |
| `compliance_analyzer` | Compliance Analyzer Agent (`analyze_batch`, SPEC-010) | Paralelo com `knowledge_builder` |
| `knowledge_builder` | Knowledge Builder Agent (`index_normativos`, SPEC-012) | Paralelo com `compliance_analyzer` |
| `conformance_validator` | Conformance Validator Agent (`build_conformance_report`, SPEC-011) | Sequencial, depende de `compliance_analyzer` |
| `report_consolidator` | Report Consolidator Agent (`consolidate_and_publish`, SPEC-014) | Sequencial, última etapa |

A delegação "agente-para-agente via chamada de ferramenta" pedida pelo desafio original já
existe de verdade um nível abaixo: o Scraper Agent delega, via uma chamada MCP real, ao
servidor MCP separado (SPEC-007/008) — este módulo não introduz um segundo mecanismo de
tool-calling.

## Input

```python
# Execução ad-hoc — mesmo handler chamado pelo CLI e pelo scheduler
await run_pipeline(
    PipelineRequest(pipeline_id="...", fontes=["https://..."]),
    bootstrap_local_servers=None,  # usa settings.orchestrator_bootstrap_local_servers
)
```

```bash
# CLI — execução única
python -m pix_compliance.agents.orchestrator_agent

# Modo daemon — inicia o agendamento (APScheduler) e mantém o processo vivo
python -m pix_compliance.agents.orchestrator_agent --daemon
```

Nenhuma dependência via `RunContext`/`deps_type` (não há `Agent` Pydantic AI envolvido) — os
parâmetros opcionais `model_scraper`/`model_extractor`/`model_analyzer`/`model_conformance`
existem para os testes injetarem modelos determinísticos (`FunctionModel`) em cada etapa
delegada, sem depender de `settings.llm_provider`.

Configuração relevante (`Settings`):

| Campo | Descrição |
|---|---|
| `orchestrator_bootstrap_local_servers` | Se `True` (default local), sobe mock BCB/MCP em processo antes de `scrape` |
| `orchestrator_schedule_cron` | Cron (5 campos) do disparo periódico via `start_scheduler` |

## Output

`PipelineResult` (modelo Pydantic já existente, `src/pix_compliance/models.py`, SPEC-002/015,
`ConfigDict(extra="forbid")`), reaproveitado sem alteração de contrato:

| Campo | Tipo | Descrição |
|---|---|---|
| `sucesso` | `bool` | `True` somente se nenhuma etapa `fatal` falhou |
| `report` | `ReportOutput \| None` | Saída do Report Consolidator, quando o pipeline chega até o fim |
| `erro` | `str \| None` | Mensagem acionável identificando a etapa que abortou o pipeline, se houver |
| `etapas` | `list[EtapaMetric]` | Uma entrada por etapa executada — nome, duração, status, contadores agregados (SPEC-017) |

`start_scheduler(settings) -> AsyncIOScheduler` — registra `run_pipeline` como job agendado
(mesmo handler do CLI/API, nunca um segundo caminho de disparo, FR-008 da SPEC-015); devolve o
scheduler já iniciado, o chamador decide quando pará-lo.
