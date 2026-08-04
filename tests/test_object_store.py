"""Testes de round-trip do object store (SPEC-006, US1).

Escritos antes de `S3ObjectStore` existir (Princípio IX da constituição) —
rodam contra o MinIO real subido via `docker compose up minio -d`, sem mock
do `boto3` (a spec exige integridade byte-a-byte contra o serviço de fato).
Os valores de ambiente abaixo correspondem exatamente às credenciais do
serviço `minio` de docker-compose.yml.
"""

import hashlib
import uuid

import pytest

from tests.conftest import settings_for_test as _settings


@pytest.fixture
def store(monkeypatch):
    from pix_compliance.object_store import S3ObjectStore

    return S3ObjectStore(_settings(monkeypatch))


def test_upload_download_round_trip_preserves_bytes(store) -> None:
    key = f"test-{uuid.uuid4()}.bin"
    original = b"\x00\x01\x02conteudo-arbitrario\xff\xfe" * 100

    store.upload(key, original)
    recovered = store.download(key)

    assert hashlib.sha256(recovered).hexdigest() == hashlib.sha256(original).hexdigest()


def test_download_missing_key_raises_object_not_found_error(store) -> None:
    from pix_compliance.object_store import ObjectNotFoundError

    with pytest.raises(ObjectNotFoundError):
        store.download(f"chave-inexistente-{uuid.uuid4()}")
