# Feature Specification: API FastAPI (SPEC-013)

**Feature Branch**: `013-api-fastapi`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "API FastAPI (SPEC-013) — serviço HTTP documentado, expondo os endpoints nominalmente exigidos pelo desafio original, com Swagger completo."

**Dependências**: SPEC-002 (modelos de domínio — todos os `response_model` reusam esses tipos), SPEC-006 (storage, para os endpoints de listagem e o health check), SPEC-012 (Knowledge Builder/RAG, consumido pelo endpoint de busca semântica).

**Nota**: Esta é a SPEC-013 do catálogo do projeto — a API FastAPI em si, não
um agente do enxame. `src/pix_compliance/agents/report_consolidator_agent.py`
(SPEC-014, já implementado) é **cliente** desta API (`settings.api_url`); esta
spec é quem finalmente implementa o **servidor** do outro lado dessa chamada.

**Adendo pós-implementação**: durante a revisão de integração entre esta
feature e o Report Consolidator Agent (SPEC-014), verificou-se que
`publish_to_api` (SPEC-014) sempre apontou para `POST /reports` — endpoint
que não fazia parte da lista original de rotas desta spec. Foi adicionado
`POST /reports` a esta implementação como o endpoint real de recebimento do
relatório final consolidado (recebe/reconhece um `ReportOutput`, SPEC-002,
sem reprocessar nada — a única forma de fechar de fato a integração
cliente/servidor entre as duas specs). Ver `contracts/api.md` para o
contrato completo desta rota.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são
  o operador/avaliador do projeto, que consulta `/docs` como evidência
  formal de entrega (screenshot do Swagger exigido pelo desafio original), e
  clientes HTTP do enxame (o Report Consolidator Agent, SPEC-014) ou de
  ferramentas externas que consultam normativos/compliance/busca via REST.
-->

### User Story 1 - Consultar normativos, compliance e busca semântica via HTTP (Priority: P1)

Um cliente HTTP consulta `GET /normativos` (paginado, com filtros por tipo,
categoria e período), `GET /compliance` (análises e gap analysis, com filtro
por severidade) e `GET /search?query=...&top_k=...` (busca via RAG,
SPEC-012), recebendo respostas tipadas (`response_model`) que reaproveitam
os modelos já definidos na SPEC-002 — nenhum schema de resposta duplicado.

**Why this priority**: É o objetivo nominal central da spec — os três
endpoints de consulta são os que o desafio original exige nominalmente e o
que qualquer cliente (incluindo o próprio Report Consolidator) precisa para
extrair valor do enxame via HTTP.

**Independent Test**: Pode ser testado isoladamente chamando cada um dos três
endpoints com dados já persistidos (via `ObjectStore`/`PgVectorStore`,
SPEC-006, e o índice do Knowledge Builder, SPEC-012) e verificando que a
resposta corresponde ao `response_model` esperado.

**Acceptance Scenarios**:

1. **Given** normativos já persistidos, **When** `GET /normativos` é chamado
   com filtros de tipo/categoria/período e parâmetros de paginação, **Then**
   a resposta retorna apenas os normativos que casam com os filtros, no
   formato paginado esperado.
2. **Given** avaliações de conformidade já produzidas (SPEC-011), **When**
   `GET /compliance` é chamado com um filtro de severidade, **Then** a
   resposta retorna apenas os itens de gap analysis cuja severidade atende
   ao filtro.
3. **Given** o índice de busca semântica já populado (SPEC-012), **When**
   `GET /search?query=...&top_k=...` é chamado, **Then** a resposta retorna
   os resultados de busca no formato `SearchResult` (SPEC-002), sem exceder
   `top_k` itens.

---

### User Story 2 - Verificar a saúde do serviço e disparar uma execução ad-hoc (Priority: P1)

Um operador chama `GET /health` para confirmar conectividade com as
dependências externas (storage, etc.) antes de considerar o serviço no ar, e
`POST /runs` para disparar uma execução ad-hoc do pipeline sob demanda.

**Why this priority**: Mesma prioridade dos endpoints de consulta — sem
`/health`, não há como confirmar que o serviço está operacional antes de
depender dele (inclusive como parte de evidência de entrega); sem
`POST /runs`, não há forma de disparar o pipeline via HTTP, um requisito
nominal explícito do desafio original.

**Independent Test**: Pode ser testado isoladamente chamando `GET /health`
com as dependências disponíveis e indisponíveis (verificando que o status
reportado muda de acordo), e chamando `POST /runs` verificando que uma
execução é de fato disparada.

