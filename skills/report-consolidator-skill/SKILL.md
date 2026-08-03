# Report Consolidator Skill

Documenta o Report Consolidator Agent (SPEC-014), implementado em
`src/pix_compliance/agents/report_consolidator_agent.py`. Segue o mesmo
formato de quatro seções já estabelecido pelos `SKILL.md` anteriores —
embora, como o Knowledge Builder (SPEC-012), este módulo não instancie
`pydantic_ai.Agent`: não há decisão de LLM aqui, apenas consolidação
determinística de dados já produzidos e I/O (arquivo local, `ObjectStore`,
HTTP).

**Este é o agente que cumpre, de forma literal e verificável, o requisito
nominal da seção 2 do desafio técnico original: "invocar uma API FastAPI
como cliente HTTP para ação final".** A função `publish_to_api` é o cliente
HTTP que faz essa chamada — ver a seção Ferramentas abaixo.

## Responsabilidade

O Report Consolidator Agent gera o relatório final do pipeline de
compliance e publica esse resultado na API FastAPI (SPEC-013).

Este agente:

- Gera um relatório em JSON, no formato `ReportOutput` (SPEC-002), a partir
  de um `ConformanceReport` (SPEC-011) e das listas de `NormativoItem`/
  `RegraExtraida` que o originaram.
- Gera um relatório em PDF via `reportlab`, com cinco seções obrigatórias:
  capa, sumário executivo, tabela de normativos coletados, regras agrupadas
  por categoria, e gap analysis com indicação de severidade.
- Envia ambos os artefatos ao `ObjectStore` (SPEC-006).
- **Publica o resultado consolidado na API FastAPI (SPEC-013) como cliente
  HTTP** — a URL da API vem exclusivamente de `settings.api_url`, nunca de
  um literal no código-fonte deste agente. Hardcoded, a URL não poderia ser
  trocada por ambiente (dev/staging/produção) sem editar código, o oposto
  do padrão de configuração já usado em toda outra integração deste
  projeto (Bedrock, Postgres, MinIO).
- Aplica **degradação controlada** quando a API está indisponível: os
  artefatos já gerados (localmente e no `ObjectStore`) permanecem
  persistidos, e o erro é logado de forma clara — o trabalho de geração do
  relatório nunca é perdido só porque a publicação HTTP falhou.

Este agente **não** recategoriza nem revalida dados já produzidos por
features anteriores (Compliance Analyzer, Conformance Validator) — apenas
consolida e publica (Princípio IV, um agente/uma responsabilidade).

## Ferramentas

| Ferramenta | Entrada | Saída | Uso pelo agente |
|---|---|---|---|
| `reportlab` (`SimpleDocTemplate`/`Table`/`Paragraph`) | `ConformanceReport`, `NormativoItem`, `RegraExtraida` | arquivo PDF | Renderiza as cinco seções obrigatórias do relatório |
| `ObjectStore.upload` (SPEC-006) | `key: str`, `data: bytes` | — | Envia o JSON e o PDF gerados ao armazenamento de objetos |
| **`httpx.Client` (cliente HTTP)** | `ReportOutput` (JSON) | resposta HTTP | **Publica o resultado consolidado na API FastAPI (SPEC-013) — requisito literal do desafio original** |

## Input

```python
# Consolida e publica em um único fluxo
consolidate_and_publish(settings, object_store, conformance_report, normativos, regras)

# Ou passo a passo
report_output = generate_json(conformance_report, normativos, regras)
generate_pdf(conformance_report, normativos, regras, Path(report_output.pdf_path))
upload_artifacts(object_store, Path(report_output.json_path), Path(report_output.pdf_path), conformance_report.report_id)
publish_to_api(settings, report_output)
```

Nenhuma dependência via `RunContext` — este módulo recebe `settings` e
`object_store` diretamente como argumentos de função, sem `deps_type` (não
há `Agent` Pydantic AI envolvido).

Configuração relevante (`Settings`):

| Campo | Descrição |
|---|---|
| `api_url` | URL base da API FastAPI (SPEC-013) usada por `publish_to_api` — única fonte da URL, nunca um literal no código |

## Output

`consolidate_and_publish(...) -> ReportOutput` — modelo já existente
(`src/pix_compliance/models.py`, SPEC-002, `ConfigDict(extra="forbid")`),
reaproveitado sem alteração:

| Campo | Tipo | Descrição |
|---|---|---|
| `json_path` | `str` | Caminho local do JSON gerado (`reports/<report_id>.json`) |
| `pdf_path` | `str` | Caminho local do PDF gerado (`reports/<report_id>.pdf`) |
| `total_normativos` | `int` | Contagem de `NormativoItem` consolidados |
| `total_regras` | `int` | Contagem de `RegraExtraida` consolidadas |
| `total_gaps` | `int` | Contagem de `ConformanceItem` com status de gap (não conforme, alterado, revogado) |
| `gerado_em` | `datetime` | Herdado de `ConformanceReport.gerado_em` |

O retorno é sempre um `ReportOutput` válido, independentemente do sucesso da
publicação HTTP — a falha de publicação é logada, nunca propagada como
exceção (degradação controlada).
