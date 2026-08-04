"""Testes do Orchestrator Agent (Harness) e agendamento (SPEC-015).

Escritos antes de `orchestrator_agent.py` existir (Princípio IX da
constituição). Reaproveita `mock_bcb_server` (`tests/conftest.py`) e
`running_mcp_server` (`tests/test_scraper_agent.py`) para exercitar o
pipeline completo real — scrape via MCP, extract, compliance_analyzer,
knowledge_builder, conformance_validator, report_consolidator — com
`LLM_PROVIDER=offline` e `FunctionModel` determinístico por etapa, nunca
uma chamada real ao Bedrock.
"""

import asyncio
import importlib
import re
from datetime import UTC, datetime

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from structlog.testing import capture_logs

from tests.conftest import REQUIRED_ENV
from tests.test_scraper_agent import (  # noqa: F401
    RunningMcpServer,
    _make_collect_all_decision,
    running_mcp_server,
)

_FAKE_HASH = "a" * 64


_VOLATILE_ENV_KEYS = {"BCB_BASE_URL", "MCP_SCRAPER_HOST", "MCP_SCRAPER_PORT"}


def _reload_settings(monkeypatch):
    """`orchestrator_agent.run_pipeline` sempre lê o singleton
    `pix_compliance.config.settings` (nunca um `settings` passado pelo
    chamador — é assim que garante o mesmo handler para CLI e scheduler,
    FR-008). Reaplica `REQUIRED_ENV` (exceto as três chaves "voláteis" que
    `running_mcp_server`, reaproveitada de `test_scraper_agent.py`, define
    dinamicamente — porta livre e URL do `mock_bcb_server`) imediatamente
    antes de recarregar: como fixtures compartilham o mesmo `monkeypatch`
    da execução do teste, a ordem de aplicação entre a REQUIRED_ENV deste
    arquivo e a de `running_mcp_server` não é garantida — reaplicar aqui
    garante que os demais valores (ex. `API_URL`, também presente nas duas
    REQUIRED_ENV) sempre vençam por último, sem sobrescrever a porta/URL
    dinâmicas que a fixture MCP já configurou (mesmo padrão de reload já
    usado em `tests/test_knowledge_builder_agent.py`)."""
    for key, value in REQUIRED_ENV.items():
        if key not in _VOLATILE_ENV_KEYS:
            monkeypatch.setenv(key, value)

    import pix_compliance.config as config_module

    importlib.reload(config_module)
    return config_module.settings


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(autouse=True)
def _reports_dir_isolado(tmp_path, monkeypatch):
    """Isola `reports/` (gravado pelo Report Consolidator via caminho
    relativo, SPEC-014) em `tmp_path` por teste — mesma convenção de
    `tests/test_report_consolidator_agent.py`, evita poluir o diretório de
    trabalho real do repositório com artefatos de execuções de teste."""
    monkeypatch.chdir(tmp_path)


