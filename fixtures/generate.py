"""Gerador determinístico do corpus mock de normativos PIX (SPEC-003).

Produz `fixtures/normativos.json`, `fixtures/documents/*.{pdf,html}`,
`fixtures/EXPECTED_DELTAS.md` e o site mock estático em `mock_bcb/`, todos
reprodutíveis byte a byte entre execuções — ver `SEED_FIXA` abaixo. Executável
via `python -m fixtures.generate`.
"""

import hashlib
import json
import random
import re
import textwrap
import uuid
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from fixtures import pii
from pix_compliance.models import CategoriaCompliance, NormativoItem, TipoNormativo

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
DOCUMENTS_DIR = FIXTURES_DIR / "documents"
MOCK_BCB_DIR = REPO_ROOT / "mock_bcb"

# Namespace fixo para uuid5 — junto com SEED_FIXA, garante que os `id` gerados
# sejam determinísticos entre execuções (não usamos uuid4).
NORMATIVOS_NAMESPACE = uuid.UUID("6f6f6f0a-0000-4000-8000-000000000000")

# Seed fixa: o corpus gerado é consumido como fixture de avaliação por outras
# specs (guardrail de PII, Conformance Validator). Determinismo aqui garante
# que o avaliador reproduza exatamente o mesmo corpus documentado a cada
# execução — reprodutibilidade da avaliação, não apenas conveniência de
# desenvolvimento.
SEED_FIXA = 20260731

NUM_NORMATIVOS_BASE = 50

# Índices reservados: 0 e 1 viram o par de versão "prazo estendido" (status
# `alterado`); 2 vira o par de versão "revogação de inciso" (status
# `revogado`). Esses três usam um template fixo e dedicado (em vez do pool
# de templates por categoria) para que a transformação texto->v2 continue
# correta independentemente de qual template genérico teria sido sorteado.
INDICES_PAR_PRAZO = (0, 1)
INDICE_PAR_REVOGACAO = 2

_ESPACOS_RE = re.compile(r"\s+")
_ARTIGO_RE = re.compile(r"(Art\.\s*\d+º)")
_INCISO_RE = re.compile(r"(Inciso\s+[IVXLCDM]+)")

