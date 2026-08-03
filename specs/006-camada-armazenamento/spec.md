# Feature Specification: Camada de armazenamento (SPEC-006)

**Feature Branch**: `006-camada-armazenamento`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Camada de armazenamento (SPEC-006) — object storage com abstração real (MinIO/S3 via Protocol) e vector store concreto (pgvector), sem interface especulativa, com dimensão de embedding travada em 512 (Titan Text Embeddings V2, herdada da SPEC-005)."

**Dependências**: SPEC-001 (config e logging) e SPEC-004 (guardrail — todo texto persistido deve ter atravessado `guard()` antes de chegar aqui, mas a responsabilidade de chamar o guardrail é de quem grava, não desta camada). Esta feature também herda uma decisão já tomada na SPEC-005: o modelo de embeddings escolhido é o **Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`), com dimensão de saída fixada em **512**. Essa dimensão precisa ser travada em `config.py` e usada na criação do schema do vector store — é o número que define a coluna de vetor da tabela.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são os
  demais agentes do enxame e os pipelines de ingestão/consulta, que precisam
  gravar e recuperar artefatos binários (object store) e vetores de embedding
  com metadados (vector store) de forma confiável e sem perda de fidelidade.
-->

### User Story 1 - Round-trip de arquivo binário no object store (Priority: P1)

Um agente ou pipeline de ingestão precisa gravar um arquivo (por exemplo, um PDF de normativo ou um documento fictício) no object store e, mais tarde, recuperá-lo integralmente, sem qualquer corrupção ou alteração de bytes.

**Why this priority**: É a garantia central desta metade da spec — sem round-trip íntegro, nenhum consumidor posterior (indexação, auditoria, exibição) pode confiar no armazenamento.

**Independent Test**: Pode ser testado isoladamente fazendo upload de um blob de bytes conhecido, fazendo o download em seguida, e comparando o hash (por exemplo, SHA-256) do conteúdo original com o do conteúdo recuperado.

**Acceptance Scenarios**:

1. **Given** um blob de bytes arbitrário, **When** ele é enviado via `ObjectStore.upload` e depois recuperado via `ObjectStore.download`, **Then** o hash do conteúdo recuperado é idêntico ao hash do conteúdo original.
2. **Given** o mesmo `ObjectStore`, **When** a variável de ambiente `endpoint_url` aponta para MinIO local em vez de S3 real, **Then** a mesma implementação concreta funciona sem alteração de código, apenas de configuração.

---

### User Story 2 - Round-trip vetorial com busca por similaridade (Priority: P1)

Um agente de indexação precisa gravar vetores de embedding (dimensão 512, gerados pelo Titan Text Embeddings V2) com metadados associados, e um agente de consulta precisa recuperar os vetores mais similares a uma consulta, opcionalmente filtrando por metadados.

**Why this priority**: Empatada com a User Story 1 — é a outra metade da garantia estrutural desta feature (persistência íntegra), e sem ela nenhum agente de busca semântica do enxame tem onde consultar.

**Independent Test**: Pode ser testado isoladamente fazendo upsert de 10 vetores de dimensão 512 com metadados distintos, executando uma busca por similaridade com um vetor de consulta conhecido, e verificando que o resultado esperado (o vetor mais próximo, dado o conjunto de teste) é retornado, com o filtro de metadados restringindo corretamente o conjunto de candidatos.

**Acceptance Scenarios**:

1. **Given** 10 vetores de dimensão 512 inseridos via `PgVectorStore.upsert`, **When** `PgVectorStore.similarity_search` é chamado com um vetor de consulta conhecido, **Then** o resultado esperado (mais similar) é retornado corretamente.
2. **Given** o mesmo conjunto de vetores com metadados distintos, **When** a busca é feita com um filtro de metadados, **Then** apenas vetores que satisfazem o filtro são considerados candidatos ao resultado.
3. **Given** um vetor com dimensão diferente de 512, **When** `PgVectorStore.upsert` é chamado, **Then** o sistema rejeita a operação antes de qualquer escrita, com uma mensagem clara sobre a incompatibilidade de dimensão.

---

### User Story 3 - Ambiente local sobe via Docker Compose e os testes passam contra ele (Priority: P2)

Um desenvolvedor ou avaliador do projeto precisa subir os serviços de armazenamento localmente com um único comando e confirmar que a suíte de testes de armazenamento passa contra esses serviços reais, não contra mocks.

**Why this priority**: Depende das User Stories 1 e 2 já existirem como código; é a demonstração de que a integração funciona de ponta a ponta em ambiente reproduzível, não um pré-requisito para a lógica em si.

**Independent Test**: Pode ser testado isoladamente rodando `docker compose up postgres minio` e, em seguida, a suíte de testes de object store e vector store, verificando que ambos os serviços sobem e os testes passam contra eles.

**Acceptance Scenarios**:

1. **Given** o `docker-compose.yml` do projeto, **When** `docker compose up postgres minio` é executado, **Then** os dois serviços sobem e ficam prontos para aceitar conexões.
2. **Given** os serviços em execução, **When** os testes de round-trip (User Stories 1 e 2) são executados contra eles, **Then** todos passam sem necessidade de mock adicional.

---

### Edge Cases

- O que acontece se o schema do pgvector ainda não existir quando a aplicação tenta gravar? A criação do schema MUST ocorrer via migration SQL versionada, aplicada antes de qualquer escrita — a feature não cria schema implicitamente em tempo de execução.
- Como o sistema trata uma tentativa de `similarity_search` com filtro de metadados que não corresponde a nenhum vetor armazenado? MUST retornar lista vazia, não erro.
- O que acontece se `ObjectStore.download` for chamado para uma chave inexistente? MUST levantar uma exceção própria e legível, não propagar o erro cru do cliente `boto3`.
- Como o sistema garante que a dimensão do embedding não diverge silenciosamente entre o que o provider gera e o que a tabela espera? A dimensão (512) MUST estar centralizada em `config.py` e ser usada tanto na criação do schema quanto em uma validação explícita de tamanho de vetor antes de qualquer `upsert`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer `ObjectStore` como `Protocol`, com uma implementação concreta via `boto3` apontando para MinIO usando `endpoint_url` configurável, capaz de servir S3 real apenas trocando variável de ambiente.
- **FR-002**: O sistema MUST fornecer os métodos `upload` (bytes) e `download` (retornando os mesmos bytes) no `ObjectStore`, com integridade byte-a-byte garantida entre upload e download.
- **FR-003**: O sistema MUST fornecer `PgVectorStore` como classe concreta, sem `Protocol` ou interface, dado que existe apenas uma implementação de vector store neste projeto.
- **FR-004**: O sistema MUST definir o schema de tabela do pgvector com coluna de vetor na dimensão 512, criada por migration SQL versionada.
- **FR-005**: O sistema MUST criar um índice HNSW ou IVFFlat sobre a coluna de vetor para suportar busca por similaridade eficiente.
- **FR-006**: O sistema MUST fornecer o método `PgVectorStore.upsert`, aceitando vetor, metadados e identificador, validando a dimensão do vetor (512) antes de qualquer escrita.
- **FR-007**: O sistema MUST fornecer o método `PgVectorStore.similarity_search`, aceitando um vetor de consulta e um filtro opcional por metadados, retornando os resultados mais similares.
- **FR-008**: O sistema MUST centralizar a dimensão do embedding (512) em `config.py`, reutilizada tanto na criação do schema quanto na validação de tamanho de vetor no `upsert`.
- **FR-009**: O sistema MUST NOT criar qualquer abstração, protocolo ou stub de código para OpenSearch ou qualquer outro backend de vector store alternativo — a alternativa é documentada apenas em prosa em `docs/architecture.md` (ADR-01).
- **FR-010**: O sistema MUST NOT implementar provisionamento AWS real ou replicação de dados — ambos fora de escopo desta feature.
- **FR-011**: Após esta feature, o repositório MUST NOT conter nenhuma classe abstrata ou `Protocol` sem pelo menos uma implementação concreta correspondente.

### Key Entities *(include if feature involves data)*

- **ObjectStore**: `Protocol` para armazenamento de objetos binários, com implementação concreta via `boto3`/MinIO (compatível com S3 real por configuração de `endpoint_url`). Métodos: `upload`, `download`.
- **PgVectorStore**: Classe concreta (sem interface) para armazenamento e busca de vetores de embedding sobre PostgreSQL/pgvector. Métodos: `upsert`, `similarity_search`. Dimensão de vetor fixada em 512, herdada da SPEC-005.
- **Migration SQL**: Arquivo versionado responsável por criar o schema da tabela de vetores (coluna de dimensão 512 e índice HNSW/IVFFlat) antes de qualquer escrita da aplicação.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável: todo critério de aceite é um comando executável,
  não um julgamento subjetivo) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato).
-->

### Measurable Outcomes

- **SC-001**: Teste de round-trip no object store: upload de bytes, download, hash idêntico ao original.
- **SC-002**: Teste de round-trip vetorial: upsert de 10 vetores de dimensão 512, busca por similaridade retorna o resultado esperado.
- **SC-003**: `docker compose up postgres minio` sobe os dois serviços, e os testes acima passam contra eles.
- **SC-004**: Nenhuma classe abstrata ou protocolo sem implementação concreta existe no repositório após esta feature.

## Assumptions

- A dimensão de 512 é uma decisão já tomada na SPEC-005 (Titan Text Embeddings V2, `amazon.titan-embed-text-v2:0`) e não é reaberta nesta spec — esta feature apenas a consome e a trava em `config.py` e no schema do pgvector.
- A responsabilidade de invocar `guard()` (SPEC-004) sobre qualquer texto antes de persisti-lo é de quem grava, não desta camada; esta spec assume que os dados que chegam ao `ObjectStore`/`PgVectorStore` já passaram por essa checagem.
- `ObjectStore` é `Protocol` porque há, de fato, uma segunda implementação real (S3) além do MinIO local, trocável apenas por `endpoint_url` — um seam real, não hipotético (Princípio II da constituição). `PgVectorStore` é classe concreta porque este projeto implementa apenas uma opção de índice vetorial; a alternativa (OpenSearch Serverless) fica documentada em prosa em `docs/architecture.md`, nunca como stub de código morto.
- Migrations são simples e versionadas em SQL puro, sem uso de uma ferramenta de migration adicional além do necessário para criar e versionar o schema do pgvector.
- Conforme o Princípio IX da constituição, os arquivos `tests/test_object_store.py` e `tests/test_vector_store.py` devem ser escritos e revisados antes de qualquer código de `ObjectStore` ou `PgVectorStore`, derivados exclusivamente dos critérios de aceite desta spec — nunca escritos olhando para uma implementação já pronta. Ao gerar `tasks.md`, as tarefas de teste de cada user story devem preceder as tarefas de implementação correspondentes, incluindo um passo explícito de rodar os testes e confirmar que falham antes de a implementação começar.
- Identificadores de código são em inglês; comentários e docstrings em português. O código do `ObjectStore` deve comentar explicitamente por que é `Protocol` (segunda implementação real com S3), e o `PgVectorStore` deve comentar explicitamente por que é classe concreta sem interface (única implementação neste projeto, OpenSearch documentado apenas em prosa) — tornando visível, no próprio código, a aplicação do Princípio II da constituição.
