# Implementation Plan: Camada de armazenamento (SPEC-006)

**Branch**: `006-camada-armazenamento` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-camada-armazenamento/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Fornecer duas primitivas de persistência para o enxame: `ObjectStore`, um
`Protocol` com implementação concreta via `boto3` apontando para MinIO/S3
(seam real — mesma classe serve os dois backends trocando `endpoint_url`), e
`PgVectorStore`, uma classe concreta sobre PostgreSQL/pgvector (sem interface,
única implementação de vector store neste projeto), com schema criado por
migration SQL versionada. A dimensão do vetor (512, herdada da SPEC-005 —
Titan Text Embeddings V2) é centralizada em `config.py` e reutilizada tanto na
criação da coluna quanto na validação de tamanho antes de qualquer `upsert`.
Testes de round-trip (bytes e vetores) escritos antes da implementação
(Princípio IX), validados contra os serviços reais subidos via
`docker compose up postgres minio`.

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `boto3`/`botocore` (cliente S3, reaproveitado da
SPEC-005 para o cliente `bedrock-runtime`), `psycopg` (driver PostgreSQL),
`pgvector` (extensão + tipo Python `pgvector.psycopg` para (de)serializar a
coluna de vetor), `pydantic` v2 (contratos de metadados/resultado de busca),
`structlog` (log estruturado, já estabelecido em SPEC-001)

**Storage**: PostgreSQL 16+ com extensão `pgvector` (vector store) e um bucket
S3-compatível via MinIO local / AWS S3 real (object store) — ambos já
referenciados em `.env.example` (`POSTGRES_DSN`, `OBJECT_STORAGE_ENDPOINT`)
desde a fundação do projeto (SPEC-001)

**Testing**: pytest, rodando os testes de round-trip contra os serviços reais
(`postgres`, `minio`) subidos via `docker compose up postgres minio` — sem
mock do `boto3`/driver Postgres, dado que o critério de aceite (SC-003) exige
passar contra os serviços de fato

**Target Platform**: Linux server (container Docker Compose, mesmo alvo do
restante do projeto)

**Project Type**: Single project (biblioteca Python consumida pelos agentes
do enxame) — mesma estrutura de `src/pix_compliance/` já estabelecida

**Performance Goals**: Sem meta de throughput própria desta feature (o enxame
roda em lote); a busca por similaridade usa índice HNSW ou IVFFlat para não
degradar para varredura sequencial conforme o volume de vetores cresce

**Constraints**: Nunca criar schema implicitamente em tempo de execução
(apenas via migration SQL versionada); nunca aceitar `upsert` com vetor de
dimensão diferente de 512 (validado contra o valor centralizado em
`config.py`); nunca introduzir `Protocol`/abstração para o vector store
(Princípio II — única implementação real)

**Scale/Scope**: Duas classes de armazenamento (`ObjectStore`,
`PgVectorStore`), uma migration SQL, dois arquivos de teste de round-trip

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  N/A nesta spec: esta feature não invoca LLM/provider, apenas persiste dados
  já produzidos por quem chama (incluindo embeddings gerados via SPEC-005).
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS,
  é o próprio objetivo estrutural da spec. `ObjectStore` é `Protocol` porque
  há uma segunda implementação real (S3), trocável por `endpoint_url` — seam
  real. `PgVectorStore` é classe concreta, sem interface, porque há apenas uma
  implementação de vector store neste projeto; a alternativa (OpenSearch
  Serverless) fica documentada em prosa em `docs/architecture.md` (ADR-01),
  nunca como stub de código morto (FR-009).
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS. Object
  store e vector store são dois módulos separados (`object_store.py`,
  `vector_store.py`) porque cada um tem volume de responsabilidade próprio
  (cliente, validação, schema) que justifica a separação — não são unidas em
  um módulo `storage.py` genérico, o que misturaria dois contratos e dois
  ciclos de vida distintos.
- **Princípio IV (Responsabilidade única por agente / SRP)** — N/A nesta
  spec: não há agente do enxame definido aqui, apenas infraestrutura de
  persistência consumida por specs futuras de agentes.
