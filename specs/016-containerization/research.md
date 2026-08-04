# Research: Conteinerização (SPEC-016)

## 0. Um `Dockerfile` multi-stage com três estágios finais, não três arquivos

**Decision**: Um único `Dockerfile` na raiz, com um estágio `builder`
compartilhado (instala todas as dependências Python) e três estágios
finais nomeados (`api`, `mcp-scraper`, `scheduler`), cada um copiando só o
necessário do `builder` e do código-fonte, e rodando como usuário
não-root. `docker-compose.yml` referencia cada serviço via `build.target`.

**Rationale**: Os três serviços da aplicação compartilham exatamente o
mesmo conjunto de dependências Python (`pyproject.toml` único, sem extras
por serviço) — três Dockerfiles separados duplicariam a mesma lógica de
instalação de dependências três vezes, com risco real de divergência
silenciosa entre eles (Princípio III, KISS). "Dockerfiles multi-stage"
(plural, na spec original) é satisfeito pelos três estágios finais
multi-stage dentro do mesmo arquivo — a intenção da spec (build eficiente,
usuário não-root, sem ferramentas de build na imagem final) é preservada
integralmente.

**Alternatives considered**: Três arquivos `Dockerfile.api`/
`Dockerfile.mcp-scraper`/`Dockerfile.scheduler`, cada um com seu próprio
estágio builder, foi considerado e descartado — triplicaria a lista de
`RUN pip install` (e o cache de camadas correspondente), sem nenhum
benefício real já que os três serviços compartilham o mesmo
`pyproject.toml`.

## 1. `mock-bcb`: imagem oficial `python:3.12-slim` direto no compose, sem Dockerfile próprio

**Decision**: O serviço `mock-bcb` usa a imagem `python:3.12-slim` oficial
diretamente em `docker-compose.yml` (`image:`, não `build:`), com
`command: python -m http.server 8080 --directory /mock_bcb` e um volume
somente-leitura montando `./mock_bcb:/mock_bcb:ro`.

**Rationale**: Servir um diretório estático (`mock_bcb/`, SPEC-003) não
precisa de nenhuma dependência além da stdlib — o mesmo mecanismo já usado
em `tests/conftest.py::mock_bcb_server` e em
`orchestrator_agent.py::_start_mock_bcb_server` (SPEC-015). Construir uma
imagem custom para isso seria uma abstração sem necessidade real
(Princípio II, YAGNI).

**Alternatives considered**: `nginx:alpine` servindo os arquivos estáticos
foi considerado — descartado por introduzir uma segunda tecnologia de
servidor HTTP no projeto (nginx) só para replicar o que `http.server` já
faz, sem ganho real para um mock de demonstração.

## 2. Cache de dependências: ordem de `COPY` + cache mount do BuildKit, não o "truque do pacote vazio"

**Decision**: No estágio `builder`, `COPY pyproject.toml ./` acontece
antes de `COPY src/ ./src/`; `RUN --mount=type=cache,target=/root/.cache/pip
pip install --no-cache-dir .` usa um cache mount do BuildKit para o cache
interno do `pip` (não a flag `--no-cache-dir` sozinha, que desativaria
justamente o cache que se quer preservar entre builds — a flag evita que o
cache vá parar na camada final da imagem, enquanto o cache mount preserva
o cache entre execuções de build subsequentes, nunca na imagem em si).

**Rationale**: O projeto usa um layout `src/` com `pyproject.toml`
(`[tool.setuptools.packages.find] where = ["src"]`) — um `pip install .`
local sempre precisa do diretório `src/` presente para o backend do
setuptools localizar o pacote, então a ordem de `COPY` sozinha (manifesto
antes do código) só evita reinstalação completa quando **apenas**
`pyproject.toml` muda (raro). Para o caso comum (mudança de código, não de
dependência), um cache mount do `pip` garante que as dependências pesadas
já baixadas (`boto3`, `pydantic-ai-slim`, `anthropic`, etc.) nunca sejam
baixadas de novo — apenas o pacote local (rápido, sem rede) é reinstalado
— satisfazendo FR-010 ("não reinstalar tudo") de forma robusta nos dois
cenários, sem depender de um truque frágil de arquivo de pacote vazio.

