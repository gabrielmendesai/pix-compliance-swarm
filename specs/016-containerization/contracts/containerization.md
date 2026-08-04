# Contrato: `Dockerfile` / `docker-compose.yml` / `scripts/` (SPEC-016)

Esta feature não expõe uma API/CLI de aplicação — o "contrato" é a
interface de infraestrutura: os comandos que um operador roda, e o que
cada um garante.

## `Dockerfile` — estágios

```dockerfile
# builder: instala dependências (cache mount do pip), compartilhado pelos 3 estágios finais
FROM python:3.12-slim AS builder
...

# api, mcp-scraper, scheduler: cada um copia apenas o necessário do builder,
# roda como usuário não-root, entrypoint específico do serviço
FROM python:3.12-slim AS api
...
FROM python:3.12-slim AS mcp-scraper
...
FROM python:3.12-slim AS scheduler
...
```

**Pós-condição**: nenhum estágio final contém ferramentas de build
(compiladores, `pip` de dependências de desenvolvimento) — apenas o
runtime Python e o pacote já instalado (FR-010).

## `docker-compose.yml` — comportamento

```bash
docker compose up -d
```

**Pós-condição**: todos os serviços (`postgres`, `minio`, `mock-bcb`,
`bootstrap`, `mcp-scraper`, `api`, `scheduler`) ficam com
`docker inspect --format '{{.State.Health.Status}}'` igual a `healthy`
(exceto `bootstrap`, que termina com status `exited (0)`), sem nenhum
comando manual além deste (SC-001).

```bash
docker compose down -v && docker compose up -d
```

**Pós-condição**: mesmo resultado do comando anterior — o serviço
`bootstrap` recria o bucket e reaplica a migration automaticamente, sem
intervenção manual (SC-003).

## `scripts/bootstrap.py` — ver data-model.md

## `scripts/verify_containerization.sh`

```bash
scripts/verify_containerization.sh
```

**Comportamento**: sobe o compose (`docker compose up -d`), faz polling
(com timeout) do status de saúde de cada serviço, confere `GET /docs` a
partir do host, confere que `mcp-scraper` aceita conexão TCP na porta
configurada, e roda o ciclo `down -v && up -d` para confirmar
reprodutibilidade — sai com código 0 apenas se todos os critérios de
aceite (SC-001 a SC-003) forem satisfeitos.

## Extensão de `orchestrator_agent.py`

```bash
python -m pix_compliance.agents.orchestrator_agent --daemon
```

**Comportamento**: chama `start_scheduler(settings)` e mantém o processo
vivo — usado pelo `command` do serviço `scheduler` no compose. Sem a flag,
comportamento inalterado em relação à SPEC-015 (execução única, imprime
`PipelineResult`, termina).

## Cenários de contrato cobertos pelo script de verificação (ver quickstart.md)

1. `docker compose up -d` a partir de um checkout limpo deixa todos os
   serviços saudáveis (SC-001).
2. `GET /docs` responde no host; `mcp-scraper` aceita handshake (SC-002).
3. `docker compose down -v && docker compose up -d` reproduz o mesmo
   estado funcional, incluindo bucket/migration recriados automaticamente
   (SC-003).
4. Rebuild após mudança trivial de código não reinstala dependências do
   zero (SC-004, verificado via inspeção do log de build, não parte do
   script de verificação automatizado — documentado em quickstart.md como
   validação manual).
