"""Cobre todos os modelos de domínio Pydantic v2 definidos em SPEC-002.

Cada teste prova, para o modelo correspondente, o caminho feliz e pelo menos
um caso de rejeição de cada validador não trivial (data_vigencia, hash,
texto vazio, categoria fora do vocabulário, faixa numérica, extra="forbid").
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from pix_compliance.models import (
    MODELOS_PUBLICOS,
    CategoriaCompliance,
    ConformanceItem,
    ConformanceReport,
    EtapaMetric,
    NormativoItem,
    Obrigatoriedade,
    PipelineRequest,
    PipelineResult,
    RawDocument,
    RegraExtraida,
    ReportOutput,
    ScrapeResult,
    SearchQuery,
    SearchResult,
    StatusConformidade,
    TipoNormativo,
)

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "docs" / "schemas"

HASH_VALIDO = "a" * 64


def _normativo_valido(**overrides: object) -> dict:
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "titulo": "Resolução sobre tarifas do PIX",
        "tipo": TipoNormativo.RESOLUCAO_BCB,
        "numero": "123/2024",
        "texto": "Texto do normativo com regras de tarifação.",
        "data_publicacao": date(2024, 1, 1),
        "data_vigencia": date(2024, 1, 1),
        "categoria": CategoriaCompliance.TARIFAS,
        "url_origem": "https://www.bcb.gov.br/normativos/123",
        "hash_conteudo": HASH_VALIDO,
        "versao": 1,
    }
    base.update(overrides)
    return base


def _regra_valida(**overrides: object) -> dict:
    base = {
        "regra_id": "22222222-2222-2222-2222-222222222222",
        "normativo_id": "11111111-1111-1111-1111-111111111111",
        "categoria": CategoriaCompliance.TARIFAS,
        "enunciado": "Toda instituição participante deve informar tarifas.",
        "obrigatoriedade": Obrigatoriedade.OBRIGATORIO,
        "atores_afetados": ["PSP"],
        "confianca": 0.9,
    }
    base.update(overrides)
    return base


class TestNormativoItem:
    def test_happy_path(self):
        item = NormativoItem(**_normativo_valido())
        assert item.tipo == TipoNormativo.RESOLUCAO_BCB
        assert item.categoria == CategoriaCompliance.TARIFAS
        assert item.hash_conteudo == HASH_VALIDO

    def test_data_vigencia_igual_publicacao_e_aceita(self):
        item = NormativoItem(
            **_normativo_valido(data_publicacao=date(2024, 5, 1), data_vigencia=date(2024, 5, 1))
        )
        assert item.data_vigencia == item.data_publicacao

    def test_data_vigencia_anterior_publicacao_e_rejeitada(self):
        with pytest.raises(ValidationError, match="data_vigencia"):
            NormativoItem(
                **_normativo_valido(
                    data_publicacao=date(2024, 6, 1), data_vigencia=date(2024, 1, 1)
                )
            )

    def test_hash_conteudo_malformado_e_rejeitado(self):
        with pytest.raises(ValidationError, match="hash_conteudo"):
            NormativoItem(**_normativo_valido(hash_conteudo="nao-e-um-hash"))

    def test_texto_vazio_e_rejeitado(self):
        with pytest.raises(ValidationError):
            NormativoItem(**_normativo_valido(texto="   "))

    def test_texto_com_espacos_redundantes_e_normalizado(self):
        item = NormativoItem(**_normativo_valido(texto="Texto  com   espaços\n\nredundantes"))
        assert item.texto == "Texto com espaços redundantes"

    def test_numero_fora_do_formato_e_rejeitado(self):
        with pytest.raises(ValidationError, match="numero"):
            NormativoItem(**_normativo_valido(numero="abc"))

    def test_categoria_fora_do_vocabulario_e_rejeitada(self):
        with pytest.raises(ValidationError):
            NormativoItem(**_normativo_valido(categoria="outra-categoria-qualquer"))

    def test_instancia_e_imutavel(self):
        item = NormativoItem(**_normativo_valido())
        with pytest.raises(ValidationError):
            item.versao = 2

    def test_campo_extra_e_rejeitado(self):
        with pytest.raises(ValidationError):
            NormativoItem(**_normativo_valido(foo="bar"))


class TestRegraExtraida:
    def test_happy_path(self):
        regra = RegraExtraida(**_regra_valida())
        assert regra.obrigatoriedade == Obrigatoriedade.OBRIGATORIO

    def test_categoria_case_insensitive_e_coagida(self):
        regra = RegraExtraida(**_regra_valida(categoria="Tarifas"))
        assert regra.categoria == CategoriaCompliance.TARIFAS

    def test_categoria_fora_do_vocabulario_e_rejeitada(self):
        with pytest.raises(ValidationError):
            RegraExtraida(**_regra_valida(categoria="inexistente"))

    def test_confianca_fora_da_faixa_e_rejeitada(self):
        with pytest.raises(ValidationError):
            RegraExtraida(**_regra_valida(confianca=1.5))
        with pytest.raises(ValidationError):
            RegraExtraida(**_regra_valida(confianca=-0.1))

    def test_revisao_humana_necessaria_default_e_false(self):
        regra = RegraExtraida(**_regra_valida())
        assert regra.revisao_humana_necessaria is False

    def test_revisao_humana_necessaria_roundtrip_sem_perda(self):
        regra = RegraExtraida(**_regra_valida(revisao_humana_necessaria=True))
        dump = regra.model_dump()
        assert RegraExtraida.model_validate(dump) == regra
        assert dump["revisao_humana_necessaria"] is True

    def test_regra_extraida_extra_field_e_rejeitado(self):
        with pytest.raises(ValidationError):
            RegraExtraida(**_regra_valida(foo="bar"))


class TestConformanceItemReport:
    def test_conformance_report_agrega_itens_corretamente(self):
        item = ConformanceItem(
            regra_id="22222222-2222-2222-2222-222222222222",
            status=StatusConformidade.CONFORME,
            severidade=0.2,
        )
        report = ConformanceReport(
            report_id="33333333-3333-3333-3333-333333333333",
            gerado_em=datetime(2024, 1, 1, tzinfo=UTC),
            itens=[item],
            resumo="Relatório de conformidade",
            criticidade_maxima=StatusConformidade.CONFORME,
        )
        assert report.itens == [item]
        assert report.criticidade_maxima == StatusConformidade.CONFORME

    def test_severidade_fora_da_faixa_e_rejeitada(self):
        with pytest.raises(ValidationError):
            ConformanceItem(
                regra_id="22222222-2222-2222-2222-222222222222",
                status=StatusConformidade.CONFORME,
                severidade=1.5,
            )

    def test_status_fora_do_vocabulario_e_rejeitado(self):
        with pytest.raises(ValidationError):
            ConformanceItem(
                regra_id="22222222-2222-2222-2222-222222222222",
                status="invalido",
                severidade=0.5,
            )


class TestSearchAndReportAndPipeline:
    def test_search_query_e_result_happy_path(self):
        query = SearchQuery(query="tarifas PIX", top_k=5)
        result = SearchResult(
            score=0.8,
            trecho="trecho encontrado",
            normativo_id="11111111-1111-1111-1111-111111111111",
        )
        assert query.top_k == 5
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.parametrize(
        "modelo,kwargs",
        [
            (SearchQuery, {"query": "x", "top_k": 1}),
            (
                SearchResult,
                {
                    "score": 0.5,
                    "trecho": "x",
                    "normativo_id": "11111111-1111-1111-1111-111111111111",
                },
            ),
            (
                ReportOutput,
                {
                    "json_path": "a.json",
                    "pdf_path": "a.pdf",
                    "total_normativos": 1,
                    "total_regras": 1,
                    "total_gaps": 0,
                    "gerado_em": datetime(2024, 1, 1, tzinfo=UTC),
                },
            ),
            (
                PipelineRequest,
                {"pipeline_id": "p1", "fontes": ["https://bcb.gov.br/normativos"]},
            ),
            (
                PipelineResult,
                {
                    "pipeline_id": "p1",
                    "sucesso": True,
                    "iniciado_em": datetime(2024, 1, 1, tzinfo=UTC),
                    "concluido_em": datetime(2024, 1, 1, tzinfo=UTC),
                },
            ),
            (
                RawDocument,
                {
                    "source_uri": "https://bcb.gov.br/x",
                    "content_type": "text/html",
                    "bytes_ref": "minio://bucket/key",
                    "hash_conteudo": HASH_VALIDO,
                    "coletado_em": datetime(2024, 1, 1, tzinfo=UTC),
                },
            ),
        ],
    )
    def test_extra_field_e_rejeitado(self, modelo: type[BaseModel], kwargs: dict):
        with pytest.raises(ValidationError):
            modelo.model_validate({**kwargs, "foo": "bar"})

    def test_pipeline_request_result_roundtrip_sem_perda(self):
        req = PipelineRequest(pipeline_id="p1", fontes=["https://bcb.gov.br/normativos"])
        req_dump = req.model_dump()
        assert PipelineRequest.model_validate(req_dump) == req

        report = ReportOutput(
            json_path="a.json",
            pdf_path="a.pdf",
            total_normativos=1,
            total_regras=2,
            total_gaps=0,
            gerado_em=datetime(2024, 1, 1, tzinfo=UTC),
        )
        result = PipelineResult(
            pipeline_id="p1",
            sucesso=True,
            report=report,
            iniciado_em=datetime(2024, 1, 1, tzinfo=UTC),
            concluido_em=datetime(2024, 1, 2, tzinfo=UTC),
        )
        result_dump = result.model_dump()
        assert PipelineResult.model_validate(result_dump) == result


class TestEtapaMetric:
    """SPEC-017 (FR-007): `contadores` é aditivo — `EtapaMetric` sem esse
    campo continua válido (default `None`), e o campo aceita um dict de
    contadores agregados por etapa quando presente."""

    def test_contadores_e_opcional_com_default_none(self):
        etapa = EtapaMetric(nome="scrape", duracao_segundos=1.0, status="sucesso")
        assert etapa.contadores is None

    def test_contadores_aceita_dict_de_inteiros_por_etapa(self):
        etapa = EtapaMetric(
            nome="compliance_analyzer",
            duracao_segundos=2.5,
            status="sucesso",
            contadores={"regras_extraidas": 12, "tokens_consumidos": 480},
        )
        assert etapa.contadores == {"regras_extraidas": 12, "tokens_consumidos": 480}


class TestScrapeResult:
    """SPEC-008: saída do Scraper Agent — apenas dados de coleta, sem campo
    de conteúdo estruturado/extraído."""

    def _raw_document(self) -> RawDocument:
        return RawDocument(
            source_uri="https://bcb.gov.br/x",
            content_type="text/html",
            bytes_ref="minio://bucket/key",
            hash_conteudo=HASH_VALIDO,
            coletado_em=datetime(2024, 1, 1, tzinfo=UTC),
        )

    def test_roundtrip_sem_perda(self):
        resultado = ScrapeResult(
            documentos=[self._raw_document()],
            total_coletado=1,
            executado_em=datetime(2024, 1, 1, tzinfo=UTC),
        )
        dump = resultado.model_dump()
        assert ScrapeResult.model_validate(dump) == resultado

    def test_lista_vazia_e_valida(self):
        resultado = ScrapeResult(
            documentos=[], total_coletado=0, executado_em=datetime(2024, 1, 1, tzinfo=UTC)
        )
        assert resultado.documentos == []

    def test_extra_field_e_rejeitado(self):
        with pytest.raises(ValidationError):
            ScrapeResult.model_validate(
                {
                    "documentos": [],
                    "total_coletado": 0,
                    "executado_em": datetime(2024, 1, 1, tzinfo=UTC),
                    "foo": "bar",
                }
            )

    def test_total_coletado_negativo_e_rejeitado(self):
        with pytest.raises(ValidationError):
            ScrapeResult(
                documentos=[], total_coletado=-1, executado_em=datetime(2024, 1, 1, tzinfo=UTC)
            )


class TestJsonSchemaExport:
    """Prova o contrato de contracts/schemas-contract.md: um schema por modelo,
    persistido em docs/schemas/ e sem divergência entre código e arquivo."""

    def test_todos_os_modelos_exportam_schema_sem_divergencia(self):
        SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
        for modelo in MODELOS_PUBLICOS:
            schema = modelo.model_json_schema()
            assert schema.get("additionalProperties") is False

            schema_path = SCHEMAS_DIR / f"{modelo.__name__}.schema.json"
            serializado = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

            if not schema_path.exists() or schema_path.read_text(encoding="utf-8") != serializado:
                schema_path.write_text(serializado, encoding="utf-8")

            assert schema_path.read_text(encoding="utf-8") == serializado