# Vários templates genuinamente distintos por categoria (estrutura de
# artigo/inciso, cláusulas e números diferentes) — o objetivo é que dois
# normativos da mesma categoria tenham conteúdo semanticamente diferente
# entre si, não apenas o rótulo da categoria trocado dentro do mesmo
# parágrafo. Isso dá à busca semântica (RAG) e ao Compliance Analyzer texto
# real para diferenciar, em vez de uma única frase-molde repetida.
TEMPLATES_POR_CATEGORIA: dict[CategoriaCompliance, list[str]] = {
    CategoriaCompliance.PARTICIPANTES: [
        (
            "Art. 1º Esta {tipo} disciplina o credenciamento de novos "
            "participantes do arranjo PIX.\n"
            "Inciso I - O interessado deve comprovar capital mínimo regulatório.\n"
            "Inciso II - A habilitação é concedida em até 60 dias após análise "
            "documental.\n"
            "Art. 2º O participante habilitado deve iniciar operação em até 30 "
            "dias sob pena de cancelamento do credenciamento."
        ),
        (
            "Art. 1º Esta {tipo} regula o desligamento voluntário de "
            "participante do arranjo PIX.\n"
            "Inciso I - O pedido de desligamento deve ser protocolado com 90 "
            "dias de antecedência.\n"
            "Art. 2º O participante permanece responsável por transações "
            "pendentes até a efetivação do desligamento."
        ),
        (
            "Art. 1º Esta {tipo} estabelece obrigações de participantes "
            "indiretos conectados via participante liquidante.\n"
            "Inciso I - O participante indireto responde solidariamente por "
            "falhas operacionais que causem prejuízo a usuários finais.\n"
            "Inciso II - O participante liquidante deve manter registro "
            "atualizado de todos os indiretos conectados."
        ),
        (
            "Art. 1º Esta {tipo} disciplina a suspensão temporária de "
            "participante por descumprimento reiterado de obrigações.\n"
            "Inciso I - A suspensão não pode exceder 15 dias corridos.\n"
            "Inciso II - Durante a suspensão, o participante não pode "
            "iniciar novas transações, mas deve liquidar as pendentes."
        ),
    ],
    CategoriaCompliance.TARIFAS: [
        (
            "Art. 1º Esta {tipo} fixa o teto da tarifa de interoperabilidade "
            "interbancária cobrada entre participantes do arranjo PIX.\n"
            "Inciso I - O valor máximo é revisado anualmente pelo Banco "
            "Central.\n"
            "Art. 2º É vedada a cobrança de tarifa interbancária superior ao "
            "teto vigente na data da transação."
        ),
        (
            "Art. 1º Esta {tipo} assegura a gratuidade da tarifa cobrada de "
            "pessoas físicas em transações Pix entre contas de mesma "
            "titularidade.\n"
            "Inciso I - A gratuidade não se aplica a transações comerciais "
            "(P2C).\n"
            "Inciso II - Instituições que descumprirem a gratuidade ficam "
            "sujeitas a devolução em dobro do valor cobrado."
        ),
        (
            "Art. 1º Esta {tipo} regula a tarifa de saque em espécie via "
            "Pix Saque e Pix Troco realizado em correspondente bancário.\n"
            "Inciso I - O valor cobrado do usuário final não pode exceder o "
            "limite estabelecido pelo Banco Central."
        ),
        (
            "Art. 1º Esta {tipo} determina a revisão anual do teto de "
            "tarifas cobradas de lojistas (P2C) por recebimento via Pix.\n"
            "Inciso I - A revisão considera o volume agregado de transações "
            "do arranjo no exercício anterior.\n"
            "Inciso II - Alterações de teto entram em vigor apenas no "
            "exercício seguinte à publicação."
        ),
    ],
    CategoriaCompliance.LIQUIDACAO: [
        (
            "Art. 1º Esta {tipo} estabelece que a liquidação das transações "
            "Pix ocorre em tempo real, ininterruptamente, 24 horas por dia, "
            "7 dias por semana.\n"
            "Inciso I - Eventual indisponibilidade deve ser comunicada ao "
            "Banco Central em até 1 hora."
        ),
        (
            "Art. 1º Esta {tipo} disciplina o plano de contingência de "
            "liquidação em caso de indisponibilidade do Sistema de "
            "Transferência de Reservas (STR).\n"
            "Inciso I - As transações represadas devem ser liquidadas em "
            "até 2 horas após o restabelecimento do STR.\n"
            "Inciso II - O participante deve manter plano de contingência "
            "homologado pelo Banco Central."
        ),
        (
            "Art. 1º Esta {tipo} fixa o prazo para devolução de valores ao "
            "usuário pagador em caso de fraude confirmada.\n"
            "Inciso I - A devolução deve ocorrer em até 24 horas após a "
            "confirmação da fraude pelo Mecanismo Especial de Devolução."
        ),
        (
            "Art. 1º Esta {tipo} regula a compensação multilateral entre "
            "participantes do arranjo PIX ao final de cada ciclo de "
            "liquidação.\n"
            "Inciso I - Divergências na compensação devem ser reportadas "
            "antes do início do ciclo seguinte.\n"
            "Inciso II - O saldo líquido de cada participante é liquidado "
            "em conta de reservas bancárias."
        ),
    ],
    CategoriaCompliance.SEGURANCA: [
        (
            "Art. 1º Esta {tipo} exige autenticação multifator para "
            "transações Pix acima do limite noturno estabelecido pelo "
            "usuário.\n"
            "Inciso I - A autenticação deve combinar ao menos dois fatores "
            "independentes.\n"
            "Inciso II - A ausência de autenticação multifator sujeita a "
            "instituição a responsabilização por fraude subsequente."
        ),
        (
            "Art. 1º Esta {tipo} torna obrigatória a criptografia de dados "
            "de transações Pix em trânsito e em repouso.\n"
            "Inciso I - Deve-se utilizar, no mínimo, o padrão TLS 1.2 para "
            "dados em trânsito."
        ),
        (
            "Art. 1º Esta {tipo} fixa o prazo para comunicação de "
            "incidentes de segurança cibernética ao Banco Central.\n"
            "Inciso I - Incidentes que afetem dados de usuários devem ser "
            "comunicados em até 6 horas da detecção.\n"
            "Inciso II - O relatório final de causa-raiz deve ser enviado "
            "em até 10 dias úteis."
        ),
        (
            "Art. 1º Esta {tipo} estabelece a obrigatoriedade de testes de "
            "intrusão periódicos nos sistemas que processam transações "
            "Pix.\n"
            "Inciso I - Os testes devem ser realizados a cada 12 meses por "
            "empresa independente.\n"
            "Inciso II - Vulnerabilidades críticas identificadas devem ser "
            "corrigidas em até 30 dias."
        ),
    ],
    CategoriaCompliance.SLA: [
        (
            "Art. 1º Esta {tipo} fixa o tempo máximo de resposta da API de "
            "confirmação de pagamento em 10 segundos.\n"
            "Inciso I - Descumprimentos recorrentes geram registro no "
            "indicador de qualidade do participante."
        ),
        (
            "Art. 1º Esta {tipo} estabelece a disponibilidade mínima mensal "
            "exigida dos participantes em 99,9%.\n"
            "Inciso I - Janelas de manutenção programada não contam para o "
            "cálculo de indisponibilidade, desde que previamente "
            "comunicadas.\n"
            "Inciso II - A apuração da disponibilidade é mensal e "
            "publicada pelo Banco Central."
        ),
        (
            "Art. 1º Esta {tipo} disciplina penalidades por descumprimento "
            "reiterado de SLA por participantes do arranjo PIX.\n"
            "Inciso I - A partir da terceira reincidência no mesmo "
            "semestre, aplica-se multa proporcional ao volume "
            "transacionado."
        ),
        (
            "Art. 1º Esta {tipo} exige monitoramento contínuo de latência "
            "e a publicação mensal de métricas de desempenho.\n"
            "Inciso I - As métricas devem incluir latência média, latência "
            "de pico e taxa de erro.\n"
            "Inciso II - Os dados devem ficar disponíveis para consulta "
            "pelo Banco Central por, no mínimo, 5 anos."
        ),
    ],
    CategoriaCompliance.INTEROPERABILIDADE: [
        (
            "Art. 1º Esta {tipo} torna obrigatório o suporte ao padrão de "
            "mensageria ISO 20022 para transações Pix.\n"
            "Inciso I - A migração completa deve ocorrer em até 180 dias "
            "da publicação."
        ),
        (
            "Art. 1º Esta {tipo} disciplina a portabilidade de chaves Pix "
            "entre instituições participantes.\n"
            "Inciso I - A portabilidade deve ser concluída em até 24 horas "
            "a partir da solicitação do usuário.\n"
            "Inciso II - A instituição de origem não pode impor obstáculos "
            "operacionais à portabilidade."
        ),
        (
            "Art. 1º Esta {tipo} regula a interoperabilidade entre QR Code "
            "estático e QR Code dinâmico no arranjo PIX.\n"
            "Inciso I - Todo participante deve ser capaz de ler e "
            "processar ambos os formatos."
        ),
        (
            "Art. 1º Esta {tipo} exige a integração obrigatória com o "
            "Diretório de Identificadores de Contas Transacionais (DICT).\n"
            "Inciso I - A sincronização com o DICT deve ocorrer em tempo "
            "real, sem processamento em lote.\n"
            "Inciso II - Divergências entre o DICT e a base local do "
            "participante devem ser corrigidas em até 24 horas."
        ),
    ],
}


