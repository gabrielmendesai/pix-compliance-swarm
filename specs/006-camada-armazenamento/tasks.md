---

description: "Task list template for feature implementation"
---

# Tasks: Camada de armazenamento (SPEC-006)

**Input**: Design documents from `/specs/006-camada-armazenamento/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/storage.md, quickstart.md

**Tests**: Incluídos e obrigatórios — o Princípio IX da constituição exige que os arquivos `tests/test_object_store.py` e `tests/test_vector_store.py` sejam escritos e confirmados como falhos antes de qualquer código de `ObjectStore`/`PgVectorStore` existir, derivados exclusivamente dos critérios de aceite do spec.md.

**Organization**: Tarefas agrupadas por user story do spec.md, permitindo implementação e teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: A qual user story esta tarefa pertence (US1, US2, US3)
- Caminhos de arquivo exatos incluídos em cada descrição

## Path Conventions

Projeto único: `src/pix_compliance/`, `tests/`, `migrations/`, `docker-compose.yml`, `docs/` na raiz do repositório (conforme `plan.md`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar dependências, serviços locais e schema versionado antes de qualquer código de storage

- [X] T001 Adicionar `psycopg[binary]` e `pgvector` às dependências de `pyproject.toml` (seção `[project.dependencies]`) — `boto3`/`botocore` já existem desde a SPEC-005
- [X] T002 [P] Adicionar os serviços `postgres` (imagem `pgvector/pgvector:pg16`, variáveis compatíveis com `POSTGRES_DSN` de `.env.example`) e `minio` (imagem `minio/minio`, compatível com `OBJECT_STORAGE_ENDPOINT`) a `docker-compose.yml` na raiz do repositório
- [X] T003 [P] Criar `migrations/0001_create_vector_store_schema.sql` com `CREATE EXTENSION IF NOT EXISTS vector`, a tabela de vetores (`id text primary key`, `embedding vector(512)`, `metadata jsonb`, `created_at timestamptz default now()`) e o índice `USING hnsw (embedding vector_cosine_ops)`, conforme `data-model.md`

**Checkpoint**: Dependências instaláveis, serviços locais definidos em `docker-compose.yml`, schema versionado pronto para ser aplicado.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contratos e infraestrutura que TODAS as user stories dependem

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase estar completa

- [X] T004 Adicionar o campo `embedding_dimension: int = 512` (constante de domínio, não lida de variável de ambiente, com comentário explicando que é a dimensão do Titan Text Embeddings V2 herdada da SPEC-005) a `Settings` em `src/pix_compliance/config.py`
- [X] T005 [P] Teste: `Settings().embedding_dimension == 512` em `tests/test_config.py`
- [X] T006 [P] Definir os modelos Pydantic `VectorRecord` (`id`, `embedding: list[float]`, `metadata`) e `SearchResult` (`id`, `score`, `metadata`) em `src/pix_compliance/vector_store.py`, conforme `data-model.md`
- [X] T007 [P] Definir a exceção `ObjectNotFoundError` em `src/pix_compliance/object_store.py` e a exceção `VectorDimensionError` em `src/pix_compliance/vector_store.py`, ambas com mensagem acionável (padrão de `ConfigurationError`/`BedrockProviderError`)
- [X] T008 Definir o `Protocol ObjectStore` (`upload(key: str, data: bytes) -> None`, `download(key: str) -> bytes`) em `src/pix_compliance/object_store.py`, com comentário explícito sobre por que é `Protocol` (segunda implementação real com S3, Princípio II)

**Checkpoint**: Contratos, exceções e schema versionado prontos; nenhuma implementação concreta de `ObjectStore`/`PgVectorStore` ainda.

---

## Phase 3: User Story 1 - Round-trip de arquivo binário no object store (Priority: P1) 🎯 MVP

**Goal**: Upload de bytes seguido de download retorna os mesmos bytes (hash idêntico), com a mesma classe servindo MinIO local e S3 real por configuração de `endpoint_url`

**Independent Test**: Upload de um blob de bytes conhecido, download em seguida, comparação de hash SHA-256 entre original e recuperado

### Tests for User Story 1 ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação (Princípio IX)

- [X] T009 [P] [US1] Teste: round-trip de bytes arbitrários via `upload`/`download`, hash SHA-256 idêntico ao original, em `tests/test_object_store.py`
- [X] T010 [P] [US1] Teste: `download` de uma chave inexistente levanta `ObjectNotFoundError`, em `tests/test_object_store.py`
- [X] T011 [US1] Rodar `docker compose up minio -d` e em seguida `pytest tests/test_object_store.py -q`, confirmando que os testes FALHAM por ausência de `S3ObjectStore` (nenhuma implementação ainda) — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ImportError: cannot import name 'S3ObjectStore'`

### Implementation for User Story 1

