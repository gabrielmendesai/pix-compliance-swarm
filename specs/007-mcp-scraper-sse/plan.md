# Implementation Plan: Servidor MCP do Scraper com transporte SSE (SPEC-007)

**Branch**: `007-mcp-scraper-sse` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-mcp-scraper-sse/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Expor a coleta de normativos do site mock do BCB como servidor MCP em
transporte SSE (`mcp_servers/scraper_sse/`), com três ferramentas tipadas
(`list_normativos`, `fetch_normativo`, `detect_changes`). A coleta é dividida
em um `Fetcher` genérico (HTTP via `httpx`, retry/backoff via `tenacity`,
rate limit, hash SHA-256) e um `Adapter` (`Protocol`, única exceção do
projeto sem segunda implementação real — `MockBcbAdapter` interpreta a
estrutura HTML do site mock). O documento bruto de cada `fetch_normativo` é
persistido no `ObjectStore` (SPEC-006); o último hash conhecido de cada
normativo também é persistido no `ObjectStore` (um pequeno blob JSON), para
que `detect_changes` compare contra ele em chamadas subsequentes sem exigir
um serviço de estado adicional.

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `mcp` (SDK oficial do Model Context Protocol,
`FastMCP` com transporte SSE embutido), `httpx` (cliente HTTP do Fetcher),
`beautifulsoup4` (parser HTML do `MockBcbAdapter`, com o parser `html.parser`
da stdlib — sem dependência de extensão C como `lxml`), `tenacity` (retry com
backoff, já dependência desde a SPEC-005), `pydantic` v2 (schemas de entrada/
saída das três ferramentas), `structlog` (log estruturado, já padrão do
projeto)

**Storage**: Reaproveita `ObjectStore`/`S3ObjectStore` da SPEC-006 para (a) o
documento bruto coletado por `fetch_normativo` e (b) o estado de "último hash
conhecido" por normativo, persistido como um único blob JSON sob uma chave
fixa — nenhum serviço de estado novo é introduzido (Princípio III, KISS)

**Testing**: pytest, com um fixture de teste que sobe `mock_bcb/` via
`http.server` da stdlib em porta efêmera (mesmo padrão já usado em
`tests/test_fixtures.py`), e um cliente MCP de teste (SDK `mcp` já inclui um
cliente para testes de integração contra transporte SSE) — sem mock do
`httpx` nem do `MockBcbAdapter`, contra o site mock real servido localmente

**Target Platform**: Linux server (container Docker Compose, mesmo alvo do
restante do projeto)

**Project Type**: Single project — novo pacote `mcp_servers/scraper_sse/` na
raiz do repositório, consumindo `src/pix_compliance/` (config, object store)
como dependência, não o inverso

**Performance Goals**: Sem meta de throughput própria (coleta em lote,
poucas dezenas de normativos no corpus fictício); o rate limit do Fetcher
prioriza não sobrecarregar a fonte, não velocidade máxima

**Constraints**: `Adapter` é a única interface do projeto sem segunda
implementação concreta (exceção documentada ao Princípio II); o Fetcher nunca
importa nada específico de estrutura de página; a troca de alvo (mock → real)
só pode depender de `BCB_BASE_URL`, nunca de alteração de código do Fetcher