**Acceptance Scenarios**:

1. **Given** as dependências externas (storage) disponíveis, **When**
   `GET /health` é chamado, **Then** a resposta indica status saudável.
2. **Given** uma dependência externa indisponível, **When** `GET /health` é
   chamado, **Then** a resposta indica claramente qual dependência falhou,
   sem lançar um erro não tratado.
3. **Given** uma requisição válida, **When** `POST /runs` é chamado,
   **Then** uma execução do pipeline é disparada e a resposta confirma o
   disparo (não necessariamente aguarda a conclusão síncrona completa).

---

### User Story 3 - Erros são estruturados e a documentação é substantiva, não genérica (Priority: P1)

Qualquer erro de validação (422) ou de aplicação retorna um corpo
estruturado do próprio projeto, incluindo `correlation_id`, nunca o corpo
cru default do FastAPI. `/docs` (Swagger) renderiza com título, descrição,
versão, tags e exemplos reais preenchidos em todos os endpoints — não os
placeholders genéricos do FastAPI.

**Why this priority**: Mesma prioridade dos endpoints funcionais — o
desafio original pede screenshot do Swagger como evidência formal de
entrega, e erro estruturado com `correlation_id` é o que permite
rastrear uma falha em produção ligando a resposta HTTP ao log estruturado
correspondente (já existente desde a SPEC-001, `bind_run_correlation_id`).

**Independent Test**: Pode ser testado isoladamente enviando uma requisição
inválida a qualquer endpoint e verificando que a resposta 422 tem o formato
estruturado do projeto (com `correlation_id`), e abrindo `/docs` verificando
que nenhum endpoint mostra a descrição/exemplo default genérico do FastAPI.

**Acceptance Scenarios**:

1. **Given** uma requisição malformada a qualquer endpoint, **When** a
   validação falha, **Then** a resposta 422 retorna um corpo estruturado do
   projeto contendo `correlation_id`, não o corpo cru default do FastAPI.
2. **Given** o serviço no ar, **When** `/docs` é aberto, **Then** todos os
   endpoints mostram título, descrição e exemplo preenchidos — nenhum
   placeholder genérico do FastAPI.

---

### Edge Cases

- O que acontece quando `GET /normativos`/`GET /compliance` são chamados
  sem nenhum filtro? MUST retornar a primeira página de todos os itens
  disponíveis, não um erro.
- O que acontece quando um recurso específico (ex. um `normativo_id`
  inexistente, se a API expuser uma rota de detalhe) não existe? MUST
  retornar 404 com o mesmo corpo de erro estruturado (`correlation_id`), não
  uma exceção não tratada (500).
- O que acontece quando `POST /runs` é chamado enquanto uma dependência
  crítica (ex. storage) está indisponível? MUST retornar um erro estruturado
  claro, não uma exceção não tratada nem uma resposta de sucesso enganosa.
- Como o sistema decide o `top_k` default de `GET /search` quando o
  parâmetro não é informado? MUST ter um valor default razoável (ver
  Assumptions), nunca falhar por ausência do parâmetro.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST expor `GET /normativos`, com paginação e
  filtros por tipo, categoria e período.
- **FR-002**: O sistema MUST expor `GET /compliance`, retornando análises e
  gap analysis, com filtro por severidade.
- **FR-003**: O sistema MUST expor `GET /search?query=...&top_k=...`,
  executando busca semântica via o Knowledge Builder Agent (SPEC-012).
- **FR-004**: O sistema MUST expor `GET /health`, checando conectividade com
  as dependências externas (storage, no mínimo) e reportando o status de
  cada uma.
- **FR-005**: O sistema MUST expor `POST /runs`, disparando uma execução
  ad-hoc do pipeline.
- **FR-006**: Todo endpoint MUST declarar `response_model` reaproveitando os
  modelos já definidos na SPEC-002 — nenhum schema de resposta duplicado ou
  paralelo é criado por esta feature.
- **FR-007**: O sistema MUST ter exception handlers que devolvem erro
  estruturado do próprio projeto (incluindo `correlation_id`) para qualquer
  falha — validação (422), recurso não encontrado (404), ou erro de
  aplicação — nunca o corpo cru default do FastAPI.
- **FR-008**: Os metadados de OpenAPI (título, descrição, versão, tags) MUST
  estar completamente preenchidos, e cada endpoint MUST ter descrição e
  exemplo de request/response preenchidos — nunca os defaults genéricos do
  FastAPI.
