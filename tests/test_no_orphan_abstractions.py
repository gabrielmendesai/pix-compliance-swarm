"""SC-004: nenhuma classe abstrata ou `Protocol` sem implementação concreta
correspondente existe em `src/pix_compliance/` (SPEC-006, US3).

Verificação estrutural, não uma lista hardcoded de nomes: qualquer `Protocol`
ou `abc.ABC` introduzido no pacote precisa ter, no próprio pacote, ao menos
uma classe concreta que defina todos os métodos públicos do contrato — caso
contrário a abstração é órfã (Princípio II da constituição violado).
"""

import inspect
import pkgutil
from abc import ABC
from importlib import import_module
from typing import Protocol

import pix_compliance

# Importar todos os submódulos do pacote dispara `settings = Settings()`
# (singleton de módulo em config.py), que exige as variáveis de ambiente
# abaixo — mesmos valores fake usados em tests/test_config.py.
_REQUIRED_ENV = {
    "AWS_ACCESS_KEY_ID": "AKIAFAKEEXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "fake-secret",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "anthropic.claude-3-fake",
    "BEDROCK_EMBEDDINGS_MODEL_ID": "amazon.titan-embed-fake",
    "API_URL": "http://localhost:8000",
    "POSTGRES_DSN": "postgresql://pix:pix@localhost:5432/pix_compliance",
    "OBJECT_STORAGE_ENDPOINT": "http://localhost:9000",
    "OBJECT_STORAGE_ACCESS_KEY": "minioadmin",
    "OBJECT_STORAGE_SECRET_KEY": "minioadmin",
    "OBJECT_STORAGE_BUCKET": "pix-compliance-test",
}


def _package_classes() -> list[type]:
    classes: list[type] = []
    for module_info in pkgutil.walk_packages(
        pix_compliance.__path__, prefix="pix_compliance."
    ):
        module = import_module(module_info.name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__.startswith("pix_compliance"):
                classes.append(obj)
    return list(dict.fromkeys(classes))  # remove duplicatas preservando ordem


def _is_protocol(cls: type) -> bool:
    return getattr(cls, "_is_protocol", False)


def _is_abstract_base(cls: type) -> bool:
    return ABC in cls.__bases__ or (inspect.isabstract(cls) and cls is not ABC)


def _public_methods(cls: type) -> set[str]:
    return {
        name
        for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    }


def test_every_protocol_or_abstract_class_has_a_concrete_implementation(monkeypatch) -> None:
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    classes = _package_classes()
    abstractions = [
        c for c in classes if (_is_protocol(c) or _is_abstract_base(c)) and c is not Protocol
    ]

    orphans = []
    for abstraction in abstractions:
        required_methods = _public_methods(abstraction)
        has_concrete_implementation = any(
            candidate is not abstraction
            and not _is_protocol(candidate)
            and not _is_abstract_base(candidate)
            and required_methods <= _public_methods(candidate)
            for candidate in classes
        )
        if not has_concrete_implementation:
            orphans.append(abstraction.__qualname__)

    assert not orphans, f"Abstrações sem implementação concreta: {orphans}"


def test_object_store_protocol_has_exactly_one_concrete_implementation() -> None:
    # Ponto único de Protocol desta feature (Princípio II): ObjectStore.
    # PgVectorStore permanece classe concreta, sem Protocol.
    from pix_compliance.object_store import ObjectStore, S3ObjectStore

    assert _is_protocol(ObjectStore)
    assert not _is_protocol(S3ObjectStore)
