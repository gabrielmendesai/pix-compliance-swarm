<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0
- Modified principles: nenhum dos oito princípios anteriores foi alterado
- Added sections:
  - Core Principle IX (Testes escritos antes da implementação, a partir do contrato,
    nunca do código)
- Removed sections: nenhuma
- Templates requiring follow-up:
  - .specify/templates/plan-template.md ⚠ pending manual check (validar que o
    "Constitution Check" passa a referenciar os 9 princípios acima)
  - .specify/templates/spec-template.md ⚠ pending manual check (não lido nesta execução)
  - .specify/templates/tasks-template.md ⚠ pending manual check (validar que a ordenação
    de tarefas — teste antes de implementação por user story — reflete o Princípio IX)
  - .specify/templates/checklist-template.md ⚠ pending manual check (não lido nesta execução)
- Deferred TODOs: nenhum — todos os campos foram preenchidos com conteúdo fornecido pelo usuário.
-->

# PIX Compliance Swarm Constitution

## Core Principles

### I. Bedrock é o caminho padrão, nunca um fallback silencioso

A integração com Amazon Bedrock é o modo de execução padrão da aplicação
(`LLM_PROVIDER=bedrock` como valor default em config e `.env.example`), não uma opção
entre outras. Na ausência de credencial ou de acesso ao modelo liberado no console, a
aplicação DEVE falhar alto, com mensagem clara e acionável — nunca degradar
automaticamente para outro provider. Existe um único provider alternativo,
`LLM_PROVIDER=offline`, implementado como test double vivendo exclusivamente em
`tests/doubles/`, fora de `src/`, usado apenas pela suíte de testes para rodar sem rede
e sem custo de token. Nenhum caminho de produção pode depender dele, e ele nunca deve
ser intercambiável com o Bedrock em tempo de execução fora de teste.

### II. Abstração exige justificativa concreta (YAGNI)

Toda interface, `Protocol` ou classe abstrata só é criada quando existir, dentro do
próprio repositório, (a) uma segunda implementação real, ou (b) um teste que precise
substituir aquela dependência. Sem uma das duas razões, usa-se a classe concreta
diretamente. Não se cria abstração especulativa "pensando no futuro". Exemplo de
aplicação: `ObjectStore` é um protocolo porque a mesma classe serve MinIO local e S3
real trocando `endpoint_url` — seam real. O vector store sobre pgvector é uma classe
concreta, sem interface, porque este projeto implementa apenas uma opção de índice
vetorial; a alternativa (OpenSearch Serverless) fica documentada em prosa, não como
stub de código morto.

### III. Simplicidade sobre segmentação (KISS)

Módulos, agentes e specs só se separam quando o volume de responsabilidade justifica a
separação. Não se cria uma unidade de organização (spec, módulo, classe de serviço)
para menos de um punhado de linhas de lógica real. Quando duas responsabilidades
pequenas e fortemente relacionadas surgirem — como orquestração do pipeline e
agendamento de sua execução — elas vivem juntas na mesma unidade, com a relação entre
elas documentada.

### IV. Responsabilidade única por agente (SRP)

Cada agente do enxame tem exatamente uma responsabilidade e um contrato de
entrada/saída em Pydantic. Nenhum agente decide internamente entre múltiplos papéis
(por exemplo, extrair ou categorizar); múltiplos papéis significam múltiplos agentes.
Toda ferramenta invocada por um agente é tipada, com modelo Pydantic de entrada e
saída.

### V. Guardrail é ponto único e obrigatório

Todo texto que trafega em direção a um LLM ou a qualquer camada de persistência
atravessa a função de guardrail de PII. Não há exceção para testes, scripts ou
execuções ad-hoc. Novos detectores de PII se adicionam sem alterar nenhum agente —
este é o único ponto do sistema onde extensibilidade futura paga o custo de abstração
hoje, porque o conjunto de padrões de PII plausivelmente cresce.

### VI. Contrato antes de comportamento

