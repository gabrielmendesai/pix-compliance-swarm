# Feature Specification: Conteinerização (SPEC-016)

**Feature Branch**: `016-containerization`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Conteinerização (SPEC-016) — `docker compose up` sobe o sistema inteiro sem nenhum passo manual, a partir de um repositório limpo."

**Dependências**: SPEC-013 (API FastAPI), SPEC-007 (servidor MCP do Scraper), SPEC-015 (Orchestrator e agendamento) — todas já implementadas e funcionando de ponta a ponta.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seu "usuário" é o
  operador/avaliador do projeto, que clona o repositório e sobe o sistema
  inteiro com um único comando, sem nenhum passo manual de setup (criar
  bucket no console do MinIO, aplicar migration à mão, etc.) — exatamente o
  tipo de fricção que "eficiência de conteinerização" (critério de avaliação
  explícito do desafio original) recompensa eliminar.
-->

### User Story 1 - Subir o sistema inteiro com um único comando, a partir de um repositório limpo (Priority: P1)

Um operador clona o repositório, copia `.env.example` para `.env`, preenche as credenciais, e roda `docker compose up -d`. Todos os serviços (`api`, `mcp-scraper`, `scheduler`, `postgres`, `minio`, `mock-bcb`) sobem e ficam com status saudável, sem nenhuma intervenção manual adicional — incluindo a criação do bucket do object storage e a aplicação da migration do pgvector, que até esta feature exigiam passos manuais.

**Why this priority**: É o objetivo nominal central da spec — sem isso, a "eficiência de conteinerização" avaliada pelo desafio original não é demonstrável, e cada avaliador precisaria repetir manualmente os mesmos passos de setup que já causaram fricção durante o desenvolvimento.

**Independent Test**: Pode ser testado isoladamente rodando `docker compose up -d` a partir de um checkout limpo (sem volumes/estado residual) e verificando que todos os serviços reportam `healthy`, sem nenhum comando manual além do `docker compose up -d` em si.

**Acceptance Scenarios**:

1. **Given** um repositório recém-clonado com `.env` preenchido, **When** `docker compose up -d` é executado, **Then** todos os serviços ficam com status saudável, sem nenhum passo manual adicional (SC-001).
2. **Given** o sistema já no ar, **When** `GET /docs` é acessado a partir do host e o servidor MCP recebe o handshake inicial do protocolo, **Then** ambos respondem corretamente (SC-002).

---

### User Story 2 - Reiniciar do zero reproduz o mesmo estado funcional, sem fricção manual (Priority: P1)

Um operador roda `docker compose down -v` (removendo volumes) seguido de `docker compose up -d`. O sistema volta a ficar completamente funcional, incluindo a recriação automática do bucket do object storage e a reaplicação da migration do pgvector — nenhuma etapa que antes exigia intervenção manual no console do MinIO ou execução manual de SQL volta a ser necessária.

**Why this priority**: Mesma prioridade da User Story 1 — a idempotência do bootstrap (recriar do zero sem fricção) é o que efetivamente elimina a lacuna manual identificada durante o desenvolvimento (o nome do bucket não tinha valor padrão nem criação automática); sem essa garantia, a User Story 1 só funcionaria "na primeira vez", não de forma repetível.

**Independent Test**: Pode ser testado isoladamente rodando `docker compose down -v && docker compose up -d` e confirmando que o sistema fica funcional novamente sem nenhum comando manual além dos dois comandos do compose.

**Acceptance Scenarios**:

1. **Given** o sistema já rodou uma vez e seus volumes foram removidos (`docker compose down -v`), **When** `docker compose up -d` é executado novamente, **Then** o bucket do object storage é recriado automaticamente, a migration do pgvector é reaplicada automaticamente, e o sistema fica funcional sem qualquer intervenção manual (SC-003).

---

### User Story 3 - Imagens eficientes, com rebuild rápido para mudanças triviais de código (Priority: P2)

Um operador que altera uma linha de código da aplicação e roda `docker compose build` novamente observa que apenas a camada de código é reconstruída — as camadas de dependências (já instaladas) permanecem cacheadas, e as imagens finais têm tamanho razoável (sem ferramentas de build/dependências de desenvolvimento presentes na imagem final).

