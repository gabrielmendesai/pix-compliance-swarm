"""Cobre todos os cenários de aceitação de SPEC-003 (fixtures e corpus mock).

Testa idempotência do gerador, contagem mínima de normativos, validação
contra `NormativoItem`, PII plantada, pares de versão com delta documentado
e o site mock servindo a página de listagem.
"""

import http.client
import json
import re
import subprocess
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from fixtures import generate, pii

from pix_compliance.models import NormativoItem

REPO_ROOT = Path(__file__).resolve().parent.parent
NORMATIVOS_JSON = REPO_ROOT / "fixtures" / "normativos.json"
DOCUMENTS_DIR = REPO_ROOT / "fixtures" / "documents"
EXPECTED_DELTAS_MD = REPO_ROOT / "fixtures" / "EXPECTED_DELTAS.md"
MOCK_BCB_DIR = REPO_ROOT / "mock_bcb"


def test_corpus_cli_regenera_via_python_m_fixtures_generate():
    resultado = subprocess.run(
        [sys.executable, "-m", "fixtures.generate"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr


def test_corpus_tem_no_minimo_50_registros():
    generate.main()
    dados = json.loads(NORMATIVOS_JSON.read_text(encoding="utf-8"))
    assert len(dados) >= 50


def test_corpus_valida_contra_normativo_item_sem_reimplementar_schema():
    generate.main()
    dados = json.loads(NORMATIVOS_JSON.read_text(encoding="utf-8"))
    for registro in dados:
        NormativoItem.model_validate(registro)  # não deve levantar ValidationError


def test_corpus_e_idempotente_entre_duas_execucoes_no_mesmo_processo():
    generate.main()
    conteudo_1 = NORMATIVOS_JSON.read_bytes()
    generate.main()
    conteudo_2 = NORMATIVOS_JSON.read_bytes()
    assert conteudo_1 == conteudo_2


def test_corpus_e_idempotente_entre_duas_execucoes_via_cli():
    subprocess.run([sys.executable, "-m", "fixtures.generate"], cwd=REPO_ROOT, check=True)
    conteudo_1 = NORMATIVOS_JSON.read_bytes()
    subprocess.run([sys.executable, "-m", "fixtures.generate"], cwd=REPO_ROOT, check=True)
    conteudo_2 = NORMATIVOS_JSON.read_bytes()
    assert conteudo_1 == conteudo_2


def test_pii_documentos_minimos_pdf_e_html():
    generate.main()
    documentos = list(DOCUMENTS_DIR.iterdir())
    assert len([d for d in documentos if d.suffix == ".pdf"]) >= 3
    assert len([d for d in documentos if d.suffix == ".html"]) >= 3


def test_pii_cpf_valido_e_cnpj_invalido_plantados_em_algum_documento():
    generate.main()
    htmls = list(DOCUMENTS_DIR.glob("*.html"))
    conteudo = "\n".join(html.read_text(encoding="utf-8") for html in htmls)

    cpf_encontrado = re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", conteudo)
    cnpj_encontrado = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", conteudo)

    assert cpf_encontrado is not None
    assert cnpj_encontrado is not None
    assert pii.validar_cpf(cpf_encontrado.group()) is True
    assert pii.validar_cnpj(cnpj_encontrado.group()) is False


def test_delta_pares_de_versao_existem_no_corpus():
    generate.main()
    dados = json.loads(NORMATIVOS_JSON.read_text(encoding="utf-8"))
    por_numero: dict[str, list[dict]] = {}
    for registro in dados:
        por_numero.setdefault(registro["numero"], []).append(registro)
    pares = [registros for registros in por_numero.values() if len(registros) > 1]
    assert len(pares) >= 2


def test_delta_documentado_corresponde_exatamente_ao_diff_dos_registros():
    generate.main()
    dados = json.loads(NORMATIVOS_JSON.read_text(encoding="utf-8"))
    por_numero: dict[str, list[dict]] = {}
    for registro in dados:
        por_numero.setdefault(registro["numero"], []).append(registro)
    pares = [
        sorted(registros, key=lambda r: r["versao"])
        for registros in por_numero.values()
        if len(registros) > 1
    ]

    conteudo_deltas = EXPECTED_DELTAS_MD.read_text(encoding="utf-8")
    campos_ignorados = {"id", "versao", "hash_conteudo"}

    for v1, v2 in pares:
        assert v1["numero"] in conteudo_deltas
        campos_alterados_reais = {
            campo
            for campo in v1
            if campo not in campos_ignorados and v1[campo] != v2[campo]
        }
        for campo in campos_alterados_reais:
            assert f"`{campo}`" in conteudo_deltas


def test_mock_bcb_index_linka_todos_os_documentos_html():
    generate.main()
    quantidade_html = len(list(DOCUMENTS_DIR.glob("*.html")))
    index_html = (MOCK_BCB_DIR / "index.html").read_text(encoding="utf-8")
    assert index_html.count("<a href=") >= quantidade_html


def test_mock_bcb_serve_pagina_de_listagem_via_http_server():
    generate.main()

    def _handler(*args, **kwargs):
        return SimpleHTTPRequestHandler(*args, directory=str(MOCK_BCB_DIR), **kwargs)

    servidor = HTTPServer(("127.0.0.1", 0), _handler)
    porta = servidor.server_address[1]
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
        conexao.request("GET", "/")
        resposta = conexao.getresponse()
        assert resposta.status == 200
        corpo = resposta.read().decode("utf-8")
        assert "<a href=" in corpo
    finally:
        servidor.shutdown()
        thread.join()
