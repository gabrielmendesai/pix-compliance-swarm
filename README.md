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

## Provider LLM e embeddings via Amazon Bedrock (`src/pix_compliance/llm_provider.py`)

`LLM_PROVIDER=bedrock` é o único caminho de produção (Princípio I da
constituição): sem credencial válida ou sem acesso ao modelo liberado, a
aplicação recusa subir com uma mensagem acionável — nunca degrada
silenciosamente para outro provider. `LLM_PROVIDER=offline` existe
exclusivamente para a suíte de testes (`OfflineProvider`, isolado em
`tests/doubles/`, nunca importável de dentro de `src/`).

### Configuração de acesso AWS necessária

1. **Usuário IAM com acesso programático**, com a policy gerenciada
   `AmazonBedrockFullAccess` anexada (ou uma policy mais restrita
   equivalente, por exemplo permitindo apenas `bedrock:InvokeModel` e
   `bedrock:InvokeModelWithResponseStream` nos ARNs dos modelos usados por
   este projeto). Gere um `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` para
   esse usuário e preencha `.env` (nunca versionar essas credenciais).
2. **Passo de "primeiro uso" (First Time Use) para modelos Anthropic**: no
   console AWS, abra o Bedrock → *Model access* → *Model catalog*, selecione
   o modelo Claude desejado e preencha o formulário de caso de uso no
   playground **uma única vez por conta** — a liberação é imediata (não há
   mais espera de aprovação manual por horas). Sem esse passo, toda
   invocação ao modelo falha com `AccessDeniedException`, que este projeto
   converte na mesma mensagem acionável usada para credencial ausente (ver
   `BedrockAccessDeniedError`/`BedrockCredentialsError` em
   `llm_provider.py`).
3. A autenticação é sempre via credenciais IAM da AWS — não existe uma
   "chave de API do Claude" separada nesse fluxo, diferente da API direta da
   Anthropic.

### Cadeia de fallback

`BEDROCK_FALLBACK_MODEL_IDS` (`.env.example`) aceita uma lista de `model_id`
adicionais, no mesmo formato de `BEDROCK_MODEL_ID`, separados por vírgula,
tentados em ordem com backoff exponencial caso o modelo primário falhe
(throttling, indisponibilidade momentânea). Erros de limite de taxa e de
requisição inválida acionam a tentativa do próximo modelo da cadeia; acesso
negado e credencial inválida falham alto imediatamente, sem tentar outro
modelo (não são transientes).

### Nota de arquitetura: duas superfícies de integração do Bedrock

O Bedrock hoje expõe **duas superfícies de integração distintas** para
modelos Anthropic, e este projeto usa a segunda de propósito, não por
descuido:

- **Legada** — API `InvokeModel`/`Converse`, acessada via `boto3.client
  ("bedrock-runtime")`. Documentada pela Anthropic como o caminho para
  **Claude Opus 4.6 e modelos anteriores**. Formato de `model_id`
  ARN-versionado (ex. `anthropic.claude-3-sonnet-20240229-v1:0`).
- **Atual** — Messages API em `/anthropic/v1/messages`, acessada via
  `AnthropicBedrock` do pacote `anthropic` (instalado com o extra
  `[bedrock]`). É a **única** superfície que serve os modelos Anthropic mais
  recentes, incluindo o **Claude Haiku 4.5** escolhido para este projeto. O
  formato de `model_id` aqui depende da disponibilidade do modelo na
  conta/região: pode ser um ID direto (`anthropic.claude-haiku-4-5`) ou,
  como neste projeto, um **inference profile de cross-region** (prefixo de
  grupo de região + sufixo de data/versão, ex.
  `us.anthropic.claude-haiku-4-5-20251001-v1:0`) — verificado em setup manual
  no console, quando o ID direto não estava disponível para invocação nessa
  conta. O que diferencia esta superfície da legada não é o formato do
  `model_id`, e sim o transporte (`AnthropicBedrock`/Messages API vs.
  `boto3`/Converse).

`BedrockChatProvider` (`src/pix_compliance/llm_provider.py`) usa a superfície
atual (`AnthropicBedrock`/Messages API) — não por preferência estética, mas
porque é a única que funciona com o modelo escolhido. Um efeito colateral
favorável: o formato de mensagens da Messages API (`{"role": ..., "content":
...}`) é o mesmo usado nativamente pelo Pydantic AI e por agentes que
conversam com modelos Anthropic fora do Bedrock, o que simplifica a
integração em vez de complicá-la. A autenticação continua idêntica nas duas
superfícies — sempre via `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/
`AWS_REGION`, resolvidos explicitamente a partir de `Settings`, nunca por
uma "chave de API do Claude" separada.

Embeddings Titan não têm equivalente no SDK `anthropic` —
`BedrockEmbeddingsProvider` continua na superfície legada
(`boto3`/`invoke_model`), que é a única forma de invocar Titan.
