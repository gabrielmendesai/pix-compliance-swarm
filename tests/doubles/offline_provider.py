"""`OfflineChatProvider`/`OfflineEmbeddingsProvider` (SPEC-005).

Test double determinístico para a suíte de testes rodar sem rede e sem
custo de token (`LLM_PROVIDER=offline`). Vive fora de `src/` de propósito:
nenhum caminho de produção pode importar este módulo (Princípio I da
constituição) — a única forma de chegar aqui é pelo branch `"offline"` de
`get_chat_provider()`/`get_embeddings_provider()` em
`pix_compliance.llm_provider`, que existe apenas para a suíte de testes.
"""

import hashlib


class OfflineChatProvider:
    """Mesmo prompt sempre produz a mesma resposta, sem chamada de rede —
    determinismo é o que permite os testes offline serem reprodutíveis."""

    def complete(self, prompt: str) -> str:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        return f"[offline-response:{digest}]"


class OfflineEmbeddingsProvider:
    """Vetor determinístico derivado de hash do texto — dimensão fixa
    pequena, suficiente para testes que validam formato, não qualidade
    semântica do embedding."""

    _DIMENSIONS = 8

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [byte / 255.0 for byte in digest[: self._DIMENSIONS]]
