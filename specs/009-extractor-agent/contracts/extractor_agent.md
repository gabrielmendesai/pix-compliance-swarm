# Contrato: `src/pix_compliance/agents/extractor_agent.py`

Esta feature não expõe uma API HTTP/CLI de terceiros — o "contrato" é a
interface Python que o CLI deste projeto (e, no futuro, o orquestrador do
enxame) consome, seguindo o mesmo formato de `contracts/scraper_agent.md`
(SPEC-008).

## Funções de extração determinística (ver data-model.md)

```python
def extract_pdf_text(data: bytes) -> str:
    """Extrai texto de um PDF via pdfplumber. Levanta PdfExtractionError
    em caso de arquivo corrompido/malformado."""

def extract_html_text(data: bytes) -> str:
    """Extrai texto de um HTML via BeautifulSoup."""
```

## Função pública: `build_extractor_agent`

```python
def build_extractor_agent(
    settings: Settings, model: Model | None = None
) -> Agent[ExtractorAgentDeps, NormativoItem]:
    """Monta o Agent com deps_type=ExtractorAgentDeps, output_type=NormativoItem,
    retries={"output": 0} (o loop de reparo é escrito à mão em
    run_extractor_agent, não delegado ao retry automático da biblioteca).
    O modelo é selecionado por settings.llm_provider, mesmo padrão de
    _build_model já estabelecido em scraper_agent.py (SPEC-008)."""
```

## Função pública: `run_extractor_agent`

```python
def run_extractor_agent(
    settings: Settings,
    object_store: ObjectStore,
    object_store_key: str,
    content_type: str,
    model: Model | None = None,
) -> NormativoItem:
    """Lê o documento bruto do ObjectStore, extrai o texto deterministicamente
    (PDF ou HTML, conforme content_type), aplica guard() sobre o texto
    extraído, e executa o loop de reparo de validação (máximo 2 tentativas)
    até produzir um NormativoItem válido. Levanta PdfExtractionError se a
    extração de um PDF falhar, ou ValidationRepairExhaustedError se as duas
    tentativas de estruturação falharem na validação."""
```

**Pré-condição**: `object_store_key` já deve referenciar um documento bruto
persistido (ex. por `fetch_normativo`, SPEC-007, via Scraper Agent, SPEC-008).

**Pós-condição em sucesso**: retorna um `NormativoItem` validado, cujo
`texto` é derivado do conteúdo já mascarado por `guard()`.

**Pós-condição em falha de extração de PDF**: levanta `PdfExtractionError`
— nunca a exceção crua de `pdfplumber`.

**Pós-condição em falha do loop de reparo**: levanta
`ValidationRepairExhaustedError` — nunca uma terceira tentativa, nunca um
`NormativoItem` parcialmente inválido.

## `ExtractorAgentDeps` (ver data-model.md)

```python
@dataclass
class ExtractorAgentDeps:
    object_store: ObjectStore
```

## Exceções expostas (ver data-model.md para detalhe completo)

```python
class PdfExtractionError(Exception): ...
class ValidationRepairExhaustedError(Exception): ...
```

## CLI

```bash
python -m pix_compliance.agents.extractor_agent <object_store_key> <content_type>
```

Lê configuração de `Settings`, executa `run_extractor_agent(...)`, e
imprime o `NormativoItem` (JSON) na saída padrão.

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. Cada um dos 3+ documentos mock (PDF e HTML, SPEC-003) produz um
   `NormativoItem` válido ao passar por `run_extractor_agent` (SC-001).
2. Um PDF corrompido/malformado levanta `PdfExtractionError` — nunca a
   exceção crua de `pdfplumber` (SC-002).
3. Um `FunctionModel` de teste que retorna dado inválido na primeira chamada
   e válido na segunda comprova o loop de reparo: duas tentativas, nunca uma
   terceira, com log estruturado por tentativa (SC-003).
4. Um `spy`/instrumentação sobre `guard()` confirma que ele é invocado sobre
   o texto extraído antes de qualquer chamada ao LLM, para todo documento
   processado.
