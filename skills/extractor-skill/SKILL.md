# Extractor Skill

Documenta o Extractor Agent (SPEC-009), segundo agente do enxame, implementado
em `src/pix_compliance/agents/extractor_agent.py`. Segue o mesmo formato de
quatro seções já estabelecido por `skills/scraper-skill/SKILL.md` (SPEC-008).

## Responsabilidade

O Extractor Agent converte um documento bruto (PDF ou HTML, referenciado por
chave no `ObjectStore`) em um `NormativoItem` validado. Este agente:

- Extrai o texto do documento de forma **determinística** (nunca delegada ao
  LLM) via `extract_pdf_text`/`extract_html_text`.
- Usa o LLM **apenas** para estruturar campos ambíguos que a extração
  determinística não resolve sozinha (ex. limite exato entre dois artigos,
  normalização de uma data escrita por extenso) — nunca para fazer o
  parsing bruto do documento.
- Aplica `guard()` (SPEC-004) sobre todo texto extraído, sempre, antes de
  qualquer chamada ao LLM — este é o primeiro ponto do pipeline do enxame
  em que conteúdo de documento realmente chega a um provider de LLM.

Este agente **não** categoriza regras individuais em categorias de
compliance (`RegraExtraida.categoria`, granularidade por regra — isso
pertence ao Compliance Analyzer, feature futura) e **não** compara versões
de normativos nem decide sobre novo/alterado/revogado (Princípio IV, um
agente/uma responsabilidade).

## Ferramentas

| Ferramenta | Entrada | Saída | Uso pelo agente |
|---|---|---|---|
| `extract_pdf_text` | `bytes` | `str` | Função determinística (não um `@agent.tool`) — sempre executada antes de qualquer chamada ao LLM, para documentos `application/pdf` |
| `extract_html_text` | `bytes` | `str` | Análoga, via `BeautifulSoup`, para documentos `text/html` |
| `guard()` (SPEC-004) | `str` | `GuardedText` | Aplicado sobre o texto extraído, sempre, antes de montar o prompt enviado ao LLM |

Nenhuma das duas funções de extração é registrada como ferramenta que o LLM
decide chamar: não há ambiguidade sobre "se"/"como" extrair — a única
ambiguidade real está na estruturação de campos, que é o papel do LLM.

## Input

```bash
python -m pix_compliance.agents.extractor_agent <object_store_key> <content_type>
```

Dependências injetadas via `RunContext[ExtractorAgentDeps]`:

| Campo | Tipo | Descrição |
|---|---|---|
| `object_store` | `ObjectStore` | Reaproveitado da SPEC-006, usado para ler o documento bruto pela chave |

Parâmetros de execução:

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `object_store_key` | `str` | Chave do documento bruto no `ObjectStore` (ex. produzida por `fetch_normativo`, SPEC-007) |
| `content_type` | `str` | `"application/pdf"` ou `"text/html"` — decide qual função de extração usar |

## Output

`NormativoItem` (modelo Pydantic já existente, `src/pix_compliance/models.py`,
SPEC-002, `ConfigDict(extra="forbid", frozen=True)`) — reaproveitado sem
alteração de contrato. Este agente preenche todos os campos obrigatórios,
incluindo `categoria` (um único valor por documento, atribuído como parte da
estruturação geral via LLM — distinto da categorização de regras individuais,
fora de escopo desta feature).

## Tratamento de erro de dependência externa e resiliência

- **PDF corrompido/malformado**: `extract_pdf_text` levanta
  `PdfExtractionError` (nunca a exceção crua de `pdfplumber`) — o pipeline
  não quebra de forma não controlada.
- **Loop de reparo de validação**: se a estruturação via LLM falhar na
  validação Pydantic de `NormativoItem` na primeira tentativa, uma segunda
  tentativa recebe a mensagem de erro específica do Pydantic e pede
  correção — no máximo duas tentativas, nunca uma terceira. Se a segunda
  também falhar, `ValidationRepairExhaustedError` é levantada. Cada
  tentativa é instrumentada com log estruturado (`tentativa`, `motivo`,
  `sucesso`) — evidência direta de "padrões de orquestração com loops e
  condições".