- **Princípio V (Guardrail é ponto único e obrigatório)** — PASS, com
  responsabilidade explicitamente fora desta camada: `guard()` (SPEC-004) é
  invocado por quem grava, não reimplementado aqui (Edge Cases da spec).
  `ObjectStore`/`PgVectorStore` persistem o que recebem, sem duplicar
  detecção/mascaramento de PII.
- **Princípio VI (Contrato antes de comportamento)** — PASS. Os modelos
  Pydantic de metadados e resultado de busca, e o schema SQL da tabela de
  vetores, são definidos na Fase 1 (`data-model.md`) antes de qualquer lógica
  de `upsert`/`similarity_search`.
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês (`ObjectStore`, `PgVectorStore`, `upsert`, `similarity_search`);
  comentários/docstrings em português explicando o porquê — em particular,
  comentário explícito no `ObjectStore` sobre por que é `Protocol` (segunda
  implementação real com S3) e no `PgVectorStore` sobre por que é classe
  concreta sem interface (única implementação, OpenSearch em prosa), conforme
  exigido nas Assumptions da spec.
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. Todos
  os critérios de aceite são comandos executáveis (testes de round-trip,
  `docker compose up postgres minio`, verificação de ausência de abstração
  órfã no repositório).
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, é requisito explícito da spec.
  `tests/test_object_store.py` e `tests/test_vector_store.py` são escritos e
  confirmados como falhos antes de `object_store.py`/`vector_store.py`
  existirem; `tasks.md` (Fase 2) ordena a tarefa de teste antes da tarefa de
  implementação em cada user story, com um passo explícito de rodar os testes
  e confirmar a falha antes de a implementação começar.

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` e `contracts/storage.md` confirmam
que apenas `ObjectStore` é `Protocol` (com implementação `S3ObjectStore` via
`boto3`/MinIO), e que `PgVectorStore` permanece classe concreta sem interface,
com dimensão de vetor (512) centralizada em `Settings.embedding_dimension` e
validada em `upsert` antes de qualquer escrita. Nenhuma abstração adicional
(ex. `Protocol` genérico de "storage" cobrindo os dois) foi introduzida — os
dois módulos permanecem desacoplados. Gates permanecem PASS sem alteração.

## Project Structure

### Documentation (this feature)

```text
specs/006-camada-armazenamento/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/pix_compliance/
├── config.py                  # já existe (SPEC-001) — ADICIONA Settings.embedding_dimension (512, travado)
├── object_store.py            # NOVO — Protocol ObjectStore + S3ObjectStore (boto3, endpoint_url configurável)
├── vector_store.py            # NOVO — PgVectorStore (classe concreta): upsert, similarity_search
└── logging.py                  # já existe (SPEC-001)

migrations/
└── 0001_create_vector_store_schema.sql  # NOVO — schema versionado: tabela + coluna vector(512) + índice HNSW/IVFFlat

docs/
└── architecture.md            # NOVO ou ATUALIZADO — ADR-01: escolha de pgvector sobre OpenSearch Serverless (prosa, não código)

docker-compose.yml              # NOVO ou ATUALIZADO — serviços postgres (com pgvector) e minio

tests/
├── test_object_store.py        # NOVO — escrito e confirmado falho ANTES de object_store.py (Princípio IX)
└── test_vector_store.py        # NOVO — escrito e confirmado falho ANTES de vector_store.py (Princípio IX)
```

**Structure Decision**: Projeto único (Option 1), reaproveitando o layout já
estabelecido em `src/pix_compliance/` (SPEC-001 a SPEC-005). `object_store.py`
e `vector_store.py` são módulos separados por terem volume de responsabilidade
e ciclo de vida próprios (cliente S3 vs. conexão Postgres, schema próprio) —
não se junta os dois em um único módulo `storage.py` (Princípio III aplicado
no sentido correto: separar quando o volume justifica, não segmentar por
segmentar). A migration SQL vive em `migrations/`, fora de `src/`, versionada
e aplicada explicitamente antes de qualquer escrita da aplicação — nunca
criada implicitamente em runtime. `docker-compose.yml` ganha os serviços
`postgres` (imagem com extensão pgvector) e `minio`, necessários para o
critério de aceite SC-003.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | Nenhuma violação identificada nesta feature. |
