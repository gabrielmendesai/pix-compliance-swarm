# PIX Compliance Swarm

Enxame de agentes Pydantic AI para compliance de normativos PIX fictícios do BCB.

## Fixtures: `documents/` vs `normativos.json`

O projeto mantém dois corpora de fixture com propósitos deliberadamente
diferentes, não redundantes entre si:

- **`fixtures/documents/` (3+ PDF/HTML)** é a prova de conceito da extração:
  demonstra que o par Scraper → Extractor funciona de ponta a ponta a partir
  de um documento bruto real (um documento denso multi-artigo/multi-categoria,
  um documento com PII plantada, e um par de versões com delta conhecido).
  Não precisa de volume — precisa de estrutura e conteúdo realistas o
  suficiente para segmentação em artigo/inciso.
- **`fixtures/normativos.json` (50+ registros)** representa o corpus já
  extraído e estruturado, usado para exercitar as features que dependem de
  volume — Compliance Analyzer, Conformance Validator, Knowledge
  Builder/RAG e a API. É a base de dados real do sistema. Os PDFs de
  `fixtures/documents/` não são reprocessados em massa por decisão consciente
  de escopo: gerar e parsear 50 documentos reais não agregaria sinal de
  engenharia proporcional ao tempo que custaria.

O scraping (SPEC-007/008) é feito contra o site mock estático em
`mock_bcb/`, nunca contra o `bcb.gov.br` real — decisão já registrada em
ADR-04 (`Initial Design/BRIEFING.md`), reafirmada aqui para não parecer
inconsistência para quem avaliar o projeto.

## Guardrail de PII (`src/pix_compliance/guardrails.py`)

`guard()` é o único caminho permitido para texto destinado a um LLM ou a uma
escrita de storage: detecta CPF, CNPJ, e-mail, telefone e chave PIX
aleatória, e mascara cada ocorrência preservando o formato original (ex.
`123.***.***-01`), em vez de um marcador genérico.

O detalhe que diferencia esta implementação de um regex ingênuo é a
**validação real do dígito verificador de CPF/CNPJ** (módulo 11), não
apenas checagem de formato. Um regex sozinho trataria qualquer sequência de
11 dígitos como um possível CPF; validar o dígito verificador elimina a
esmagadora maioria desses falsos positivos e é barato de implementar (menos
de 15 linhas por documento) — não há motivo para não fazê-lo.
