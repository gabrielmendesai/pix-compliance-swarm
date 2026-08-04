"""Testes do Report Consolidator Agent (SPEC-014).

Escritos antes de `report_consolidator_agent.py` existir (Princípio IX da
constituição). SPEC-011 (Conformance Validator) e SPEC-013 (API FastAPI)
ainda não existem como código neste repositório — os testes constroem um
`ConformanceReport` diretamente (sem depender de um Conformance Validator
real) e usam `httpx.MockTransport` (parte do próprio `httpx`, já dependência
do projeto — nenhuma dependência de teste nova) para simular a API FastAPI,
tanto no caminho feliz quanto na indisponibilidade (ver research.md,
Decisões 0 e 1).
"""

import ast
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from structlog.testing import capture_logs

from pix_compliance.models import (
    CategoriaCompliance,
    ConformanceItem,
    ConformanceReport,
    NormativoItem,
    Obrigatoriedade,
    RegraExtraida,
    StatusConformidade,
)
from tests.conftest import settings_for_test as _settings


@pytest.fixture
def settings(monkeypatch):
    return _settings(monkeypatch)


@pytest.fixture
def object_store(settings):
    from pix_compliance.object_store import S3ObjectStore

    return S3ObjectStore(settings)


@pytest.fixture
def normativos() -> list[NormativoItem]:
    return [
        NormativoItem(
            id="norm-tarifas",
            titulo="Resolução BCB nº 1/2024 sobre tarifas",
            tipo="Resolução BCB",
            numero="1/2024",
            artigo="1º",
            inciso="I",
            texto="Art. 1º Cobranca interbancaria vedada no arranjo PIX.",
            data_publicacao=datetime(2024, 1, 1).date(),
            data_vigencia=datetime(2024, 1, 1).date(),
            categoria=CategoriaCompliance.TARIFAS,
            url_origem="https://mock-bcb.local/normativos/1-2024.html",
            hash_conteudo="a" * 64,
            versao=1,
        ),
        NormativoItem(
            id="norm-seguranca",
            titulo="Instrução Normativa nº 2/2024 sobre segurança",
            tipo="Instrução Normativa",
            numero="2/2024",
            artigo="2º",
            inciso=None,
            texto="Art. 2º Criptografia obrigatoria em repouso.",
            data_publicacao=datetime(2024, 1, 8).date(),
            data_vigencia=datetime(2024, 1, 8).date(),
            categoria=CategoriaCompliance.SEGURANCA,
            url_origem="https://mock-bcb.local/normativos/2-2024.html",
            hash_conteudo="b" * 64,
            versao=1,
        ),
    ]


@pytest.fixture
def regras() -> list[RegraExtraida]:
    return [
        RegraExtraida(
            regra_id="regra-tarifas-1",
            normativo_id="norm-tarifas",
            categoria=CategoriaCompliance.TARIFAS,
            enunciado="Cobranca interbancaria vedada entre participantes.",
            obrigatoriedade=Obrigatoriedade.OBRIGATORIO,
            atores_afetados=["participante"],
            confianca=0.95,
        ),
        RegraExtraida(
            regra_id="regra-seguranca-1",
            normativo_id="norm-seguranca",
            categoria=CategoriaCompliance.SEGURANCA,
            enunciado="Criptografia obrigatoria de dados em repouso.",
            obrigatoriedade=Obrigatoriedade.OBRIGATORIO,
            atores_afetados=["participante"],
            confianca=0.9,
        ),
    ]


@pytest.fixture
def conformance_report() -> ConformanceReport:
    return ConformanceReport(
        report_id="report-teste-014",
        gerado_em=datetime(2024, 2, 1, 12, 0, 0),
        itens=[
            ConformanceItem(
                regra_id="regra-tarifas-1",
                status=StatusConformidade.CONFORME,
                severidade=0.1,
            ),
            ConformanceItem(
                regra_id="regra-seguranca-1",
                status=StatusConformidade.NAO_CONFORME,
                delta="Criptografia ausente no ambiente avaliado",
                recomendacao="Habilitar criptografia em repouso imediatamente",
                severidade=0.9,
            ),
        ],
        resumo="Um gap crítico de segurança identificado; demais itens conformes.",
        criticidade_maxima=StatusConformidade.NAO_CONFORME,
    )


