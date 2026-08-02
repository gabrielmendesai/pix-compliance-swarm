# Feature Specification: Provider LLM e embeddings via Amazon Bedrock (SPEC-005)

**Feature Branch**: `005-provider-llm-bedrock`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "Provider LLM e embeddings via Amazon Bedrock (SPEC-005) — integração real com o Amazon Bedrock como caminho padrão de execução da aplicação, com um test double isolado exclusivamente para a suíte de testes offline, nunca o inverso."

**Dependências**: SPEC-001 (config e logging) e SPEC-004 (guardrail — todo texto que entra nesta feature deve atravessar `guard()` antes de qualquer chamada ao provider).

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são
  os demais agentes do enxame, que precisam de um provider de chat e de
  embeddings configurado e confiável, e o operador/avaliador do projeto, que
  precisa de garantias de que a integração real com o Bedrock é o caminho de
  produção de fato exercitado — não substituível silenciosamente por um double.
-->

### User Story 1 - Aplicação recusa subir sem credencial Bedrock válida (Priority: P1)

Um agente do enxame, ou o operador do sistema, tenta rodar a aplicação com `LLM_PROVIDER=bedrock` (o padrão) sem que as credenciais AWS estejam configuradas no ambiente. A aplicação precisa falhar imediatamente, com uma mensagem clara e acionável, em vez de tentar prosseguir sem um provider funcional ou de trocar silenciosamente para outro caminho de execução.

**Why this priority**: É a garantia central desta spec — sem falha alta e explícita na ausência de credencial, não há como comprovar que a integração real com o Bedrock é o caminho padrão de fato exercitado, e uma degradação silenciosa comprometeria a avaliação do requisito nominal do desafio.

**Independent Test**: Pode ser testado isoladamente removendo `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` do ambiente, mantendo `LLM_PROVIDER=bedrock`, e verificando que a inicialização da aplicação levanta uma exceção com a mensagem acionável esperada, sem nenhuma chamada de rede.

**Acceptance Scenarios**:

1. **Given** `LLM_PROVIDER=bedrock` e nenhuma credencial AWS no ambiente, **When** a aplicação tenta subir, **Then** ela recusa subir e apresenta a mensagem "Credenciais Bedrock ausentes ou modelo sem acesso liberado. Configure AWS_ACCESS_KEY_ID/SECRET, ou use LLM_PROVIDER=offline apenas para rodar a suíte de testes."
2. **Given** o mesmo cenário anterior, **When** a falha ocorre, **Then** a aplicação nunca tenta prosseguir com outro provider por conta própria.

---

### User Story 2 - Suíte de testes roda inteira, offline e sem custo de token (Priority: P1)

Um desenvolvedor rodando a suíte de testes localmente ou em CI precisa que todos os testes passem sem depender de rede, de credenciais AWS reais ou de custo de invocação de modelo, usando um test double determinístico selecionado explicitamente via `LLM_PROVIDER=offline`.

**Why this priority**: Empatada em prioridade com a User Story 1 porque ambas expressam a mesma garantia estrutural (produção vs. teste nunca se confundem) a partir de lados opostos — aqui, o caminho de teste precisa funcionar de forma completa e isolada.

**Independent Test**: Pode ser testado isoladamente rodando `LLM_PROVIDER=offline pytest -q` em uma máquina sem acesso à internet e verificando que toda a suíte passa.

**Acceptance Scenarios**:

1. **Given** `LLM_PROVIDER=offline`, **When** a suíte de testes é executada, **Then** `pytest -q` roda por completo sem nenhuma chamada de rede.
2. **Given** o `OfflineProvider` implementado em `tests/doubles/`, **When** o código de `src/` é inspecionado, **Then** nenhum módulo de produção importa ou depende desse double.

---

### User Story 3 - Cadeia de fallback troca de modelo automaticamente na falha (Priority: P2)

Um agente do enxame está invocando o modelo primário configurado no Bedrock e esse modelo falha (por exemplo, por throttling ou indisponibilidade momentânea). O sistema precisa tentar automaticamente o próximo modelo da cadeia de fallback configurada, com backoff exponencial entre tentativas, em vez de propagar a falha imediatamente ao chamador.

