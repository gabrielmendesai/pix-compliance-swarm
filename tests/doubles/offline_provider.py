"""`OfflineChatProvider`/`OfflineEmbeddingsProvider` (SPEC-005).

Test double determinístico para a suíte de testes rodar sem rede e sem
custo de token (`LLM_PROVIDER=offline`). Vive fora de `src/` de propósito:
nenhum caminho de produção pode importar este módulo (Princípio I da
constituição) — a única forma de chegar aqui é pelo branch `"offline"` de
`get_chat_provider()`/`get_embeddings_provider()` em
`pix_compliance.llm_provider`, que existe apenas para a suíte de testes.
"""

import hashlib

from pix_compliance.config import EMBEDDING_DIMENSION


class OfflineChatProvider:
    """Mesmo prompt sempre produz a mesma resposta, sem chamada de rede —
    determinismo é o que permite os testes offline serem reprodutíveis."""

    def complete(self, prompt: str) -> str:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        return f"[offline-response:{digest}]"


class OfflineEmbeddingsProvider:
    """Vetor determinístico derivado de hash do texto — dimensão igual a
    EMBEDDING_DIMENSION (SPEC-012), para permanecer compatível com o
    `vector(512)` do PgVectorStore (SPEC-006). Um único digest SHA-256 (32
    bytes) não basta; expande-se concatenando digests de `f"{text}:{i}"`
    para i crescente até atingir a dimensão exigida. Sem sinal semântico
    real — mesmo texto sempre produz o mesmo vetor, textos diferentes
    produzem vetores efetivamente aleatórios entre si."""

    _DIMENSIONS = EMBEDDING_DIMENSION

    def embed(self, text: str) -> list[float]:
        blocks: list[bytes] = []
        counter = 0
        total_bytes = 0
        while total_bytes < self._DIMENSIONS:
            digest = hashlib.sha256(f"{text}:{counter}".encode()).digest()
            blocks.append(digest)
            total_bytes += len(digest)
            counter += 1
        expanded = b"".join(blocks)[: self._DIMENSIONS]
        return [byte / 255.0 for byte in expanded]
