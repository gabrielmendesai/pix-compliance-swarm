# Research: Orchestrator Agent (Harness) e agendamento (SPEC-015)

## 0. Orchestrator é um harness de orquestração puro, não um `pydantic_ai.Agent`

**Decision**: `orchestrator_agent.py` não instancia `pydantic_ai.Agent` —
`run_pipeline()` é uma função `async def` comum que chama, em sequência ou
em paralelo, as funções já expostas por cada um dos seis agentes.

**Rationale**: Não há nenhum julgamento de LLM na decisão de "qual etapa
roda quando" — isso é fluxo de controle determinístico (sequencial,
`asyncio.gather`, política de falha por `if`/`try`), exatamente o mesmo
raciocínio já aplicado ao Knowledge Builder (SPEC-012) e ao Report
Consolidator (SPEC-014): usar `Agent` onde há decisão real via LLM, e uma
função determinística onde não há.

**Alternatives considered**: Envolver a orquestração inteira num
`pydantic_ai.Agent` com cada etapa registrada como `@agent.tool` foi
considerado e descartado — introduziria uma camada de decisão via LLM
("qual tool chamar a seguir") onde a ordem já é conhecida e fixa pela
própria spec (sequencial → paralelo → sequencial), custo e latência sem
benefício real, e uma abstração nova sem justificativa concreta (Princípio
II).

## 1. "Delegação agente-para-agente via chamada de ferramenta" (FR-007) já existe — não precisa de uma nova

**Decision**: FR-007 é satisfeito apontando para o mecanismo de
tool-calling MCP já existente no Scraper Agent (SPEC-007/008) — o
`Agent` do Scraper já delega, via chamada de ferramenta real (protocolo
MCP), ao servidor MCP separado (`mcp_servers/scraper_sse`). O Orchestrator
não precisa introduzir um segundo mecanismo de delegação.

**Rationale**: Esse já é, literalmente, "orquestração... via chamada de
ferramenta (não apenas orquestração sequencial simples de fora)" — um
`Agent` (o Scraper) invocando uma ferramenta que delega a um processo/
componente separado (o servidor MCP), não uma chamada de função Python
direta de fora. Introduzir um segundo mecanismo de "tool call" só para
esta spec duplicaria uma capacidade já demonstrada, sem necessidade real
(Princípio II).

**Alternatives considered**: Registrar um dos seis agentes como
`@agent.tool` de um `Agent` orquestrador top-level foi descartado junto com
a Decisão 0 — mesma razão.

## 2. `make run` autossuficiente: Orchestrator sobe o mock BCB e o servidor MCP em processo

**Decision**: Antes da etapa de scraping, `run_pipeline()` sobe, em
processo (threads/tasks efêmeras, não containers novos): (a) um servidor
HTTP simples servindo `mock_bcb/` (mesmo padrão de
`tests/conftest.py::mock_bcb_server`), e (b) o servidor MCP SSE do Scraper
(`mcp_servers/scraper_sse`, mesmo padrão de
`tests/test_scraper_agent.py::running_mcp_server`) — ambos derrubados ao
final da execução (sucesso ou falha).

**Rationale**: `run_scraper_agent` (SPEC-008) exige uma URL de servidor MCP
já rodando, que por sua vez busca de `BCB_BASE_URL` — nenhum dos dois hoje
sobe automaticamente fora dos testes (nem em `docker-compose.yml`, nem em
nenhum script). Para `make run` ser de fato "uma execução, ponta a ponta"
(SC-001) sem exigir que o operador suba manualmente dois processos
adicionais antes, o Orchestrator sobe as mesmas duas dependências efêmeras
já usadas nos testes — reaproveitando um padrão já validado, em vez de
inventar um terceiro serviço em `docker-compose.yml` para algo que só serve
como mock de demonstração (Princípio II).

**Alternatives considered**: Adicionar o servidor MCP e o mock BCB como
serviços permanentes em `docker-compose.yml` foi considerado e descartado
— manteria dois processos rodando indefinidamente para um mock que só
precisa existir durante a janela de uma execução do pipeline, custo de
recursos sem benefício (o padrão efêmero já resolve o problema real).
Exigir que o operador suba os dois manualmente antes de `make run` foi
descartado por quebrar a expectativa de "um comando só" do SC-001.