**Alternatives considered**: O "truque do pacote fake" (copiar apenas
`pyproject.toml` + arquivos `__init__.py` vazios, instalar, depois copiar
o código real por cima) foi considerado — descartado por ser mais frágil
(quebra silenciosamente se a estrutura de pacotes mudar) e por o cache
mount do BuildKit já resolver o problema real (não baixar dependências de
novo) de forma mais simples e menos propensa a erro.

## 3. Bootstrap como serviço de execução única do compose, não um script rodado manualmente

**Decision**: Um serviço `bootstrap` no compose, usando o mesmo estágio
`api` da imagem (já tem `boto3`/`psycopg` instalados), com
`command: python scripts/bootstrap.py`, sem porta exposta, que termina com
código de saída 0 em caso de sucesso. `api` e `scheduler` declaram
`depends_on: bootstrap: condition: service_completed_successfully`, além
de `postgres`/`minio: condition: service_healthy`.

**Rationale**: `depends_on` com `condition: service_completed_successfully`
é o mecanismo idiomático do Compose para "rode isto uma vez, com sucesso,
antes dos demais subirem" — evita a necessidade de um script de shell
externo chamado manualmente pelo operador (que reintroduziria exatamente o
tipo de passo manual que esta feature existe para eliminar, FR-007).

**Alternatives considered**: Rodar a lógica de bootstrap dentro do
`entrypoint` de `api`/`scheduler` (cada um verificando e criando o bucket/
aplicando a migration antes de iniciar o próprio serviço) foi considerado
— descartado porque duplicaria a mesma lógica em dois lugares (dois
entrypoints) e tornaria a ordem de inicialização menos explícita que um
serviço dedicado com `depends_on` (Princípio III).

## 4. `scripts/bootstrap.py`: reaproveita `S3ObjectStore`/`psycopg`, idempotente por natureza

**Decision**: `scripts/bootstrap.py` importa `S3ObjectStore` (SPEC-006) —
sua própria construção já cria o bucket via `_ensure_bucket()`
(`head_bucket`/`create_bucket`, idempotente: `head_bucket` bem-sucedido
não recria nada) — e aplica `migrations/0001_create_vector_store_schema.sql`
via `psycopg`, executando o SQL diretamente (o próprio arquivo já usa
`CREATE EXTENSION IF NOT EXISTS`/`CREATE TABLE IF NOT EXISTS`/`CREATE INDEX
IF NOT EXISTS` — idempotente por construção, sem precisar de um sistema de
controle de versão de migrations para uma única migration).

**Rationale**: Reaproveitar `S3ObjectStore` em vez de chamar `boto3`
diretamente garante que o bucket seja criado com exatamente a mesma lógica
(e nome, lido de `settings.object_storage_bucket`, nunca hardcoded — FR-005)
que qualquer outro serviço já usa — uma única fonte de verdade para "como
criar o bucket" (Princípio II: não introduzir uma segunda forma de fazer a
mesma coisa). A migration já era idempotente desde a SPEC-006 (todos os
`CREATE ... IF NOT EXISTS`) — bastava um lugar automatizado para executá-la.

**Alternatives considered**: Uma ferramenta de migration dedicada (Alembic,
`golang-migrate`) foi considerada e descartada — over-engineering para uma
única migration `.sql` já idempotente por construção; introduziria uma
dependência nova e um conceito de versionamento de schema sem necessidade
real neste projeto (Princípio II, YAGNI).

## 5. Extensão aditiva de `orchestrator_agent.py`: modo daemon + flag de bootstrap efêmero

