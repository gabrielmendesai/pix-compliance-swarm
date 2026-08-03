# Feature Specification: Report Consolidator Agent (SPEC-014)

**Feature Branch**: `014-report-consolidator-agent`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Report Consolidator Agent (SPEC-014) — gera o relatório final do pipeline (JSON e PDF) e cumpre o requisito literal do desafio original de invocar uma API FastAPI como cliente HTTP para ação final."

**Dependências**: SPEC-011 (Conformance Validator — este agente recebe `ConformanceReport` como entrada) e SPEC-013 (API FastAPI — este agente é cliente HTTP dela). Reaproveita o mesmo padrão estrutural de agente das specs anteriores.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos durante a execução:
  seu "usuário" é o operador/avaliador do projeto, que roda o pipeline
  completo e recebe o relatório final (JSON + PDF) como entregável, e a API
  FastAPI (SPEC-013), que recebe a publicação HTTP do resultado consolidado
  como seu cliente.
-->

### User Story 1 - Gerar o relatório final em JSON e PDF a partir do corpus completo (Priority: P1)

Um `ConformanceReport` (SPEC-011) do corpus completo de fixtures é consolidado em dois artefatos: um JSON no formato `ReportOutput` (SPEC-002) e um PDF via `reportlab`, com capa, sumário executivo, tabela de normativos coletados, regras agrupadas por categoria e uma seção de gap analysis com indicação de severidade. Ambos os artefatos são enviados ao `ObjectStore` (SPEC-006).

**Why this priority**: É o objetivo nominal desta feature — sem os dois artefatos gerados corretamente, não há relatório final a publicar ou entregar.

**Independent Test**: Pode ser testado isoladamente executando o agente sobre um `ConformanceReport` construído a partir do corpus completo de fixtures e verificando que o JSON e o PDF resultantes existem, têm conteúdo estruturalmente correto (JSON no formato `ReportOutput`; PDF com as cinco seções exigidas) e foram enviados ao `ObjectStore`.

**Acceptance Scenarios**:

1. **Given** um `ConformanceReport` do corpus completo de fixtures, **When** o agente consolida o relatório, **Then** um arquivo JSON no formato `ReportOutput` é gerado e enviado ao `ObjectStore`.
2. **Given** o mesmo `ConformanceReport`, **When** o agente consolida o relatório, **Then** um arquivo PDF é gerado (via `reportlab`) contendo capa, sumário executivo, tabela de normativos coletados, regras agrupadas por categoria e seção de gap analysis com indicação de severidade, e é enviado ao `ObjectStore`.

---

### User Story 2 - Publicar o resultado consolidado na API FastAPI, como requisito literal do desafio (Priority: P1)

Após consolidar o relatório, o agente atua como **cliente HTTP** e publica o resultado na API FastAPI (SPEC-013). A URL base da API usada por esse cliente vem exclusivamente de `settings` (nunca um literal no código-fonte deste agente) — este é o requisito nominal da seção 2 do desafio original ("invocar uma API FastAPI como cliente HTTP para ação final"), e a conexão entre este agente e esse requisito é documentada explicitamente tanto no `SKILL.md` quanto no README.

**Why this priority**: Mesma prioridade da User Story 1 — sem a chamada HTTP à API, o requisito literal do desafio original não é cumprido, independentemente da qualidade dos artefatos gerados.

**Independent Test**: Pode ser testado isoladamente configurando a URL da API via `settings`, executando o agente, e verificando (via mock/observação do cliente HTTP) que uma requisição foi feita para a URL configurada, com o payload esperado, sem nenhuma URL hardcoded no código-fonte do agente.

**Acceptance Scenarios**:

1. **Given** um relatório consolidado e uma URL de API configurada via `settings`, **When** o agente publica o resultado, **Then** uma requisição HTTP é enviada para essa URL (nunca para um literal hardcoded no código).
2. **Given** o código-fonte deste agente, **When** inspecionado, **Then** nenhuma URL de API aparece como literal — apenas leitura de `settings`.