**Why this priority**: Prioridade abaixo das garantias centrais de "sobe sem fricção" (P1) — é uma otimização de qualidade de engenharia (o outro critério de avaliação explícito citado pela spec: "eficiência de conteinerização"), mas o sistema já é funcional e demonstrável sem ela.

**Independent Test**: Pode ser testado isoladamente alterando uma linha de um módulo Python já existente, rodando `docker compose build`, e observando (via `docker compose build` ou `docker history`) que a etapa de instalação de dependências não foi reexecutada.

**Acceptance Scenarios**:

1. **Given** uma imagem já construída, **When** apenas o código da aplicação muda (nenhuma dependência), **Then** o rebuild reaproveita a camada de dependências já cacheada, sem reinstalar tudo (SC-004).
2. **Given** as imagens finais construídas, **When** inspecionadas, **Then** têm tamanho razoável — sem compiladores/ferramentas de build presentes na imagem final (multi-stage), e rodam com um usuário não-root (Notas de implementação).

---

### Edge Cases

- O que acontece se o script de bootstrap rodar mais de uma vez (ex. um restart do container `scheduler` sem `down -v`)? MUST ser idempotente — bucket e migration já existentes não causam erro nem duplicação, apenas confirmam o estado já correto.
- O que acontece se um serviço dependente (ex. `api`) subir antes de `postgres`/`minio` estarem prontos? MUST ser impedido por `depends_on` com condição de saúde (`condition: service_healthy`), não apenas ordem de inicialização do compose.
- O que acontece se `OBJECT_STORAGE_BUCKET` não estiver definido no `.env`? MUST falhar de forma clara (mesmo padrão de `ConfigurationError` já estabelecido, SPEC-001) — nunca um bucket com nome hardcoded criado silenciosamente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer Dockerfiles multi-stage para a API, o servidor MCP do Scraper, e o scheduler (Orchestrator), todos rodando com um usuário não-root na imagem final.
- **FR-002**: O sistema MUST fornecer um `docker-compose.yml` com os serviços `api`, `mcp-scraper`, `scheduler`, `postgres` (com a extensão pgvector), `minio`, e `mock-bcb`.
- **FR-003**: Todo serviço com dependência de outro MUST ter um healthcheck, e `depends_on` MUST usar `condition: service_healthy` — nunca apenas ordem de subida.
- **FR-004**: O sistema MUST persistir dados relevantes (Postgres, MinIO) em volumes, sobrevivendo a reinícios de container (mas não a `down -v`, que remove volumes deliberadamente).
- **FR-005**: O sistema MUST executar, na primeira subida (e de forma idempotente em subidas subsequentes), um script de bootstrap que cria o bucket do object storage usando o nome definido em `OBJECT_STORAGE_BUCKET` (nunca um literal hardcoded) e aplica a migration do pgvector (SPEC-006) automaticamente.
- **FR-006**: O sistema MUST fornecer um `.dockerignore` excluindo arquivos irrelevantes ao build (ex. `.venv/`, `__pycache__/`, `.git/`, `tests/`, documentação).
- **FR-007**: `docker compose up -d` a partir de um repositório limpo MUST deixar todos os serviços com status saudável, sem nenhum passo manual.
- **FR-008**: `GET /docs` MUST estar acessível a partir do host, e o servidor MCP MUST responder corretamente ao handshake inicial do protocolo.
- **FR-009**: `docker compose down -v && docker compose up -d` MUST reproduzir o mesmo estado funcional, sem qualquer intervenção manual.
- **FR-010**: As imagens finais MUST ter tamanho razoável (sem ferramentas de build/dependências de desenvolvimento), com as camadas de instalação de dependências cacheadas separadamente das camadas de código-fonte (para que uma mudança trivial de código não force reinstalação de dependências).
- **FR-011**: Esta feature MUST NOT introduzir Kubernetes nem publicação em registry de imagens — ambos explicitamente fora de escopo.

### Key Entities *(include if feature involves data)*

- **Script de bootstrap**: Não é uma entidade de dados — um script de infraestrutura (shell/Python) que roda uma vez por ciclo de vida dos volumes, criando o bucket (via `S3ObjectStore`/`boto3`, mesma credencial já configurada em `Settings`) e aplicando `migrations/0001_create_vector_store_schema.sql` (SPEC-006).

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato — aqui, um script de verificação em
  vez de `pytest`, dado que esta feature é majoritariamente infraestrutura
  declarativa).
