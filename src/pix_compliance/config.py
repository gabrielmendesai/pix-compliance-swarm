"""Configuração tipada da aplicação, carregada de variáveis de ambiente.

`Settings` é uma classe concreta (sem `Protocol`) porque não há segunda
implementação nem teste que precise substituí-la — testes variam apenas os
valores de ambiente injetados (Princípio II da constituição).
"""

from typing import Literal

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dimensão do vetor gerado pelo Titan Text Embeddings V2
# (amazon.titan-embed-text-v2:0), decisão já tomada na SPEC-005. Travada como
# constante de módulo (não como campo de Settings lido de env var) para que
# nenhuma configuração de ambiente possa divergir do schema já criado pela
# migration do pgvector (migrations/0001_create_vector_store_schema.sql,
# SPEC-006) — é o mesmo número dos dois lados, sempre.
EMBEDDING_DIMENSION = 512


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
    object_storage_access_key: str
    object_storage_secret_key: SecretStr
    object_storage_bucket: str

    # SPEC-007: alvo de coleta do scraper (site mock do BCB por padrão) e
    # host/porta do servidor MCP (transporte SSE). Trocar apenas
    # bcb_base_url é o único passo necessário para apontar a um alvo real
    # no futuro (Fetcher é agnóstico à origem; ver adapters.py).
    bcb_base_url: str
    mcp_scraper_host: str
    mcp_scraper_port: int

    # SPEC-010: limite de chamadas simultâneas ao LLM no processamento em
    # lote do Compliance Analyzer Agent (custo e rate limit do Bedrock, não
    # só performance) e limiar de confiança abaixo do qual uma regra
    # extraída é sinalizada para revisão humana.
    compliance_analyzer_max_concurrency: int
    compliance_analyzer_confidence_threshold: float

    # SPEC-015: cron (5 campos, formato padrão) do disparo periódico do
    # pipeline completo via APScheduler — mesmo handler usado pelo CLI
    # (FR-008), nunca um segundo caminho de entrada.
    orchestrator_schedule_cron: str = "0 3 * * *"

    @property
    def embedding_dimension(self) -> int:
        """Dimensão do vetor de embedding, travada em `EMBEDDING_DIMENSION`
        (constante de módulo, não configurável por env var)."""
        return EMBEDDING_DIMENSION

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
