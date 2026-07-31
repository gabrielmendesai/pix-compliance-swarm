# Contract: API do módulo de guardrail

Esta feature não expõe uma API HTTP — o "contrato externo" é a API pública
de `src/pix_compliance/guardrails.py`, consumida por agentes futuros
(SPEC-005+) como o único caminho permitido para texto destinado a um LLM ou
a uma escrita de storage.

## Contrato de `guard`

```python
def guard(text: str) -> GuardedText: ...
```

- **Pré-condição**: `text` é uma `str` (pode ser vazia).
- **Pós-condição (tamanho)**: se `len(text) > MAX_TEXT_LENGTH`, levanta
  `GuardrailInputError` — nenhum processamento adicional ocorre.
- **Pós-condição (mascaramento)**: `GuardedText.texto_mascarado` NUNCA
  contém nenhuma ocorrência de PII detectada em sua forma original —
  apenas a forma mascarada com formato preservado (data-model.md).
- **Pós-condição (relatório)**: `GuardedText.relatorios` contém exatamente
  um `PIIReport` por tipo de PII efetivamente detectado (0 a 5 itens,
  conforme os 5 tipos suportados); tipos não encontrados no texto não geram
  entrada.
- **Pós-condição (injeção)**: `GuardedText.injecao_suspeita` é `True` se e
  somente se algum padrão de injeção de prompt (research.md §5) foi
  encontrado no texto original.
- **Pós-condição (log)**: para cada `PIIReport` em `relatorios`, e para
  `injecao_suspeita=True`, um evento de log estruturado é emitido via
  `structlog`, contendo tipo/contagem (ou o fato da suspeita de injeção) —
  o texto original ou o trecho detectado NUNCA aparece em nenhum campo do
  evento de log.
- **Idempotência de detecção**: aplicar `guard()` sobre o mesmo `text` duas
  vezes produz `GuardedText` equivalente (mesmo `texto_mascarado`, mesmos
  `relatorios`) — a detecção é determinística.

## Contrato de `call_with_guard`

```python
def call_with_guard(func: Callable[[str], T], text: str) -> T: ...
```

- **Pós-condição**: `func` é invocada com exatamente um argumento posicional
  — o valor de `guard(text).texto_mascarado` — nunca com `text` original.
- **Valor de retorno**: o mesmo valor que `func` retornaria se chamada
  diretamente (passthrough transparente, exceto pelo argumento).

## Contrato de mascaramento por tipo (research.md §3)

| Tipo | Exemplo de entrada | Exemplo de saída mascarada |
|---|---|---|
| CPF | `123.456.789-01` | `123.***.***-01` |
| CNPJ | `12.345.678/0001-90` | `12.***.***/****-90` |
| E-mail | `joao.silva@exemplo.com` | `j***@exemplo.com` |
| Telefone | `(11) 98765-4321` | `(11) 9****-**21` |
| Chave PIX aleatória | `123e4567-e89b-12d3-a456-426614174000` | `123e4567-****-****-****-426614174000` |

## Verificação

Comando executável que prova o contrato (Princípio VIII — evidência como
entregável):

```bash
pytest tests/test_guardrails.py -q
```

Este teste MUST cobrir, no mínimo: mascaramento de CPF/CNPJ válidos, não
detecção de CPF/CNPJ com dígito verificador inválido, ausência de falso
positivo em sequências de 11 dígitos aleatórias, `call_with_guard` nunca
expondo o texto original à função de destino, e inspeção da saída de log
confirmando tipo+contagem sem o valor original.
