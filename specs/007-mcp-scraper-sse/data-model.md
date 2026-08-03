# Data Model: Servidor MCP do Scraper com transporte SSE (SPEC-007)

Todos os modelos seguem o padrão já estabelecido no projeto: Pydantic v2
(`extra="forbid"`) para contratos de dados, identificadores em inglês,
docstrings/comentários em português explicando o porquê.

## NormativoFilter (entrada de `list_normativos`)

| Campo | Tipo | Validação | Descrição |
|---|---|---|---|
| `categoria` | `str \| None` | opcional, default `None` | Filtra por categoria do normativo, quando presente no site mock |
| `numero` | `str \| None` | opcional, default `None` | Filtra por número/identificador do normativo |

**Regra de negócio**: `NormativoFilter()` vazio (todos os campos `None`)
retorna todos os normativos listados no site mock, sem filtro aplicado.

## NormativoListItem (item de saída de `list_normativos`)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | `str` | Identificador do normativo (derivado do nome do arquivo/URL no site mock) |
| `titulo` | `str` | Título extraído da página do normativo |
| `url` | `str` | URL completa de origem (`BCB_BASE_URL` + path relativo) |

## FetchNormativoResult (saída de `fetch_normativo`)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | `str` | Identificador do normativo solicitado |
| `hash_sha256` | `str` | Hash do conteúdo coletado nesta chamada |
| `object_store_key` | `str` | Chave sob a qual o documento bruto foi persistido no `ObjectStore` (SPEC-006) |

**Regra de negócio (adendo pós-implementação, revisão cruzada com SPEC-008)**:
`FetchNormativoResult` deliberadamente NÃO inclui o conteúdo bruto do
documento. O resultado de uma tool call MCP retorna ao contexto do modelo
que a chamou — devolver o texto completo aqui faria PII eventualmente
plantada no documento (SPEC-003) trafegar a um LLM consumidor (ex. Scraper
Agent, SPEC-008) sem passar por `guard()` (Princípio V), mesmo sem nenhum
"processamento" semântico do conteúdo por parte de quem chama. Quem precisa
do conteúdo integral (Extractor Agent, feature futura) lê diretamente do
`ObjectStore` pela chave em `object_store_key` — nesse ponto, `guard()` se
aplica antes de qualquer envio a um LLM.

**Regra de negócio**: se `id` não corresponder a nenhum normativo conhecido
pelo Adapter, a ferramenta MUST retornar um erro MCP claro (não uma exceção
Python crua) — ver Edge Cases do spec.md.

## ChangeRecord (item de saída de `detect_changes`)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | `str` | Identificador do normativo alterado ou novo |
| `hash_anterior` | `str \| None` | Hash conhecido antes desta chamada; `None` se o normativo é novo (nunca visto antes) |
| `hash_atual` | `str` | Hash calculado nesta chamada |
| `detectado_em` | `datetime` | Momento da detecção, usado para comparação com o parâmetro `since` em chamadas futuras |

**Regra de negócio**: `detect_changes(since)` retorna apenas os
`ChangeRecord` cujo `detectado_em` seja maior ou igual a `since`, quando
fornecido; se `since` for omitido, retorna todas as mudanças detectadas na
chamada atual (comparando contra o estado persistido de hashes conhecidos).

## NormativoRef (estrutura interna, não exposta como schema MCP)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | `str` | Identificador do normativo |
| `url` | `str` | URL completa da página do normativo |

Produzida pelo `Adapter.list_refs()` a partir da página de listagem, e
consumida pelo `Fetcher` para coletar cada página individual.

## Estado persistido: `scraper-state/known-hashes.json` (blob no `ObjectStore`)

Estrutura: `dict[str, str]` (mapa de `id` do normativo para o último hash
SHA-256 conhecido), serializado como JSON e persistido sob uma chave fixa no
`ObjectStore` (SPEC-006) — não é uma tabela nem um novo serviço de estado
(ver research.md, Decisão 4).

## Ponto de troca entre implementações (única exceção documentada ao Princípio II)

```
Adapter (Protocol)
└── MockBcbAdapter (única implementação concreta hoje)
```

Diferente de todo outro `Protocol` já introduzido no projeto (`ObjectStore`
na SPEC-006, por exemplo, que tem duas implementações reais), `Adapter` tem
apenas uma implementação concreta no momento desta feature. Esta é a única
exceção deliberada do projeto à regra geral do Princípio II — documentada na
docstring do `Protocol` em `mcp_servers/scraper_sse/adapters.py` e no README
do pacote, com o caminho de evolução (`RealBcbAdapter`, trocando
`BCB_BASE_URL`) explicitado, mas não implementado (fora de escopo desta
spec).

`Fetcher` não participa deste diagrama — é classe concreta, sem `Protocol`,
por não haver uma segunda implementação real de "como fazer uma requisição
HTTP com retry" neste projeto.
