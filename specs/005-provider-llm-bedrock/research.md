# Research: Provider LLM e embeddings via Amazon Bedrock (SPEC-005)

> **Adendo (patch pós-implementação)**: a Decision #2 abaixo (Pydantic AI
> nativo, `BedrockConverseModel`/API Converse) foi **revertida** para o
> transporte de chat depois de descoberta em setup manual no console: Claude
> Haiku 4.5 (o modelo escolhido) só é servido pela Messages API atual do
> Bedrock (`/anthropic/v1/messages`, via `AnthropicBedrock` do SDK
> `anthropic`), não pela API Converse legada, que atende apenas modelos até
> Opus 4.6. Decisão #1 (autenticação explícita a partir de `Settings`) e
> Decisão #3 (embeddings via `invoke_model`/`boto3`) permanecem válidas sem
> alteração — só o transporte de chat mudou. Ver nota completa no README
> ("Nota de arquitetura: duas superfícies de integração do Bedrock") e o
> código atual em `src/pix_compliance/llm_provider.py`
> (`BedrockChatProvider`).

## 1. Cliente Bedrock e autenticação

**Decision**: Usar `boto3.client("bedrock-runtime", region_name=settings.aws_region)`,
com credenciais resolvidas pela cadeia padrão de resolução do `boto3`
(variáveis de ambiente lidas primeiro por `Settings`/`pydantic-settings`, depois
passadas explicitamente ao client via `aws_access_key_id`/`aws_secret_access_key`
— não delegar a descoberta implícita do `boto3` a `~/.aws/credentials`, para que
o comportamento seja idêntico em CI e em qualquer máquina do avaliador).

