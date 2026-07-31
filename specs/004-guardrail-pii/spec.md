# Feature Specification: Camada de guardrail e PII (SPEC-004)

**Feature Branch**: `004-guardrail-pii`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Camada de guardrail e PII (SPEC-004) — garantir que nenhum dado sensível (CPF, CNPJ, e-mail, telefone, chave PIX aleatória) chegue a um LLM ou a qualquer camada de armazenamento sem antes ser mascarado."

**Dependências**: SPEC-002 (modelos de domínio, já implementada em `src/pix_compliance/models.py`). Esta feature **não** depende do provider LLM (SPEC-005) nem do storage (SPEC-006) — ambos vêm depois no cronograma, então o teste de enforcement do guardrail usa uma função-callable de exemplo, não o Bedrock real. A confirmação de que o provider Bedrock de fato atravessa o guardrail fica para quando a SPEC-005 for implementada.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são
  os demais agentes e camadas do sistema (agentes que chamam o LLM, camadas
  que escrevem em storage) que devem passar todo texto por este guardrail
  antes de qualquer envio externo ou persistência.
-->

### User Story 1 - Agente evita vazamento de CPF/CNPJ para o LLM (Priority: P1)

Um agente do enxame que está prestes a enviar um trecho de texto extraído de um normativo para o LLM precisa ter certeza de que nenhum CPF ou CNPJ real presente nesse texto seja enviado sem mascaramento, mas também precisa que sequências numéricas parecidas com CPF/CNPJ (porém com dígito verificador inválido, ou meramente 11 dígitos aleatórios) não sejam mascaradas desnecessariamente, preservando a legibilidade do texto legítimo.

**Why this priority**: É o núcleo do guardrail — sem detecção confiável (com baixo falso positivo) de CPF/CNPJ, o restante do enxame não pode confiar que dados sensíveis não vazam para o LLM nem que texto legítimo é destruído por mascaramento excessivo.

**Independent Test**: Pode ser testado isoladamente chamando as funções de detecção/mascaramento de `src/pix_compliance/guardrails.py` com strings de exemplo (CPF válido, CPF com dígito verificador inválido, sequência de 11 dígitos aleatória) e inspecionando o resultado, sem depender de nenhum LLM real.

**Acceptance Scenarios**:

1. **Given** um texto contendo um CPF com dígito verificador válido, **When** o texto passa pelo guardrail, **Then** o CPF é mascarado preservando o formato original (por exemplo, `123.***.***-01`).
2. **Given** um texto contendo uma sequência no formato de CPF mas com dígito verificador inválido, **When** o texto passa pelo guardrail, **Then** a sequência não é reconhecida como PII e permanece no texto como está.
3. **Given** um texto contendo uma sequência de 11 dígitos que claramente não é um CPF (por exemplo, sem nenhuma formatação de CPF e falhando o dígito verificador), **When** o texto passa pelo guardrail, **Then** nenhum falso positivo é gerado.

---

### User Story 2 - Ponto único de aplicação impede chamadas acidentais com texto não mascarado (Priority: P2)

Um desenvolvedor implementando um novo agente ou uma nova camada de storage precisa de uma única função (`guard`) que force, estruturalmente, que qualquer texto destinado a um LLM ou a uma escrita de storage passe pela detecção e mascaramento de PII antes de chegar ao destino — sem depender de disciplina manual do desenvolvedor em lembrar de aplicar o guardrail em cada novo ponto de código.

**Why this priority**: Depende dos detectores da User Story 1, mas é o que transforma detecção em garantia arquitetural: sem um ponto único e obrigatório de aplicação, é fácil um novo agente esquecer de aplicar o guardrail e vazar PII mesmo com os detectores corretos implementados.

**Independent Test**: Pode ser testado isoladamente envolvendo uma função de exemplo (não o Bedrock real) com `guard()` e verificando que essa função nunca é invocada com o texto original não mascarado, mesmo quando o texto de entrada contém PII.

**Acceptance Scenarios**:

1. **Given** uma função de exemplo que apenas registra o argumento recebido, **When** essa função é envolvida por `guard()` e chamada com um texto contendo PII, **Then** o argumento efetivamente recebido pela função de exemplo é o texto mascarado, nunca o original.
2. **Given** um texto sem nenhuma PII, **When** o texto passa por `guard()`, **Then** o texto chega à função de exemplo inalterado (nenhum mascaramento espúrio).

---

### User Story 3 - Detecção é auditável sem expor o dado sensível em log (Priority: P3)

Um responsável por operar o sistema em produção precisa conseguir auditar quantas detecções de PII ocorreram e de que tipo, através do log estruturado, sem que o próprio log se torne uma nova superfície de vazamento de dado sensível (o valor original nunca aparece no log).

**Why this priority**: Depende do guardrail já estar detectando e mascarando (User Stories 1 e 2), mas é a prioridade mais baixa porque é uma capacidade de observabilidade sobre um mecanismo que já funciona, não um requisito para o mascaramento em si funcionar.

**Independent Test**: Pode ser testado isoladamente chamando `guard()` com um texto contendo PII e inspecionando a saída de log capturada, verificando que ela contém tipo e contagem de detecção, mas não o valor original.

**Acceptance Scenarios**:

1. **Given** um texto contendo um CPF e um e-mail válidos, **When** o texto passa pelo guardrail, **Then** o log estruturado registra uma entrada por tipo de PII detectado, com a contagem de ocorrências.
2. **Given** o mesmo cenário anterior, **When** a saída de log é inspecionada, **Then** o valor original do CPF e do e-mail não aparece em nenhum campo do log.

---

### Edge Cases

- O que acontece quando o texto de entrada excede um tamanho máximo razoável? O guardrail MUST rejeitar ou sinalizar o texto antes de processá-lo, em vez de tentar aplicar os detectores sobre um payload arbitrariamente grande.
- Como o sistema trata um texto contendo um delimitador suspeito ou uma instrução embutida do tipo "ignore as instruções anteriores" (indício de tentativa de injeção de prompt)? O guardrail MUST sinalizar esse padrão, além de continuar aplicando a detecção/mascaramento normal de PII.
- O que acontece com um texto que contém múltiplas ocorrências do mesmo tipo de PII (por exemplo, dois CPFs diferentes)? Cada ocorrência válida MUST ser mascarada individualmente, e a contagem no `PIIReport` MUST refletir o total de ocorrências, não apenas presença/ausência.
- Como o sistema trata uma chave PIX aleatória (UUID) presente no texto? Ela MUST ser detectada e mascarada como as demais categorias de PII.
- O que acontece se o texto de entrada for vazio ou `None`? O guardrail MUST tratar esse caso sem lançar exceção não tratada.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer detectores de CPF, CNPJ, e-mail, telefone e chave PIX aleatória em `src/pix_compliance/guardrails.py`.
- **FR-002**: O sistema MUST validar o dígito verificador de CPF e CNPJ (não apenas formato/regex), reduzindo falsos positivos em relação a uma checagem ingênua de padrão numérico.
- **FR-003**: O sistema MUST mascarar cada ocorrência detectada preservando o formato original do dado (por exemplo, `123.***.***-01` para CPF), em vez de substituir por um marcador genérico sem relação com o formato de origem.
- **FR-004**: O sistema MUST fornecer um modelo `PIIReport` (Pydantic, seguindo o padrão dos modelos da SPEC-002) contendo, no mínimo: tipo de PII detectado, posição no texto e contagem de ocorrências.
- **FR-005**: O sistema MUST expor uma função `guard(text: str) -> GuardedText` como único ponto de aplicação permitido para qualquer texto destinado a um LLM ou a uma escrita de storage.
- **FR-006**: O sistema MUST realizar uma verificação básica de tamanho de texto antes de aplicar os detectores.
- **FR-007**: O sistema MUST detectar padrões simples de injeção de prompt (delimitadores suspeitos, instruções embutidas do tipo "ignore as instruções anteriores").
- **FR-008**: O sistema MUST registrar, via log estruturado (JSON, seguindo o padrão de logging da SPEC-001), toda detecção de PII com tipo e contagem de ocorrências.
- **FR-009**: O sistema MUST NUNCA incluir o valor original detectado no log estruturado.
- **FR-010**: Uma função de exemplo (não o provider Bedrock real) envolvida por `guard()` MUST, comprovadamente, nunca receber o texto original não mascarado como argumento.
- **FR-011**: Esta feature MUST NOT implementar anonimização reversível, criptografia, ou integração real com o provider Bedrock — esses itens ficam fora de escopo (anonimização reversível e criptografia permanentemente; a integração real com Bedrock fica para a SPEC-005).

