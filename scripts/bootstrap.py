"""Bootstrap de infraestrutura (SPEC-016) — roda uma vez por ciclo de vida
dos volumes, como o serviço `bootstrap` do docker-compose (`depends_on:
condition: service_completed_successfully` em `api`/`scheduler`).

Cria o bucket do object storage (reaproveitando `S3ObjectStore`, SPEC-006 —
nunca uma segunda forma de criar o bucket, e o nome vem sempre de
`settings.object_storage_bucket`, nunca hardcoded, FR-005) e aplica
`migrations/0001_create_vector_store_schema.sql` (SPEC-006).

Seguro rodar mais de uma vez (idempotente): `S3ObjectStore.__init__` já
usa `head_bucket`/`create_bucket` (não recria um bucket já existente), e a
migration já usa `CREATE EXTENSION IF NOT EXISTS`/`CREATE TABLE IF NOT
EXISTS`/`CREATE INDEX IF NOT EXISTS` desde a SPEC-006 — nenhum dos dois
passos falha ou duplica efeito ao ser reexecutado (ex. após um restart do
serviço sem `docker compose down -v`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg
import structlog

from pix_compliance.config import ConfigurationError, settings
from pix_compliance.object_store import S3ObjectStore

logger = structlog.get_logger()

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "migrations" / "0001_create_vector_store_schema.sql"
)


def _create_bucket() -> None:
    # A própria construção de S3ObjectStore já cria o bucket
    # (_ensure_bucket, SPEC-006) — nenhuma chamada adicional necessária
    # aqui além de instanciá-lo.
    S3ObjectStore(settings)
    logger.info("bootstrap_bucket_pronto", bucket=settings.object_storage_bucket)


def _apply_migration() -> None:
    sql = _MIGRATION_PATH.read_text(encoding="utf-8")
    with psycopg.connect(settings.postgres_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql)
    logger.info("bootstrap_migration_aplicada", arquivo=_MIGRATION_PATH.name)


def main() -> None:
    try:
        _create_bucket()
        _apply_migration()
    except ConfigurationError as exc:
        logger.error("bootstrap_configuracao_invalida", erro=str(exc))
        print(f"bootstrap falhou: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 — qualquer falha aqui deve abortar a subida do compose, com mensagem clara
        logger.error("bootstrap_falhou", erro=str(exc))
        print(f"bootstrap falhou: {exc}", file=sys.stderr)
        sys.exit(1)

    logger.info("bootstrap_concluido")
    print("bootstrap concluído: bucket pronto, migration aplicada.")


if __name__ == "__main__":
    main()
