# Research: Conformance Validator Agent (SPEC-011)

## 0. Comparação semântica via julgamento de LLM, não embeddings nem diff textual bruto

**Decision**: A classificação de cada regra (`novo`/`alterado`/`revogado`/
`conforme`) e a produção de `delta`/`recomendacao`/`severidade` são feitas
por um único `Agent` Pydantic AI (mesmo padrão do Compliance Analyzer,
SPEC-010) que recebe, em um único prompt, as `RegraExtraida` da versão
anterior e da versão atual do mesmo normativo, e devolve
`list[ConformanceItem]` estruturado (`output_type`).

**Rationale**: FR-001 exige diff "semântico... não diff textual bruto — a
comparação do significado da regra, não da string". Duas alternativas foram
avaliadas e descartadas (ver Alternatives), restando o julgamento por LLM
como a única abordagem que de fato compara *significado* em vez de
*string*: um humano lendo as duas regras entende que "prazo de 90 dias"
virou "prazo de 180 dias" é uma alteração de prazo, não duas regras
completamente diferentes — esse tipo de julgamento é exatamente o que um
LLM resolve bem e um diff de string ou uma similaridade de embedding não
capturam de forma confiável. Mesmo padrão estrutural do Compliance Analyzer
(SPEC-010): um `Agent` com `output_type` estruturado decide a partir de
texto, sem código de comparação especulativo por fora do LLM.

**Alternatives considered**: (a) Correspondência via similaridade de
embeddings (`EmbeddingsProvider`, SPEC-005) com um limiar de distância de
cosseno — descartada porque o double offline
(`OfflineEmbeddingsProvider`, SPEC-012) não carrega sinal semântico real
(é hash do texto completo), o que tornaria os testes desta feature contra
`EXPECTED_DELTAS.md` não determinísticos/não confiáveis em modo offline; em
produção, mediria similaridade lexical/estrutural aproximada, não
necessariamente o "significado" da regra, e introduziria um limiar
numérico arbitrário sem necessidade concreta (Princípio II, YAGNI: não há
uma segunda necessidade real de embeddings nesta feature, apenas
especulação de que "poderia ajudar"). (b) Diff textual bruto (`difflib`,
`git diff`-like) sobre `RegraExtraida.enunciado` — descartada
explicitamente pela própria spec (FR-001): um diff de string marcaria
"90 dias" → "180 dias" como uma pequena alteração textual, mas não
saberia dizer que o *significado* mudou (prazo estendido), nem
distinguiria uma correção ortográfica irrelevante de uma mudança de
substância (ver Edge Cases de spec.md).

## 1. Determinismo em teste: `FunctionModel` orientado pelo conteúdo real do prompt, não julgamento de LLM real

**Decision**: Os testes desta feature usam `pydantic_ai.models.function.FunctionModel`
com funções de decisão que **leem o texto real das `RegraExtraida`** contidas
nas mensagens do prompt (o mesmo conteúdo que viria de rodar o Compliance
Analyzer sobre os textos reais de `fixtures/normativos.json`) e retornam
deterministicamente a classificação/delta correspondente ao par documentado
em `fixtures/EXPECTED_DELTAS.md` — nunca uma chamada real ao Bedrock.

**Rationale**: SC-001/FR-010 exigem que os três pares já existentes
produzam *exatamente* os deltas documentados. Rodar isso contra um Bedrock
real tornaria o teste não determinístico (saída de LLM varia) e dependente
de rede/custo — inaceitável para uma suíte automatizada (mesma razão já
estabelecida em todas as features anteriores com LLM, SPEC-005 em diante).
A alternativa adotada prova exatamente o que um teste automatizado consegue
provar de forma honesta: que a **orquestração** deste agente (agrupamento
correto de versões por `numero`, roteamento correto de cada par para
comparação, montagem correta do `ConformanceReport` a partir da resposta do
modelo) está correta — a *qualidade do julgamento semântico* em si só um
Bedrock real poderia validar, e isso está deliberadamente fora do escopo de
um teste determinístico (mesmo caveat já registrado explicitamente em
research.md da SPEC-012, Decisão 0, para embeddings offline).

**Alternatives considered**: Rodar os testes contra o Bedrock real
(gated por uma env var, ex. `RUN_LIVE_BEDROCK_TESTS=1`) foi considerado e
descartado — nenhuma feature anterior deste projeto introduziu esse padrão,
e criar uma exceção aqui quebraria a consistência da suíte (Princípio III);
além disso, tornaria `pytest tests/test_conformance.py -q` (SC-003, comando
exigido literalmente pela spec) não reproduzível sem credencial AWS
configurada, contradizendo o espírito de "comando executável" do Princípio
VIII.

