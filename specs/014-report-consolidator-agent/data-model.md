# Data Model: Report Consolidator Agent (SPEC-014)

Esta feature não introduz nenhum modelo Pydantic novo — reaproveita
integralmente os contratos já existentes (SPEC-002). O único "dado novo"
desta spec é a convenção de composição de entrada (os três tipos já
existentes juntos) e a estrutura das cinco seções do PDF (não um modelo
Pydantic, um artefato de saída).

## ConformanceReport (já existe — SPEC-002, sem alteração)

Reaproveitado como entrada principal — determina status/severidade/gap por
regra.

| Campo | Tipo | Uso nesta feature |
|---|---|---|
| `report_id` | `str` | Usado como nome determinístico dos arquivos locais/`ObjectStore` (`reports/<report_id>.json`, `reports/<report_id>.pdf`) |
| `gerado_em` | `datetime` | Propagado para `ReportOutput.gerado_em` |
| `itens` | `list[ConformanceItem]` | Fonte da seção de gap analysis do PDF (status, severidade, delta, recomendação por regra) |
| `resumo` | `str` | Fonte do sumário executivo do PDF |
| `criticidade_maxima` | `StatusConformidade \| None` | Exibido no sumário executivo do PDF |

## NormativoItem / RegraExtraida (já existem — SPEC-002, sem alteração)

Compostos junto com `ConformanceReport` como entrada da função de
consolidação (ver research.md, Decisão 2) — necessários porque
`ConformanceReport` sozinho não carrega texto/categoria de normativo ou
regra.

| Campo | Uso nesta feature |
|---|---|
| `NormativoItem.titulo`/`numero`/`categoria` | Linhas da tabela de normativos coletados do PDF |
| `RegraExtraida.enunciado`/`categoria`/`obrigatoriedade` | Agrupamento de regras por categoria no PDF |

## ReportOutput (já existe — SPEC-002, sem alteração)

Formato do artefato JSON gerado por esta feature.

| Campo | Valor nesta feature |
|---|---|
| `json_path` | Caminho do JSON gerado (local e/ou `ObjectStore`, mesmo valor de chave) |
| `pdf_path` | Caminho do PDF gerado (idem) |
| `total_normativos` | `len(normativos)` |
| `total_regras` | `len(regras)` |
| `total_gaps` | Contagem de `ConformanceItem` com `status` indicando não conformidade (`não conforme`, `alterado`, `revogado`) |
| `gerado_em` | `ConformanceReport.gerado_em` |

## Convenção: nome de arquivo determinístico

```
json_key = f"reports/{conformance_report.report_id}.json"
pdf_key  = f"reports/{conformance_report.report_id}.pdf"
```

**Regra de negócio**: mesmo `report_id` sempre produz a mesma chave — tanto
no diretório local (`reports/` na raiz do projeto) quanto no `ObjectStore`
(mesma chave, SPEC-006), permitindo reencontrar/reenviar manualmente um
relatório cuja publicação HTTP tenha falhado (edge case de spec.md).

## Estrutura do PDF (artefato de saída, não modelo Pydantic)

| Seção | Conteúdo |
|---|---|
| Capa | Título, `report_id`, `gerado_em` |
| Sumário executivo | `ConformanceReport.resumo`, `criticidade_maxima` |
| Tabela de normativos coletados | Uma linha por `NormativoItem` (`numero`, `titulo`, `categoria`) |
| Regras agrupadas por categoria | `RegraExtraida` agrupadas por `categoria`, com `enunciado`/`obrigatoriedade` |
| Gap analysis com severidade | Uma linha por `ConformanceItem` (`regra_id`, `status`, `severidade`, `delta`, `recomendacao`) |

## Funções públicas (contratos internos, ver contracts/)

| Função | Assinatura | Descrição |
|---|---|---|
| `generate_json` | `(report: ConformanceReport, normativos: list[NormativoItem], regras: list[RegraExtraida]) -> ReportOutput` | Monta o `ReportOutput` e grava o JSON localmente |
| `generate_pdf` | `(report: ConformanceReport, normativos: list[NormativoItem], regras: list[RegraExtraida], output_path: Path) -> None` | Renderiza o PDF (5 seções) via `reportlab` |
| `upload_artifacts` | `(object_store: ObjectStore, json_path: Path, pdf_path: Path, report_id: str) -> None` | Envia ambos os artefatos ao `ObjectStore` |
| `publish_to_api` | `(settings: Settings, report_output: ReportOutput, client: httpx.Client \| None = None) -> None` | Publica o `ReportOutput` na API (`settings.api_url`); nunca levanta em caso de falha de transporte (degradação controlada) |
| `consolidate_and_publish` | `(settings, object_store, report, normativos, regras) -> ReportOutput` | Orquestra as quatro funções acima, nesta ordem |
