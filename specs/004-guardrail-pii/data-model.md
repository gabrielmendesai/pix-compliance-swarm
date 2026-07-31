# Data Model: Camada de guardrail e PII (SPEC-004)

Modelos definidos em `src/pix_compliance/guardrails.py`, seguindo o mesmo
padrão de `src/pix_compliance/models.py` (SPEC-002): `ConfigDict(extra=
"forbid")`, `StrEnum` para vocabulário fechado.

## TipoPII (StrEnum)

Vocabulário fechado dos tipos de PII detectáveis.

- `CPF` = "cpf"
- `CNPJ` = "cnpj"
- `EMAIL` = "email"
- `TELEFONE` = "telefone"
- `CHAVE_PIX_ALEATORIA` = "chave_pix_aleatoria"

## PIIReport

Relatório agregado de uma execução de detecção, por tipo de PII (research.md §2).

| Campo | Tipo | Regras |
|---|---|---|
| `tipo` | `TipoPII` | enum |
| `posicao` | `int` | índice (0-based) da primeira ocorrência no texto original; `>= 0` |
| `ocorrencias` | `int` | contagem total de ocorrências daquele tipo no texto; `>= 1` |

## GuardedText

Resultado da aplicação de `guard()` sobre um texto de entrada — o único
formato que deve chegar a um LLM ou a uma escrita de storage.

| Campo | Tipo | Regras |
|---|---|---|
| `texto_mascarado` | `str` | texto de entrada com todas as ocorrências de PII mascaradas (research.md §3); nunca contém o valor original detectado |
| `relatorios` | `list[PIIReport]` | um `PIIReport` por tipo de PII efetivamente detectado; lista vazia se nenhuma PII foi encontrada |
| `injecao_suspeita` | `bool` | `True` se algum padrão de injeção de prompt (research.md §5) foi encontrado no texto original |

## GuardrailInputError (exceção)

Exceção concreta única (sem hierarquia) levantada por `guard()` quando o
texto de entrada excede `MAX_TEXT_LENGTH` (research.md §5) — mensagem clara
e acionável, análoga a `ConfigurationError` em `src/pix_compliance/
config.py` (SPEC-001).

## Funções públicas do módulo

| Função | Assinatura | Papel |
|---|---|---|
| `guard` | `guard(text: str) -> GuardedText` | Ponto único de aplicação: valida tamanho, detecta padrões de injeção, detecta e mascara PII, loga cada detecção (tipo + contagem, nunca o valor), retorna `GuardedText` |
| `call_with_guard` | `call_with_guard(func: Callable[[str], T], text: str) -> T` | Aplica `guard(text)` e invoca `func` apenas com `texto_mascarado` — mecanismo usado para provar que uma função de destino nunca recebe o texto original (research.md §7) |

## Relacionamentos

```
texto de entrada (str)
        │
        ▼
     guard(text) ──► GuardrailInputError (se len(text) > MAX_TEXT_LENGTH)
        │
        ▼
  GuardedText
   ├── texto_mascarado: str
   ├── relatorios: list[PIIReport]   (um por tipo detectado)
   └── injecao_suspeita: bool

call_with_guard(func, text) = func(guard(text).texto_mascarado)
```

## Correção de fixture bloqueante (FR-012, fora de `src/`)

Não é um modelo desta feature, mas uma correção de dado em
`fixtures/documents/normativo-100-2020-pii.{html,pdf}` (e seu espelho em
`mock_bcb/normativos/`): o CNPJ plantado `80.683.921/0001-36` (dígito
verificador inválido) é substituído por um CNPJ com dígito verificador
correto, gerado pela mesma lógica já existente em `fixtures/pii.py`
(`gerar_cnpj_valido`), preservando formato e o restante do documento.
