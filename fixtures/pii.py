"""Geração e validação de CPF/CNPJ fictícios para a fixture de PII (FR-006).

Calculamos o dígito verificador (módulo 11) diretamente, em vez de usar uma
biblioteca de terceiros, porque precisamos produzir os dois ramos exigidos
pelo guardrail de PII (um identificador sintaticamente válido e um inválido)
— bibliotecas como Faker só geram o caso válido por padrão, o que ainda
exigiria esta mesma lógica para o ramo negativo.
"""

import random

SEED_PII_PADRAO = 20260731

_PESOS_CPF_1 = [10, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_CPF_2 = [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_CNPJ_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_CNPJ_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def _digito_verificador(digitos: list[int], pesos: list[int]) -> int:
    soma = sum(digito * peso for digito, peso in zip(digitos, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def _somente_digitos(texto: str) -> list[int]:
    return [int(caractere) for caractere in texto if caractere.isdigit()]


def gerar_cpf_valido(rng: random.Random | None = None) -> str:
    """Gera um CPF fictício com dígitos verificadores corretos."""
    rng = rng or random.Random(SEED_PII_PADRAO)
    base = [rng.randint(0, 9) for _ in range(9)]
    d1 = _digito_verificador(base, _PESOS_CPF_1)
    d2 = _digito_verificador(base + [d1], _PESOS_CPF_2)
    n = base + [d1, d2]
    return f"{n[0]}{n[1]}{n[2]}.{n[3]}{n[4]}{n[5]}.{n[6]}{n[7]}{n[8]}-{n[9]}{n[10]}"


def gerar_cpf_invalido(rng: random.Random | None = None) -> str:
    """Gera um CPF fictício com o último dígito verificador propositalmente
    incorreto, para exercitar o ramo negativo do guardrail de PII."""
    valido = gerar_cpf_valido(rng)
    ultimo_corrompido = (int(valido[-1]) + 1) % 10
    return f"{valido[:-1]}{ultimo_corrompido}"


def gerar_cnpj_valido(rng: random.Random | None = None) -> str:
    """Gera um CNPJ fictício (filial 0001) com dígitos verificadores corretos."""
    rng = rng or random.Random(SEED_PII_PADRAO)
    base = [rng.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    d1 = _digito_verificador(base, _PESOS_CNPJ_1)
    d2 = _digito_verificador(base + [d1], _PESOS_CNPJ_2)
    n = base + [d1, d2]
    return (
        f"{n[0]}{n[1]}.{n[2]}{n[3]}{n[4]}.{n[5]}{n[6]}{n[7]}/"
        f"{n[8]}{n[9]}{n[10]}{n[11]}-{n[12]}{n[13]}"
    )


def gerar_cnpj_invalido(rng: random.Random | None = None) -> str:
    """Gera um CNPJ fictício com dígito verificador propositalmente incorreto."""
    valido = gerar_cnpj_valido(rng)
    ultimo_corrompido = (int(valido[-1]) + 1) % 10
    return f"{valido[:-1]}{ultimo_corrompido}"


def validar_cpf(cpf: str) -> bool:
    """Confere os dígitos verificadores de um CPF (reusado pela geração e pelos testes)."""
    digitos = _somente_digitos(cpf)
    if len(digitos) != 11:
        return False
    d1 = _digito_verificador(digitos[:9], _PESOS_CPF_1)
    d2 = _digito_verificador(digitos[:9] + [d1], _PESOS_CPF_2)
    return digitos[9:] == [d1, d2]


def validar_cnpj(cnpj: str) -> bool:
    """Confere os dígitos verificadores de um CNPJ (reusado pela geração e pelos testes)."""
    digitos = _somente_digitos(cnpj)
    if len(digitos) != 14:
        return False
    d1 = _digito_verificador(digitos[:12], _PESOS_CNPJ_1)
    d2 = _digito_verificador(digitos[:12] + [d1], _PESOS_CNPJ_2)
    return digitos[12:] == [d1, d2]
