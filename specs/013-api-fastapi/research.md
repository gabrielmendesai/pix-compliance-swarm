# Research: API FastAPI (SPEC-013)

## 0. `GET /normativos`: lê `fixtures/normativos.json` diretamente, sem tabela SQL nova

**Decision**: `GET /normativos` carrega `fixtures/normativos.json` em
memória (mesmo arquivo já usado por todo CLI do projeto desde a SPEC-003) e
aplica filtro (`tipo`/`categoria`/período) e paginação em Python — nenhuma
tabela SQL nova é criada para persistir `NormativoItem`.

**Rationale**: Inspecionado `migrations/0001_create_vector_store_schema.sql`
(SPEC-006): a única tabela existente é `vector_store` (embeddings +
metadata parcial, sem os campos completos de `NormativoItem` como `tipo`/
`data_publicacao`/`data_vigencia`). Criar uma tabela `normativos` nova só
para servir esta rota seria uma segunda fonte de verdade para o mesmo dado
já materializado em `fixtures/normativos.json`, sem necessidade real neste
projeto (volume pequeno, um desafio técnico, não uma API de produção em
escala) — violação de YAGNI (Princípio II). O corpus mock já é a fonte de
verdade usada por todo o resto do pipeline (Compliance Analyzer,
Conformance Validator, Knowledge Builder); esta rota lê a mesma fonte.

**Alternatives considered**: Criar uma tabela SQL `normativos` e persistir
o corpus nela durante o boot da API foi descartado — introduziria uma
segunda camada de persistência (SQL, além de `vector_store`) e um passo de
sincronização (quando o corpus muda, a tabela precisa ser re-populada) sem
nenhum requisito real que justifique isso agora.

## 1. `GET /compliance`: lê os `ConformanceReport` JSON já persistidos localmente pelo Report Consolidator (SPEC-014)

**Decision**: `GET /compliance` lê todos os arquivos `reports/*.json`
(convenção de nome determinístico já estabelecida em
`report_consolidator_agent.py`, SPEC-014, `research.md` Decisão 3),
desserializa cada um como `ReportOutput`... na verdade como o
`ConformanceReport` de origem — ver nota abaixo —, agrega os `itens`
(`ConformanceItem`) de todos os relatórios encontrados, e aplica o filtro
de `severidade` em memória.

**Nota de ajuste**: `ReportOutput` (o que o Report Consolidator grava em
`reports/<id>.json`) não inclui os `ConformanceItem` individuais — apenas
contagens agregadas (`total_gaps` etc., ver data-model.md da SPEC-014).
Para `GET /compliance` servir itens individuais com filtro por severidade,
esta feature também persiste o `ConformanceReport` completo (não apenas o
`ReportOutput` resumido) em `reports/<report_id>.conformance.json` durante
`POST /runs` — um segundo arquivo, mesma convenção de diretório, mesmo
padrão de nome determinístico, sem introduzir uma tabela nova. Fora do
fluxo de `POST /runs` (ex. se o operador rodar `conformance_validator_agent`
via CLI diretamente), o mesmo arquivo pode ser gravado manualmente pelo
operador antes de consultar `GET /compliance` — documentado em
quickstart.md.

**Rationale**: Mesma lógica da Decisão 0 — reaproveitar a persistência local
já garantida pelo Report Consolidator (research.md da SPEC-014, Decisão 3:
"artefatos sempre gravados em disco antes de qualquer chamada de rede") em
vez de introduzir uma tabela SQL nova só para este endpoint. Persistir o
`ConformanceReport` completo ao lado do `ReportOutput` resumido é a menor
mudança possível para fechar a lacuna de dados sem duplicar responsabilidade
entre duas specs (o Report Consolidator continua sendo o único ponto que
grava relatórios em disco).

**Alternatives considered**: Rodar `build_conformance_report` (SPEC-011) a
cada chamada de `GET /compliance`, ao vivo, foi descartado — exigiria
chamadas de LLM síncronas dentro de uma requisição GET, tornando a rota
lenta, cara e não idempotente para uma simples consulta de leitura; dados de
compliance já processados devem ser lidos, não recomputados a cada consulta.

## 2. `GET /health`: reconstrução leve de `S3ObjectStore`/`PgVectorStore`, captura de exceção por dependência

**Decision**: `GET /health` tenta instanciar `S3ObjectStore(settings)` e
`PgVectorStore(settings)` (ambos já validam conectividade na construção —
`_ensure_bucket()`/`psycopg.connect()`, respectivamente) dentro de um
`try`/`except` por dependência, reportando `{"objeto_store": "ok"/"falhou:
<mensagem>", "vector_store": "ok"/"falhou: <mensagem>"}` — nunca deixando
uma exceção não tratada derrubar a rota (Edge Case da spec.md).

**Rationale**: `S3ObjectStore.__init__`/`PgVectorStore.__init__` (SPEC-006)
já fazem uma chamada de rede real na construção (`head_bucket`/
`create_bucket`, `psycopg.connect`) — não é necessário nenhum código de
"ping" adicional, apenas capturar a exceção que essas classes já levantam
em caso de falha de conectividade, e reportá-la por dependência em vez de
deixar a requisição inteira falhar com 500.

