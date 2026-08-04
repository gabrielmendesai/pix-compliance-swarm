# Implementation Plan: Conteinerização (SPEC-016)

**Branch**: `016-containerization` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-containerization/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Um único `Dockerfile` multi-stage na raiz do projeto, com um estágio
`builder` compartilhado (instala dependências) e três estágios finais
(`api`, `mcp-scraper`, `scheduler`), cada um rodando como usuário não-root
— evita triplicar a lógica de instalação de dependências em três
Dockerfiles separados (Princípio III). `docker-compose.yml` ganha os
serviços `api`, `mcp-scraper`, `scheduler`, `mock-bcb` (além de
`postgres`/`minio` já existentes), com healthchecks em todo serviço do
qual outro depende, e `depends_on: condition: service_healthy`. Um serviço
`bootstrap` de execução única (não um script rodado manualmente) cria o
bucket do object storage e aplica a migration do pgvector antes de
`api`/`scheduler` subirem (`depends_on: condition:
service_completed_successfully`). `orchestrator_agent.py` ganha um modo de
execução contínua (`--daemon`) para o container `scheduler` não terminar
logo após o primeiro disparo, e um sinalizador para desabilitar o
bootstrap efêmero de mock BCB/MCP em processo (SPEC-015) quando os
serviços `mock-bcb`/`mcp-scraper` já existem como containers próprios. Um
script de verificação (`scripts/verify_containerization.sh`) serve como o
"teste" desta feature (Princípio IX adaptado a infraestrutura declarativa).

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto);
Docker/Docker Compose (Compose v2, sintaxe `docker compose`)

**Primary Dependencies**: Nenhuma dependência Python nova — reaproveita
`boto3`/`psycopg` (já declarados) no script de bootstrap; `pgvector/
pgvector:pg16` e `minio/minio` (imagens já usadas em `docker-compose.yml`,
SPEC-006); `python:3.12-slim` como base das imagens da aplicação e do
serviço `mock-bcb` (sem Dockerfile próprio — usa a imagem oficial
diretamente com `command`/volume, servindo `mock_bcb/` via `http.server`
da stdlib, mesmo mecanismo já usado em `tests/conftest.py`)

**Storage**: Volumes Docker nomeados para `postgres`/`minio` (persistência
entre reinícios de container, removidos deliberadamente por `down -v`) —
nenhuma mudança de schema.

**Testing**: `scripts/verify_containerization.sh` — sobe o compose, faz
polling do status de saúde de cada serviço (`docker inspect --format
'{{.State.Health.Status}}'`), confere `GET /docs` no host e um handshake
SSE contra `mcp-scraper`, e roda o ciclo `down -v && up -d` para confirmar
reprodutibilidade — escrito e confirmado como falho (nada construído
ainda) antes de qualquer Dockerfile/compose existir (Princípio IX).

**Target Platform**: Linux containers (Docker Compose), mesmo alvo já
declarado no restante do projeto.

**Project Type**: Single project — acréscimos de infraestrutura
(`Dockerfile`, `docker-compose.yml` estendido, `scripts/`), sem pacote
Python novo.

**Performance Goals**: Rebuild de uma mudança trivial de código não deve
re-executar a instalação de dependências (FR-010) — resolvido via ordem de
`COPY` (manifesto de dependências antes do código-fonte) combinada com
cache mount do BuildKit para o cache do `pip` (research.md, Decisão 2).

**Constraints**: Toda imagem final MUST rodar como usuário não-root
(FR-001); todo serviço do qual outro depende MUST ter healthcheck, com
`depends_on: condition: service_healthy` (FR-003); o bootstrap MUST ser
idempotente (Edge Case de spec.md); nenhum nome de bucket hardcoded
(FR-005).