**Decision**: `orchestrator_agent.py` ganha dois parâmetros/flags novos,
aditivos, sem alterar nenhuma assinatura existente:
1. Uma flag de CLI `--daemon` no bloco `if __name__ == "__main__":` que,
   quando presente, chama `start_scheduler(settings)` e mantém o processo
   vivo (`asyncio.Event().wait()`), em vez de rodar uma única execução
   ad-hoc e sair.
2. Uma variável de ambiente nova em `Settings`
   (`orchestrator_bootstrap_local_servers: bool = True`), lida por
   `run_pipeline` como o valor default de `bootstrap_local_servers` quando
   o chamador não passa o parâmetro explicitamente — o container
   `scheduler` do compose define essa variável como `false`, já que
   `mock-bcb`/`mcp-scraper` existem como containers próprios (evita
   colisão de porta com o padrão efêmero da SPEC-015).

**Rationale**: FR-008 do desafio original (via SPEC-013/015) já estabeleceu
que CLI e scheduler chamam exatamente o mesmo `run_pipeline` — a extensão
aqui é mínima e não reabre esse contrato: apenas dá ao operador (via
variável de ambiente, não um segundo caminho de código) controle sobre se
o Orchestrator deve subir suas próprias cópias efêmeras do mock BCB/MCP
(fora de container, ex. rodando `make run` localmente) ou reaproveitar os
containers já existentes (dentro do compose).

**Alternatives considered**: Um segundo entrypoint Python separado
(`scheduler_daemon.py`) foi considerado e descartado — duplicaria a lógica
de leitura de `Settings`/construção de `PipelineRequest` já presente no
`__main__` existente, para uma diferença de comportamento (rodar uma vez
vs. continuamente) que uma única flag já resolve (Princípio III, KISS).

## 6. Healthchecks: `GET /health` (API), checagem TCP simples (`mcp-scraper`), `pg_isready`/`mc ready` (já existentes)

**Decision**: `api` usa `curl -f http://localhost:8000/health` (endpoint
já implementado, SPEC-013 — reporta `"ok"`/`"degraded"` por dependência,
mas para o healthcheck do container basta o código HTTP 200, que a rota
sempre retorna mesmo em `"degraded"` controlado). `mcp-scraper` usa uma
checagem TCP simples via Python (`python -c "import socket;
socket.create_connection(('localhost', 8100), timeout=2)"`) — o protocolo
MCP/SSE não tem um endpoint HTTP de health dedicado, mas uma conexão TCP
bem-sucedida na porta já confirma que o processo está de fato escutando.
`postgres`/`minio` mantêm os healthchecks já existentes desde a SPEC-006
(`pg_isready`, `mc ready local`). `mock-bcb` usa `curl -f
http://localhost:8080/` (o `http.server` já responde 200 na raiz).
`scheduler` usa uma checagem de processo vivo (`pgrep -f
orchestrator_agent` ou equivalente) — nada depende dele no compose, mas um
healthcheck ainda ajuda a observabilidade (`docker compose ps`).

**Rationale**: Reaproveitar `GET /health` (já existente, projetado para
isso) evita introduzir um segundo endpoint só para o Docker; a checagem
TCP para `mcp-scraper` é a menor superfície possível que ainda prova que o
processo está aceitando conexões, sem exigir client MCP completo dentro do
healthcheck.

**Alternatives considered**: Implementar um endpoint HTTP `/health`
dedicado no servidor MCP (fora do protocolo SSE) foi considerado — fora de
escopo desta feature (mudaria o contrato do servidor MCP, SPEC-007), e a
checagem TCP já é suficiente para o propósito de um healthcheck de
container.

## Resumo de dependências novas

Nenhuma dependência Python nova. Infraestrutura: `Dockerfile`,
`docker-compose.yml` estendido, `python:3.12-slim` (base já usada
implicitamente pela stack do projeto), imagens `pgvector/pgvector:pg16`/
`minio/minio` já em uso desde a SPEC-006.

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
