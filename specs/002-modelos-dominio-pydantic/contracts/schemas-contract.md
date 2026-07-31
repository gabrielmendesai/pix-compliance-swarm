# Contract: JSON Schema dos modelos de domínio

Esta feature não expõe um endpoint HTTP próprio — seu "contrato externo" (FR-018,
SC-002) é o conjunto de JSON Schemas gerados por `model_json_schema()` para cada modelo
público de `src/pix_compliance/models.py`, persistidos em `docs/schemas/`.

## Regras do contrato

1. Todo modelo público listado em Key Entities do `spec.md` MUST ter um arquivo de
   schema correspondente em `docs/schemas/<NomeDoModelo>.schema.json`.
2. O arquivo de schema é gerado por código (não editado manualmente) a partir de
   `Modelo.model_json_schema()`, garantindo que nunca diverge da implementação.
3. Todo schema gerado MUST refletir `"additionalProperties": false` (via `extra="forbid"`
   do Pydantic), tornando explícito para consumidores externos que campos extras são
   rejeitados.
4. Enums (`TipoNormativo`, `CategoriaCompliance`, `Obrigatoriedade`,
   `StatusConformidade`) MUST aparecer no schema como `enum` de valores string.

## Arquivos esperados em `docs/schemas/`

- `NormativoItem.schema.json`
- `RegraExtraida.schema.json`
- `ConformanceItem.schema.json`
- `ConformanceReport.schema.json`
- `SearchQuery.schema.json`
- `SearchResult.schema.json`
- `ReportOutput.schema.json`
- `PipelineRequest.schema.json`
- `PipelineResult.schema.json`
- `RawDocument.schema.json`

## Verificação

Comando executável que prova o contrato (Princípio VIII — evidência como entregável):

```bash
pytest tests/test_models.py -q -k schema
```

Este teste MUST, para cada um dos 10 modelos acima: (a) chamar `model_json_schema()`,
(b) gravar/atualizar o arquivo correspondente em `docs/schemas/`, e (c) falhar se o
schema gerado em memória divergir do arquivo commitado (drift check), garantindo que o
artefato em `docs/schemas/` nunca fica desatualizado em relação ao código-fonte.
