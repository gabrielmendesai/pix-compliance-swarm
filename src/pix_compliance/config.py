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

    api_url: str
    postgres_dsn: str
    object_storage_endpoint: str

    def __init__(self, **kwargs: object) -> None:
        try:
            super().__init__(**kwargs)
        except ValidationError as exc:
            first_error = exc.errors()[0]
            missing_field = str(first_error["loc"][0]).upper()
            raise ConfigurationError(
                f"falta {missing_field}; copie .env.example para .env e preencha "
                "os valores necessários."
            ) from None


settings = Settings()