- [X] T012 [US1] Implementar `S3ObjectStore` (via `boto3.client("s3", endpoint_url=settings.object_storage_endpoint)`), com `upload`/`download` e `ObjectNotFoundError` no lugar do erro cru do `botocore`, em `src/pix_compliance/object_store.py` (depende de T007, T008)
- [X] T013 [US1] Rodar novamente `pytest tests/test_object_store.py -q` e confirmar que os testes de T009-T010 agora PASSAM — 2/2 passando contra MinIO real

**Checkpoint**: User Story 1 completa e testável de forma independente — round-trip do object store funciona contra MinIO real.

---

## Phase 4: User Story 2 - Round-trip vetorial com busca por similaridade (Priority: P1) 🎯 MVP

**Goal**: Upsert de vetores de dimensão 512 com metadados, busca por similaridade retornando o resultado esperado e respeitando filtro por metadados; dimensão incompatível é rejeitada antes de qualquer escrita

**Independent Test**: Upsert de 10 vetores de dimensão 512, busca por similaridade com vetor de consulta conhecido retorna o resultado esperado, filtro de metadados restringe corretamente os candidatos

### Tests for User Story 2 ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação (Princípio IX)

- [X] T014 [P] [US2] Teste: upsert de 10 `VectorRecord` de dimensão 512 com metadados distintos, `similarity_search` com vetor de consulta conhecido retorna o resultado mais similar esperado, em `tests/test_vector_store.py`
- [X] T015 [P] [US2] Teste: `similarity_search` com `metadata_filter` restringe corretamente os candidatos considerados, em `tests/test_vector_store.py`
- [X] T016 [P] [US2] Teste: `upsert` com vetor de dimensão diferente de 512 levanta `VectorDimensionError` antes de qualquer escrita (nenhuma linha inserida), em `tests/test_vector_store.py`
- [X] T017 [P] [US2] Teste: `similarity_search` com `metadata_filter` que não corresponde a nenhum vetor armazenado retorna lista vazia, em `tests/test_vector_store.py`
- [X] T018 [US2] Rodar `docker compose up postgres -d`, aplicar `psql "$POSTGRES_DSN" -f migrations/0001_create_vector_store_schema.sql`, e em seguida `pytest tests/test_vector_store.py -q`, confirmando que os testes FALHAM por ausência de `PgVectorStore` (nenhuma implementação ainda) — passo explícito do Princípio IX antes de iniciar a implementação. Confirmado: `ImportError: cannot import name 'PgVectorStore'`

### Implementation for User Story 2

- [X] T019 [US2] Implementar `PgVectorStore` (conexão via `psycopg` usando `settings.postgres_dsn`, adaptador `pgvector.psycopg` registrado), com `upsert` (validando `len(embedding) == settings.embedding_dimension` antes de qualquer escrita, levantando `VectorDimensionError` caso contrário) e `similarity_search` (distância de cosseno, filtro por `metadata` via `jsonb`), com comentário explícito sobre por que é classe concreta sem `Protocol` (única implementação, OpenSearch em prosa, Princípio II), em `src/pix_compliance/vector_store.py` (depende de T004, T006, T007) — vetores passados como `pgvector.Vector` (não lista crua) para que o adaptador `pgvector.psycopg` serialize corretamente o tipo `vector` nativo do Postgres
- [X] T020 [US2] Rodar novamente `pytest tests/test_vector_store.py -q` e confirmar que os testes de T014-T017 agora PASSAM — 4/4 passando contra Postgres/pgvector real

**Checkpoint**: User Story 2 completa e testável de forma independente — round-trip vetorial funciona contra Postgres/pgvector real.

---

## Phase 5: User Story 3 - Ambiente local sobe via Docker Compose e os testes passam contra ele (Priority: P2)

**Goal**: `docker compose up postgres minio` sobe os dois serviços do zero, e a suíte completa de armazenamento passa contra eles, sem nenhuma abstração órfã (classe abstrata/`Protocol` sem implementação concreta) no repositório

**Independent Test**: A partir de um estado limpo (`docker compose down -v`), rodar `docker compose up postgres minio` seguido da suíte de testes de armazenamento e confirmar que tudo passa

### Tests for User Story 3 ⚠️

- [X] T021 [P] [US3] Teste estático: nenhuma classe abstrata (`abc.ABC`) ou `Protocol` em `src/pix_compliance/` existe sem pelo menos uma implementação concreta correspondente no mesmo pacote (inspeção via `inspect`/`typing.get_type_hints` sobre os módulos de `src/pix_compliance/`), em `tests/test_no_orphan_abstractions.py`

### Implementation for User Story 3

- [X] T022 [US3] A partir de estado limpo (`docker compose down -v`), rodar `docker compose up postgres minio -d`, aplicar a migration (T003) e rodar `pytest tests/test_object_store.py tests/test_vector_store.py tests/test_no_orphan_abstractions.py -q`, confirmando que toda a suíte passa contra os serviços reais (SC-003, SC-004) — 8/8 passando

**Checkpoint**: Todas as user stories demonstráveis de ponta a ponta em ambiente reproduzível via Docker Compose.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentação e validação final que atravessa todas as user stories

