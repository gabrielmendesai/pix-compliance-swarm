# Contrato: `src/pix_compliance/agents/report_consolidator_agent.py`

Esta feature não expõe uma API HTTP/CLI de terceiros — o "contrato" é a
interface Python que o CLI deste projeto (e, no futuro, o Orchestrator
Agent) consome. Este módulo é, por sua vez, **cliente** da API FastAPI
(SPEC-013) — não seu servidor.

## Função pública: `generate_json`

```python
def generate_json(
    report: ConformanceReport,
    normativos: list[NormativoItem],
    regras: list[RegraExtraida],
) -> ReportOutput:
    """Monta o ReportOutput (SPEC-002) a partir do ConformanceReport e das
    listas de normativos/regras, e grava o JSON correspondente em
    reports/<report_id>.json (ver research.md, Decisão 3: sempre local,
    antes de qualquer chamada de rede)."""
```

## Função pública: `generate_pdf`

```python
def generate_pdf(
    report: ConformanceReport,
    normativos: list[NormativoItem],
    regras: list[RegraExtraida],
    output_path: Path,
) -> None:
    """Renderiza via reportlab as cinco seções obrigatórias (capa, sumário
    executivo, tabela de normativos, regras por categoria, gap analysis com
    severidade) em output_path (ver data-model.md)."""
```

## Função pública: `upload_artifacts`

```python
def upload_artifacts(
    object_store: ObjectStore, json_path: Path, pdf_path: Path, report_id: str
) -> None:
    """Envia o JSON e o PDF já gerados localmente ao ObjectStore (SPEC-006),
    sob as chaves reports/<report_id>.json e reports/<report_id>.pdf."""
```

## Função pública: `publish_to_api`

```python
def publish_to_api(
    settings: Settings, report_output: ReportOutput, client: httpx.Client | None = None
) -> None:
    """Publica report_output (POST) na API FastAPI (SPEC-013), usando
    settings.api_url como única fonte da URL (FR-005 — nenhum literal de URL
    neste módulo). Captura httpx.TransportError (falha de conexão) e loga um
    erro estruturado sem levantar exceção — degradação controlada (FR-006,
    ver research.md, Decisão 4). Erros de aplicação (HTTP 4xx/5xx) MUST
    propagar via response.raise_for_status(), não são mascarados."""
```

**Pós-condição de degradação controlada**: quando a API está indisponível
(erro de conexão), esta função retorna normalmente (sem levantar), e os
artefatos gerados por `generate_json`/`generate_pdf` permanecem intactos —
nada nesta função os apaga ou invalida.

## Função pública: `consolidate_and_publish`

```python
def consolidate_and_publish(
    settings: Settings,
    object_store: ObjectStore,
    report: ConformanceReport,
    normativos: list[NormativoItem],
    regras: list[RegraExtraida],
    client: httpx.Client | None = None,
) -> ReportOutput:
    """Orquestra, nesta ordem: generate_json -> generate_pdf ->
    upload_artifacts -> publish_to_api. Retorna o ReportOutput
    independentemente do sucesso da publicação HTTP (FR-006)."""
```

## CLI

```bash
python -m pix_compliance.agents.report_consolidator_agent
```

Lê `Settings`, carrega um `ConformanceReport`/`list[NormativoItem]`/
`list[RegraExtraida]` de um caminho fornecido (ou dos fixtures/artefatos já
existentes de execuções anteriores do pipeline), executa
`consolidate_and_publish`, e imprime os caminhos gerados.

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. A partir do corpus completo de fixtures, `generate_json`/`generate_pdf`
   produzem um JSON no formato `ReportOutput` e um PDF com as cinco seções
   exigidas (SC-001).
2. `publish_to_api` faz uma requisição HTTP para `settings.api_url` (nunca
   para um literal hardcoded), verificável via `httpx.MockTransport` (SC-003).
3. Quando `client` simula um erro de conexão (`httpx.ConnectError` via
   `httpx.MockTransport`), `consolidate_and_publish` não levanta exceção, os
   artefatos locais permanecem gravados, e um log de erro estruturado é
   emitido (SC-002).
