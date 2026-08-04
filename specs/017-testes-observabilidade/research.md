# Research: Testes e observabilidade (SPEC-017)

Esta feature é consolidação, não construção — a "pesquisa" aqui é a
auditoria honesta do estado real do repositório, exigida pelas Notas de
implementação da spec, feita antes de decidir o que falta escrever.
Achados obtidos rodando a suíte, lendo `conftest.py`/módulos de teste, e
inspecionando `logging.py`, `orchestrator_agent.py` e `api/routes.py`.

## Decisão 0 — Estado atual da suíte (linha de base)

**Decisão**: A suíte já roda 100% offline hoje. `make test`/`pytest -q`
(194 testes, confirmado em execução real nesta sessão) passa sem nenhuma
credencial AWS configurada, porque todo teste usa `LLM_PROVIDER=offline`
(`OfflineProvider`, `tests/doubles/`, SPEC-005) — nenhuma chamada de rede a
Bedrock ocorre durante a suíte.

**Racional**: FR-001/SC-001 já estão satisfeitos pela infraestrutura
existente. O trabalho real desta feature não é "tornar a suíte offline" —
já é — mas confirmar isso via evidência (não assumir) e cobrir a lacuna que
falta: um teste ponta a ponta que amarre as etapas, e não apenas cada
agente isoladamente.

**Alternativas consideradas**: N/A — constatação, não escolha de design.

## Decisão 1 — Teste ponta a ponta já existe parcialmente, mas não cobre a API

**Decisão**: `tests/test_orchestrator_agent.py::TestPipelineCompleto` já
tem um teste (`test_run_pipeline_completa_com_sucesso_e_etapas_na_ordem_esperada`)
que chama `run_pipeline` diretamente e verifica as seis etapas na ordem
esperada, com `bootstrap_local_servers=False` e modelos `FunctionModel`
determinísticos (equivalente ao propósito de `LLM_PROVIDER=offline`, mas
por injeção direta de modelo em vez da variável de ambiente). Isso já
cobre FR-002 na dimensão "Orchestrator + todos os seis agentes
coordenados", mas **não cobre a API** — `POST /runs` nunca é exercitado
por esse teste.

**Racional**: Investigação de `src/pix_compliance/api/routes.py::_run_pipeline_sync`
revelou que `POST /runs` **não delega a `run_pipeline`** (SPEC-015) — é uma
segunda implementação inline, já documentada como dívida pendente no
README ("Nota de integração pendente") desde a SPEC-015. Essa implementação
inline **pula Scraper e Extractor completamente** (lê `fixtures/normativos.json`
direto) e roda só 4 das 6 etapas (`compliance_analyzer` →
`conformance_validator`/`knowledge_builder` → `report_consolidator`).

Isso significa que testar `POST /runs` como está, junto com `run_pipeline`,
não produziria um teste ponta a ponta real de "Orchestrator, todos os sete
agentes, API" (FR-002/SC-002) — produziria dois testes de dois pipelines
diferentes e parcialmente sobrepostos, o que a Nota de implementação da
spec explicitamente pede para evitar ("não invente cobertura decorativa").

**Decisão de correção**: `POST /runs` passa a delegar a `run_pipeline`
(SPEC-015), removendo `_run_pipeline_sync` como implementação duplicada —
não é uma abstração nova (Princípio II), é a eliminação de uma já
existente e divergente, alinhado ao próprio Princípio III (duas
implementações do mesmo fluxo não deveriam coexistir). Esse ajuste de
código de produção é exatamente o tipo de mudança que a "Ordem de execução
exigida" da spec já antecipa como legítima quando necessária para
viabilizar o teste que falta — feita depois de o teste ponta a ponta via
API ser escrito e confirmado como falho contra o comportamento antigo
(Princípio IX).

**Alternativas consideradas**:
- Manter `_run_pipeline_sync` como está e testar `POST /runs` isoladamente
  (sem cobrir scrape/extract nesse caminho): rejeitada — deixaria FR-002
  formalmente "satisfeito" por dois testes que não provam a integração
  real ponta a ponta pedida, contradizendo a Nota de implementação.