-->

### Measurable Outcomes

- **SC-001**: `docker compose up -d` a partir de um repositório limpo deixa todos os serviços com status saudável.
- **SC-002**: `/docs` está acessível no host, e o servidor MCP responde ao handshake.
- **SC-003**: `docker compose down -v && docker compose up -d` reproduz o mesmo estado funcional sem qualquer intervenção manual — incluindo a criação do bucket, que não deve mais exigir passo manual no console do MinIO.
- **SC-004**: As imagens ficam em tamanho razoável, com camadas de dependência devidamente cacheadas (não reinstalar tudo a cada rebuild por mudança trivial de código).

## Assumptions

- Conforme o Princípio IX da constituição (adaptado à natureza desta feature, majoritariamente infraestrutura declarativa, não lógica de aplicação testável por `pytest` no sentido usual), um script de verificação (`scripts/verify_containerization.sh` ou equivalente) MUST ser escrito e confirmado como falho antes de qualquer Dockerfile/`docker-compose.yml` existir, servindo como o "teste" desta feature.
- **O bucket do object storage já é criado automaticamente pelo código de aplicação, não apenas pelo script de bootstrap**: `S3ObjectStore.__init__` (`src/pix_compliance/object_store.py`, SPEC-006) já chama `_ensure_bucket()` (`head_bucket`/`create_bucket`) sempre que qualquer serviço constrói um `S3ObjectStore` — ou seja, a lacuna manual "criar bucket no console do MinIO" já teria sido resolvida na prática assim que qualquer serviço (`api`, `scheduler`) subisse e tocasse o object storage pela primeira vez. O script de bootstrap desta feature (FR-005) tem valor real mesmo assim: (a) torna a criação do bucket explícita e antecipada — não dependente de qual serviço "tocar" o object storage primeiro —, e (b) é o único lugar que também aplica a migration do pgvector, que não tem nenhum mecanismo de auto-aplicação hoje. Resolvido aqui sem pedir esclarecimento ao usuário, por ser uma constatação técnica sobre código já existente, não uma decisão de produto.
- **`mock-bcb` e `mcp-scraper` tornam-se serviços de container persistentes, diferente do padrão efêmero já usado pelo Orchestrator (SPEC-015)**: `run_pipeline` (SPEC-015) hoje sobe sua própria cópia efêmera do mock BCB e do servidor MCP em processo (`bootstrap_local_servers=True`, research.md da SPEC-015). Nesta feature, ambos passam a ser serviços de container de longa duração — o serviço `scheduler` (rodando `run_pipeline` periodicamente) MUST ser configurado para **não** subir suas próprias cópias efêmeras quando os serviços `mock-bcb`/`mcp-scraper` já existem no compose (evitando colisão de porta) — mecanismo exato (variável de ambiente, parâmetro de CLI) é decisão técnica a resolver em `/speckit-plan`, não uma decisão de produto desta spec.
- **O serviço `scheduler` precisa de um modo de execução contínua que ainda não existe**: o CLI atual de `orchestrator_agent.py` (`if __name__ == "__main__":`, SPEC-015) faz uma única execução ad-hoc e termina — não inicia `start_scheduler()` em modo daemon/contínuo. Um pequeno modo de invocação adicional (ex. uma flag ou um segundo entrypoint chamando `start_scheduler` e mantendo o processo vivo) é necessário para que o serviço `scheduler` do compose funcione como um container de longa duração, não um `Job` que termina — detalhe de implementação a resolver em `/speckit-plan`.
- Identificadores de código (nomes de serviço, variáveis de script) são em inglês; comentários em português explicando decisões de infraestrutura não óbvias — em particular, por que multi-stage, por que usuário não-root, e por que o script de bootstrap é seguro para rodar mais de uma vez (idempotência) — Princípio VII da constituição.
- Nenhuma abstração de código nova é introduzida — é configuração e scripts de infraestrutura (Dockerfiles, compose, bootstrap), não lógica de aplicação (Princípio II, YAGNI).