TITULO_DOCUMENTO_DENSO = "Resolução BCB nº 200/2023 sobre múltiplos temas de compliance PIX"

# Documento "denso" (fixtures/documents/): ao contrário dos registros de
# normativos.json (uma categoria por registro, volume estatístico), este
# documento existe para provar que o Extractor consegue segmentar um único
# documento bruto em múltiplos artigos de categorias diferentes — 4 artigos,
# cada um com 2-3 incisos, cobrindo tarifas, SLA, segurança e participantes.
# Não corresponde a nenhum registro de normativos.json (ver README, seção
# "Fixtures: documents/ vs normativos.json").
TEXTO_DOCUMENTO_DENSO = (
    "Art. 1º Esta Resolução BCB fixa o teto da tarifa de interoperabilidade "
    "interbancária aplicável às transações Pix realizadas entre "
    "participantes do arranjo.\n"
    "Inciso I - O valor máximo é revisado anualmente pelo Banco Central.\n"
    "Inciso II - É vedada a cobrança de tarifa interbancária superior ao "
    "teto vigente na data da transação.\n"
    "Inciso III - Tarifas cobradas de pessoas físicas em transações P2P "
    "permanecem gratuitas, independentemente do teto interbancário.\n"
    "Art. 2º Esta Resolução BCB fixa o tempo máximo de resposta da API de "
    "confirmação de pagamento e a disponibilidade mínima mensal exigida "
    "dos participantes.\n"
    "Inciso I - O tempo máximo de resposta da API de confirmação é de 10 "
    "segundos.\n"
    "Inciso II - A disponibilidade mínima mensal exigida é de 99,9%, "
    "apurada e publicada pelo Banco Central.\n"
    "Art. 3º Esta Resolução BCB exige autenticação multifator para "
    "transações acima do limite noturno e criptografia de dados de "
    "transações Pix em trânsito e em repouso.\n"
    "Inciso I - A autenticação deve combinar ao menos dois fatores "
    "independentes.\n"
    "Inciso II - Deve-se utilizar, no mínimo, o padrão TLS 1.2 para dados "
    "em trânsito.\n"
    "Inciso III - Incidentes que comprometam a autenticação ou a "
    "criptografia devem ser comunicados ao Banco Central em até 6 horas.\n"
    "Art. 4º Esta Resolução BCB disciplina o prazo de adequação dos "
    "participantes às obrigações previstas nos artigos anteriores.\n"
    "Inciso I - O prazo de adequação é de 90 dias a contar da publicação.\n"
    "Inciso II - Participantes recém-credenciados têm prazo de adequação "
    "de 180 dias a contar da data de habilitação."
)


