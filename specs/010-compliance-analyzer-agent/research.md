# Research: Compliance Analyzer Agent (SPEC-010)

## 1. Mecanismo de limite de concorrência

**Decision**: `asyncio.Semaphore(settings.compliance_analyzer_max_concurrency)`,
adquirido antes de cada `await agent.run(...)` individual, com o lote inteiro
orquestrado via `asyncio.gather(*(analyze_one(item) for item in batch))`.

**Rationale**: É a primitiva mais simples da própria stdlib para limitar
concorrência — nenhuma dependência nova, nenhuma abstração própria do
projeto (Princípio II/III). Validado em spike manual: um `FunctionModel`
assíncrono com `asyncio.sleep` e um contador protegido por `asyncio.Lock`
confirma que, com `Semaphore(3)` e 10 tarefas em `asyncio.gather`, o pico de
chamadas simultâneas nunca excede 3 — exatamente o comportamento que o
critério de aceite (SC-003) exige comprovar por instrumentação, não apenas
pelo resultado final.

**Alternatives considered**: Um pool de workers/threads foi descartado —
`Agent.run()` do Pydantic AI já é assíncrono nativamente (`asyncio`), e usar
threads introduziria uma segunda forma de concorrência no projeto sem
necessidade, já que a chamada ao LLM é I/O-bound (rede), o caso ideal para
`asyncio`, não threads.

## 2. Onde armazenar o limite de concorrência e o limiar de confiança

**Decision**: Dois novos campos em `Settings`
(`compliance_analyzer_max_concurrency: int`,
`compliance_analyzer_confidence_threshold: float`), lidos de variável de
ambiente, seguindo o mesmo padrão já estabelecido para toda configuração do
projeto (nunca fixo no código, sempre documentado em `.env.example`).

**Rationale**: A spec exige explicitamente que ambos sejam configuráveis
(FR-003, FR-005), não fixos no código — `Settings` já é o único ponto de
configuração centralizada do projeto desde a SPEC-001; adicionar dois campos
novos segue o padrão existente em vez de introduzir uma segunda fonte de
configuração (ex. um arquivo YAML próprio desta feature).

**Alternatives considered**: Passar esses valores como argumentos de função
sem lastro em `Settings`/env var foi descartado — a spec pede
"configurável", que no vocabulário já estabelecido do projeto significa
"configurável via variável de ambiente através de `Settings`", não apenas
"parametrizável em código".

## 3. Campo de sinalização de revisão humana em `RegraExtraida`

**Decision**: Adicionar `revisao_humana_necessaria: bool` a `RegraExtraida`
(SPEC-002), calculado como `confianca < settings.compliance_analyzer_confidence_threshold`
no momento da produção da regra pelo agente — sem alterar nenhum campo já
existente do modelo.

**Rationale**: A spec exige uma marcação explícita, distinta do valor
numérico de `confianca` (FR-005) — um booleano é o tipo mais simples que
comunica "precisa de revisão: sim/não" sem exigir que o consumidor da saída
interprete um número. Estender `RegraExtraida` pontualmente segue o mesmo
precedente já usado em features anteriores (`ScrapeResult`, SPEC-008, foi
adicionado a `models.py` sem alterar modelos existentes).

**Alternatives considered**: Um campo de enum (`status_revisao`) com mais de
dois valores foi considerado e descartado — a spec pede apenas sinalização
binária ("precisa de revisão ou não"), e um enum de dois valores seria
equivalente a um booleano com passo extra de indireção, sem ganho real
(Princípio III, KISS).

## 4. System prompt: definição operacional das seis categorias

**Decision**: O system prompt do agente inclui uma definição operacional
curta e concreta de cada uma das seis categorias
(`participantes`, `tarifas`, `liquidação`, `segurança`, `SLA`,
`interoperabilidade`), com foco em distinguir pares de categorias
plausivelmente ambíguos entre si (ex. "participantes" trata de quem pode
integrar o arranjo e as condições para isso; "interoperabilidade" trata de
como diferentes participantes/sistemas se comunicam entre si — uma regra
sobre certificação técnica de conexão é "interoperabilidade", uma regra
sobre credenciamento de instituição é "participantes").

**Rationale**: A spec e as Notas de Implementação enfatizam que a qualidade
da categorização depende diretamente da clareza dessa definição — é o único
mecanismo de redução de ambiguidade disponível para um LLM que precisa
escolher exatamente uma categoria por regra, dado que o modelo `CategoriaCompliance`
(SPEC-002) já fecha o vocabulário em seis valores, sem espaço para uma
sétima categoria "outro"/"indefinido".

**Alternatives considered**: Usar poucas palavras-chave por categoria (sem
frase operacional completa) foi descartado — insuficiente para os pares
ambíguos citados na spec (participantes vs. interoperabilidade); a fronteira
precisa ser expressa em termos do "o que a regra regula", não apenas em
substantivos soltos.

## 5. Corpus de teste para as seis categorias (SC-001)

**Decision**: Construir os `NormativoItem` de teste (para exercitar as seis
categorias) diretamente a partir de `fixtures/normativos.json` (SPEC-003) —
confirmado que esse arquivo já contém registros reais das seis categorias
(`liquidação`, `SLA`, `participantes`, `tarifas`, `interoperabilidade`,
`segurança`), com pelo menos 4 registros por categoria.

**Rationale**: Este agente recebe `NormativoItem` como entrada (não
documento bruto) — não há necessidade de rodar o Extractor Agent (SPEC-009)
novamente para obter dados de teste; `fixtures/normativos.json` já é o
corpus estruturado e validado contra `NormativoItem` (garantia da SPEC-003),
cobrindo as seis categorias sem esforço adicional de fixture.

**Alternatives considered**: Gerar `NormativoItem` de teste ad-hoc, um por
categoria, escritos à mão no arquivo de teste, foi considerado — descartado
em favor de reaproveitar o corpus mock já existente e validado, que já
cobre as seis categorias organicamente (Princípio III, não duplicar dado de
teste que já existe).

## Resumo de dependências novas

Nenhuma dependência nova — `asyncio` é da stdlib; `pydantic-ai-slim`,
`structlog` e `pydantic` já são dependências existentes.

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