## 2. Agrupamento de versões: par mais recente vs. imediatamente anterior, por `numero`

**Decision**: Agrupar `NormativoItem` por `numero`, ordenar por `versao`
dentro de cada grupo, e comparar apenas a versão mais alta (`atual`) contra
a segunda mais alta (`anterior`) — ou `None` se só existir uma versão.
Versões mais antigas que a penúltima (histórico de 3+ versões) não são
comparadas nesta feature.

**Rationale**: Inspecionado `fixtures/normativos.json`: nenhum `numero`
tem mais de duas versões no corpus atual — o agrupamento "mais recente vs.
imediatamente anterior" já cobre 100% dos casos reais (3 pares com duas
versões, 50 normativos com uma versão só). Comparar contra um histórico
mais profundo seria especulação sem caso de uso real no corpus deste
projeto (Princípio II, YAGNI) — se o corpus crescer para ter cadeias de 3+
versões no futuro, o mesmo agrupamento "mais recente vs. imediatamente
anterior" continua correto sem alteração (gap analysis é sempre sobre o
estado atual vs. o estado imediatamente anterior, não a história completa).

**Alternatives considered**: Comparar a versão atual contra *todas* as
versões anteriores (cadeia completa) foi descartado — não há caso de uso
no corpus, nem pedido pela spec, que fala em "diferentes versões do mesmo
normativo" no singular implícito (uma comparação por normativo).

## 3. `resumo`/`criticidade_maxima` do `ConformanceReport`: calculados em código, não pelo LLM

**Decision**: Após todos os `ConformanceItem` serem produzidos (via LLM,
Decisão 0, ou deterministicamente para `novo`, Decisão 4), `resumo` e
`criticidade_maxima` do `ConformanceReport` são calculados em código puro
— `resumo` como uma frase gerada a partir das contagens reais por status
(quantos `alterado`/`revogado`/`novo`/`conforme`), `criticidade_maxima`
como o `StatusConformidade` de maior severidade entre `alterado` e
`revogado` presentes (ou `None` se nenhum gap existir).

**Rationale**: Delegar esses dois campos agregados ao LLM arriscaria uma
inconsistência entre o resumo/criticidade reportados e os itens de fato
presentes na lista (o LLM "errar a conta") — um bug de confiabilidade
evitável computando algo que já é 100% determinístico a partir dos dados já
estruturados (`ConformanceItem.status`), sem exigir nenhum julgamento
adicional de significado.

**Alternatives considered**: Pedir ao mesmo `Agent` que gere `resumo` como
texto livre a partir dos itens já classificados (uma segunda chamada de
LLM, ou o mesmo `output_type` incluindo `resumo`) foi descartado — o texto
do resumo não precisa de criatividade/julgamento (é uma contagem), e uma
segunda chamada de LLM para isso seria custo/latência sem benefício real.

## 4. Normativo sem versão anterior: `novo` resolvido em código, sem chamada ao LLM

**Decision**: Quando um `numero` só tem uma versão, todas as suas
`RegraExtraida` recebem `ConformanceItem(status=novo, delta=None,
recomendacao=None, severidade=0.0)` diretamente em código — nenhuma
chamada ao `Agent`/LLM acontece para esse caso.

**Rationale**: FR-006 exige que isso nunca lance erro — a forma mais
simples e robusta de garantir isso é não ter caminho nenhum que dependa de
uma "versão anterior" inexistente: o `if regras_anteriores is None` retorna
cedo, sem tentar montar um prompt de comparação com um lado vazio (que
poderia confundir o LLM ou produzir uma classificação incorreta como
`alterado`/`revogado` a partir de nada). É também mais barato: 50 dos 53
normativos do corpus mock caem neste caso — evitar 50 chamadas de LLM
desnecessárias para uma resposta já conhecida de antemão (`novo`, sempre)
é a escolha correta tanto por custo quanto por simplicidade.

**Alternatives considered**: Enviar ao LLM um prompt com "versão anterior:
nenhuma" e pedir que ele mesmo decida `novo` foi descartado — delegaria a
uma etapa não determinística (e com custo/latência) uma decisão que já é
100% determinística em código, sem nenhum julgamento de significado
envolvido (Princípio III, KISS).

## Resumo de dependências novas

Nenhuma dependência nova — `pydantic_ai`, `pix_compliance.guardrails`,
`pix_compliance.llm_provider`, `pix_compliance.models` já são módulos/
pacotes existentes, reaproveitados sem alteração.

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
