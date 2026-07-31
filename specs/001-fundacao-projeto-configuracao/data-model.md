# Data Model: Fundação do projeto e configuração (SPEC-001)

Esta spec introduz uma única entidade de configuração — não há modelos de domínio
(esses são congelados na SPEC-002). `Settings` não é um modelo de negócio; é a
representação tipada do ambiente de execução.

## Settings

Classe concreta (`pydantic_settings.BaseSettings`), sem protocolo — conforme
Princípio II, não há segunda implementação nem teste que exija substituí-la por
outra classe (testes injetam variáveis de ambiente diferentes, não uma classe
diferente).

`model_config = SettingsConfigDict(extra="forbid", env_file=".env")`.

| Campo | Tipo | Obrigatório | Default | Origem / Nota |
|---|---|---|---|---|
| `llm_provider` | `Literal["bedrock", "offline"]` | Não | `"bedrock"` | Princípio I — Bedrock é o caminho padrão, nunca fallback silencioso |
| `aws_access_key_id` | `str` | Sim (quando `llm_provider="bedrock"`) | — | Credencial AWS |
| `aws_secret_access_key` | `SecretStr` | Sim (quando `llm_provider="bedrock"`) | — | Credencial AWS; `SecretStr` evita vazamento em `repr`/log |
| `aws_region` | `str` | Sim | — | Região AWS (ex.: `us-east-1`) |
| `bedrock_model_id` | `str` | Sim | — | ID do modelo Claude no Bedrock (consumido pela SPEC-005) |
| `bedrock_embeddings_model_id` | `str` | Sim | — | ID do modelo Titan Embeddings (consumido pela SPEC-005/012) |
| `api_url` | `str` (`AnyHttpUrl`) | Sim | — | URL da API FastAPI (consumida como cliente HTTP pela SPEC-014) |
| `postgres_dsn` | `str` (`PostgresDsn`) | Sim | — | DSN do Postgres/pgvector (consumido pela SPEC-006) |
| `object_storage_endpoint` | `str` | Sim | — | Endpoint do object storage MinIO/S3 (consumido pela SPEC-006) |

**Validação/comportamento**:
- Instanciação (`Settings()`) roda no import de `pix_compliance.config`, expondo
  `settings` já construído — conforme SC-002.
- Qualquer campo obrigatório ausente levanta `ConfigurationError` (exceção tipada do
  projeto, não `pydantic.ValidationError` cru), com mensagem citando a primeira
  variável ausente e a instrução de copiar `.env.example` para `.env` (FR-004).
- Nenhum valor default inseguro para credenciais — campos de credencial não têm
  default (Edge Case da spec: ausência de `.env` deve falhar, nunca silenciosamente
  usar valor vazio ou fake).

**Relações**: nenhuma — é uma entidade isolada, sem referência a outros modelos
(que ainda não existem nesta spec).

**Transições de estado**: nenhuma — `Settings` é imutável após a instanciação
(`frozen=True` seguindo a mesma convenção de imutabilidade que a SPEC-002 adotará
para os modelos de domínio onde fizer sentido semântico).
