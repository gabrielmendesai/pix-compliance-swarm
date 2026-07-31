"""Camada de guardrail de PII — ponto único de aplicação obrigatório.

`guard()` é o único caminho permitido para qualquer texto destinado a um LLM
ou a uma escrita de storage (Princípio V da constituição: guardrail é ponto
único e obrigatório). Detecta e mascara CPF, CNPJ, e-mail, telefone e chave
PIX aleatória, verifica tamanho de texto e padrões simples de injeção de
prompt, e audita cada detecção via log estruturado — sem nunca expor o
valor original detectado. Novos detectores de PII se adicionam dentro deste
módulo, sem exigir alteração de nenhum agente consumidor.
"""

import re
from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar

import structlog
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

# Acima deste tamanho, o texto provavelmente não é um trecho de normativo
# isolado, mas um artefato indevido (ex. múltiplos documentos concatenados
# por engano) — uma ordem de grandeza maior que o maior documento de
# normativo esperado, para não penalizar texto legítimo.
MAX_TEXT_LENGTH = 100_000


class GuardrailInputError(Exception):
    """Texto de entrada não pode ser processado pelo guardrail (ex.: excede
    `MAX_TEXT_LENGTH`) — mensagem clara e acionável, análoga a
    `ConfigurationError` em `pix_compliance.config`."""


class TipoPII(StrEnum):
    """Vocabulário fechado dos tipos de PII detectáveis pelo guardrail."""

    CPF = "cpf"
    CNPJ = "cnpj"
    EMAIL = "email"
    TELEFONE = "telefone"
    CHAVE_PIX_ALEATORIA = "chave_pix_aleatoria"


class PIIReport(BaseModel):
    """Relatório agregado de uma detecção de PII, por tipo (não por
    ocorrência individual): "contagem de ocorrências" só faz sentido como
    campo se o relatório for por tipo — caso contrário seria sempre 1."""

    model_config = ConfigDict(extra="forbid")

    tipo: TipoPII
    posicao: int = Field(ge=0)
    ocorrencias: int = Field(ge=1)


class GuardedText(BaseModel):
    """Resultado de `guard()` — o único formato que deve chegar a um LLM ou
    a uma escrita de storage."""

    model_config = ConfigDict(extra="forbid")

    texto_mascarado: str
    relatorios: list[PIIReport]
    injecao_suspeita: bool


# --- Validação de dígito verificador (CPF/CNPJ) -----------------------------
#
# Reimplementado aqui (em vez de importar de `fixtures/pii.py`) porque
# `fixtures/` é um pacote de geração de dados de desenvolvimento/avaliação,
# nunca importado por `src/` (decisão de arquitetura da SPEC-003) — o
# algoritmo é curto o suficiente para não valer a pena compartilhar
# especulativamente entre os dois pacotes (Princípio II, YAGNI).
#
# Validar o dígito verificador (módulo 11), e não apenas o formato via
# regex, é o que reduz drasticamente falso positivo: qualquer sequência de
# 11 dígitos "parece" um CPF por formato, mas só uma fração ínfima delas
# tem dígito verificador correto (FR-002).

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


def _validar_cpf(candidato: str) -> bool:
    digitos = _somente_digitos(candidato)
    if len(digitos) != 11:
        return False
    d1 = _digito_verificador(digitos[:9], _PESOS_CPF_1)
    d2 = _digito_verificador(digitos[:9] + [d1], _PESOS_CPF_2)
    return digitos[9:] == [d1, d2]


def _validar_cnpj(candidato: str) -> bool:
    digitos = _somente_digitos(candidato)
    if len(digitos) != 14:
        return False
    d1 = _digito_verificador(digitos[:12], _PESOS_CNPJ_1)
    d2 = _digito_verificador(digitos[:12] + [d1], _PESOS_CNPJ_2)
    return digitos[12:] == [d1, d2]


# --- Padrões de detecção -----------------------------------------------------
#
# O regex localiza candidatos plausíveis por formato; para CPF/CNPJ, cada
# candidato ainda passa pela validação de dígito verificador acima antes de
# virar uma detecção real. Para telefone, exigimos um separador explícito
# (parênteses ou espaço após o DDD) para não colidir com uma sequência de
# 11 dígitos sem formatação, que já é tratada como possível CPF.

_CPF_RE = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
_CNPJ_RE = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TELEFONE_RE = re.compile(r"(?:\(\d{2}\)\s?|\d{2}\s)9?\d{4}-\d{4}")
_CHAVE_PIX_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# Padrões sintáticos simples de injeção de prompt — verificação básica
# (delimitadores suspeitos, frases de instrução embutida conhecidas), não um
# classificador; construir detecção sofisticada está fora do escopo desta
# spec (FR-007).
_PADROES_INJECAO = [
    re.compile(r"ignore\s+(as\s+)?instru[çc][õo]es\s+anteriores", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(above|previous)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"```|<\|.*?\|>|###"),
]


def _detectar_injecao_prompt(texto: str) -> bool:
    return any(padrao.search(texto) for padrao in _PADROES_INJECAO)


# --- Mascaramento preservando formato ---------------------------------------
#
# Mascarar preservando formato (em vez de substituir tudo por um marcador
# genérico como `[REDACTED]`) permite que quem consome o texto mascarado
# (LLM, log, revisor humano) ainda reconheça que aquele trecho *era* um
# CPF/CNPJ/e-mail/telefone/chave PIX — sem preservar informação suficiente
# para reidentificação.