## 3. Contexto compartilhado: `PipelineContext`, não literalmente `RunContext` do Pydantic AI

**Decision**: `PipelineContext` é uma `@dataclass` concreta (settings,
`object_store`, `vector_store`, `httpx.Client`, `correlation_id`),
construída uma vez por execução e passada explicitamente para cada função
de etapa — não o tipo `pydantic_ai.RunContext`, que só existe dentro da
máquina de tool-calling de um `Agent` específico.

**Rationale**: A spec usa o termo "RunContext" de forma informal para
descrever "um contexto de dependências compartilhado entre as etapas" —
como o Orchestrator não é ele mesmo um `Agent` (Decisão 0), não há um
`RunContext` do Pydantic AI abrangendo a execução inteira (cada agente
individual continua tendo seu próprio `deps_type`/`RunContext` interno,
inalterado). `PipelineContext` cumpre a mesma função pretendida pela spec
(dependências comuns + `correlation_id` únicos por execução), com o nome
técnico correto para o que de fato é.

**Alternatives considered**: N/A — esclarecimento de nomenclatura, não uma
escolha de design alternativa.

## 4. Política de falha por etapa: enum + wrapper único

**Decision**: `StepPolicy` (`StrEnum`: `FATAL`, `DEGRADABLE`, `IGNORABLE`)
associado a cada etapa nomeada; uma função `_run_step(nome, policy, corotina)`
envolve cada chamada, mede duração, captura exceção conforme a política
(relança para `FATAL`, loga e segue para `DEGRADABLE`/`IGNORABLE`), e
registra um `EtapaMetric` por etapa executada.

**Rationale**: Um único ponto de decisão (`_run_step`) para as três
políticas evita repetir a mesma lógica de `try`/`except`/log em seis
lugares diferentes (Princípio III, KISS) — e centraliza onde a métrica de
duração por etapa é sempre coletada, mesmo quando a etapa falha.

**Alternatives considered**: Deixar cada chamada de etapa implementar seu
próprio tratamento de falha inline foi descartado — duplicaria a mesma
lógica de captura/log/métrica seis vezes, com risco real de divergência
sutil entre as implementações (ex. uma etapa esquecer de logar a duração).

## 5. `PipelineResult`: extensão aditiva com `EtapaMetric`

**Decision**: Novo modelo `EtapaMetric` (`nome: str`, `duracao_segundos:
float`, `status: Literal["sucesso", "degradada", "ignorada", "falhou"]`);
`PipelineResult` (SPEC-002) ganha `etapas: list[EtapaMetric] =
Field(default_factory=list)` — único campo novo.

**Rationale**: SC-004 exige duração por etapa na saída do `PipelineResult`;
a spec também pede "contagens por etapa". Uma lista de `EtapaMetric` cobre
os dois com um único campo — a duração está em cada item, e a "contagem"
é obtida trivialmente contando itens por `status` (não precisa de um
segundo campo `dict[str, int]` paralelo, que duplicaria informação já
presente na lista). `default_factory=list` mantém a extensão puramente
aditiva — nenhum consumidor existente de `PipelineResult` quebra.

**Alternatives considered**: Dois campos separados
(`duracao_por_etapa: dict[str, float]` e `contagem_por_status: dict[str,
int]`) foram considerados e descartados — a lista de `EtapaMetric` já
contém ambas as informações sem duplicação, e evita duas fontes de verdade
que precisariam ser mantidas sincronizadas manualmente.

## 6. Lock em processo, rejeição imediata (não fila)

**Decision**: Um único `asyncio.Lock` em nível de módulo, adquirido via
`lock.acquire()` não bloqueante (checagem de `lock.locked()` antes de
tentar rodar); se já travado, `run_pipeline()` retorna imediatamente
`PipelineResult(sucesso=False, erro="pipeline já em execução")`, sem
esperar a execução em andamento nem enfileirar.

**Rationale**: FR-010/SC-006 pedem que a segunda execução seja "rejeitada",
não atrasada — enfileirar introduziria complexidade (fila, ordem, timeout
de espera) sem necessidade real para o escopo desta spec (execução
distribuída e filas de mensageria estão explicitamente fora de escopo,
FR-012). Um lock em processo é suficiente porque o scheduler e o CLI
compartilham o mesmo processo Python de longa duração (Technical Context)
— não há necessidade de um lock distribuído (arquivo, Redis) para um
cenário de execução distribuída que este projeto não tem.