**Scale/Scope**: Um servidor MCP, três ferramentas, um Fetcher, um Adapter
concreto (`MockBcbAdapter`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  N/A nesta spec: não invoca LLM/provider, apenas coleta e persiste conteúdo.
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS,
  com uma exceção deliberada e documentada: `Adapter` é `Protocol` com apenas
  uma implementação concreta (`MockBcbAdapter`) hoje, o que normalmente
  violaria o princípio — mas a spec já registra a justificativa (cenário de
  produção do desafio original) tanto nas Assumptions quanto exigindo
  docstring/README explicando a exceção. Fora desse ponto, nenhuma abstração
  adicional é introduzida: `Fetcher` é classe concreta (não há segunda
  implementação de "como fazer uma requisição HTTP" neste projeto).
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS. O estado
  de "último hash conhecido" reaproveita o `ObjectStore` já existente (um
  blob JSON), em vez de introduzir um banco de estado dedicado só para isso.
  Fetcher e Adapter vivem em módulos separados dentro do mesmo pacote
  (`mcp_servers/scraper_sse/`) porque cada um tem volume de responsabilidade
  próprio que justifica a separação (Princípio III aplicado corretamente:
  separar quando o volume justifica).
- **Princípio IV (Responsabilidade única por agente / SRP)** — N/A direto:
  esta feature não define um agente do enxame, mas o espírito é seguido — o
  servidor MCP expõe ferramentas, não decide entre múltiplos papéis; cada
  ferramenta (`list_normativos`, `fetch_normativo`, `detect_changes`) tem uma
  responsabilidade única e um contrato de entrada/saída em Pydantic.
- **Princípio V (Guardrail é ponto único e obrigatório)** — N/A: o conteúdo
  coletado é bruto (HTML de origem), ainda não destinado a um LLM; o
  guardrail se aplica na feature consumidora (Scraper Agent, fora de escopo
  aqui), quando o conteúdo for de fato enviado a um LLM.
- **Princípio VI (Contrato antes de comportamento)** — PASS. Os schemas
  Pydantic de entrada/saída das três ferramentas e as estruturas internas
  (`NormativoRef`, `ChangeRecord`) são definidos na Fase 1 (`data-model.md`)
  antes de qualquer lógica de Fetcher/Adapter/servidor MCP.
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês (`Fetcher`, `Adapter`, `MockBcbAdapter`); comentários/docstrings em
  português explicando o porquê — em particular, a docstring do `Protocol`
  `Adapter` explicando por que é a única exceção do projeto à regra de
  seam real (Princípio II), e o README documentando o caminho de evolução
  para `RealBcbAdapter`.
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. Todos
  os critérios de aceite são comandos executáveis (handshake SSE, listagem
  de ferramentas, `detect_changes` determinístico); o README de integração é,
  em si, um critério de aceite verificável por um terceiro sem contexto
  adicional (SC-004).
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, requisito explícito da spec. Testes
  do Fetcher, do `MockBcbAdapter` e das três ferramentas MCP são escritos e
  confirmados como falhos antes de qualquer implementação correspondente;
  `tasks.md` ordena teste antes de implementação em cada user story, com
  passo explícito de confirmação de falha.

Nenhuma violação **não justificada** identificada. A única exceção
(`Adapter` sem segunda implementação real) já é uma decisão documentada pelo
próprio usuário na spec, registrada em Complexity Tracking abaixo por
transparência, não por ser um gate falho.

**Re-check pós-Fase 1**: `data-model.md` e `contracts/scraper_mcp.md`
confirmam que `Adapter` permanece o único `Protocol` desta feature com uma
única implementação concreta (`MockBcbAdapter`), documentado como exceção; o
`Fetcher` permanece classe concreta sem `Protocol`; nenhuma abstração
adicional foi introduzida na Fase 1. Gates permanecem PASS.

## Project Structure

### Documentation (this feature)

```text
specs/007-mcp-scraper-sse/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
mcp_servers/
└── scraper_sse/
    ├── __init__.py
    ├── models.py          # NOVO — NormativoRef, NormativoFilter, FetchNormativoResult, ChangeRecord (Pydantic)
    ├── fetcher.py          # NOVO — Fetcher (classe concreta): httpx + retry/backoff (tenacity) + rate limit + hash SHA-256
    ├── adapters.py          # NOVO — Protocol Adapter (única exceção do projeto, documentada) + MockBcbAdapter (bs4)
    ├── state.py             # NOVO — leitura/escrita do blob JSON de "último hash conhecido" via ObjectStore (SPEC-006)
    ├── server.py            # NOVO — FastMCP app, registra as três ferramentas, transporte SSE, porta via env var
    └── README.md            # NOVO — documentação de integração (bloco de configuração pronto para copiar)

src/pix_compliance/
├── config.py              # ATUALIZADO — BCB_BASE_URL, porta do servidor MCP
├── object_store.py         # já existe (SPEC-006) — reaproveitado sem alteração de contrato
└── ...

tests/
├── test_scraper_fetcher.py    # NOVO — escrito e confirmado falho ANTES de fetcher.py (Princípio IX)
├── test_scraper_adapter.py    # NOVO — escrito e confirmado falho ANTES de adapters.py (Princípio IX)
└── test_scraper_mcp_server.py # NOVO — escrito e confirmado falho ANTES de server.py (Princípio IX)
```

**Structure Decision**: Novo pacote `mcp_servers/scraper_sse/`, fora de
`src/pix_compliance/` — reflete que este é um processo servidor distinto
(entrypoint próprio, `python -m mcp_servers.scraper_sse.server` ou
equivalente), não uma biblioteca importada pelos agentes do enxame da mesma
forma que `object_store`/`vector_store`. Ele importa de `src/pix_compliance/`
(config, `ObjectStore`) como dependência — nunca o inverso, preservando a
direção de dependência já estabelecida no projeto. Dentro do pacote,
`fetcher.py`/`adapters.py`/`state.py`/`server.py` são módulos separados por
terem volume de responsabilidade próprio (Princípio III): misturar Fetcher e
Adapter no mesmo arquivo apagaria visualmente a separação que é o próprio
objetivo arquitetural desta feature.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| `Adapter` (`Protocol`) com uma única implementação concreta (`MockBcbAdapter`), sem segunda implementação real hoje | O cenário de produção (scraping do `bcb.gov.br` real) é parte explícita do enunciado do desafio original, mas implementá-lo de fato está fora do escopo de 4 dias desta spec — o ponto de extensão precisa existir e estar documentado mesmo sem uma segunda implementação ainda | Usar `MockBcbAdapter` diretamente, sem `Protocol`, foi rejeitado porque apagaria do código o caminho de evolução para produção que o próprio enunciado do desafio exige tornar explícito — a exceção é deliberada, documentada na docstring do `Protocol` e no README, não uma abstração especulativa comum |