- [X] T023 [P] Documentar ADR-01 (escolha de pgvector sobre OpenSearch Serverless, caminho de migração) em prosa em `docs/architecture.md`, conforme Escopo — fora do spec.md
- [X] T024 [P] Atualizar README com instruções de `docker compose up postgres minio` e aplicação da migration `0001_create_vector_store_schema.sql`
- [X] T025 [P] Rodar `ruff check src tests` e corrigir eventuais violações introduzidas por esta feature — 1 violação de line-length corrigida em `tests/test_no_orphan_abstractions.py`; limpo
- [X] T026 Rodar `pytest -q` como checagem final de regressão de toda a suíte do projeto (não apenas os testes desta feature) — 87/87 passando (precisou atualizar `REQUIRED_ENV` de `tests/test_llm_provider.py`/`tests/test_llm_provider_offline.py` com os novos campos `OBJECT_STORAGE_ACCESS_KEY`/`SECRET_KEY`/`BUCKET` exigidos por `Settings`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: Depende da Setup — BLOQUEIA todas as user stories
- **User Stories (Phase 3-5)**: Todas dependem da conclusão da Foundational
  - US1 e US2 (ambas P1) podem prosseguir em paralelo entre si — não têm dependência mútua (object store e vector store são módulos independentes)
  - US3 (P2) depende de US1 e US2 já implementadas (valida a suíte completa contra os serviços reais e a ausência de abstração órfã)
- **Polish (Phase 6)**: Depende de todas as user stories estarem completas

### User Story Dependencies

- **US1 (P1)**: Depende apenas da Foundational — nenhuma dependência de outra story
- **US2 (P1)**: Depende apenas da Foundational — independente de US1 (módulo e schema próprios)
- **US3 (P2)**: Depende da Foundational, de US1 e de US2 (valida a suíte inteira já implementada, de ponta a ponta)

### Within Each User Story

- Testes escritos e confirmados como FALHANDO (passo explícito, Princípio IX) antes da implementação correspondente
- Modelos/exceções/contratos (Foundational) antes das classes concretas
- Classe concreta implementada até os testes da story passarem

### Parallel Opportunities

- T002 e T003 (Setup) em paralelo — arquivos diferentes
- Dentro da Foundational: T005, T006, T007 em paralelo (arquivos/campos diferentes); T008 depende de T007 (mesma exceção referenciada no `Protocol`)
- Após a Foundational, US1 (Phase 3) e US2 (Phase 4) podem ser trabalhadas em paralelo por desenvolvedores diferentes
- Testes marcados [P] dentro de cada story rodam em paralelo entre si (mesmo arquivo, mas casos de teste independentes)

---

## Parallel Example: User Story 1

```bash
# Testes da User Story 1 em paralelo:
Task: "Teste round-trip upload/download com hash idêntico em tests/test_object_store.py"
Task: "Teste download de chave inexistente levanta ObjectNotFoundError em tests/test_object_store.py"
```

## Parallel Example: User Story 2

```bash
# Testes da User Story 2 em paralelo:
Task: "Teste upsert de 10 vetores + similarity_search retorna resultado esperado em tests/test_vector_store.py"
Task: "Teste similarity_search com metadata_filter restringe candidatos em tests/test_vector_store.py"
Task: "Teste upsert com dimensão incorreta levanta VectorDimensionError em tests/test_vector_store.py"
Task: "Teste similarity_search sem candidatos retorna lista vazia em tests/test_vector_store.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (CRÍTICO — bloqueia todas as stories)
3. Completar Phase 3: User Story 1 (round-trip object store)
4. Completar Phase 4: User Story 2 (round-trip vetorial)
5. **PARAR e VALIDAR**: rodar os Cenários 3 e 4 de `quickstart.md`
6. Este é o MVP real desta feature — as duas garantias P1 que sustentam toda persistência do enxame (arquivos e vetores)

### Incremental Delivery

1. Setup + Foundational → fundação pronta (schema versionado, contratos, exceções)
2. US1 + US2 → MVP (object store + vector store) → validar com `quickstart.md`
3. US3 → Docker Compose de ponta a ponta + ausência de abstração órfã → validar com Cenário 5/6 de `quickstart.md`
4. Polish → ADR-01, README, lint, regressão completa

---

## Notes

- [P] = arquivos diferentes ou casos de teste independentes, sem dependência bloqueante
- [Story] mapeia cada tarefa à user story correspondente do spec.md
- Testes devem ser escritos e confirmados como falhando antes da implementação correspondente (Princípio IX) — cada story inclui um passo explícito de execução e confirmação de falha antes da tarefa de implementação
- Commitar após cada tarefa ou grupo lógico de tarefas
- Parar em cada checkpoint para validar a story de forma independente
- Evitar: tarefas vagas, conflito de mesmo arquivo sem necessidade, dependências entre stories que quebrem a independência (US3 depende de US1/US2 por necessidade real de validação de ponta a ponta, não por acoplamento evitável)
