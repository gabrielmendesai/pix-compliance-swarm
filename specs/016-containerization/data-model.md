# Data Model: Conteinerização (SPEC-016)

Esta feature não introduz nenhum modelo Pydantic novo — é infraestrutura
declarativa (Dockerfiles, compose, scripts). O "modelo de dados" relevante
aqui é a topologia de serviços do `docker-compose.yml` e o contrato do
script de bootstrap.

## Topologia de serviços

| Serviço | Origem da imagem | Depende de (`condition: service_healthy` salvo indicação) | Healthcheck |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` (já existente) | — | `pg_isready` (já existente) |
| `minio` | `minio/minio` (já existente) | — | `mc ready local` (já existente) |
| `mock-bcb` | `python:3.12-slim` (`command`, sem build) | — | `curl -f http://localhost:8080/` |
| `bootstrap` | `build: target: api` | `postgres`, `minio` | N/A — serviço de execução única; `depends_on` de outros usa `condition: service_completed_successfully` |
| `mcp-scraper` | `build: target: mcp-scraper` | `mock-bcb` | checagem TCP na porta MCP |
| `api` | `build: target: api` | `postgres`, `minio`, `bootstrap` (`service_completed_successfully`) | `curl -f http://localhost:8000/health` |
| `scheduler` | `build: target: scheduler` | `postgres`, `minio`, `bootstrap` (`service_completed_successfully`), `mcp-scraper`, `mock-bcb` | checagem de processo vivo |

## Variáveis de ambiente específicas de container (sobrescrevem `.env` local)

Hostnames internos do compose substituem `localhost` para comunicação
entre containers — definidos diretamente em `docker-compose.yml`
(`environment:`), não em `.env` (que continua valendo para execução local
fora de container, `make run`):

| Variável | Valor local (`.env`) | Valor em container (compose) |
|---|---|---|
| `POSTGRES_DSN` | `postgresql://pix:pix@localhost:5432/...` | `postgresql://pix:pix@postgres:5432/...` |
| `OBJECT_STORAGE_ENDPOINT` | `http://localhost:9000` | `http://minio:9000` |
| `BCB_BASE_URL` | `http://localhost:8080` | `http://mock-bcb:8080` |
| `MCP_SCRAPER_HOST` | `127.0.0.1` | `mcp-scraper` (nome do serviço, resolvido pela rede interna do compose) |
| `API_URL` | `http://localhost:8000` | `http://api:8000` |
| `ORCHESTRATOR_BOOTSTRAP_LOCAL_SERVERS` (novo, SPEC-016) | não definida (default `true`) | `false` — `mock-bcb`/`mcp-scraper` já são containers próprios |

Credenciais (`AWS_*`, `OBJECT_STORAGE_ACCESS_KEY`/`SECRET_KEY`,
`OBJECT_STORAGE_BUCKET`, `BEDROCK_*`) continuam vindas de `.env` via
`env_file: .env` em cada serviço da aplicação — nunca hardcoded no
compose.

## Contrato: `scripts/bootstrap.py`

```python
def main() -> None:
    """Cria o bucket do object storage (S3ObjectStore, idempotente) e
    aplica migrations/0001_create_vector_store_schema.sql (idempotente,
    já usa CREATE ... IF NOT EXISTS) — roda uma vez por ciclo de vida dos
    volumes, seguro rodar mais de uma vez. Termina com código de saída
    != 0 e mensagem clara em caso de falha (nunca falha silenciosamente)."""
```

## Extensão aditiva: `orchestrator_agent.py` (ver research.md, Decisão 5)

| Adição | Tipo | Default | Papel |
|---|---|---|---|
| CLI `--daemon` | flag | ausente (execução única) | Container `scheduler`: mantém o processo vivo rodando `start_scheduler` |
| `Settings.orchestrator_bootstrap_local_servers` | `bool` | `True` | `run_pipeline` usa como default de `bootstrap_local_servers` quando o chamador não especifica — `False` no container `scheduler` (compose) |
