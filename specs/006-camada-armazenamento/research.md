# Research: Camada de armazenamento (SPEC-006)

## 1. Cliente object store (MinIO/S3)

**Decision**: Usar `boto3.client("s3", endpoint_url=settings.object_storage_endpoint)`
dentro de `S3ObjectStore`, a implementação concreta do `Protocol ObjectStore`.

**Rationale**: `boto3` já é dependência do projeto (usada para `bedrock-runtime`
na SPEC-005) e seu cliente `s3` fala o mesmo protocolo tanto com MinIO
(`endpoint_url` apontando para o container local, ex. `http://localhost:9000`)
quanto com S3 real (bastando omitir/trocar `endpoint_url` para o endpoint AWS
padrão) — é exatamente o seam que justifica `ObjectStore` ser `Protocol`
(Princípio II): a mesma classe concreta serve os dois backends por
configuração, não por uma segunda implementação de código.

**Alternatives considered**: Um SDK dedicado do MinIO (`minio-py`) foi
descartado — introduziria uma dependência adicional para um cliente que fala
uma API distinta da AWS, quebrando exatamente o seam (mesma classe para MinIO
e S3) que é o objetivo desta spec.

## 2. Driver Postgres e tipo de vetor

**Decision**: Usar `psycopg` (v3) como driver, com a extensão `pgvector` do
lado do banco (`CREATE EXTENSION vector`) e o adaptador Python
`pgvector.psycopg` para (de)serializar `list[float]` na coluna `vector(512)`
sem conversão manual de tipo.

**Rationale**: `psycopg` v3 é o driver Postgres síncrono padrão atual em
Python, com suporte nativo a adaptadores de tipo (`register_vector`) — o
pacote `pgvector` oficial fornece esse adaptador pronto, evitando serializar
o vetor manualmente como string/array antes de cada query (fonte comum de
bugs sutis de formatação).

**Alternatives considered**: `asyncpg` foi descartado por introduzir um
runtime assíncrono só para esta camada, quando o restante do enxame (agentes
Pydantic AI síncronos por spec) não exige I/O concorrente aqui — contrariaria
o Princípio III (KISS): não segmentar/complicar por uma capacidade não usada
em nenhum outro ponto do projeto.

## 3. Tipo de índice vetorial (HNSW vs. IVFFlat)

**Decision**: Usar índice **HNSW** (`USING hnsw (embedding vector_cosine_ops)`)
na migration de criação do schema.

**Rationale**: HNSW é a recomendação atual do próprio projeto `pgvector` para
a maioria dos casos — não exige um passo de treinamento prévio sobre dados já
carregados (diferente do IVFFlat, cuja qualidade depende do número de listas
escolhido em função do volume de linhas no momento da criação do índice, algo
que não se conhece de antemão neste projeto de escala pequena/fictícia).
Distância de cosseno (`vector_cosine_ops`) é a métrica padrão para embeddings
de texto do Titan.

**Alternatives considered**: IVFFlat foi considerado e descartado para este
projeto — exigiria escolher um número de `lists` calibrado ao volume de dados,
decisão sem base empírica no escopo de um desafio técnico de poucos dias; a
spec já permite HNSW **ou** IVFFlat (FR-005), e HNSW é a opção sem esse
parâmetro sensível a acertar.

## 4. Migrations simples em SQL versionado

**Decision**: Um único arquivo `migrations/0001_create_vector_store_schema.sql`,
aplicado manualmente (via `psql` ou script simples) contra o Postgres antes de
qualquer escrita da aplicação — sem uma ferramenta de migration (Alembic,
Flyway) além do necessário.

**Rationale**: O escopo desta feature é a criação de um único schema, uma
única vez; introduzir uma ferramenta de migration completa para uma única
migration violaria o Princípio II (YAGNI) — não há uma segunda migration
prevista nesta spec, nem histórico de mudanças de schema a versionar em
sequência que justifique o ferramental.

**Alternatives considered**: Alembic foi considerado (é o padrão de mercado
para projetos SQLAlchemy) e descartado — o projeto não usa um ORM
(`PgVectorStore` fala SQL diretamente via `psycopg`), e Alembic sem um ORM
subjacente adicionaria configuração (`env.py`, diretório `versions/`) sem
ganho real sobre um arquivo `.sql` versionado no controle de versão do próprio
repositório.

## 5. Validação de hash no round-trip do object store

**Decision**: Usar `hashlib.sha256` sobre os bytes originais e sobre os bytes
recuperados no teste de round-trip (`test_object_store.py`), comparando os
dois digests.

**Rationale**: SHA-256 é suficiente para detectar qualquer corrupção de bytes
no ciclo upload/download; é biblioteca padrão do Python, sem dependência
adicional.

**Alternatives considered**: Comparação byte-a-byte direta (`==` entre os dois
`bytes`) foi considerada e é equivalente em corretude — o teste usa hash por
ser o padrão explicitamente citado no critério de aceite (SC-001) da spec, e
por deixar a asserção legível como "integridade", não como coincidência de
igualdade.

## 6. Imagem Docker para Postgres com pgvector

**Decision**: Usar a imagem `pgvector/pgvector:pg16` no `docker-compose.yml`
para o serviço `postgres`, e `minio/minio` para o serviço `minio`.

**Rationale**: `pgvector/pgvector` é a imagem oficial mantida pelo projeto
`pgvector`, já com a extensão compilada — evita instalar a extensão
manualmente em uma imagem `postgres` genérica. `minio/minio` é a imagem
oficial do MinIO, já usada implicitamente pelo `OBJECT_STORAGE_ENDPOINT`
documentado em `.env.example` desde a SPEC-001.

**Alternatives considered**: Rodar Postgres genérico e instalar `pgvector` via
script de inicialização foi descartado — a imagem oficial já resolve isso de
forma mais simples e reprodutível (Princípio III).

## Resumo de dependências novas

| Pacote | Uso | Justificativa |
|---|---|---|
| `psycopg[binary]` | Driver Postgres para `PgVectorStore` | Driver síncrono padrão atual, compatível com o restante do enxame (síncrono) |
| `pgvector` | Adaptador Python do tipo `vector` para `psycopg` | Pacote oficial do projeto pgvector, evita serialização manual |

`boto3`/`botocore` já são dependências existentes (SPEC-005) e são
reaproveitadas para o cliente `s3` do `ObjectStore` — nenhuma dependência nova
necessária para o object store.

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