---

### User Story 3 - Degradação controlada quando a API está indisponível (Priority: P1)

Quando a API FastAPI está indisponível (erro de conexão), o relatório já consolidado (JSON e PDF) é persistido localmente e o erro é logado de forma clara — o trabalho de geração do relatório não é perdido só porque a publicação via HTTP falhou.

**Why this priority**: Mesma faixa de prioridade das anteriores — sem essa garantia, uma falha de rede transitória destruiria todo o trabalho de consolidação já realizado, o que é inaceitável para um relatório de compliance.

**Independent Test**: Pode ser testado isoladamente simulando (mock) um erro de conexão ao publicar na API, e verificando que o JSON/PDF permanecem persistidos (localmente e/ou no `ObjectStore`) e que um log de erro claro é emitido, sem exceção não tratada interrompendo o restante do fluxo.

**Acceptance Scenarios**:

1. **Given** a API FastAPI indisponível (erro de conexão simulado), **When** o agente tenta publicar o relatório consolidado, **Then** o JSON e o PDF já gerados permanecem persistidos (localmente e no `ObjectStore`), e um erro é logado de forma clara, sem interromper a consolidação em si.

---

### Edge Cases

- O que acontece se a geração do PDF falhar (ex. dado inesperado no `ConformanceReport`) antes mesmo da tentativa de publicação HTTP? A falha MUST ser reportada de forma clara — o agente não tenta publicar um relatório parcial/corrompido na API.
- O que acontece se a URL da API estiver ausente/malformada em `settings`? MUST falhar de forma clara e acionável (mesmo padrão de `ConfigurationError` já estabelecido no projeto, SPEC-001), nunca silenciosamente pular a publicação.
- Como o sistema decide o nome/local do artefato persistido localmente quando a API está indisponível? MUST ser determinístico e re-encontrável (ex. mesmo caminho/nome usado no upload ao `ObjectStore`), para que o operador consiga localizar e reenviar manualmente depois.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST gerar um relatório em JSON no formato `ReportOutput` (SPEC-002) a partir de um `ConformanceReport` (SPEC-011).
- **FR-002**: O sistema MUST gerar um relatório em PDF via `reportlab`, contendo: capa, sumário executivo, tabela de normativos coletados, regras agrupadas por categoria, e seção de gap analysis com indicação de severidade.
- **FR-003**: O sistema MUST enviar ambos os artefatos (JSON e PDF) ao `ObjectStore` (SPEC-006).
- **FR-004**: O sistema MUST publicar o resultado consolidado na API FastAPI (SPEC-013) via um cliente HTTP.
- **FR-005**: A URL da API usada pelo cliente HTTP MUST vir exclusivamente de `settings` (`Settings`/`config.py`) — nenhum literal de URL MUST aparecer no código-fonte deste agente.
- **FR-006**: Quando a publicação HTTP falhar (API indisponível), o sistema MUST persistir o relatório localmente e logar o erro de forma clara, MUST NOT perder o trabalho de geração já realizado, e MUST NOT propagar uma exceção não tratada que interrompa o restante do fluxo do pipeline.
- **FR-007**: O sistema MUST fornecer `skills/report-consolidator-skill/SKILL.md`, documentando explicitamente que este agente cumpre o requisito literal do desafio original de "invocar uma API FastAPI como cliente HTTP para ação final".
- **FR-008**: Este agente MUST NOT implementar templates de relatório customizáveis pelo usuário — fica fora de escopo desta spec.
- **FR-009**: Este agente MUST NOT implementar envio do relatório por e-mail — fica fora de escopo desta spec.
- **FR-010**: Este agente MUST NOT recategorizar nem revalidar dados já produzidos por features anteriores (Compliance Analyzer, Conformance Validator) — apenas consolida e publica (Princípio IV, um agente/uma responsabilidade).

### Key Entities *(include if feature involves data)*