Os modelos de domínio Pydantic (entrada, ferramentas, saída, intermediários) são
definidos e congelados antes de qualquer lógica de agente ser implementada. Toda spec
de agente programa contra esses tipos; mudança de contrato depois de congelado exige
atualização explícita da spec correspondente antes da mudança de código.

### VII. Comentários e nomenclatura

Identificadores de código (variáveis, funções, classes) são em inglês. Vocabulário de
domínio do BCB/PIX é preservado como está — termos como normativo, inciso, regra,
vigência não se traduzem, são termos técnicos do setor regulatório. Docstrings e
comentários de linha são em português. Todo comentário responde a uma pergunta que um
leitor atento faria — por que este algoritmo, por que esta ordem, por que este caso de
borda é tratado assim — e nunca parafraseia a linha de código seguinte. Módulos com
lógica de domínio não trivial (guardrail, comparação de conformidade, chunking do
índice vetorial) recebem docstring de módulo ou classe explicando o raciocínio antes
do código.

### VIII. Evidência é entregável, não subproduto

Logs estruturados, critérios de aceite verificáveis por comando e artefatos de
evidência (screenshots, logs de execução) são produzidos durante o desenvolvimento de
cada spec, não reconstruídos ao final. Todo critério de aceite é um comando executável
ou um teste automatizado — nunca um julgamento subjetivo.

### IX. Testes escritos antes da implementação, a partir do contrato, nunca do código

Para toda feature com critérios de aceite verificáveis por teste, os arquivos de teste
são escritos e revisados antes de qualquer código de produção correspondente existir.
Os testes derivam exclusivamente dos contratos já definidos em `spec.md`,
`data-model.md` e `contracts/` daquela feature — nunca são escritos olhando para uma
implementação já pronta, o que os tornaria uma confirmação enviesada em vez de uma
verificação independente. A ordem de trabalho dentro de cada tarefa de implementação é:
escrever o teste que define o comportamento esperado, confirmar que ele falha (porque o
código ainda não existe ou ainda não satisfaz o contrato), só então escrever a
implementação até o teste passar. Ao gerar `tasks.md`, as tarefas de teste de cada user
story devem preceder as tarefas de implementação correspondentes, não vir depois delas.

## Contexto do Projeto e Stack Técnica

O PIX Compliance Swarm é um enxame de 7 agentes Pydantic AI para compliance de
normativos PIX fictícios do BCB, desenvolvido como desafio técnico com prazo de 4 dias
para a vaga de AI Engineer Sênior na Verity.

Stack técnica obrigatória: Python 3.11+, Pydantic v2, Pydantic AI, AWS Bedrock,
FastAPI, MCP (SSE), pgvector, MinIO, APScheduler, Docker Compose. Mudanças de stack que
substituam qualquer um desses componentes exigem justificativa explícita na spec
afetada, avaliada à luz dos Princípios I e II desta constituição.

## Governance

Esta constituição prevalece sobre qualquer prática de desenvolvimento, convenção de
equipe ou instrução pontual em conflito com ela. Em caso de conflito entre um destes
princípios e uma instrução pontual durante a implementação, os princípios desta
constituição prevalecem. Qualquer exceção precisa ser justificada por escrito na spec
afetada antes da implementação, não decidida silenciosamente durante a codificação.

Emendas a esta constituição exigem: (1) registro explícito da mudança proposta e sua
motivação, (2) atualização do número de versão segundo semver — MAJOR para remoção ou
redefinição incompatível de princípio, MINOR para adição de novo princípio ou seção,
PATCH para esclarecimentos e correções redacionais —, e (3) verificação de que specs,
plans e tasks em andamento permanecem compatíveis com o texto emendado, ou atualização
explícita deles.

Toda spec, plan e tasks gerados a partir deste projeto DEVEM ser revisados quanto à
conformidade com os nove princípios acima antes de merge. Complexidade adicional
(nova abstração, novo módulo, novo agente) deve ser justificada por escrito em relação
aos Princípios II, III e IV.

**Version**: 1.1.0 | **Ratified**: 2026-07-30 | **Last Amended**: 2026-08-03
