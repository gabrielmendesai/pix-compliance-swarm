# Quickstart: Extractor Agent (SPEC-009)

## Pré-requisitos

- Dependências instaladas: `pip install -e ".[dev]"` (adiciona `pdfplumber`;
  `beautifulsoup4` já é dependência desde a SPEC-007).
- `.env` preenchido a partir de `.env.example` (credenciais Bedrock/object
  storage já existentes desde a SPEC-005/SPEC-006).
- `docker compose up postgres minio -d` (SPEC-006), e os documentos mock
  (`fixtures/documents/`, SPEC-003) persistidos no `ObjectStore` (via
  `fetch_normativo`/Scraper Agent, SPEC-007/SPEC-008, ou upload direto para
  fins de teste).

## Cenário 1 — Documentos mock produzem `NormativoItem` válidos (SC-001)

```bash
pytest tests/test_extractor_agent.py -k mock_documents -q
```

**Resultado esperado**: cada um dos 3+ documentos mock (PDF e HTML,
`fixtures/documents/`, SPEC-003) persistidos no `ObjectStore` produz um
`NormativoItem` válido ao passar por `run_extractor_agent`, sem exceção não
tratada.

## Cenário 2 — PDF corrompido gera erro tratado e tipado (SC-002)

```bash
pytest tests/test_extractor_agent.py -k corrupted_pdf -q
```

**Resultado esperado**: `extract_pdf_text` levanta `PdfExtractionError`
(nunca a exceção crua de `pdfplumber`) ao processar um arquivo PDF
deliberadamente corrompido — documentado em `contracts/extractor_agent.md`,
cenário 2.

## Cenário 3 — Guardrail aplicado antes de qualquer chamada ao LLM

```bash
pytest tests/test_extractor_agent.py -k guardrail -q
```

**Resultado esperado**: para o documento mock com PII plantada (SPEC-003),
`guard()` é invocado sobre o texto extraído antes de qualquer chamada ao
LLM, e o `NormativoItem` resultante não expõe o valor original da PII —
documentado em `contracts/extractor_agent.md`, cenário 4.

## Cenário 4 — Loop de reparo de validação aciona e para na segunda tentativa (SC-003)

```bash
pytest tests/test_extractor_agent.py -k validation_repair -q
```

**Resultado esperado**: com um `FunctionModel` que retorna dado inválido na
primeira chamada e válido na segunda, o teste confirma que a segunda
tentativa recebe a mensagem de erro Pydantic da primeira, que o
`NormativoItem` final é válido, e que nenhuma terceira tentativa é feita —
documentado em `contracts/extractor_agent.md`, cenário 3. O log estruturado
por tentativa (`tentativa`, `motivo`, `sucesso`) é observável na saída do
teste (`caplog`/`structlog`).

## Cenário 5 — Suíte completa do agente

```bash
pytest tests/test_extractor_agent.py -q
```

**Resultado esperado**: todos os testes passam, sem chamada real ao Bedrock
(`LLM_PROVIDER=offline`).

## Cenário 6 — `SKILL.md` segue o formato já estabelecido

```bash
cat skills/extractor-skill/SKILL.md
```

**Resultado esperado**: o arquivo descreve responsabilidade, ferramentas
(extração determinística de PDF/HTML, estruturação via LLM), input e
output (`NormativoItem`), no mesmo formato de quatro seções de
`skills/scraper-skill/SKILL.md` (SPEC-008) — verificado por teste
automatizado (presença das seções), não apenas leitura humana.

## Checklist de leitura antes de implementar

- [research.md](./research.md) — decisões de `pdfplumber`/`BeautifulSoup`,
  ponto único de aplicação de `guard()`, loop de reparo escrito à mão (não
  o retry automático do Pydantic AI), exceção tipada para PDF corrompido.
- [data-model.md](./data-model.md) — `ExtractorAgentDeps`,
  `PdfExtractionError`, `ValidationRepairExhaustedError`, mecânica do loop
  de reparo.
- [contracts/extractor_agent.md](./contracts/extractor_agent.md) —
  assinatura de `extract_pdf_text`/`extract_html_text`/
  `build_extractor_agent`/`run_extractor_agent`, CLI, e cenários de
  contrato cobertos por teste.

**Lembrete do Princípio IX**: `tests/test_extractor_agent.py` deve ser
escrito e confirmado como falho (por ausência de implementação) antes de
`extractor_agent.py` existir — incluindo o teste do loop de reparo com
`FunctionModel`. Ver ordenação de tarefas em `tasks.md` (gerado por
`/speckit-tasks`).
