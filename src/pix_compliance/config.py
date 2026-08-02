"""Configuração tipada da aplicação, carregada de variáveis de ambiente.

`Settings` é uma classe concreta (sem `Protocol`) porque não há segunda
implementação nem teste que precise substituí-la — testes variam apenas os
valores de ambiente injetados (Princípio II da constituição).
"""

from typing import Literal

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(Exception):
    """Erro de configuração com mensagem acionável para quem sobe o projeto.

    Nunca deixamos vazar o `pydantic.ValidationError` cru (FR-004): o primeiro
    contato do avaliador com o projeto deve ser uma instrução, não um traceback.
    """


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="forbid", env_file=".env", frozen=True)

    llm_provider: Literal["bedrock", "offline"] = "bedrock"

    aws_access_key_id: str
    aws_secret_access_key: SecretStr
    aws_region: str
    bedrock_model_id: str
    bedrock_embeddings_model_id: str
    # Lista bruta (separada por vírgula) de model_id de fallback (SPEC-005) —
    # mantida como string simples porque `pydantic-settings` exigiria JSON
    # para um campo `list[str]` nativo; `bedrock_fallback_model_ids_list`
    # abaixo faz o parsing de formato "comma-separated" documentado em
    # .env.example.
    bedrock_fallback_model_ids: str = ""

    api_url: str
    postgres_dsn: str
    object_storage_endpoint: str

    def __init__(self, **kwargs: object) -> None:
        try:
            super().__init__(**kwargs)
        except ValidationError as exc:
            first_error = exc.errors()[0]
            field = str(first_error["loc"][0])
            if first_error["type"] == "literal_error" and field == "llm_provider":
                raise ConfigurationError(
                    "LLM_PROVIDER inválido "
                    f"({first_error.get('input')!r}); use 'bedrock' ou 'offline'."
                ) from None
            raise ConfigurationError(
                f"falta {field.upper()}; copie .env.example para .env e preencha "
                "os valores necessários."
            ) from None

    @property
    def bedrock_fallback_model_ids_list(self) -> list[str]:
        """Parseia `bedrock_fallback_model_ids` (string "a,b,c") em lista,
        ignorando espaços e entradas vazias — usado por `llm_provider.py`
        para montar a cadeia de fallback completa junto com
        `bedrock_model_id`."""
        return [item.strip() for item in self.bedrock_fallback_model_ids.split(",") if item.strip()]


settings = Settings()