**Alternatives considered**: `filelock` (lock baseado em arquivo,
sobrevive a reinícios de processo) foi considerado e descartado —
resolveria um problema (coordenação entre processos distintos) que não
existe neste projeto, onde CLI e scheduler já rodam no mesmo processo
(YAGNI, Princípio II).

## 7. Scheduler: `APScheduler`, cron/intervalo configurável, mesmo handler do CLI

**Decision**: `AsyncIOScheduler` (APScheduler) registra `run_pipeline` via
`add_job`, com o intervalo/cron lido de uma variável de ambiente nova em
`Settings` (`ORCHESTRATOR_SCHEDULE_CRON`, formato cron padrão de 5 campos;
um valor com granularidade de minutos, ex. `*/1 * * * *`, cobre o cenário
de teste manual do SC-005). O CLI (`make run`) e o `job` do scheduler
chamam exatamente a mesma função `run_pipeline(context)` — nunca dois
caminhos de código divergentes.

**Rationale**: FR-008 exige explicitamente "chamando exatamente o mesmo
handler usado pelo disparo ad-hoc via CLI" — usar cron (não um intervalo
simples em segundos) como formato de configuração é o padrão mais
reconhecível para quem for revisar a variável de ambiente, e mapeia
diretamente para a regra de `schedule` do EventBridge documentada em
paralelo (Decisão 8), mantendo os dois caminhos (local/produção)
conceitualmente equivalentes.

**Alternatives considered**: Um scheduler próprio (thread com `time.sleep`
em loop) foi descartado — `APScheduler` já está na stack técnica
obrigatória da constituição, reimplementar um scheduler ad-hoc seria
exatamente o tipo de abstração não justificada que o Princípio II proíbe
quando uma biblioteca já resolvida está disponível e mandada pela própria
constituição.

## 8. IaC do EventBridge: Terraform, não CDK

**Decision**: `docs/aws/eventbridge-schedule.tf` — um recurso
`aws_scheduler_schedule` (ou `aws_cloudwatch_event_rule` +
`aws_cloudwatch_event_target`, a decidir no detalhe da implementação),
com a expressão de schedule e o target comentados, apontando
conceitualmente para o mesmo entrypoint do handler local.

**Rationale**: Terraform (HCL) é autocontido e revisável sem exigir um
toolchain adicional (Node/CDK) só para um snippet de documentação que
nunca será de fato aplicado (FR-012, "documentando o caminho de produção
sem implementá-lo de fato") — um `.tf` é legível e comentável diretamente
no repositório, sem depender de `npm install`/síntese de CDK para ser
revisado.

**Alternatives considered**: AWS CDK (Python, para manter a linguagem do
projeto) foi considerado — descartado porque CDK gera CloudFormation via
síntese (exige rodar `cdk synth` para produzir o artefato real), tornando o
snippet menos autocontido como peça de documentação pura do que um `.tf`
direto.

## 9. Log de evidência: captura de uma execução real via `structlog`, redirecionada a arquivo

**Decision**: `docs/evidence/pipeline-run.log` é gerado rodando uma
execução real do pipeline completo (mesma forma que `make run`), com a
saída do `structlog` (já JSON por linha, SPEC-001) redirecionada a esse
arquivo — parte do processo de implementação desta feature (FR-011), não
uma tarefa avulsa depois.

**Rationale**: FR-011 e a nota de implementação da spec são explícitos:
este log é, literalmente, um entregável formal do desafio original. Gerar
o arquivo durante a implementação (não prometer gerar depois) é a única
forma de garantir que ele reflita o comportamento real do Orchestrator
implementado, não uma reconstrução posterior editada à mão.

**Alternatives considered**: N/A — requisito explícito, sem alternativa de
design real.

## Resumo de dependências novas

`apscheduler>=3.10` — já prevista pela stack técnica obrigatória da
constituição, apenas nunca antes declarada em `pyproject.toml` (mesma
situação do FastAPI/uvicorn na SPEC-013). Nenhuma outra dependência nova
(o servidor mock BCB reaproveita `http.server` da stdlib, já usado em
`tests/conftest.py`).

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
