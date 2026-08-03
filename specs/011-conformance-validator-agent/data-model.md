# Data Model: Conformance Validator Agent (SPEC-011)

Esta feature não introduz nenhum modelo Pydantic novo — reaproveita
integralmente os contratos já existentes (SPEC-002). O único "dado novo"
desta spec é a convenção de agrupamento de versões e a fórmula determinística
de `resumo`/`criticidade_maxima`.

## RegraExtraida (já existe — SPEC-002, sem alteração)

Reaproveitado como unidade de comparação — uma coleção por versão do
normativo.

| Campo | Tipo | Uso nesta feature |
|---|---|---|
| `regra_id` | `str` | Referenciado em `ConformanceItem.regra_id` — sempre a regra da **versão atual** (não estável entre versões, ver spec.md Edge Cases) |
| `normativo_id` | `str` | Usado para saber a qual `NormativoItem` (e portanto qual `versao`) a regra pertence |
| `categoria` | `CategoriaCompliance` | Propagado ao prompt de comparação como contexto |
| `enunciado` | `str` | Texto comparado semanticamente — protegido por `guard()` antes do prompt (Princípio V) |
| `obrigatoriedade` | `Obrigatoriedade` | Propagado ao prompt como contexto |

## NormativoItem (já existe — SPEC-002, sem alteração)

Usado apenas para agrupamento/ordenação de versões — não para o conteúdo
comparado (esse é `RegraExtraida.enunciado`).

| Campo | Uso nesta feature |
|---|---|
| `id` | Correlaciona com `RegraExtraida.normativo_id` |
| `numero` | Chave de agrupamento — todas as versões do "mesmo normativo" compartilham `numero` |
| `versao` | Critério de ordenação dentro de um grupo — a mais alta é `atual`, a segunda mais alta é `anterior` |

## ConformanceItem (já existe — SPEC-002, sem alteração)

Formato de saída por regra comparada.

| Campo | Valor nesta feature |
|---|---|
| `regra_id` | `RegraExtraida.regra_id` da versão atual |
| `status` | `StatusConformidade.NOVO` (sem versão anterior, determinístico — research.md Decisão 4) ou decidido pelo `Agent` (`ALTERADO`/`REVOGADO`/`CONFORME`, research.md Decisão 0) |
| `delta` | `None` para `novo`; texto legível gerado pelo `Agent` para `alterado`/`revogado`; `None` para `conforme` |
| `recomendacao` | `None` para `novo`/`conforme`; texto acionável gerado pelo `Agent` para `alterado`/`revogado` |
| `severidade` | `0.0` para `novo`; gerada pelo `Agent` para os demais status (maior para `revogado` que para `alterado`, por critério do próprio julgamento do modelo) |

## ConformanceReport (já existe — SPEC-002, sem alteração)

Agregado de todos os `ConformanceItem` de uma execução sobre o corpus
inteiro.

| Campo | Valor nesta feature |
|---|---|
| `report_id` | Gerado pelo chamador (ex. `uuid4().hex`) — não decidido internamente por esta feature |
| `gerado_em` | `datetime.now()` no momento da montagem do relatório |
| `itens` | Concatenação de todos os `ConformanceItem` de todos os grupos de `numero` processados |
| `resumo` | Frase gerada em código a partir das contagens reais por `status` (research.md, Decisão 3) |
| `criticidade_maxima` | `StatusConformidade` de maior severidade entre `alterado`/`revogado` presentes, ou `None` se nenhum gap existir (research.md, Decisão 3) |

## Convenção: agrupamento de versões

```
grupos = agrupar NormativoItem por numero
para cada grupo, ordenado por versao:
    atual = versao mais alta
    anterior = segunda versao mais alta, ou None se só existe uma versao
```

**Regra de negócio**: apenas a comparação `atual` vs. `anterior` imediato é
feita — não uma cadeia completa de histórico (research.md, Decisão 2).

## Funções públicas (contratos internos, ver contracts/)

| Função | Assinatura | Descrição |
|---|---|---|
| `compare_regras` | `(settings, regras_anteriores: list[RegraExtraida] \| None, regras_atuais: list[RegraExtraida], model=None) -> list[ConformanceItem]` | Compara um par de versões (ou classifica como `novo` se `regras_anteriores` for `None`) |
| `build_conformance_report` | `(settings, report_id: str, normativos: list[NormativoItem], regras_por_normativo: dict[str, list[RegraExtraida]], model=None) -> ConformanceReport` | Agrupa por `numero`/`versao`, chama `compare_regras` por grupo, agrega o `ConformanceReport` completo |
