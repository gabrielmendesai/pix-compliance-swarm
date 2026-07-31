# PIX Compliance Swarm

Enxame de 7 agentes Pydantic AI que coleta, extrai, analisa, indexa e consolida
normativos PIX fictícios do BCB. Desafio técnico com prazo de 4 dias.
Briefing completo: `docs/BRIEFING.pdf`. Arquitetura: `docs/architecture.md`.

## Fluxo de trabalho — Spec-Driven Development

Este projeto é conduzido por specs. A regra é inegociável:

1. **Antes de escrever código, leia a spec correspondente em `specs/`.**
   Se eu disser "implemente a SPEC-009", leia `specs/SPEC-009-*.md` inteira
   antes de qualquer edição.
2. **Não implemente nada que esteja na seção "Fora" da spec.** Se algo parecer
   necessário e não estiver no escopo, pare e me pergunte — não expanda por
   conta própria.
3. **Critério de aceite é comando.** Ao terminar uma spec, rode os comandos
   listados em "Critérios de aceite" e me mostre a saída real.
4. **Se a implementação exigir uma decisão não prevista na spec**, proponha a
   alteração da spec primeiro, em texto. Só depois codifique.
5. Ao fechar uma spec, atualize seu `Status` para `done` e registre desvios na
   seção de notas.

## Stack

- Python 3.11+ · Pydantic v2 · Pydantic AI
- AWS Bedrock (LLM + Titan Embeddings) via `boto3` — caminho **padrão** de
  execução, credenciais só por env
- FastAPI · MCP com transporte SSE · pgvector · MinIO (S3-compatível)
- APScheduler · Docker Compose · pytest · ruff

## Princípios de código: SOLID/YAGNI/KISS aplicados, não decorados

Este é o ponto onde mais se perde qualidade em geração assistida por IA — o
padrão é gerar abstração demais. A regra aqui é o oposto do reflexo comum:

- **Toda `Protocol`/interface precisa responder: qual é a segunda
  implementação real, ou qual teste precisa substituir esta dependência?**
  Sem resposta concreta, use a classe direto. Não crie `AbstractBase` para uma
  única implementação "pensando no futuro" — isso é YAGNI, não design.
- `ObjectStore` é `Protocol` porque MinIO e S3 real são a mesma classe com
  `endpoint_url` diferente — seam real. `VectorStore`/pgvector é classe
  concreta, sem interface — só há uma implementação neste projeto.
- Um agente, uma responsabilidade. Não faça um agente "genérico" que decide
  internamente se extrai, categoriza ou compara — isso pertence a agentes
  separados por design do desafio.
- Prefira função pura e módulo simples a classe com estado quando não há
  necessidade real de estado. Não crie um `Manager`/`Service`/`Handler` para
  encapsular uma função de 5 linhas.
- Se ficar em dúvida entre duas abordagens, prefira a mais simples e registre
  a dúvida em comentário — não implemente as duas "para garantir".

## Comentários e nomenclatura

- **Identificadores (variáveis, funções, classes) em inglês.** Vocabulário de
  domínio do BCB/PIX mantido como está — `normativo`, `inciso`, `regra`,
  `vigencia` não se traduzem, são termos técnicos do setor regulatório.
- **Docstrings e comentários de linha em português.**
- **Todo comentário responde a uma pergunta que um leitor atento faria** —
  por que este algoritmo e não o óbvio, por que esta ordem, por que este caso
  de borda é tratado assim. Nunca parafraseie a linha seguinte
  (`# incrementa o contador` acima de `count += 1` é para deletar, não para
  escrever).
- Módulos com lógica de domínio não trivial — guardrail, conformance
  validator, chunking do RAG — recebem docstring de módulo ou classe
  explicando o raciocínio *antes* do código.
- Quando gerar um trecho de código, gere o comentário de "por quê" junto,
  não como passo separado depois.

## Convenções gerais

- **Toda** configuração passa por `src/pix_compliance/config.py`
  (`pydantic-settings`). Nunca literais de URL, região, modelo ou credencial
  no código.
- Modelos de domínio ficam em `models/` e são a fonte de verdade. Não crie
  dataclasses paralelas nem dicionários soltos para dados que já têm modelo.
- Todo modelo Pydantic usa `ConfigDict(extra="forbid")`.
- **Todo texto que vai para o LLM ou para o storage atravessa
  `guardrails.guard()`.** Não há exceção, nem em teste, nem em script.
- Logging estruturado em JSON, sempre com `correlation_id`.
- Erros de dependência externa viram exceções tipadas do projeto, nunca
  tracebacks crus vazando para o usuário.

## Bedrock é o padrão — nunca um fallback silencioso

`LLM_PROVIDER=bedrock` é o valor padrão em `config.py` e em `.env.example`.
Sem credencial ou sem acesso ao modelo liberado no console, a aplicação
**falha alto com mensagem clara** — nunca cai sozinha para outro provider.
O único outro valor é `LLM_PROVIDER=offline`, que usa um test double vivendo
em `tests/doubles/`, fora de `src/`, e existe exclusivamente para a suíte de
testes rodar sem rede. Não escreva nenhum caminho de produção que dependa do
double, e não o torne intercambiável com o Bedrock em tempo de execução fora
de teste.

## Comandos

```
make install   # dependências
make up        # docker compose up -d
make run       # pipeline ponta a ponta (usa Bedrock real)
make test      # suíte offline (LLM_PROVIDER=offline)
make lint      # ruff
```

## Armadilhas conhecidas

- A dimensão do embedding está travada em `config.py`. Ao mexer no vector
  store, valide a dimensão no upsert — incompatibilidade aqui falha
  silenciosamente.
- Extração de PDF/HTML é determinística, feita por ferramenta Python. O LLM
  só estrutura campos ambíguos. Não delegue parsing ao modelo.
- Chunking do RAG é por artigo/inciso, não por janela fixa de tokens.
- O Report Consolidator precisa chamar a API FastAPI como cliente HTTP com URL
  vinda de env var — isso é requisito literal do desafio, não detalhe.
- Acesso a modelos no Bedrock precisa ser solicitado por modelo no console
  AWS antes de qualquer teste manual — não é instantâneo.

## Git

Um commit por spec, no mínimo. Formato:
`feat(spec-007): servidor MCP SSE do scraper`
