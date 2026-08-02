import importlib

import pytest

REQUIRED_ENV = {
    "AWS_ACCESS_KEY_ID": "AKIAFAKEEXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "fake-secret",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "anthropic.claude-3-fake",
    "BEDROCK_EMBEDDINGS_MODEL_ID": "amazon.titan-embed-fake",
    "API_URL": "http://localhost:8000",
    "POSTGRES_DSN": "postgresql://user:pass@localhost:5432/pix",
    "OBJECT_STORAGE_ENDPOINT": "http://localhost:9000",
}


def _reload_config():
    """Reimporta o módulo para reavaliar `settings` contra o ambiente atual."""
    import pix_compliance.config as config_module

    return importlib.reload(config_module)


def test_settings_loads_successfully_with_valid_env(monkeypatch):
    monkeypatch.delenv("AWS_REGION", raising=False)
    # LLM_PROVIDER isolado do ambiente real: este teste verifica o default
    # ("bedrock"), independentemente de a própria suíte estar rodando sob
    # LLM_PROVIDER=offline (SC-002 da SPEC-005).
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    config_module = _reload_config()

    dumped = config_module.settings.model_dump()
    assert dumped["aws_region"] == "us-east-1"
    assert dumped["llm_provider"] == "bedrock"


def test_settings_raises_actionable_error_when_aws_region_missing(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AWS_REGION", raising=False)

    from pix_compliance.config import ConfigurationError, Settings

    with pytest.raises(ConfigurationError) as exc_info:
        Settings(_env_file=None)

    message = str(exc_info.value)
    assert "AWS_REGION" in message
    assert ".env.example" in message


def test_settings_defaults_fallback_model_ids_to_empty_list(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("BEDROCK_FALLBACK_MODEL_IDS", raising=False)

    from pix_compliance.config import Settings

    settings = Settings(_env_file=None)

    assert settings.bedrock_fallback_model_ids_list == []


def test_settings_parses_comma_separated_fallback_model_ids(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("BEDROCK_FALLBACK_MODEL_IDS", " modelo-a , modelo-b ,,modelo-c")

    from pix_compliance.config import Settings

    settings = Settings(_env_file=None)

    assert settings.bedrock_fallback_model_ids_list == [
        "modelo-a",
        "modelo-b",
        "modelo-c",
    ]


def test_settings_raises_actionable_error_when_llm_provider_invalid(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("LLM_PROVIDER", "chatgpt")

    from pix_compliance.config import ConfigurationError, Settings

    with pytest.raises(ConfigurationError) as exc_info:
        Settings(_env_file=None)

    message = str(exc_info.value)
    assert "LLM_PROVIDER" in message
    assert "bedrock" in message
    assert "offline" in message