- Reescrever `run_pipeline` para não precisar de MCP/scraper ao vivo (para
  caber no processo da API sem infraestrutura externa): rejeitada — já
  existe `bootstrap_local_servers` para isso (`run_pipeline` já sobe suas
  próprias cópias efêmeras de mock BCB/MCP scraper quando necessário,
  SPEC-015); reaproveitar esse mecanismo dentro de `post_runs` resolve o
  problema sem inventar um caminho novo.

## Decisão 2 — `correlation_id` é propagado via `contextvars`, não via `RunContext`

**Decisão**: A spec de origem (FR-006) fala em "propagado por `RunContext`",
mas a implementação real (`src/pix_compliance/logging.py`, SPEC-001) usa
`structlog.contextvars.bind_contextvars` — vinculado uma vez no início de
`run_pipeline` (`bind_run_correlation_id()`) e automaticamente incluído em
todo log subsequente emitido no mesmo contexto assíncrono, sem precisar
passar o valor explicitamente por parâmetro de função ou por
`pydantic_ai.RunContext`. Esta feature mantém esse mecanismo — não
introduz uma passagem explícita por `RunContext` — porque fazer isso seria
uma abstração adicional sem justificativa concreta (Princípio II):
`contextvars` já resolve o requisito real ("todo log de uma execução
carrega o mesmo id") de forma mais simples.

**Racional**: `asyncio.Task` (usado por `asyncio.gather` no fan-out
`compliance_analyzer`/`knowledge_builder`) copia o contexto de execução no
momento da criação da task — logs emitidos dentro de tasks concorrentes
lançadas depois do `bind_contextvars` inicial já carregam o mesmo
`correlation_id`, sem trabalho adicional.

**Gap real encontrado**: `mcp_servers/scraper_sse/` (o servidor MCP do
Scraper, processo/serviço separado — container próprio desde a SPEC-016)
**não emite nenhum log estruturado hoje** (nenhum uso de `structlog` ou
`logging` encontrado no módulo). Como é um processo separado, o
`correlation_id` vinculado no processo do Orchestrator não alcançaria
esses logs mesmo se existissem — precisaria ser recebido explicitamente
(ex. num campo da chamada de ferramenta MCP) e revinculado localmente. Dado
que esta feature é sobre auditar e fechar exatamente esse tipo de lacuna
(FR-006 é explícito: "qualquer lacuna encontrada... MUST ser corrigida"),
o servidor MCP passa a: (a) aceitar e logar o `correlation_id` recebido do
chamador nas chamadas de ferramenta relevantes, e (b) emitir logs
estruturados mínimos de entrada/saída de cada ferramenta MCP exposta —
sem introduzir uma segunda forma de logging (reaproveita `pix_compliance.logging.configure_logging`).

**Alternativas consideradas**:
- Não tocar no servidor MCP e considerar a propagação "resolvida" porque a
  maior parte do pipeline roda no processo do Orchestrator: rejeitada —
  contradiz FR-006 e a User Story 3 (auditar uma execução real pelos
  logs), que explicitamente inclui a etapa `scrape`, cuja coleta de fato
  acontece dentro do servidor MCP.

## Decisão 3 — Fixtures duplicadas: consolidar em `conftest.py`, sem nova camada

**Decisão**: Auditoria de `tests/*.py` encontrou fixtures locais
redefinidas em múltiplos arquivos com o mesmo propósito: `_settings`/`settings`
(carrega `Settings` com env de teste) repetida em 10 módulos, `store`
(instancia `S3ObjectStore`/`PgVectorStore` de teste) em 2, `_required_env`
(dict de variáveis obrigatórias para `Settings`) em 2, `_free_port` (porta
efêmera para servidor de teste) em 2. Todas migram para `tests/conftest.py`
(único arquivo de fixtures compartilhadas já existente, SPEC-007), com o
mesmo nome e comportamento — nenhuma fixture nova é inventada, apenas
movida e desduplicada.

**Racional**: FR-005 pede exatamente isso; `conftest.py` já é o padrão
estabelecido do projeto para fixture compartilhada (`mock_bcb_server`,
SPEC-007) — não há necessidade de um mecanismo novo (ex. plugin de pytest
separado), o que violaria o Princípio III (KISS).

**Alternativas consideradas**: Criar um pacote `tests/fixtures/` com
múltiplos arquivos temáticos: rejeitada — volume atual (4 fixtures
duplicadas) não justifica a segmentação (Princípio III); um único
`conftest.py` já cobre o caso.

## Decisão 4 — Contadores agregados por etapa: estender `EtapaMetric`, não criar um novo tipo

**Decisão**: `EtapaMetric` (`src/pix_compliance/models.py`, SPEC-002/015)
já registra `nome`, `status`, `duracao_segundos` por etapa executada. Os
contadores pedidos por FR-007 (documentos coletados, regras extraídas,
gaps encontrados, tokens consumidos) são adicionados como um campo
opcional estruturado dentro do mesmo modelo (`contadores: dict[str, int] | None`,
com chaves específicas por etapa preenchidas onde fazem sentido — ex.
`documentos_coletados` só em `scrape`, `regras_extraidas` só em `extract`),
e emitidos via `logger.info` estruturado ao final de cada etapa em
`_run_step` (`orchestrator_agent.py`), reaproveitando o `EtapaMetric` já
serializado no `PipelineResult`.

**Racional**: Latência por etapa já existe (`duracao_segundos`); estender o
mesmo tipo em vez de criar um `StepCounters` novo evita uma segunda
estrutura paralela para o mesmo conceito (Princípio II/III). Tokens
consumidos já são logados por chamada individual do LLM
(`bedrock_chat_invocado`, `input_tokens`/`output_tokens`,
`src/pix_compliance/llm_provider.py`) — a agregação por etapa soma esses
valores dentro do escopo de cada etapa do pipeline, não reimplementa a
contagem.

**Alternativas consideradas**: Um sistema de métricas separado (ex.
`prometheus_client`, contador em memória global): rejeitado — fora do
escopo declarado (sem testes de carga/performance), e introduziria uma
dependência nova sem justificativa (Princípio II); logging estruturado já
é o mecanismo de observabilidade escolhido pelo projeto desde a SPEC-001.

## Decisão 5 — CI: GitHub Actions, um único workflow, dois jobs simples

**Decisão**: `.github/workflows/ci.yml` novo (nenhum workflow existe hoje —
confirmado, `.github/` não existe no repositório), com dois steps
sequenciais no mesmo job (`ruff check .` depois `pytest -q`, mesma ordem
de `make lint`/`make test`), disparado em `push` e `pull_request` para
qualquer branch. Sem matriz de versões Python (o projeto já fixa
`requires-python = ">=3.11"` e roda numa única versão em desenvolvimento) —
adicionar matriz seria complexidade sem necessidade concreta hoje
(Princípio II).

**Racional**: FR-008 pede exatamente lint + suíte a cada push/PR. Como a
suíte inteira já roda offline (Decisão 0), nenhum secret AWS precisa ser
configurado no CI — outra vantagem concreta de manter `LLM_PROVIDER=offline`
como o único caminho de teste.

**Alternativas consideradas**: Dois workflows separados (lint e teste):
rejeitado — mesmo gatilho, mesmo ambiente, sem motivo para duplicar
configuração de checkout/setup Python (Princípio III).

## Decisão 6 — Relatório de cobertura: `pytest-cov`, sem meta de porcentagem total

**Decisão**: Adicionar `pytest-cov` a `[project.optional-dependencies].dev`
e configurar `--cov=src/pix_compliance --cov-report=term-missing` como
parte do job de CI (não do `make test` padrão, para não forçar a
dependência extra em todo `pip install -e ".[dev]"` local sem necessidade
imediata — mas disponível via `make test` se o dev já tem `pytest-cov`
instalado, sem falhar se não tiver). O relatório é lido com atenção
declarada aos módulos `models.py` e `guardrails.py` (FR-009) — sem
`--cov-fail-under` configurado, porque uma meta de porcentagem total
arbitrária é explicitamente rejeitada pela spec (FR-010).

**Racional**: `pytest-cov` é a ferramenta padrão do ecossistema `pytest`
já usado pelo projeto — nenhuma ferramenta nova de fora do stack já
estabelecido (Princípio II, stack técnica da constituição).

**Alternativas consideradas**: `coverage.py` direto (sem o plugin
`pytest-cov`): equivalente em resultado, mas exige um comando adicional
separado do `pytest`; `pytest-cov` integra no mesmo comando, mais simples
de rodar tanto localmente quanto no CI (Princípio III).