**Alternatives considered**: Um "ping" mais leve (ex. `SELECT 1` sem
reconstruir o cliente) foi considerado, mas descartado por não haver
método existente para isso nas classes já implementadas — reconstruir o
cliente a cada chamada de `/health` tem custo desprezível para o volume
deste projeto, e reaproveita a validação de conectividade que essas classes
já fazem, sem exigir um método novo nelas.

## 3. Erro estruturado: `ErrorResponse` (Pydantic) + `correlation_id` via `bind_run_correlation_id()`

**Decision**: Um único modelo `ErrorResponse` (`correlation_id: str`,
`detail: str`, `errors: list[dict] | None` para detalhes de validação) é
definido em `src/pix_compliance/api/errors.py`, usado por três exception
handlers registrados em `app.py`: `RequestValidationError` (422),
`ObjectNotFoundError`/`404` (recurso não encontrado), e `Exception` genérica
(500) — todos chamam `bind_run_correlation_id()` (SPEC-001, já existente) no
início do handler e incluem o `correlation_id` retornado no corpo da
resposta.

**Rationale**: FR-007 exige corpo estruturado com `correlation_id` para
qualquer falha, nunca o corpo cru do FastAPI
(`{"detail": [...]}` sem identificador rastreável). `bind_run_correlation_id`
já existe desde a SPEC-001 exatamente para esse propósito ("todo log da
execução carrega o mesmo `correlation_id`") — reaproveitá-lo aqui estende a
mesma garantia de rastreabilidade da camada de logging para a camada HTTP,
sem inventar um segundo mecanismo de geração de id.

**Alternatives considered**: Usar apenas o `detail` default do FastAPI e
adicionar um middleware que injeta `correlation_id` no header de resposta
(sem alterar o corpo) foi descartado — FR-007 exige explicitamente que o
`correlation_id` esteja no corpo estruturado, não apenas em um header.

## 4. `POST /runs`: execução síncrona, sem infraestrutura de fila (reversão da suposição inicial do spec.md)

**Decision**: `POST /runs` executa a orquestração dos agentes já
implementados **sincronamente**, dentro do próprio ciclo request/response,
e devolve o `PipelineResult` já completo (`sucesso`, `concluido_em`
preenchidos) — não um identificador de execução para consulta posterior.

**Rationale**: `spec.md` (Assumptions) havia especulado inicialmente uma
execução assíncrona/não bloqueante; investigando mais a fundo nesta fase de
planejamento, `PipelineResult` (SPEC-002, já congelado) exige `sucesso:
bool` e `concluido_em: datetime` como campos obrigatórios (não opcionais) —
não há um "status pendente" representável nesse contrato. Retrofitar um
fluxo fire-and-forget exigiria alterar um contrato já congelado (violação
do Princípio VI) ou inventar um segundo modelo de resposta "pendente"
(seria uma duplicação de schema perto do já existente, FR-006). A leitura
mais fiel ao contrato como está é: a rota só responde quando o
`PipelineResult` está de fato completo. Para o volume deste projeto
(corpus mock, `LLM_PROVIDER` configurável), execução síncrona é aceitável e
mais simples que introduzir uma fila de jobs (Celery/RQ) que não existe em
nenhuma outra parte do projeto — Princípio III (KISS) e Princípio II
(YAGNI): não introduzir infraestrutura assíncrona sem necessidade
comprovada.

**Alternatives considered**: Introduzir `BackgroundTasks` do próprio
FastAPI (não uma dependência nova) com um endpoint de consulta de status
separado foi considerado, mas descartado nesta spec por exigir alterar o
contrato de `PipelineResult` (adicionar um estado "em andamento") — fora do
escopo desta feature, que reaproveita os modelos já congelados sem
alteração (FR-006). Documentado aqui como uma evolução futura possível, não
implementada.

## 5. `FastAPI`/`uvicorn`: primeira introdução real como dependência

**Decision**: Adicionar `fastapi>=0.115` e `uvicorn[standard]>=0.30` a
`pyproject.toml` (`dependencies`, não `optional-dependencies` — é stack de
produção, não apenas de desenvolvimento).

**Rationale**: A constituição já lista FastAPI na stack técnica obrigatória
do projeto, mas nenhuma spec anterior o usou de fato — `report_consolidator_
agent.py` (SPEC-014) é **cliente** HTTP de uma API FastAPI, mas o servidor em
si nunca foi implementado até esta spec. `httpx` (cliente de teste via
`TestClient`) já é dependência declarada desde a SPEC-001, então nenhuma
dependência de teste nova é necessária.

**Alternatives considered**: N/A — FastAPI é mandado explicitamente pela
constituição do projeto (Contexto do Projeto e Stack Técnica), não uma
escolha em aberto.

## Resumo de dependências novas

`fastapi>=0.115`, `uvicorn[standard]>=0.30` — ambos já previstos pela stack
técnica obrigatória da constituição, apenas nunca antes declarados em
`pyproject.toml`. Nenhuma outra dependência nova.

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
