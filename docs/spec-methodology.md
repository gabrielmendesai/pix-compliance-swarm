# Metodologia de especificação (SDD)

Como este projeto foi de fato desenvolvido — não um resumo genérico de "o que é spec-driven
development", mas como essa prática foi aplicada especificamente ao PIX Compliance Swarm.

## O que é SDD neste projeto

Todo o desenvolvimento seguiu o [GitHub Spec Kit](https://github.com/github/spec-kit): cada
funcionalidade do projeto (dezoito ao todo, `specs/001-fundacao-projeto-configuracao` a
`specs/018-docs-diagramas-evidencias`) nasce como uma **spec numerada** — um documento que
define o que precisa existir e por quê, escrito e revisado **antes** de qualquer código
correspondente. O fluxo por spec é sempre o mesmo, executado pelos comandos do Spec Kit
(`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`):

1. **`spec.md`** — user stories priorizadas, requisitos funcionais testáveis, critérios de
   aceite mensuráveis, e um escopo "dentro"/"fora" explícito.
2. **`plan.md`** — contexto técnico, e um "Constitution Check" (ver abaixo) contra os nove
   princípios do projeto, antes e depois do design.
3. **`research.md`** — decisões de abordagem, com racional e alternativas rejeitadas
   registradas em prosa (não como comentário morto no código).
4. **`data-model.md`**/**`contracts/`** — contrato de dados/interface definido antes do
   comportamento (Princípio VI).
5. **`tasks.md`** — tarefas executáveis, organizadas por user story, com as tarefas de teste
   precedendo as de implementação correspondente (Princípio IX).

## Por que specs numeradas com escopo negativo explícito

Cada `spec.md` tem uma seção "Escopo — fora" tão obrigatória quanto "Escopo — dentro". Isso
não é boilerplate: é o mecanismo que impede duas armadilhas comuns em projetos com prazo
apertado — (a) escopo implícito, onde ninguém sabe se algo "ainda não foi feito" ou "foi
decidido que não seria feito", e (b) decisão de escopo tomada silenciosamente no meio da
codificação, sem registro. Um exemplo concreto: a SPEC-017 (testes e observabilidade)
declara explicitamente que cobertura de testes exaustiva (100%) e testes de carga/performance
estão fora de escopo — sem essa declaração, seria ambíguo se a spec "esqueceu" desses itens
ou decidiu conscientemente não persegui-los.

A numeração sequencial (`001` a `018`) também é deliberada: reflete a ordem real (ou quase
real — ver "Desvios reais do Princípio IX" abaixo) em que o projeto foi construído, permitindo
reconstruir o histórico de decisões arqueologicamente, sem depender só do `git log`.

## Papel do `constitution.md`

`.specify/memory/constitution.md` define nove princípios que **prevalecem sobre qualquer
instrução pontual em conflito** (ver a seção "Governance" do próprio arquivo). Não são
aspiracionais — cada `plan.md` de cada spec contém uma seção "Constitution Check" que avalia
explicitamente a conformidade com os nove antes do design (`research.md`) e depois dele,
sinalizando qualquer violação em uma tabela de "Complexity Tracking" com justificativa por
escrito, nunca uma exceção silenciosa.

Os nove princípios, resumidos:

| # | Princípio | Em uma frase |
|---|---|---|
| I | Bedrock é o caminho padrão | Nunca um fallback silencioso para outro provider em produção |
| II | Abstração exige justificativa concreta | Sem segunda implementação real ou teste que precise dela, não vira `Protocol` |
| III | Simplicidade sobre segmentação | Não criar uma unidade de organização para pouca lógica real |
| IV | Responsabilidade única por agente | Um agente, um papel — múltiplos papéis viram múltiplos agentes |
| V | Guardrail é ponto único e obrigatório | Todo texto rumo a um LLM/persistência passa por `guard()`, sem exceção |
| VI | Contrato antes de comportamento | Modelos Pydantic congelados antes da lógica de agente ser implementada |
| VII | Comentários e nomenclatura | Identificadores em inglês, comentários/docstrings em português, sempre respondendo "por quê" |
| VIII | Evidência é entregável | Logs estruturados e critérios de aceite verificáveis, produzidos junto com a spec, não reconstruídos depois |
| IX | Testes antes da implementação | Teste escrito e confirmado falho antes do código correspondente existir |

## Papel do `CLAUDE.md` e do Claude Code

O desenvolvimento foi assistido por IA (Claude Code) com revisão humana em cada etapa — não
geração autônoma sem supervisão (ver também "Desenvolvimento e ferramentas" no README).
`CLAUDE.md` (na raiz do repositório) documenta as convenções de projeto que o agente de IA
segue automaticamente em toda sessão: onde ficam as specs, como interpretar a constituição,
qual o fluxo de comandos do Spec Kit a seguir. As `skills/*/SKILL.md` (ver README) cumprem um
papel análogo em escopo mais estreito: documentam o contrato de cada agente do enxame, e
foram consultadas pelo Claude Code ao implementar cada spec subsequente que dependia daquele
agente — evitando redescobrir o contrato lendo o código-fonte inteiro a cada nova spec.

## Desvios reais do Princípio IX

Honestidade sobre o processo real, não uma narrativa sem atrito: dois desvios concretos do
"teste antes da implementação" aconteceram ao longo do projeto, ambos já documentados
nominalmente nas specs correspondentes (não descobertos agora, retroativamente).

### SPEC-011 (Conformance Validator) — implementada fora de ordem

A própria `specs/011-conformance-validator-agent/spec.md` registra: "esta é a SPEC-011 do
catálogo do projeto — deveria ter sido implementada antes da SPEC-012 (Knowledge Builder) e
da SPEC-014 (Report Consolidator), mas foi pulada por engano e está sendo implementada agora,
fora de ordem." O Report Consolidator (SPEC-014) foi construído **sem** essa dependência
disponível — consumindo uma versão provisória do relatório de conformidade, não a real. Uma
ação de acompanhamento (revisar o Report Consolidator para consumir o `ConformanceReport` real
produzido pela SPEC-011) ficou registrada como pendente na própria spec, não escondida —
resolvida apenas parcialmente ao longo das specs seguintes.

### SPEC-017 (Testes e observabilidade) — ordem parcialmente invertida

Por a feature ser sobre os próprios testes (não sobre construir algo novo), a ordem "teste
antes do código" se inverteu parcialmente: primeiro **auditar** a suíte já existente (rodá-la
por completo, identificar lacunas reais), depois **escrever** os testes que faltavam
(incluindo um teste ponta a ponta real), e só então **ajustar** código de produção onde a
auditoria revelou um problema real — por exemplo, um bug de PII genuíno encontrado durante
essa auditoria (e-mail de um único caractere detectado pelo guardrail, mas não mascarado no
texto final) foi corrigido depois que um teste novo o expôs, não antes. Essa inversão foi
deliberada e documentada na própria `spec.md` da SPEC-017 (seção Assumptions) — não um
descuido, mas ainda assim uma mudança de ordem em relação ao padrão das dezesseis specs
anteriores.