**Why this priority**: Depende do provider básico (User Story 1) já estar funcional; é uma capacidade de resiliência sobre um mecanismo que já funciona, não um pré-requisito para a integração real existir.

**Independent Test**: Pode ser testado isoladamente mockando o primeiro modelo da lista de fallback para lançar uma exceção (por exemplo, `ThrottlingException`) e verificando que a chamada seguinte é feita contra o segundo modelo da cadeia, com sucesso.

**Acceptance Scenarios**:

1. **Given** uma cadeia de fallback com pelo menos dois `model_id`, **When** o primeiro modelo falha de forma mockada, **Then** o sistema tenta o próximo modelo da lista, com backoff exponencial entre tentativas.
2. **Given** todos os modelos da cadeia falhando, **When** a última tentativa também falha, **Then** o sistema propaga uma exceção própria do projeto, tipada, com mensagem clara sobre qual erro causou a falha final.

---

### User Story 4 - Erros específicos do Bedrock viram exceções próprias e legíveis (Priority: P2)

Um agente do enxame que invoca o provider Bedrock e recebe um erro de `ThrottlingException`, `ValidationException` ou `AccessDeniedException` precisa receber, de volta, uma exceção própria do projeto com mensagem clara sobre a causa — não a exceção crua do `boto3`/`botocore` propagada sem contexto.

**Why this priority**: Mesma faixa de prioridade da User Story 3 — é tratamento de erro que refina a experiência de quem depende do provider, mas pressupõe que a chamada básica ao Bedrock (User Story 1) já existe.

**Independent Test**: Pode ser testado isoladamente mockando o cliente `bedrock-runtime` para lançar cada uma das três exceções do `botocore` e verificando que o provider converte cada uma na exceção própria correspondente, com mensagem legível.

**Acceptance Scenarios**:

1. **Given** o cliente Bedrock mockado para lançar `ThrottlingException`, **When** o provider é invocado, **Then** o provider levanta uma exceção própria do projeto, tipada para esse caso, com mensagem clara.
2. **Given** o cliente Bedrock mockado para lançar `ValidationException`, **When** o provider é invocado, **Then** o provider levanta uma exceção própria do projeto, tipada para esse caso, com mensagem clara.
3. **Given** o cliente Bedrock mockado para lançar `AccessDeniedException`, **When** o provider é invocado, **Then** o provider levanta uma exceção própria do projeto, tipada para esse caso, com mensagem clara, mencionando a necessidade de liberação de acesso ao modelo.

---

### Edge Cases