@pytest.fixture(autouse=True)
def _reports_dir_isolado(tmp_path, monkeypatch):
    """Isola o diretório local de artefatos (`reports/`) em `tmp_path` por
    teste, evitando colisão de `report_id` entre execuções de teste."""
    monkeypatch.chdir(tmp_path)


class TestGenerateJson:
    def test_generate_json_produz_report_output_correto(
        self, conformance_report, normativos, regras
    ) -> None:
        from pix_compliance.agents.report_consolidator_agent import generate_json

        resultado = generate_json(conformance_report, normativos, regras)

        assert resultado.total_normativos == len(normativos)
        assert resultado.total_regras == len(regras)
        assert resultado.total_gaps == 1  # apenas o item "não conforme"
        assert resultado.gerado_em == conformance_report.gerado_em

        json_path = Path(resultado.json_path)
        assert json_path.exists()
        assert json_path.name == f"{conformance_report.report_id}.json"


class TestGeneratePdf:
    def test_generate_pdf_contem_cinco_secoes_obrigatorias(
        self, conformance_report, normativos, regras, tmp_path
    ) -> None:
        import pdfplumber

        from pix_compliance.agents.report_consolidator_agent import generate_pdf

        output_path = tmp_path / f"{conformance_report.report_id}.pdf"
        generate_pdf(conformance_report, normativos, regras, output_path)

        assert output_path.exists()
        with pdfplumber.open(output_path) as pdf:
            texto = "\n".join(page.extract_text() or "" for page in pdf.pages)

        # Capa
        assert conformance_report.report_id in texto
        # Sumário executivo
        assert "gap crítico de segurança" in texto
        # Tabela de normativos coletados
        assert "Resolução BCB nº 1/2024 sobre tarifas" in texto
        # Regras agrupadas por categoria
        assert "Criptografia obrigatoria de dados em repouso." in texto
        # Gap analysis com severidade
        assert "regra-seguranca-1" in texto


class TestUploadArtifacts:
    def test_upload_artifacts_envia_json_e_pdf_ao_object_store(
        self, conformance_report, normativos, regras, object_store, tmp_path
    ) -> None:
        from pix_compliance.agents.report_consolidator_agent import (
            generate_json,
            generate_pdf,
            upload_artifacts,
        )

        report_output = generate_json(conformance_report, normativos, regras)
        pdf_path = tmp_path / f"{conformance_report.report_id}.pdf"
        generate_pdf(conformance_report, normativos, regras, pdf_path)

        upload_artifacts(
            object_store, Path(report_output.json_path), pdf_path, conformance_report.report_id
        )

        json_bytes = object_store.download(f"reports/{conformance_report.report_id}.json")
        pdf_bytes = object_store.download(f"reports/{conformance_report.report_id}.pdf")
        assert json_bytes == Path(report_output.json_path).read_bytes()
        assert pdf_bytes == pdf_path.read_bytes()


class TestPublishToApi:
    def test_publish_to_api_usa_url_de_settings(self, settings, conformance_report) -> None:
        from pix_compliance.agents.report_consolidator_agent import generate_json, publish_to_api

        report_output = generate_json(conformance_report, [], [])

        urls_chamadas = []

        def handler(request: httpx.Request) -> httpx.Response:
            urls_chamadas.append(str(request.url))
            return httpx.Response(200, json={"status": "ok"})

        client = httpx.Client(base_url=settings.api_url, transport=httpx.MockTransport(handler))

        publish_to_api(settings, report_output, client=client)

        assert len(urls_chamadas) == 1
        assert urls_chamadas[0].startswith(settings.api_url)

    def test_nenhum_literal_de_url_no_codigo_fonte(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        caminho = repo_root / "src" / "pix_compliance" / "agents" / "report_consolidator_agent.py"
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))

        for node in ast.walk(arvore):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "http://" not in node.value and "https://" not in node.value, (
                    f"literal de URL encontrado em {caminho}: {node.value!r}"
                )