def _rng() -> random.Random:
    """Nova instância local de RNG com a seed fixa.

    Recriar a instância (em vez de reutilizar um `random.Random` de módulo já
    avançado) é o que torna duas chamadas sucessivas a `main()` no mesmo
    processo idempotentes, não apenas duas invocações separadas do CLI.
    """
    return random.Random(SEED_FIXA)


def _texto_normalizado_para_hash(texto: str) -> str:
    """Replica a normalização de texto de `NormativoItem` (strip + colapso de
    espaços) apenas para calcular um `hash_conteudo` consistente com o valor
    que o modelo armazenará após validação — evita depender de um símbolo
    privado de `pix_compliance.models`."""
    return _ESPACOS_RE.sub(" ", texto.strip())


def _texto_par_prazo(tipo: TipoNormativo, categoria: CategoriaCompliance) -> str:
    """Template fixo e dedicado dos índices 0/1 (par de versão "prazo
    estendido"): preserva literalmente a frase "prazo de 90 dias" para que
    `_build_version_pair` continue substituindo-a por "180 dias" de forma
    confiável, independente da diversificação dos demais templates."""
    return (
        f"Art. 1º Esta {tipo.value} dispõe sobre {categoria.value} no âmbito "
        "do arranjo PIX.\n"
        "Inciso I - Aplica-se a todas as instituições participantes do arranjo.\n"
        "Inciso II - Exclui-se as instituições em processo de descredenciamento.\n"
        "Art. 2º As instituições participantes devem se adequar no prazo de "
        "90 dias a contar da publicação.\n"
        "Inciso I - O prazo pode ser prorrogado mediante justificativa técnica."
    )


def _texto_par_revogacao(tipo: TipoNormativo, categoria: CategoriaCompliance) -> str:
    """Template fixo e dedicado do índice 2 (par de versão "revogação de
    inciso"): o Inciso II é escrito de forma isolada e literal para que
    `_build_version_pair_revogacao` possa revogá-lo de forma confiável."""
    return (
        f"Art. 1º Esta {tipo.value} dispõe sobre {categoria.value} no âmbito "
        "do arranjo PIX.\n"
        "Inciso I - Aplica-se a todas as instituições participantes do arranjo.\n"
        "Inciso II - As instituições devem manter registro de auditoria por "
        "5 anos.\n"
        "Art. 2º O descumprimento desta norma sujeita a instituição a "
        "sanções administrativas."
    )