- O que acontece se `LLM_PROVIDER` for definido com um valor diferente de `bedrock` ou `offline`? O sistema MUST falhar alto na inicialização, com mensagem indicando os únicos dois valores aceitos.
- O que acontece se um texto chegar ao provider sem ter passado por `guard()`? Esta spec assume que a responsabilidade de invocar `guard()` é de quem chama o provider (SPEC-004); esta spec não reimplementa essa checagem, mas a integração entre as duas camadas deve ser demonstrável em teste.
- Como o sistema trata a lista de fallback configurada com um único `model_id`? O comportamento é equivalente a não ter fallback — a falha desse único modelo propaga diretamente como falha final, sem tentativa adicional.
- O que acontece quando o `OfflineProvider` recebe uma chamada de embeddings, não apenas de chat? Ele MUST responder de forma determinística também para embeddings, não apenas para chat, para que a suíte de testes cubra ambos os caminhos sem rede.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer um cliente `bedrock-runtime` via `boto3`, com credenciais (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`) lidas exclusivamente de variável de ambiente — nunca hardcoded, nunca em arquivo versionado.
- **FR-002**: O sistema MUST fornecer um provider de chat compatível com Pydantic AI, apontando para um modelo Claude no Bedrock, com `BEDROCK_MODEL_ID` configurável via variável de ambiente.
- **FR-003**: O sistema MUST fornecer um provider de embeddings usando um modelo Titan no Bedrock.
- **FR-004**: O sistema MUST implementar uma cadeia de fallback de modelos configurável por lista de `model_id` — na falha de um modelo, o sistema tenta o próximo da lista, aplicando backoff exponencial entre tentativas.
- **FR-005**: O sistema MUST definir `LLM_PROVIDER=bedrock` como valor padrão em `config.py` e em `.env.example`.
- **FR-006**: O sistema MUST falhar alto, na ausência de credencial ou de acesso ao modelo, com a mensagem "Credenciais Bedrock ausentes ou modelo sem acesso liberado. Configure AWS_ACCESS_KEY_ID/SECRET, ou use LLM_PROVIDER=offline apenas para rodar a suíte de testes." — nunca degradando silenciosamente para outro provider.
- **FR-007**: O sistema MUST tratar de forma tipada `ThrottlingException`, `ValidationException` e `AccessDeniedException`, convertendo cada uma em uma exceção própria do projeto com mensagem clara.
- **FR-008**: O sistema MUST fornecer um `OfflineProvider` determinístico, implementado em `tests/doubles/`, fora de `src/`, selecionável apenas por `LLM_PROVIDER=offline`, usado exclusivamente pela suíte de testes.
- **FR-009**: O sistema MUST NUNCA permitir que o `OfflineProvider` seja selecionado ou usado em um caminho de execução de produção, independentemente de configuração.
- **FR-010**: Esta feature MUST NOT implementar fine-tuning nem batch inference — ambos ficam fora de escopo.

### Key Entities *(include if feature involves data)*

- **BedrockChatProvider**: Provider de chat compatível com Pydantic AI que invoca um modelo Claude no Bedrock via `bedrock-runtime`, com cadeia de fallback de `model_id` e tratamento tipado de exceções.
- **BedrockEmbeddingsProvider**: Provider de embeddings que invoca o modelo Titan no Bedrock via `bedrock-runtime`.
- **OfflineProvider**: Test double determinístico (chat e embeddings) vivendo em `tests/doubles/`, fora de `src/`, selecionável apenas por `LLM_PROVIDER=offline`.
- **Exceções tipadas do provider**: Conjunto de exceções próprias do projeto que substituem as exceções cruas do `botocore` (`ThrottlingException`, `ValidationException`, `AccessDeniedException`) por mensagens acionáveis.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável: todo critério de aceite é um comando executável,
  não um julgamento subjetivo).
-->

### Measurable Outcomes

- **SC-001**: Com `LLM_PROVIDER=bedrock` e sem credencial no ambiente, a aplicação recusa subir com a mensagem de erro acionável definida em FR-006 — nunca cai para outro provider por conta própria.
- **SC-002**: `LLM_PROVIDER=offline pytest -q` roda a suíte inteira sem rede.
- **SC-003**: Um teste de fallback, com o primeiro modelo da lista mockado para falhar, demonstra a troca para o próximo modelo da cadeia.
- **SC-004**: README documenta a policy IAM mínima necessária (usuário com acesso programático e a policy `AmazonBedrockFullAccess`, ou uma policy mais restrita equivalente) e o passo de "primeiro uso" (First Time Use) exigido uma única vez por conta para modelos Anthropic, feito no playground do console antes da primeira invocação.

## Assumptions

- O acesso a modelos no Bedrock é habilitado por padrão na conta hoje — não existe mais a etapa antiga de aprovação manual por modelo com espera de horas; para modelos Anthropic, resta apenas o formulário de caso de uso no playground do console, preenchido uma vez, com liberação imediata.
- A autenticação é sempre via credenciais IAM da AWS — não existe "chave de API do Claude" separada nesse fluxo, diferente da API direta da Anthropic.
- O vídeo de evidência final desta feature precisa mostrar uma invocação real ao Bedrock, com o `model_id` usado e o consumo de tokens visível no log — essa evidência é tratada como parte do critério de aceite SC-001/SC-003 em conjunto, não um item separado.
- Este é o ponto de maior risco de avaliação do projeto inteiro: se o `OfflineProvider` fosse intercambiável em runtime com o Bedrock, não haveria como comprovar que a integração real funciona, e uma queda silenciosa para o double seria lida como não cumprimento do requisito nominal do desafio.
- A separação `BedrockChatProvider`/`OfflineProvider` como duas implementações reais selecionadas por configuração é o único ponto desta feature em que uma interface/protocolo se justifica (Princípio II da constituição) — não se cria abstração além desse ponto de troca.
- Identificadores de código são em inglês; comentários e docstrings em português, explicando o porquê (por que a cadeia de fallback existe, por que a falha é alta e não silenciosa, por que o double vive fora de `src/`), conforme Princípio VII da constituição.
