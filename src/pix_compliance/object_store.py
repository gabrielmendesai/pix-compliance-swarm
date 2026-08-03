"""Object storage para artefatos binários (SPEC-006).

`ObjectStore` é `Protocol` porque há, de fato, uma segunda implementação real
além do MinIO local: a mesma classe concreta (`S3ObjectStore`) serve S3 real
apenas trocando `endpoint_url` — um seam real, não uma abstração especulativa
(Princípio II da constituição). Se este projeto só falasse com MinIO, sem
nenhum caminho de troca para S3, `S3ObjectStore` seria usado diretamente, sem
`Protocol`.
"""

from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from pix_compliance.config import Settings


class ObjectNotFoundError(Exception):
    """Chave inexistente no bucket — substitui o erro cru do
    `boto3`/`botocore` (`ClientError` com `Error.Code == "NoSuchKey"`) por
    uma mensagem acionável, análoga a `ConfigurationError` (SPEC-001)."""


class ObjectStore(Protocol):
    """Contrato de armazenamento de objetos binários. Todo texto gravado via
    `upload` que se origina de conteúdo livre (não binário fixo) já deve ter
    atravessado `pix_compliance.guardrails.guard()` antes desta chamada —
    esta camada não reaplica o guardrail, apenas persiste o que recebe
    (Princípio V)."""

    def upload(self, key: str, data: bytes) -> None:
        """Grava `data` sob `key` no bucket configurado. Sobrescreve se a
        chave já existir."""
        ...

    def download(self, key: str) -> bytes:
        """Retorna os bytes gravados sob `key`. Levanta `ObjectNotFoundError`
        se a chave não existir."""
        ...


class S3ObjectStore:
    """Implementação concreta de `ObjectStore` via `boto3`/`s3`.

    A mesma classe serve MinIO local (endpoint_url apontando para o
    container) e S3 real (endpoint_url apontando para o endpoint AWS, ou
    omitido) — é esse seam de configuração que justifica `ObjectStore` ser
    `Protocol` (Princípio II)."""

    def __init__(self, settings: "Settings") -> None:
        self._bucket = settings.object_storage_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key.get_secret_value(),
            region_name=settings.aws_region,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        # MinIO não cria bucket automaticamente; criamos sob demanda para
        # manter o setup local simples (Princípio III), sem exigir um
        # container de inicialização separado em docker-compose.yml.
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def upload(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def download(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"NoSuchKey", "404"}:
                raise ObjectNotFoundError(f"chave não encontrada no bucket: {key}") from exc
            raise
        return response["Body"].read()
