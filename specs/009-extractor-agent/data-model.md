# Data Model: Extractor Agent (SPEC-009)

## NormativoItem (output_type — já existe, SPEC-002, sem alteração)

Reaproveitado sem alteração de contrato. Campos relevantes para esta
feature (ver `src/pix_compliance/models.py` para o modelo completo):

| Campo | Tipo | Origem nesta feature |
|---|---|---|
| `id` | `str` | Atribuído pelo agente (ex. derivado da chave do documento no ObjectStore) |
| `titulo` | `str` | Estruturado pelo LLM a partir do texto extraído |
| `tipo` | `TipoNormativo` | Estruturado pelo LLM |
| `numero` | `str` | Estruturado pelo LLM (formato validado pelo modelo já existente) |
| `artigo`/`inciso` | `str \| None` | Estruturado pelo LLM quando a extração determinística não delimita sozinha |
| `texto` | `str` | Texto extraído deterministicamente, já mascarado por `guard()` |
| `data_publicacao`/`data_vigencia` | `date` | Estruturado pelo LLM (inclui normalização de data por extenso) |
| `categoria` | `CategoriaCompliance` | Atribuído pelo LLM como parte da estruturação geral (único valor por documento — ver Assumptions do spec.md) |
| `url_origem` | `HttpUrl` | Propagado do `RawDocument`/referência de origem do documento |
| `hash_conteudo` | `str` | Propagado do hash já calculado na coleta (SPEC-007/SPEC-008) |
| `versao` | `int` | Atribuído pelo agente (ex. `1` para a primeira extração) |

## ExtractorAgentDeps (dependências injetadas via `RunContext`)

`dataclass` concreta (sem `Protocol` — Princípio II: não há uma segunda
implementação de "dependências do Extractor Agent" neste projeto).

| Campo | Tipo | Descrição |
|---|---|---|
| `object_store` | `ObjectStore` | Reaproveitado da SPEC-006, usado para ler o documento bruto pela chave |

## PdfExtractionError (exceção tipada)

Hierarquia de exceção Python própria deste módulo, análoga a
`ConfigurationError` (SPEC-001) e `ScraperTransportError` (SPEC-008), mas
isolada de ambas: cobre falha de parsing determinístico de PDF, não de
configuração nem de transporte de rede.

| Exceção | Quando é levantada | Mensagem |
|---|---|---|
| `PdfExtractionError` | `extract_pdf_text` falha ao processar um PDF corrompido/malformado | Inclui a chave do documento no ObjectStore e a causa original (`from exc`) |

## ValidationRepairExhaustedError (exceção tipada)

| Exceção | Quando é levantada | Mensagem |
|---|---|---|
| `ValidationRepairExhaustedError` | O loop de reparo de validação esgota as duas tentativas sem produzir um `NormativoItem` válido | Inclui o erro de validação Pydantic da última tentativa |

## Funções de extração determinística (contratos internos, não modelos Pydantic)

| Função | Assinatura | Descrição |
|---|---|---|
| `extract_pdf_text` | `(data: bytes) -> str` | Extrai texto de um PDF via `pdfplumber`. Levanta `PdfExtractionError` em falha. |
| `extract_html_text` | `(data: bytes) -> str` | Extrai texto de um HTML via `BeautifulSoup`. |

**Regra de negócio**: nenhuma das duas funções é registrada como
`@agent.tool` — são sempre chamadas diretamente pela função orquestradora
(`run_extractor_agent`), antes de qualquer interação com o LLM, porque não
há decisão a ser tomada sobre "se" ou "como" extrair (Princípio IV): a
única ambiguidade real está na estruturação de campos, que é o papel do
LLM.

## Loop de reparo de validação (mecanismo, não modelo Pydantic)

```
tentativa 1: agent.run_sync(prompt_inicial, deps=deps)
  ├── sucesso → retorna NormativoItem, log (tentativa=1, sucesso=True)
  └── UnexpectedModelBehavior (ValidationError) →
        log (tentativa=1, sucesso=False, motivo=<erro Pydantic>)
        tentativa 2: agent.run_sync(prompt_inicial + erro_pydantic, deps=deps)
          ├── sucesso → retorna NormativoItem, log (tentativa=2, sucesso=True)
          └── UnexpectedModelBehavior (ValidationError) →
                log (tentativa=2, sucesso=False, motivo=<erro Pydantic>)
                raise ValidationRepairExhaustedError (nunca uma 3ª tentativa)
```

Confirmado por spike manual: `Agent(..., retries={"output": 0})` faz
`agent.run_sync` levantar `pydantic_ai.exceptions.UnexpectedModelBehavior`
imediatamente na primeira falha de validação, com `exc.__cause__` sendo o
`pydantic.ValidationError` real (mensagem específica por campo) — exatamente
o texto que FR-006 exige devolver ao modelo na segunda tentativa.