- **ConformanceReport**: Modelo já existente (SPEC-002, produzido pelo Conformance Validator, SPEC-011), reaproveitado sem alteração como entrada desta feature.
- **ReportOutput**: Modelo já existente (SPEC-002), reaproveitado sem alteração como formato do artefato JSON gerado por esta feature.
- **Relatório PDF**: Artefato binário gerado via `reportlab`, com cinco seções obrigatórias (capa, sumário executivo, tabela de normativos, regras por categoria, gap analysis com severidade) — não é um modelo Pydantic, é um artefato de saída.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato).
-->

### Measurable Outcomes

- **SC-001**: JSON e PDF são gerados corretamente a partir do corpus completo de fixtures.
- **SC-002**: Quando a API está indisponível, o relatório é persistido localmente e o erro é logado de forma clara — o trabalho de geração do relatório não é perdido só porque a publicação via HTTP falhou (degradação controlada, não falha total).
- **SC-003**: A URL da API usada pelo cliente HTTP vem exclusivamente de `settings` (`Settings`/`config.py`) — nenhum literal de URL no código-fonte deste agente.

## Assumptions

- Conforme o Princípio IX da constituição, os testes desta feature devem ser escritos e confirmados como falhos antes de qualquer código de implementação, derivados exclusivamente dos critérios de aceite desta spec — incluindo um teste que simula a API FastAPI indisponível (mock de erro de conexão) para comprovar o comportamento de degradação controlada.
- **Dependências ainda não implementadas no repositório**: no momento da escrita desta spec, nem a SPEC-011 (Conformance Validator, produtor de `ConformanceReport`) nem a SPEC-013 (API FastAPI) existem como código no projeto — apenas `ConformanceReport`/`ReportOutput` (modelos Pydantic, SPEC-002) e o campo `Settings.api_url` (SPEC-001) já existem. Esta spec documenta o contrato e o comportamento esperado deste agente de qualquer forma, assumindo que SPEC-011 e SPEC-013 serão implementadas antes ou durante o mesmo ciclo de `/speckit-plan`/`/speckit-implement` desta feature; caso não estejam disponíveis no momento da implementação, os testes desta feature MUST usar um `ConformanceReport` construído diretamente (sem depender de um Conformance Validator real) e um servidor HTTP mock local (não a API FastAPI real) para validar o cliente HTTP — mesmo padrão já usado em `tests/conftest.py` (`mock_bcb_server`, SPEC-007) para simular um serviço externo ainda não implementado/disponível em ambiente de teste.
- **Reaproveitamento do campo `Settings.api_url` já existente** (SPEC-001) como a URL da API lida por este agente, em vez de introduzir um novo campo `REPORT_API_BASE_URL` — a spec original permite explicitamente "`REPORT_API_BASE_URL` ou nome equivalente em `Settings`", e `api_url: str` já existe em `Settings` desde a fundação do projeto, aparentemente reservado para este propósito (é a única URL de API já modelada em `Settings`). Nenhum campo novo é introduzido nesta spec.
- Numeração da spec: o usuário rotulou esta feature explicitamente como SPEC-014 (pulando SPEC-013, reservada à API FastAPI ainda não especificada) — o diretório `specs/014-report-consolidator-agent` segue esse rótulo explícito em vez da numeração sequencial automática (que apontaria para 013), preservando o padrão já estabelecido no projeto (mesma situação documentada na SPEC-012) de que o número do diretório corresponde exatamente ao SPEC-NNN declarado no título de cada feature.
- Identificadores de código são em inglês; comentários e docstrings em português, explicando o porquê da degradação controlada (por que persistir localmente em vez de simplesmente falhar quando a API está fora do ar) e por que a URL nunca é hardcoded (Princípio VII da constituição).
- Este agente não introduz uma segunda abstração de cliente HTTP genérica — usa a biblioteca HTTP já estabelecida no projeto (`httpx`, já dependência transitiva via `pydantic_ai`/MCP), sem `Protocol` especulativo (Princípio II).