def _build_record(rng: random.Random, indice: int) -> dict:
    """Monta um registro bruto compatível com `NormativoItem` para o índice dado."""
    tipo = rng.choice(list(TipoNormativo))
    categoria = rng.choice(list(CategoriaCompliance))
    sequencial = 100 + indice
    ano = 2020 + (indice % 6)
    numero = f"{sequencial}/{ano}"
    titulo = f"{tipo.value} nº {numero} sobre {categoria.value}"

    if indice in INDICES_PAR_PRAZO:
        texto = _texto_par_prazo(tipo, categoria)
    elif indice == INDICE_PAR_REVOGACAO:
        texto = _texto_par_revogacao(tipo, categoria)
    else:
        # Templates diversos por categoria (research.md não cobria isto
        # originalmente; ver ajuste pós-implementação): garante que dois
        # normativos da mesma categoria tenham conteúdo semanticamente
        # diferente, não apenas o rótulo trocado no mesmo parágrafo-molde.
        template = rng.choice(TEMPLATES_POR_CATEGORIA[categoria])
        texto = template.format(tipo=tipo.value)

    data_publicacao = date(2020, 1, 1) + timedelta(days=indice * 7)
    data_vigencia = data_publicacao + timedelta(days=30)
    artigo = "1º" if indice % 4 == 0 else None
    inciso = "I" if indice % 4 == 0 else None
    hash_conteudo = hashlib.sha256(
        _texto_normalizado_para_hash(texto).encode("utf-8")
    ).hexdigest()
    numero_slug = numero.replace("/", "-")

    return {
        "id": str(uuid.uuid5(NORMATIVOS_NAMESPACE, f"{numero}-v1")),
        "titulo": titulo,
        "tipo": tipo.value,
        "numero": numero,
        "artigo": artigo,
        "inciso": inciso,
        "texto": texto,
        "data_publicacao": data_publicacao.isoformat(),
        "data_vigencia": data_vigencia.isoformat(),
        "categoria": categoria.value,
        "url_origem": f"https://mock-bcb.local/normativos/{numero_slug}.html",
        "hash_conteudo": hash_conteudo,
        "versao": 1,
    }


def _build_version_pair(registro_base: dict) -> dict:
    """Cria a segunda versão de um normativo com um delta conhecido e único:
    o prazo de adequação é estendido de 90 para 180 dias e a data de vigência
    é adiada de acordo — exatamente o que `EXPECTED_DELTAS.md` documenta."""
    numero = registro_base["numero"]
    texto_v2 = registro_base["texto"].replace("prazo de 90 dias", "prazo de 180 dias")
    hash_v2 = hashlib.sha256(
        _texto_normalizado_para_hash(texto_v2).encode("utf-8")
    ).hexdigest()
    data_vigencia_v1 = date.fromisoformat(registro_base["data_vigencia"])
    data_vigencia_v2 = data_vigencia_v1 + timedelta(days=60)

    registro_v2 = dict(registro_base)
    registro_v2["id"] = str(uuid.uuid5(NORMATIVOS_NAMESPACE, f"{numero}-v2"))
    registro_v2["texto"] = texto_v2
    registro_v2["data_vigencia"] = data_vigencia_v2.isoformat()
    registro_v2["hash_conteudo"] = hash_v2
    registro_v2["versao"] = 2
    return registro_v2


def _build_version_pair_revogacao(registro_base: dict) -> dict:
    """Cria a segunda versão de um normativo em que o Inciso II é
    explicitamente revogado: a v2 declara o inciso revogado e acrescenta um
    artigo com o efeito revogatório, para que o Conformance Validator possa
    classificar este par com status `revogado` (em vez de `alterado`)."""
    numero = registro_base["numero"]
    texto_v2 = registro_base["texto"].replace(
        "Inciso II - As instituições devem manter registro de auditoria por 5 anos.",
        "Inciso II - Revogado. O registro de auditoria deixa de ser exigido "
        "em decorrência da revogação promovida por este ato.",
    )
    texto_v2 += (
        " Art. 3º Fica revogado o Inciso II do Art. 1º desta normativa, com "
        "efeitos a partir da data de vigência desta nova versão."
    )
    hash_v2 = hashlib.sha256(
        _texto_normalizado_para_hash(texto_v2).encode("utf-8")
    ).hexdigest()
    data_vigencia_v1 = date.fromisoformat(registro_base["data_vigencia"])
    data_vigencia_v2 = data_vigencia_v1 + timedelta(days=45)

    registro_v2 = dict(registro_base)
    registro_v2["id"] = str(uuid.uuid5(NORMATIVOS_NAMESPACE, f"{numero}-v2"))
    registro_v2["texto"] = texto_v2
    registro_v2["data_vigencia"] = data_vigencia_v2.isoformat()
    registro_v2["hash_conteudo"] = hash_v2
    registro_v2["versao"] = 2
    return registro_v2