### Ajuste em fixture existente (bloqueante para os testes desta feature)

- **FR-012**: O CNPJ plantado no documento de PII gerado pela SPEC-003 (`fixtures/documents/`, atualmente `80.683.921/0001-36`, com dígito verificador inválido) MUST ser corrigido para um valor com dígito verificador correto, mantendo o mesmo formato e o restante do documento inalterado — do contrário, a validação real de dígito verificador desta feature deixaria de reconhecer esse CNPJ como PII, quebrando silenciosamente a demonstração ponta a ponta desse fixture. O CPF já existente no mesmo documento (`043.931.725-82`, dígito verificador válido) permanece como está.

### Key Entities *(include if feature involves data)*

- **PIIReport**: Relatório estruturado de uma execução de detecção de PII sobre um texto — para cada ocorrência detectada, registra o tipo de PII, a posição no texto original e a contagem total de ocorrências daquele tipo.
- **GuardedText**: Resultado da aplicação do guardrail sobre um texto de entrada — contém o texto já mascarado (nunca o original) e o(s) `PIIReport` associado(s), pronto para ser enviado a um LLM ou persistido em storage.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, conforme fornecido no input
  desta feature — mantidos como estão, sem reescrever para linguagem
  tecnologia-agnóstica, por instrução explícita do solicitante e por
  alinhamento ao Princípio VIII da constituição (evidência como entregável:
  todo critério de aceite é um comando executável, não um julgamento
  subjetivo).
-->

### Measurable Outcomes

- **SC-001**: `pytest tests/test_guardrails.py -q` passa, cobrindo: CPFs com dígito verificador válido (mascarados), CPFs com dígito verificador inválido (não reconhecidos como PII, tratados como texto comum), e sequências de 11 dígitos que claramente não são CPF (sem falso positivo).
- **SC-002**: Um teste de integração prova que uma função de exemplo envolvida pelo `guard()` não pode ser chamada com o texto original não mascarado — o wrapper intercepta antes da chamada.
- **SC-003**: O log estruturado registra cada detecção com tipo e contagem, e nunca inclui o valor original detectado (confirmado por teste que inspeciona a saída de log).

## Assumptions

- Esta spec cobre apenas detecção, mascaramento, relatório estruturado e ponto único de aplicação; nenhuma lógica de agente real ou integração com o provider Bedrock é implementada aqui (Assumption compartilhada com o Escopo — fora).
- O guardrail é implementado como um módulo de funções em `src/pix_compliance/guardrails.py`, não como uma hierarquia de classes/interfaces — nenhuma segunda implementação ou teste exige essa abstração hoje (Princípio II da constituição, YAGNI).
- A verificação de padrões de injeção de prompt exigida aqui é uma checagem básica e sintática (delimitadores suspeitos, frases de instrução embutida conhecidas), não um classificador sofisticado — isso é adequado ao escopo desta spec; detecção mais avançada, se necessária, seria tratada em uma spec futura.
- O ajuste do CNPJ na fixture da SPEC-003 (FR-012) é tratado como um bloqueio direto dos testes desta feature, não uma mudança de escopo da SPEC-003 em si — a fixture continua representando a mesma demonstração de ponta a ponta, apenas com um valor sintaticamente correto.
- "Chave PIX aleatória" refere-se ao formato de chave gerada como UUID (EVP aleatório), não aos demais tipos de chave Pix (CPF/CNPJ/e-mail/telefone), que já são cobertos pelos detectores correspondentes.