**Scale/Scope**: Um `Dockerfile` (3 estágios finais), extensão de
`docker-compose.yml` (4 serviços novos: `api`, `mcp-scraper`, `scheduler`,
`mock-bcb`, mais 1 serviço de bootstrap de execução única), um script de
bootstrap, um script de verificação, um `.dockerignore`, uma pequena
extensão de `orchestrator_agent.py` (modo daemon + flag de bootstrap
efêmero opcional).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  N/A direto: esta feature é infraestrutura de deploy, não toca a lógica
  de dispatch de provider (já correta nas features anteriores).
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS.
  `mock-bcb` não ganha um Dockerfile próprio — usa a imagem
  `python:3.12-slim` oficial diretamente com `command`, porque servir um
  diretório estático via `http.server` não justifica uma imagem custom
  (Princípio III/II).
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS. Um
  único `Dockerfile` multi-stage com três estágios finais (não três
  arquivos `Dockerfile.api`/`Dockerfile.mcp`/`Dockerfile.scheduler`
  duplicando o estágio `builder`) — a mesma instalação de dependências
  serve os três serviços da aplicação.
- **Princípio IV (Responsabilidade única por agente / SRP)** — N/A direto:
  esta feature não introduz nem altera agentes — apenas os empacota para
  deploy.
- **Princípio V (Guardrail é ponto único e obrigatório)** — N/A direto:
  nenhum texto novo trafega para um LLM nesta feature.
- **Princípio VI (Contrato antes de comportamento)** — N/A direto:
  nenhum modelo Pydantic novo ou alterado — a pequena extensão de
  `orchestrator_agent.py` (modo daemon, flag de bootstrap efêmero) é
  parâmetro de função/CLI, não um contrato de dados.
- **Princípio VII (Comentários e nomenclatura)** — PASS. Nomes de serviço
  em inglês (`api`, `mcp-scraper`, `scheduler`, `bootstrap`, `mock-bcb`);
  comentários em português explicando por que multi-stage, por que
  usuário não-root, por que o bootstrap é seguro rodar mais de uma vez.
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS.
  `scripts/verify_containerization.sh` roda e confirma os critérios de
  aceite como comandos executáveis, não julgamento subjetivo.
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, adaptado à natureza desta feature
  (spec.md, Assumptions): `scripts/verify_containerization.sh` é escrito e
  confirmado como falho antes de qualquer Dockerfile/compose existir.

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` confirma que nenhum modelo
Pydantic novo é introduzido — apenas a topologia de serviços do compose e
o contrato do script de bootstrap. `contracts/` confirma que a extensão de
`orchestrator_agent.py` é aditiva (novos parâmetros opcionais, nenhuma
assinatura existente quebrada). Gates permanecem PASS.

## Project Structure

### Documentation (this feature)

```text
specs/016-containerization/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
Dockerfile                              # NOVO — estágio builder + 3 estágios finais (api, mcp-scraper, scheduler)
.dockerignore                           # NOVO
docker-compose.yml                       # ESTENDIDO — + api, mcp-scraper, scheduler, mock-bcb, bootstrap

scripts/
├── bootstrap.py                          # NOVO — cria bucket (idempotente) + aplica migration do pgvector (idempotente)
└── verify_containerization.sh             # NOVO — "teste" desta feature (Princípio IX adaptado)

src/pix_compliance/agents/
└── orchestrator_agent.py                 # ESTENDIDO — modo --daemon (start_scheduler contínuo) e flag de bootstrap efêmero opcional (aditivo, sem quebrar SPEC-015)

Makefile                                  # `up`/`down` deixam de ser placeholders (SPEC-001), passam a chamar docker compose de fato
```

**Structure Decision**: Projeto único (Option 1). Nenhum pacote Python
novo — apenas infraestrutura de deploy na raiz do repositório
(`Dockerfile`, `docker-compose.yml`, `scripts/`) e uma extensão pequena e
aditiva de `orchestrator_agent.py` (SPEC-015) para suportar execução como
container de longa duração. `scripts/bootstrap.py` reaproveita
`S3ObjectStore`/`psycopg` já existentes — não introduz uma segunda forma
de criar bucket ou aplicar migration.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| N/A | N/A | Nenhuma violação identificada nesta feature. |