def _gerar_corpus_normativos() -> list[NormativoItem]:
    """Gera >= 50 registros e valida cada um contra `NormativoItem` antes de
    retornar — falha rápido (nada é escrito em disco) se algum registro for
    inválido (FR-002)."""
    rng = _rng()
    registros_brutos = [_build_record(rng, indice) for indice in range(NUM_NORMATIVOS_BASE)]

    # Três pares de versão (User Story 3): os dois primeiros normativos
    # ganham uma segunda versão com prazo estendido (status `alterado`); o
    # terceiro ganha uma segunda versão que revoga um inciso (status
    # `revogado`) — cobrindo os dois ramos relevantes do enum de
    # ConformanceItem, não apenas um tipo de delta.
    for indice in INDICES_PAR_PRAZO:
        registros_brutos.append(_build_version_pair(registros_brutos[indice]))
    registros_brutos.append(_build_version_pair_revogacao(registros_brutos[INDICE_PAR_REVOGACAO]))

    return [NormativoItem.model_validate(registro) for registro in registros_brutos]


def _escrever_normativos_json(modelos: list[NormativoItem]) -> None:
    dados = [modelo.model_dump(mode="json") for modelo in modelos]
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    caminho = FIXTURES_DIR / "normativos.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _campos_alterados(v1: NormativoItem, v2: NormativoItem) -> list[str]:
    """Compara duas versões campo a campo, ignorando os que mudam por
    natureza da própria versão (id, versao, hash_conteudo)."""
    ignorados = {"id", "versao", "hash_conteudo"}
    return [
        nome
        for nome in NormativoItem.model_fields
        if nome not in ignorados and getattr(v1, nome) != getattr(v2, nome)
    ]


def _natureza_da_mudanca(v1: NormativoItem, v2: NormativoItem) -> str:
    """Descreve a natureza do delta e o status esperado no Conformance
    Validator para este par, inferido do próprio conteúdo alterado — assim a
    documentação nunca diverge do dado gerado, mesmo que novos tipos de par
    sejam adicionados no futuro."""
    if "revogado" in v2.texto.lower() and "revogado" not in v1.texto.lower():
        return (
            "Revogação explícita do Inciso II do Art. 1º na versão atual (a "
            "v2 declara o inciso revogado e acrescenta um artigo com o "
            "efeito revogatório). Status esperado no Conformance Validator: "
            "`revogado`."
        )
    return (
        "Prazo de adequação estendido de 90 para 180 dias, com nova data de "
        "vigência refletindo a prorrogação. Status esperado no Conformance "
        "Validator: `alterado`."
    )


def _escrever_expected_deltas(modelos: list[NormativoItem]) -> None:
    """Documenta cada par de versões no formato exigido por FR-008, gerado a
    partir da diferença real entre os registros (não uma descrição manual
    solta), para que o documento nunca fique fora de sincronia com o dado."""
    grupos: dict[str, list[NormativoItem]] = {}
    for modelo in modelos:
        grupos.setdefault(modelo.numero, []).append(modelo)
    pares = [sorted(grupo, key=lambda m: m.versao) for grupo in grupos.values() if len(grupo) > 1]

    linhas = [
        "# Deltas esperados entre versões de normativos (SPEC-003)\n\n",
        "Gerado automaticamente por `fixtures/generate.py` — cada seção documenta\n",
        "o delta conhecido entre duas versões do mesmo normativo lógico, usado\n",
        "como fixture de teste do gap analysis (Conformance Validator).\n\n",
    ]
    for indice, (v1, v2) in enumerate(pares, start=1):
        campos = _campos_alterados(v1, v2)
        linhas.append(f"## Par {indice}: {v1.tipo.value} nº {v1.numero}\n\n")
        linhas.append(f"- **Normativo (numero)**: {v1.numero}\n")
        linhas.append(f"- **Versão anterior**: {v1.versao} (id `{v1.id}`)\n")
        linhas.append(f"- **Versão atual**: {v2.versao} (id `{v2.id}`)\n")
        linhas.append(f"- **Campo(s) alterado(s)**: {', '.join(f'`{c}`' for c in campos)}\n")
        linhas.append(f"- **Natureza da mudança**: {_natureza_da_mudanca(v1, v2)}\n\n")

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURES_DIR / "EXPECTED_DELTAS.md").write_text("".join(linhas), encoding="utf-8")