- **FR-009**: O Swagger MUST estar disponível em `/docs`.
- **FR-010**: Esta feature MUST NOT implementar autenticação — decisão
  consciente de escopo, registrada em prosa no README (não uma lacuna
  esquecida).

### Key Entities *(include if feature involves data)*

- **NormativoItem / SearchResult / ConformanceReport / ConformanceItem /
  PipelineRequest / PipelineResult**: Modelos já existentes (SPEC-002),
  reaproveitados sem alteração como `response_model`/corpo de request dos
  endpoints desta feature.
- **Erro estruturado**: Corpo de resposta de erro do próprio projeto,
  incluindo `correlation_id` (mecanismo já existente desde a SPEC-001,
  `pix_compliance.logging.bind_run_correlation_id`), usado por todo
  exception handler desta feature.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato).
-->

### Measurable Outcomes

- **SC-001**: `/docs` renderiza com descrições e exemplos preenchidos em
  todos os endpoints, não os defaults genéricos do FastAPI.
- **SC-002**: `pytest tests/test_api.py -q` cobrindo status 200, 404 e 422
  em cada rota.
- **SC-003**: Uma resposta 422 de erro de validação retorna corpo
  estruturado do próprio projeto (com `correlation_id`), não o corpo padrão
  cru que o FastAPI gera sozinho.

## Assumptions

- Conforme o Princípio IX da constituição, `tests/test_api.py` deve ser
  escrito e confirmado como falho (rotas ainda não existem) antes de
  qualquer código de rota, derivado exclusivamente dos critérios de aceite
  desta spec.
- **`FastAPI`/`uvicorn` ainda não são dependências declaradas do projeto**:
  a stack técnica obrigatória da constituição já lista FastAPI, mas nenhuma
  spec anterior o introduziu como dependência real — esta é a primeira
  feature que de fato usa FastAPI, adicionando-o (junto de `uvicorn` como
  servidor ASGI) a `pyproject.toml`. `httpx` (cliente de teste do FastAPI,
  `TestClient`) já é dependência declarada desde a SPEC-001.
- **`POST /runs` orquestra os agentes já implementados diretamente, sem um
  Orchestrator Agent dedicado**: `PipelineRequest`/`PipelineResult`
  (SPEC-002) já existem como contrato, antecipando um futuro Orchestrator
  Agent que ainda não foi especificado nem implementado neste projeto. Até
  que essa spec exista, `POST /runs` chama diretamente, em sequência, os
  agentes já implementados (Scraper → Extractor → Compliance Analyzer →
  Conformance Validator → Knowledge Builder → Report Consolidator),
  reaproveitando `PipelineRequest`/`PipelineResult` como request/response
  desta rota — o contrato HTTP não muda quando um Orchestrator Agent
  dedicado for introduzido no futuro, apenas a implementação interna da
  rota passa a delegar a ele.
- **Execução de `POST /runs` é assíncrona/não bloqueante em relação à
  resposta HTTP**: dado que o pipeline completo (scraping → extração → LLM
  → indexação → relatório) pode levar minutos, a resposta a `POST /runs`
  confirma o disparo (ex. um identificador de execução), sem que o cliente
  HTTP precise aguardar a conclusão síncrona — mesmo padrão de "long-running
  job" já implícito em `PipelineResult.concluido_em` (campo que só faz
  sentido se a conclusão puder ser consultada depois, não apenas devolvida
  de imediato).
- **`top_k` default de `GET /search`**: um valor default razoável (ex. 5,
  mesmo valor mínimo implícito em `SearchQuery.top_k` de exemplos anteriores
  do projeto) é usado quando o parâmetro não é informado — decisão técnica
  sem impacto de produto, resolvida em `/speckit-plan`.
- Autenticação fica explicitamente fora de escopo (FR-010) — decisão
  consciente de escopo para um desafio técnico de prazo curto, documentada
  em prosa no README, nunca como uma lacuna esquecida ou um TODO no código.
- Identificadores de código são em inglês; comentários e docstrings em
  português, explicando decisões não óbvias — em particular, por que
  autenticação foi conscientemente deixada fora do escopo (Princípio VII da
  constituição).
- Esta feature não introduz nenhuma abstração nova além do que já existe —
  os endpoints são consumidores finos de `ObjectStore`/`PgVectorStore`
  (SPEC-006) e do índice de busca do Knowledge Builder (SPEC-012), não uma
  nova camada de acesso a dados (Princípio II, YAGNI).