def _generic_valid_extractor_decision():
    """`FunctionModel` do Extractor que produz um `NormativoItem` válido e
    único por chamada — não depende do conteúdo real do documento
    (irrelevante para provar a orquestração)."""
    contador = {"n": 0}

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        contador["n"] += 1
        n = contador["n"]
        output_tool_name = info.output_tools[0].name
        args = {
            "id": f"orch-teste-doc-{n}",
            "titulo": f"Normativo de teste do orchestrator {n}",
            "tipo": "Resolução BCB",
            "numero": f"{900 + n}/2024",
            "texto": f"Texto de teste do documento {n} do pipeline do Orchestrator.",
            "data_publicacao": "2024-01-01",
            "data_vigencia": "2024-01-01",
            "categoria": "liquidação",
            "url_origem": "https://mock-bcb.local/normativo",
            "hash_conteudo": _FAKE_HASH,
            "versao": 1,
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    return decide


def _echo_normativo_id_analyzer_decision():
    """`FunctionModel` do Compliance Analyzer que ecoa o `normativo_id`
    real presente no prompt (via `UserPromptPart`) — sem isso, o
    `normativo_id` gerado por um `TestModel` puro não bateria com nenhum
    `NormativoItem` real, e o Conformance Validator não encontraria nada
    para agrupar (mesma armadilha já identificada na integração da
    SPEC-013 com `LLM_PROVIDER=offline`)."""

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt_text = ""
        for message in messages:
            for part in message.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    prompt_text = part.content
        match = re.search(r"id '([^']+)'", prompt_text)
        normativo_id = match.group(1) if match else "desconhecido"

        output_tool_name = info.output_tools[0].name
        args = {
            "response": [
                {
                    "regra_id": f"{normativo_id}-r1",
                    "normativo_id": normativo_id,
                    "categoria": "liquidação",
                    "enunciado": "Enunciado de teste extraído pelo Orchestrator.",
                    "obrigatoriedade": "obrigatório",
                    "atores_afetados": ["participante"],
                    "confianca": 0.9,
                }
            ]
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    return decide


class TestPipelineCompleto:
    def test_run_pipeline_completa_com_sucesso_e_etapas_na_ordem_esperada(
        self, running_mcp_server: RunningMcpServer, monkeypatch
    ) -> None:
        _reload_settings(monkeypatch)
        from pix_compliance.agents.orchestrator_agent import run_pipeline
        from pix_compliance.models import PipelineRequest

        request = PipelineRequest(pipeline_id="orch-teste-1", fontes=["https://mock-bcb.local/"])

        resultado = asyncio.run(
            run_pipeline(
                request,
                bootstrap_local_servers=False,
                model_scraper=FunctionModel(_make_collect_all_decision()),
                model_extractor=FunctionModel(_generic_valid_extractor_decision()),
                model_analyzer=FunctionModel(_echo_normativo_id_analyzer_decision()),
            )
        )

        assert resultado.sucesso is True
        nomes_etapas = [etapa.nome for etapa in resultado.etapas]
        assert nomes_etapas == [
            "scrape",
            "extract",
            "compliance_analyzer",
            "knowledge_builder",
            "conformance_validator",
            "report_consolidator",
        ]
        assert nomes_etapas.index("scrape") < nomes_etapas.index("extract")
        assert nomes_etapas.index("extract") < nomes_etapas.index("compliance_analyzer")
        assert nomes_etapas.index("extract") < nomes_etapas.index("knowledge_builder")
        assert nomes_etapas.index("compliance_analyzer") < nomes_etapas.index(
            "conformance_validator"
        )
        assert all(etapa.status == "sucesso" for etapa in resultado.etapas)

    def test_compliance_analyzer_e_knowledge_builder_rodam_em_paralelo(
        self, running_mcp_server: RunningMcpServer, monkeypatch
    ) -> None:
        _reload_settings(monkeypatch)
        import pix_compliance.agents.orchestrator_agent as orch_module
        from pix_compliance.models import PipelineRequest

        contador = {"em_execucao": 0, "pico": 0}
        lock = asyncio.Lock()

        analyzer_original = orch_module.analyze_batch
        kb_original = orch_module.index_normativos

        async def analyzer_instrumentado(settings, normativos, model=None):
            async with lock:
                contador["em_execucao"] += 1
                contador["pico"] = max(contador["pico"], contador["em_execucao"])
            await asyncio.sleep(0.05)
            resultado = await analyzer_original(settings, normativos, model)
            async with lock:
                contador["em_execucao"] -= 1
            return resultado

        def kb_instrumentado(settings, vector_store, normativos):
            asyncio.run(_marcar_execucao(lock, contador))
            return kb_original(settings, vector_store, normativos)

        async def _marcar_execucao(lock, contador):
            async with lock:
                contador["em_execucao"] += 1
                contador["pico"] = max(contador["pico"], contador["em_execucao"])

        monkeypatch.setattr(orch_module, "analyze_batch", analyzer_instrumentado)
        monkeypatch.setattr(orch_module, "index_normativos", kb_instrumentado)

        request = PipelineRequest(pipeline_id="orch-teste-paralelo", fontes=["https://mock-bcb.local/"])
        resultado = asyncio.run(
            orch_module.run_pipeline(
                request,
                bootstrap_local_servers=False,
                model_scraper=FunctionModel(_make_collect_all_decision()),
                model_extractor=FunctionModel(_generic_valid_extractor_decision()),
                model_analyzer=FunctionModel(_echo_normativo_id_analyzer_decision()),
            )
        )

        assert resultado.sucesso is True
        assert contador["pico"] >= 2

    def test_extractor_loop_de_reparo_e_acionado_dentro_do_fluxo_maior(
        self, running_mcp_server: RunningMcpServer, monkeypatch
    ) -> None:
        _reload_settings(monkeypatch)
        from pix_compliance.agents.orchestrator_agent import run_pipeline
        from pix_compliance.models import PipelineRequest

        estado = {"chamadas": 0}

        def decisao_falha_depois_sucede(
            messages: list[ModelMessage], info: AgentInfo
        ) -> ModelResponse:
            estado["chamadas"] += 1
            output_tool_name = info.output_tools[0].name
            if estado["chamadas"] % 2 == 1:
                # Primeira tentativa por documento: dado inválido, aciona o
                # loop de reparo já existente no Extractor (SPEC-009).
                return ModelResponse(
                    parts=[ToolCallPart(tool_name=output_tool_name, args={"titulo": "incompleto"})]
                )
            args = {
                "id": f"orch-teste-reparo-{estado['chamadas']}",
                "titulo": "Normativo reparado",
                "tipo": "Resolução BCB",
                "numero": f"{950 + estado['chamadas']}/2024",
                "texto": "Texto reparado na segunda tentativa.",
                "data_publicacao": "2024-01-01",
                "data_vigencia": "2024-01-01",
                "categoria": "liquidação",
                "url_origem": "https://mock-bcb.local/normativo",
                "hash_conteudo": _FAKE_HASH,
                "versao": 1,
            }
            return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

        request = PipelineRequest(pipeline_id="orch-teste-reparo", fontes=["https://mock-bcb.local/"])
        resultado = asyncio.run(
            run_pipeline(
                request,
                bootstrap_local_servers=False,
                model_scraper=FunctionModel(_make_collect_all_decision()),
                model_extractor=FunctionModel(decisao_falha_depois_sucede),
                model_analyzer=FunctionModel(_echo_normativo_id_analyzer_decision()),
            )
        )

        assert resultado.sucesso is True
        assert estado["chamadas"] >= 2


class TestObservabilidade:
    """SPEC-017 (User Story 3, FR-006/FR-007): audita se `correlation_id`
    aparece de ponta a ponta nos logs, incluindo no servidor MCP separado
    (não só dentro do processo do Orchestrator), e se os contadores
    agregados por etapa são emitidos. Usa `bootstrap_local_servers=True`
    (não `running_mcp_server`, que sobe o MCP num processo/thread própria
    do teste, fora do alcance da correção de propagação desta feature) —
    mesmo caminho de `make run` (quickstart.md, Cenário 5)."""

    def test_pipeline_etapa_concluida_carrega_mesmo_correlation_id_e_contadores(
        self, mock_bcb_server, monkeypatch, capsys
    ) -> None:
        import json

        import structlog

        from tests.conftest import free_port

        monkeypatch.setenv("BCB_BASE_URL", mock_bcb_server.base_url)
        monkeypatch.setenv("MCP_SCRAPER_HOST", "127.0.0.1")
        monkeypatch.setenv("MCP_SCRAPER_PORT", str(free_port()))
        _reload_settings(monkeypatch)

        from pix_compliance.agents.orchestrator_agent import run_pipeline
        from pix_compliance.models import PipelineRequest

        request = PipelineRequest(pipeline_id="obs-teste", fontes=["https://mock-bcb.local/"])

        # `capture_logs()` (structlog.testing) substitui a cadeia de
        # processadores inteira por um único captor — descartaria
        # `merge_contextvars`, apagando o `correlation_id` que este teste
        # precisa inspecionar. `capsys` + uma config local equivalente à de
        # produção resolve isso — mas com `cache_logger_on_first_use=False`
        # (diferente de `configure_logging()` real): o logger de módulo do
        # servidor MCP (`mcp_servers/scraper_sse/server.py`) é tocado pela
        # primeira vez aqui (`bootstrap_local_servers=True`), e cachear seu
        # bound logger permanentemente vazaria esta config para os testes
        # de `test_scraper_mcp_server.py` (que dependem de `capture_logs()`
        # funcionar), rodados depois na mesma sessão do pytest.
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            cache_logger_on_first_use=False,
        )
        try:
            resultado = asyncio.run(
                run_pipeline(
                    request,
                    bootstrap_local_servers=True,
                    model_scraper=FunctionModel(_make_collect_all_decision()),
                    model_extractor=FunctionModel(_generic_valid_extractor_decision()),
                    model_analyzer=FunctionModel(_echo_normativo_id_analyzer_decision()),
                )
            )
        finally:
            structlog.reset_defaults()
        linhas = capsys.readouterr().out.strip().splitlines()
        logs = [json.loads(linha) for linha in linhas]

        assert resultado.sucesso is True

        eventos_etapa = [log for log in logs if log["event"] == "pipeline_etapa_concluida"]
        nomes = [log["nome"] for log in eventos_etapa]
        assert nomes == [
            "scrape",
            "extract",
            "compliance_analyzer",
            "knowledge_builder",
            "conformance_validator",
            "report_consolidator",
        ]

        correlation_ids = {log["correlation_id"] for log in eventos_etapa}
        assert len(correlation_ids) == 1
        (correlation_id,) = correlation_ids

        por_nome = {log["nome"]: log for log in eventos_etapa}
        assert por_nome["scrape"]["contadores"]["documentos_coletados"] == 4
        assert por_nome["report_consolidator"]["contadores"] is None

        eventos_mcp = [log for log in logs if log["event"] == "mcp_tool_chamada"]
        assert eventos_mcp, "esperava pelo menos uma chamada de ferramenta MCP logada"
        assert all(log["correlation_id"] == correlation_id for log in eventos_mcp)


class TestPoliticaDeFalha:
    def test_falha_em_etapa_degradavel_nao_aborta_pipeline(
        self, running_mcp_server: RunningMcpServer, monkeypatch
    ) -> None:
        _reload_settings(monkeypatch)
        import pix_compliance.agents.orchestrator_agent as orch_module
        from pix_compliance.models import PipelineRequest

        def index_normativos_que_falha(settings, vector_store, normativos):
            raise RuntimeError("falha simulada no knowledge builder")

        monkeypatch.setattr(orch_module, "index_normativos", index_normativos_que_falha)

        request = PipelineRequest(pipeline_id="orch-teste-degradavel", fontes=["https://mock-bcb.local/"])
        resultado = asyncio.run(
            orch_module.run_pipeline(
                request,
                bootstrap_local_servers=False,
                model_scraper=FunctionModel(_make_collect_all_decision()),
                model_extractor=FunctionModel(_generic_valid_extractor_decision()),
                model_analyzer=FunctionModel(_echo_normativo_id_analyzer_decision()),
            )
        )

        assert resultado.sucesso is True
        etapa_kb = next(e for e in resultado.etapas if e.nome == "knowledge_builder")
        assert etapa_kb.status == "degradada"

    def test_falha_em_etapa_fatal_aborta_pipeline_com_mensagem_clara(
        self, running_mcp_server: RunningMcpServer, monkeypatch
    ) -> None:
        _reload_settings(monkeypatch)
        import pix_compliance.agents.orchestrator_agent as orch_module
        from pix_compliance.models import PipelineRequest

        async def analyze_batch_que_falha(settings, normativos, model=None):
            raise RuntimeError("falha simulada no compliance analyzer")

        monkeypatch.setattr(orch_module, "analyze_batch", analyze_batch_que_falha)

        request = PipelineRequest(pipeline_id="orch-teste-fatal", fontes=["https://mock-bcb.local/"])
        resultado = asyncio.run(
            orch_module.run_pipeline(
                request,
                bootstrap_local_servers=False,
                model_scraper=FunctionModel(_make_collect_all_decision()),
                model_extractor=FunctionModel(_generic_valid_extractor_decision()),
            )
        )

        assert resultado.sucesso is False
        assert "compliance_analyzer" in resultado.erro
        nomes_etapas = [etapa.nome for etapa in resultado.etapas]
        assert "conformance_validator" not in nomes_etapas
        assert "report_consolidator" not in nomes_etapas


class TestRastreabilidadeEDuracao:
    def test_todos_os_logs_de_uma_execucao_carregam_o_mesmo_correlation_id(
        self, running_mcp_server: RunningMcpServer, monkeypatch
    ) -> None:
        _reload_settings(monkeypatch)
        from pix_compliance.agents.orchestrator_agent import run_pipeline
        from pix_compliance.models import PipelineRequest

        request = PipelineRequest(pipeline_id="orch-teste-correlation", fontes=["https://mock-bcb.local/"])

        # `capture_logs()` substitui a cadeia de processors configurada —
        # sem reincluir `merge_contextvars` explicitamente aqui, o
        # `correlation_id` (vinculado via contextvars por
        # `bind_run_correlation_id()`) não apareceria nos eventos
        # capturados, mesmo estando de fato presente no contexto.
        import structlog.contextvars

        with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as logs:
            resultado = asyncio.run(
                run_pipeline(
                    request,
                    bootstrap_local_servers=False,
                    model_scraper=FunctionModel(_make_collect_all_decision()),
                    model_extractor=FunctionModel(_generic_valid_extractor_decision()),
                    model_analyzer=FunctionModel(_echo_normativo_id_analyzer_decision()),
                )
            )

        assert resultado.sucesso is True
        correlation_ids = {log.get("correlation_id") for log in logs if "correlation_id" in log}
        assert len(correlation_ids) == 1
        assert None not in correlation_ids

    def test_pipeline_result_expõe_duracao_total_e_por_etapa(
        self, running_mcp_server: RunningMcpServer, monkeypatch
    ) -> None:
        _reload_settings(monkeypatch)
        from pix_compliance.agents.orchestrator_agent import run_pipeline
        from pix_compliance.models import PipelineRequest

        request = PipelineRequest(pipeline_id="orch-teste-duracao", fontes=["https://mock-bcb.local/"])
        resultado = asyncio.run(
            run_pipeline(
                request,
                bootstrap_local_servers=False,
                model_scraper=FunctionModel(_make_collect_all_decision()),
                model_extractor=FunctionModel(_generic_valid_extractor_decision()),
                model_analyzer=FunctionModel(_echo_normativo_id_analyzer_decision()),
            )
        )

        assert resultado.concluido_em >= resultado.iniciado_em
        assert len(resultado.etapas) > 0
        assert all(etapa.duracao_segundos >= 0 for etapa in resultado.etapas)


class TestLockEAgendamento:
    def test_duas_execucoes_simultaneas_segunda_e_rejeitada_pelo_lock(
        self, running_mcp_server: RunningMcpServer, monkeypatch
    ) -> None:
        _reload_settings(monkeypatch)
        from pix_compliance.agents.orchestrator_agent import run_pipeline
        from pix_compliance.models import PipelineRequest

        request = PipelineRequest(pipeline_id="orch-teste-lock", fontes=["https://mock-bcb.local/"])
        kwargs = dict(
            bootstrap_local_servers=False,
            model_scraper=FunctionModel(_make_collect_all_decision()),
            model_extractor=FunctionModel(_generic_valid_extractor_decision()),
            model_analyzer=FunctionModel(_echo_normativo_id_analyzer_decision()),
        )

        async def _disparar_duas():
            return await asyncio.gather(
                run_pipeline(request, **kwargs), run_pipeline(request, **kwargs)
            )

        resultado_a, resultado_b = asyncio.run(_disparar_duas())

        sucessos = [r for r in (resultado_a, resultado_b) if r.sucesso]
        rejeitados = [r for r in (resultado_a, resultado_b) if not r.sucesso]
        assert len(sucessos) == 1
        assert len(rejeitados) == 1
        assert "em execução" in rejeitados[0].erro
        assert rejeitados[0].etapas == []

    def test_scheduler_dispara_run_pipeline_mais_de_uma_vez_automaticamente(
        self, monkeypatch
    ) -> None:
        # CronTrigger tem granularidade mínima de 1 minuto — usar um
        # IntervalTrigger curto aqui é puramente para tornar o teste rápido
        # (research.md, Decisão 7); `start_scheduler` ainda registra
        # exatamente `run_pipeline` como o job, o que este teste também
        # comprova via a espionagem abaixo.
        from apscheduler.triggers.interval import IntervalTrigger

        settings = _reload_settings(monkeypatch)
        import pix_compliance.agents.orchestrator_agent as orch_module

        contador = {"chamadas": 0}

        async def run_pipeline_espiado(request, **kwargs):
            contador["chamadas"] += 1
            from pix_compliance.models import PipelineResult

            return PipelineResult(
                pipeline_id=request.pipeline_id,
                sucesso=True,
                iniciado_em=datetime.now(UTC),
                concluido_em=datetime.now(UTC),
            )

        monkeypatch.setattr(orch_module, "run_pipeline", run_pipeline_espiado)

        async def _rodar_por_alguns_segundos():
            scheduler = orch_module.start_scheduler(settings, trigger=IntervalTrigger(seconds=1))
            await asyncio.sleep(2.5)
            scheduler.shutdown(wait=False)

        asyncio.run(_rodar_por_alguns_segundos())

        assert contador["chamadas"] >= 2

    def test_eventbridge_snippet_referencia_o_mesmo_entrypoint(self) -> None:
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        conteudo = (repo_root / "docs" / "aws" / "eventbridge-schedule.tf").read_text(
            encoding="utf-8"
        )

        assert "orchestrator_agent" in conteudo
        assert "run_pipeline" in conteudo
