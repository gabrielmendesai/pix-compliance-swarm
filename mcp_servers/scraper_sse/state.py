"""Estado de "último hash conhecido" por normativo (SPEC-007).

Persistido como um único blob JSON no `ObjectStore` (SPEC-006), sob uma
chave fixa — reaproveita a primitiva de persistência já existente em vez de
introduzir um serviço de estado dedicado (Princípio III, KISS; ver
research.md, Decisão 4).
"""

import json

from pix_compliance.object_store import ObjectNotFoundError, ObjectStore

KNOWN_HASHES_KEY = "scraper-state/known-hashes.json"


def load_known_hashes(store: ObjectStore) -> dict[str, str]:
    """Retorna o mapa `{normativo_id: hash_sha256}` conhecido até agora, ou
    vazio se esta é a primeira coleta (nenhum estado persistido ainda)."""
    try:
        raw = store.download(KNOWN_HASHES_KEY)
    except ObjectNotFoundError:
        return {}
    return json.loads(raw.decode("utf-8"))


def save_known_hashes(store: ObjectStore, hashes: dict[str, str]) -> None:
    """Sobrescreve o estado de hashes conhecidos com o mapa fornecido."""
    store.upload(KNOWN_HASHES_KEY, json.dumps(hashes).encode("utf-8"))
