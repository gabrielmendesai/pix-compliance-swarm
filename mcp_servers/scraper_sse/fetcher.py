"""Fetcher genérico de coleta HTTP (SPEC-007).

Não sabe nada sobre a estrutura de nenhuma página específica — só faz
requisição HTTP com retry/backoff e rate limit, e calcula o hash de mudança.
Funciona contra qualquer fonte por URL, seja o site mock do BCB ou um alvo
real futuro; toda interpretação de estrutura HTML vive no `Adapter`
(`adapters.py`), nunca aqui.
"""

import hashlib
import time

import httpx
from pydantic import BaseModel, ConfigDict
from tenacity import retry, stop_after_attempt, wait_exponential


class FetchedContent(BaseModel):
    """Resultado de uma coleta: conteúdo bruto e hash SHA-256 correspondente."""

    model_config = ConfigDict(extra="forbid")

    content: str
    hash_sha256: str


class Fetcher:
    """Requisição HTTP com retry/backoff, rate limit e cálculo de hash."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_backoff_seconds: float = 1.0,
        min_interval_seconds: float = 0.0,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._max_attempts = max_attempts
        self._initial_backoff_seconds = initial_backoff_seconds
        self._min_interval_seconds = min_interval_seconds
        self._timeout_seconds = timeout_seconds
        # Marca o instante da última requisição para aplicar rate limit por
        # intervalo mínimo entre chamadas consecutivas — suficiente para não
        # sobrecarregar a fonte, sem exigir um limitador de taxa mais
        # sofisticado (token bucket) para o volume deste projeto.
        self._last_request_at: float | None = None

    def get(self, url: str) -> FetchedContent:
        self._respeitar_rate_limit()

        @retry(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=self._initial_backoff_seconds),
            reraise=True,
        )
        def _get_com_retry() -> httpx.Response:
            response = httpx.get(url, timeout=self._timeout_seconds)
            response.raise_for_status()
            return response

        response = _get_com_retry()
        self._last_request_at = time.monotonic()

        content = response.text
        hash_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return FetchedContent(content=content, hash_sha256=hash_sha256)

    def _respeitar_rate_limit(self) -> None:
        if self._last_request_at is None or self._min_interval_seconds <= 0:
            return
        decorrido = time.monotonic() - self._last_request_at
        restante = self._min_interval_seconds - decorrido
        if restante > 0:
            time.sleep(restante)