def _dividir_em_artigos(texto: str) -> list[tuple[str, str]]:
    """Divide o texto normalizado (uma linha só) em blocos por artigo,
    preservando o rótulo — dá estrutura hierárquica a um texto que, após
    normalização por `NormativoItem`, não tem mais quebras de linha."""
    partes = _ARTIGO_RE.split(texto)
    blocos = []
    for i in range(1, len(partes), 2):
        rotulo = partes[i].strip()
        corpo = partes[i + 1].strip() if i + 1 < len(partes) else ""
        blocos.append((rotulo, corpo))
    return blocos


def _dividir_em_incisos(corpo: str) -> tuple[str, list[str]]:
    partes = _INCISO_RE.split(corpo)
    introducao = partes[0].strip()
    incisos = []
    for i in range(1, len(partes), 2):
        rotulo = partes[i].strip()
        # O texto após o rótulo já vem com o "- " separador original (ex.
        # "Inciso I - Aplica-se..." -> resto = " - Aplica-se..."); remover
        # esse prefixo evita duplicar o traço ao remontar "rotulo - resto".
        resto = partes[i + 1].strip() if i + 1 < len(partes) else ""
        resto = resto.lstrip("-").strip()
        incisos.append(f"{rotulo} - {resto}" if resto else rotulo)
    return introducao, incisos


def _escrever_html(caminho: Path, titulo: str, texto: str) -> None:
    """Renderiza um normativo em HTML semântico, com um `<h2>` por artigo e
    uma `<ul>` por conjunto de incisos — estrutura hierárquica mínima para
    uma futura feature de extração ter conteúdo realista para processar."""
    blocos = _dividir_em_artigos(texto)
    partes_html = [f"<article>\n  <h1>{titulo}</h1>\n"]
    for rotulo, corpo in blocos:
        introducao, incisos = _dividir_em_incisos(corpo)
        partes_html.append(f"  <h2>{rotulo}</h2>\n  <p>{introducao}</p>\n")
        if incisos:
            partes_html.append("  <ul>\n")
            for inciso_texto in incisos:
                partes_html.append(f"    <li>{inciso_texto}</li>\n")
            partes_html.append("  </ul>\n")
    partes_html.append("</article>\n")

    html = (
        '<!doctype html>\n<html lang="pt-BR">\n<head>\n'
        f'  <meta charset="utf-8">\n  <title>{titulo}</title>\n</head>\n<body>\n'
        + "".join(partes_html)
        + "</body>\n</html>\n"
    )
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(html, encoding="utf-8")