**Rationale**: `Settings` (SPEC-001) já centraliza a leitura de
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_REGION` com falha alta e
mensagem acionável quando ausentes (`ConfigurationError`). Passar essas
credenciais explicitamente ao `boto3.client(...)` (em vez de deixar o SDK
procurar em `~/.aws/`, variáveis de ambiente de nome diferente, ou IAM role)
garante que o único caminho de credencial reconhecido pelo projeto é o
documentado em `.env.example` — sem uma segunda fonte de verdade implícita.

**Alternatives considered**: Deixar o `boto3` resolver credenciais pela sua
cadeia padrão (env vars com nomes que já coincidem, profile, IAM role) foi
descartado porque criaria uma segunda via de configuração não documentada nem
testável deterministicamente, divergindo do Princípio VIII (evidência
verificável por comando).

## 2. Provider de chat compatível com Pydantic AI

**Decision**: Usar o suporte nativo do Pydantic AI a Bedrock
(`pydantic_ai.models.bedrock.BedrockConverseModel` com
`pydantic_ai.providers.bedrock.BedrockProvider`), configurado com o cliente
`boto3` construído no passo 1 e `model_id=settings.bedrock_model_id`.

**Rationale**: Pydantic AI já expõe um provider Bedrock de primeira classe que
usa a API Converse do `bedrock-runtime` (suporta tool calling e streaming da
mesma forma que os demais providers da biblioteca) — não há necessidade de
escrever um adaptador manual entre a API de baixo nível do `boto3` e o
contrato de `Model`/`Agent` do Pydantic AI. Isso mantém a integração alinhada
ao Princípio II (não reinventar uma abstração que a biblioteca já resolve).

**Alternatives considered**: Chamar `bedrock-runtime.invoke_model` diretamente
e adaptar a resposta manualmente ao formato esperado pelos agentes Pydantic AI
foi descartado — duplicaria lógica que o pacote `pydantic-ai` já mantém
testada, sem ganho para este projeto.

## 3. Provider de embeddings (Titan)

**Decision**: Chamar `bedrock-runtime.invoke_model` diretamente com
`modelId=settings.bedrock_embeddings_model_id` (Titan Embeddings), encapsulado
em `BedrockEmbeddingsProvider.embed(text: str) -> list[float]`.

**Rationale**: Pydantic AI não expõe um contrato de "embeddings provider"
próprio (seu foco é chat/agent); Titan Embeddings não usa a API Converse.
Chamar `invoke_model` diretamente é o caminho mais simples e direto — sem
introduzir uma dependência adicional só para embeddings.

**Alternatives considered**: Usar uma biblioteca terceira de abstração de
embeddings (ex. LangChain embeddings) foi descartado — adicionaria uma
dependência inteira do ecossistema LangChain só para uma chamada HTTP que o
`boto3` já cobre, contrariando o Princípio III (KISS).

## 4. Cadeia de fallback com backoff exponencial

**Decision**: Usar `tenacity` (`retry`, `wait_exponential`, `retry_if_exception_type`)
para envolver a chamada a cada `model_id` da lista configurada; ao esgotar as
tentativas de um modelo, avançar para o próximo `model_id` da lista antes de
propagar a exceção final.

**Rationale**: `tenacity` é a biblioteca padrão de mercado em Python para
retry/backoff, evitando reimplementar manualmente contagem de tentativas e
cálculo de espera exponencial — uma dependência pequena e amplamente usada,
justificável pelo mesmo raciocínio do Princípio II (não construir algo que uma
biblioteca madura já resolve de forma simples).

**Alternatives considered**: Implementar backoff manual com `time.sleep` em um
laço `for` foi considerado suficiente em complexidade, mas descartado por
reinventar uma solução já resolvida por uma dependência leve e testada.

## 5. Exceções tipadas para erros do Bedrock

**Decision**: Capturar `botocore.exceptions.ClientError`, inspecionar
`error.response["Error"]["Code"]`, e mapear `ThrottlingException`,
`ValidationException` e `AccessDeniedException` para três exceções próprias
do projeto (`BedrockThrottlingError`, `BedrockValidationError`,
`BedrockAccessDeniedError`), todas herdando de uma exceção-base comum
`BedrockProviderError`, seguindo o mesmo padrão já usado por
`ConfigurationError` (SPEC-001) e `GuardrailInputError` (SPEC-004).

**Rationale**: `botocore` sempre levanta `ClientError` genérico com o código
de erro real dentro do payload de resposta, não como subclasses distintas de
exceção Python — inspecionar `Error.Code` é o padrão idiomático de
`boto3`/`botocore` para diferenciar esses casos.

**Alternatives considered**: Deixar o `ClientError` cru propagar foi descartado
— quebraria o Princípio VIII (mensagem acionável) e o FR-007 explícito da
spec.

## 6. `OfflineProvider` determinístico

**Decision**: Implementar `OfflineProvider` em `tests/doubles/offline_provider.py`
como uma classe concreta (sem herdar de nenhuma classe de `src/`) que responde
de forma determinística tanto para chat (eco/hash simples do prompt recebido)
quanto para embeddings (vetor determinístico derivado de um hash do texto de
entrada), selecionada por uma factory (`get_chat_provider()`/
`get_embeddings_provider()` em `llm_provider.py`) que verifica
`settings.llm_provider` e importa o double apenas quando o valor for
`"offline"` — o import do módulo de teste acontece dentro do branch de
seleção, nunca no topo do arquivo de produção, para que `src/` nunca dependa
estruturalmente de `tests/`.

**Rationale**: Determinismo (mesmo input sempre produz mesmo output) é o que
permite os testes offline serem reprodutíveis e comparáveis, sem introduzir
aleatoriedade que exigiria seeds ou tolerância em asserts. Isolar o import
dentro do branch condicional é o mecanismo concreto que impede o double de se
tornar acidentalmente intercambiável com o Bedrock em produção — mesmo que
`LLM_PROVIDER=offline` seja setado por engano em produção, o double
propositalmente não faz nenhuma chamada de rede nem produz resposta realista,
tornando esse cenário imediatamente detectável em vez de silenciosamente
plausível.

**Alternatives considered**: Definir uma interface (`Protocol`) formal
compartilhada entre `BedrockChatProvider`/`BedrockEmbeddingsProvider` e
`OfflineProvider` foi considerado e mantido — é o único ponto desta feature em
que uma abstração se justifica (Princípio II), porque há de fato duas
implementações reais trocadas por configuração. Uma hierarquia de classes mais
profunda (ex. classe-base abstrata com template method) foi descartada por
excesso de estrutura para duas implementações concretas simples.

## Resumo de dependências novas

| Pacote | Uso | Justificativa |
|---|---|---|
| `boto3`/`botocore` | Cliente `bedrock-runtime` | Único SDK oficial AWS em Python |
| `pydantic-ai` | Provider de chat compatível com `Agent` do enxame | Já é stack obrigatória da constituição (Contexto do Projeto) |
| `tenacity` | Backoff exponencial na cadeia de fallback | Padrão de mercado, evita reimplementação manual |

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