def _mascarar_por_digitos(candidato: str, manter_inicio: int, manter_fim: int) -> str:
    """Preserva os primeiros `manter_inicio` e os últimos `manter_fim`
    dígitos (e toda a pontuação original), mascarando os dígitos do meio."""
    total_digitos = sum(1 for caractere in candidato if caractere.isdigit())
    resultado = []
    digitos_vistos = 0
    for caractere in candidato:
        if not caractere.isdigit():
            resultado.append(caractere)
            continue
        if digitos_vistos < manter_inicio or digitos_vistos >= total_digitos - manter_fim:
            resultado.append(caractere)
        else:
            resultado.append("*")
        digitos_vistos += 1
    return "".join(resultado)


def _mascarar_email(candidato: str) -> str:
    local, _, dominio = candidato.partition("@")
    if len(local) <= 1:
        local_mascarado = local
    else:
        local_mascarado = local[0] + "*" * (len(local) - 1)
    return f"{local_mascarado}@{dominio}"


def _mascarar_chave_pix(candidato: str) -> str:
    grupos = candidato.split("-")
    if len(grupos) != 5:
        return candidato  # nunca deveria acontecer dado o regex de origem
    grupos_mascarados = [grupos[0], *("*" * len(g) for g in grupos[1:4]), grupos[4]]
    return "-".join(grupos_mascarados)


# --- Orquestração ------------------------------------------------------------

_Detector = tuple[TipoPII, re.Pattern, Callable[[str], bool] | None, Callable[[str], str]]

_DETECTORES: list[_Detector] = [
    (TipoPII.CPF, _CPF_RE, _validar_cpf, lambda m: _mascarar_por_digitos(m, 3, 2)),
    (TipoPII.CNPJ, _CNPJ_RE, _validar_cnpj, lambda m: _mascarar_por_digitos(m, 2, 2)),
    (TipoPII.EMAIL, _EMAIL_RE, None, _mascarar_email),
    (TipoPII.TELEFONE, _TELEFONE_RE, None, lambda m: _mascarar_por_digitos(m, 2, 2)),
    (TipoPII.CHAVE_PIX_ALEATORIA, _CHAVE_PIX_RE, None, _mascarar_chave_pix),
]


def _processar_pii(texto: str) -> tuple[str, list[PIIReport]]:
    """Detecta e mascara todos os tipos de PII no texto original.

    Todas as detecções usam sempre o texto original (nunca um texto já
    parcialmente mascarado por outro detector), e a reconstrução do texto
    mascarado acontece em uma única varredura por posição — isso evita que
    a máscara de um tipo interfira na regex de outro.
    """
    relatorios: list[PIIReport] = []
    substituicoes: list[tuple[int, int, str]] = []

    for tipo, padrao, validador, mascarador in _DETECTORES:
        candidatos = list(padrao.finditer(texto))
        if validador is not None:
            candidatos = [m for m in candidatos if validador(m.group())]
        if not candidatos:
            continue
        relatorios.append(
            PIIReport(tipo=tipo, posicao=candidatos[0].start(), ocorrencias=len(candidatos))
        )
        substituicoes.extend((m.start(), m.end(), mascarador(m.group())) for m in candidatos)

    if not substituicoes:
        return texto, relatorios

    substituicoes.sort(key=lambda item: item[0])
    partes = []
    cursor = 0
    for inicio, fim, mascarado in substituicoes:
        if inicio < cursor:
            continue  # sobreposição com uma substituição já aplicada; ignora
        partes.append(texto[cursor:inicio])
        partes.append(mascarado)
        cursor = fim
    partes.append(texto[cursor:])
    return "".join(partes), relatorios


# --- Ponto único de aplicação ------------------------------------------------


def guard(text: str) -> GuardedText:
    """Único caminho permitido para texto destinado a um LLM ou a uma
    escrita de storage. Verifica tamanho, sinaliza padrões de injeção de
    prompt, detecta e mascara PII, e audita cada detecção via log
    estruturado — nunca o valor original."""
    texto = text or ""
    if len(texto) > MAX_TEXT_LENGTH:
        raise GuardrailInputError(
            f"texto excede o tamanho máximo permitido de {MAX_TEXT_LENGTH} caracteres"
        )

    injecao_suspeita = _detectar_injecao_prompt(texto)
    texto_mascarado, relatorios = _processar_pii(texto)

    logger = structlog.get_logger()
    for relatorio in relatorios:
        # Nunca logamos o valor original detectado — apenas tipo e contagem
        # (FR-009): o log é uma ferramenta de auditoria, não deve se tornar
        # uma nova superfície de vazamento do próprio dado sensível.
        logger.info(
            "guardrail_pii_detectado", tipo=relatorio.tipo.value, ocorrencias=relatorio.ocorrencias
        )
    if injecao_suspeita:
        logger.warning("guardrail_injecao_prompt_suspeita")

    return GuardedText(
        texto_mascarado=texto_mascarado,
        relatorios=relatorios,
        injecao_suspeita=injecao_suspeita,
    )


def call_with_guard(func: Callable[[str], T], text: str) -> T:
    """Aplica `guard()` e invoca `func` apenas com o texto mascarado.

    Função de ordem superior em vez de decorator: o texto a proteger só é
    conhecido em tempo de chamada (não em tempo de definição de `func`), o
    que se encaixa melhor em código já existente (ex. um cliente Bedrock)
    sem precisar decorá-lo estaticamente.
    """
    resultado = guard(text)
    return func(resultado.texto_mascarado)