def _escrever_pdf(caminho: Path, titulo: str, texto: str) -> None:
    """Renderiza um normativo em PDF determinístico: `invariant=1` remove
    timestamps e fixa a numeração interna de objetos do reportlab, de modo
    que o mesmo conteúdo produza os mesmos bytes entre execuções (SC-001,
    research.md §1)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(caminho), pagesize=A4, invariant=1)
    _largura, altura = A4
    y = altura - 50

    canvas.setFont("Helvetica-Bold", 14)
    for linha in textwrap.wrap(titulo, width=80):
        canvas.drawString(50, y, linha)
        y -= 20

    canvas.setFont("Helvetica", 11)
    y -= 10
    for rotulo, corpo in _dividir_em_artigos(texto):
        introducao, incisos = _dividir_em_incisos(corpo)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(50, y, rotulo)
        y -= 18
        canvas.setFont("Helvetica", 11)
        for linha in textwrap.wrap(introducao, width=90):
            canvas.drawString(60, y, linha)
            y -= 15
        for inciso_texto in incisos:
            for linha in textwrap.wrap(inciso_texto, width=85):
                canvas.drawString(70, y, linha)
                y -= 15

    canvas.showPage()
    canvas.save()


def _texto_com_pii(texto: str) -> str:
    """Acrescenta um parágrafo com CPF/CNPJ fictícios plantados.

    Ambos com dígito verificador válido (SPEC-004, FR-012): o guardrail de
    PII valida dígito verificador de verdade, então um CNPJ com dígito
    inválido não seria reconhecido como PII e não seria mascarado, quebrando
    silenciosamente a demonstração de ponta a ponta deste fixture. Os dois
    ramos do guardrail (válido/inválido) já são cobertos diretamente pelos
    testes de `tests/test_guardrails.py`, não precisam ser cobertos aqui."""
    rng = _rng()
    cpf = pii.gerar_cpf_valido(rng)
    cnpj = pii.gerar_cnpj_valido(rng)
    return (
        f"{texto} Contato para dúvidas: CPF {cpf}, CNPJ {cnpj} "
        "(documento fictício de teste do guardrail de PII)."
    )


def _escrever_documento(nome_base: str, titulo: str, texto: str, nomes_html: list[str]) -> None:
    """Escreve um par PDF+HTML em `fixtures/documents/` e espelha o HTML em
    `mock_bcb/normativos/`, registrando o nome do arquivo gerado."""
    nome_html = f"{nome_base}.html"
    _escrever_pdf(DOCUMENTS_DIR / f"{nome_base}.pdf", titulo, texto)
    _escrever_html(DOCUMENTS_DIR / nome_html, titulo, texto)
    _escrever_html(MOCK_BCB_DIR / "normativos" / nome_html, titulo, texto)
    nomes_html.append(nome_html)


def _gerar_documentos_e_site(modelos: list[NormativoItem]) -> list[str]:
    """Gera os documentos de `fixtures/documents/` (FR-005), cada um com um
    papel distinto — não volume, variedade real de estrutura e propósito
    (ver README, seção "Fixtures: documents/ vs normativos.json"):

    1. PII: o normativo 100/2020 (v1) com CPF/CNPJ fictícios plantados no
       texto, para exercitar o guardrail de PII (FR-006) — inalterado desde
       a implementação original.
    2. Denso: um documento sintético com 4 artigos e 2-3 incisos cada,
       cobrindo tarifas, SLA, segurança e participantes no mesmo documento —
       prova de conceito de que o Extractor consegue segmentar múltiplas
       categorias a partir de uma única fonte bruta.
    3. Par de versões: as DUAS versões (v1 e v2) do normativo 101/2021 —
       reaproveita o delta de prazo já gerado e documentado em
       `EXPECTED_DELTAS.md` ("Par 2"), agora também materializado como dois
       documentos brutos distintos.
    """
    por_numero: dict[str, list[NormativoItem]] = {}
    for modelo in modelos:
        por_numero.setdefault(modelo.numero, []).append(modelo)

    nomes_html: list[str] = []

    # 1. PII — normativo 100/2020, apenas v1, com CPF/CNPJ plantados.
    modelo_pii = next(m for m in por_numero["100/2020"] if m.versao == 1)
    texto_pii = _texto_com_pii(modelo_pii.texto)
    numero_slug_pii = modelo_pii.numero.replace("/", "-")
    _escrever_documento(
        f"normativo-{numero_slug_pii}-pii", modelo_pii.titulo, texto_pii, nomes_html
    )

    # 2. Denso — documento sintético multi-artigo/multi-categoria.
    _escrever_documento(
        "normativo-200-2023-denso", TITULO_DOCUMENTO_DENSO, TEXTO_DOCUMENTO_DENSO, nomes_html
    )

    # 3. Par de versões — normativo 101/2021, v1 e v2 (delta já documentado
    # em EXPECTED_DELTAS.md, "Par 2": prazo estendido de 90 para 180 dias).
    par_versoes = sorted(por_numero["101/2021"], key=lambda m: m.versao)
    for modelo in par_versoes:
        numero_slug = modelo.numero.replace("/", "-")
        _escrever_documento(
            f"normativo-{numero_slug}-v{modelo.versao}", modelo.titulo, modelo.texto, nomes_html
        )

    return nomes_html


def _escrever_site_mock(nomes_html: list[str]) -> None:
    itens = "\n".join(
        f'    <li><a href="normativos/{nome}">{nome}</a></li>' for nome in nomes_html
    )
    html = (
        '<!doctype html>\n<html lang="pt-BR">\n<head>\n'
        '  <meta charset="utf-8">\n  <title>BCB Mock — Normativos PIX</title>\n'
        "</head>\n<body>\n  <h1>Normativos PIX (mock)</h1>\n  <ul>\n"
        + itens
        + "\n  </ul>\n</body>\n</html>\n"
    )
    MOCK_BCB_DIR.mkdir(parents=True, exist_ok=True)
    (MOCK_BCB_DIR / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    """Ponto de entrada de `python -m fixtures.generate`."""
    modelos = _gerar_corpus_normativos()
    _escrever_normativos_json(modelos)
    _escrever_expected_deltas(modelos)
    nomes_html = _gerar_documentos_e_site(modelos)
    _escrever_site_mock(nomes_html)


if __name__ == "__main__":
    main()