class TestDegradacaoControlada:
    def test_publish_to_api_degrada_controladamente_quando_api_indisponivel(
        self, settings, conformance_report
    ) -> None:
        from pix_compliance.agents.report_consolidator_agent import generate_json, publish_to_api

        report_output = generate_json(conformance_report, [], [])

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("conexão recusada", request=request)

        client = httpx.Client(base_url=settings.api_url, transport=httpx.MockTransport(handler))

        with capture_logs() as logs:
            publish_to_api(settings, report_output, client=client)  # não deve levantar

        eventos_erro = [log for log in logs if log.get("log_level") == "error"]
        assert any(conformance_report.report_id in str(log) for log in eventos_erro)

    def test_consolidate_and_publish_preserva_artefatos_quando_api_indisponivel(
        self, settings, object_store, conformance_report, normativos, regras
    ) -> None:
        from pix_compliance.agents.report_consolidator_agent import consolidate_and_publish

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("conexão recusada", request=request)

        client = httpx.Client(base_url=settings.api_url, transport=httpx.MockTransport(handler))

        resultado = consolidate_and_publish(
            settings, object_store, conformance_report, normativos, regras, client=client
        )

        assert Path(resultado.json_path).exists()
        assert Path(resultado.pdf_path).exists()
        # artefatos também persistidos no ObjectStore, apesar da falha de publicação
        object_store.download(f"reports/{conformance_report.report_id}.json")
        object_store.download(f"reports/{conformance_report.report_id}.pdf")


class TestIntegracaoConformanceValidatorEApiReal:
    """Prova que o agente funciona ponta a ponta contra as duas peças que
    faltavam no momento da implementação original (SPEC-014 foi
    implementado antes de SPEC-011/SPEC-013 existirem, research.md,
    Decisão 0): um `ConformanceReport` produzido pelo Conformance Validator
    Agent de verdade (não construído à mão), publicado via HTTP contra a
    API FastAPI real (não `httpx.MockTransport`) — `fastapi.testclient.
    TestClient` é uma subclasse de `httpx.Client`, compatível com o
    parâmetro `client` já existente de `publish_to_api`/
    `consolidate_and_publish`, sem exigir nenhum servidor real escutando em
    porta."""

    def test_conformance_report_real_e_publicado_na_api_real(
        self, settings, object_store, normativos, regras
    ) -> None:
        from fastapi.testclient import TestClient
        from structlog.testing import capture_logs

        from pix_compliance.agents.conformance_validator_agent import build_conformance_report
        from pix_compliance.agents.report_consolidator_agent import consolidate_and_publish
        from pix_compliance.api.app import app

        # Nenhum normativo aqui tem versão anterior — build_conformance_report
        # classifica tudo como "novo" deterministicamente, sem chamar LLM
        # (SPEC-011, research.md Decisão 4) — cenário 100% real, sem
        # FunctionModel nem dado hand-typed no meio do caminho.
        regras_por_normativo = {
            "norm-tarifas": [regras[0]],
            "norm-seguranca": [regras[1]],
        }
        conformance_report_real = build_conformance_report(
            settings, "report-integracao-real", normativos, regras_por_normativo
        )

        assert all(item.status.value == "novo" for item in conformance_report_real.itens)

        with TestClient(app) as test_client, capture_logs() as logs:
            resultado = consolidate_and_publish(
                settings,
                object_store,
                conformance_report_real,
                normativos,
                regras,
                client=test_client,
            )

        eventos_erro = [log for log in logs if log.get("log_level") == "error"]
        assert eventos_erro == [], "publicação contra a API real não deveria falhar"

        eventos_recebimento = [
            log for log in logs if log.get("event") == "api_relatorio_recebido"
        ]
        assert len(eventos_recebimento) == 1
        assert eventos_recebimento[0]["json_path"] == resultado.json_path

    def test_publish_to_api_via_test_client_real_recebe_200(
        self, settings, conformance_report
    ) -> None:
        from fastapi.testclient import TestClient

        from pix_compliance.agents.report_consolidator_agent import generate_json, publish_to_api
        from pix_compliance.api.app import app

        report_output = generate_json(conformance_report, [], [])

        with TestClient(app) as test_client:
            resposta = test_client.post("/reports", json=report_output.model_dump(mode="json"))
            publish_to_api(settings, report_output, client=test_client)

        assert resposta.status_code == 200
        assert resposta.json()["json_path"] == report_output.json_path


class TestSkillMd:
    def test_skill_md_menciona_requisito_do_desafio(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        conteudo = (repo_root / "skills" / "report-consolidator-skill" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        assert "## Responsabilidade" in conteudo
        assert "## Ferramentas" in conteudo
        assert "## Input" in conteudo
        assert "## Output" in conteudo
        assert "API FastAPI" in conteudo
        assert "cliente HTTP" in conteudo
