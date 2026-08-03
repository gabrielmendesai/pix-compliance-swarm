# SPEC-015: snippet de IaC do EventBridge Scheduler — documenta o caminho
# de produção do agendamento do pipeline completo, sem implementá-lo de
# fato (FR-012, "deploy real na AWS do agendamento" fica explicitamente
# fora de escopo desta feature).
#
# Terraform (HCL), não CDK: um `.tf` é revisável diretamente neste
# repositório, sem exigir um toolchain adicional (Node/CDK) só para
# produzir o artefato real via síntese (research.md, Decisão 8).
#
# O alvo conceitual desta regra é exatamente o mesmo entrypoint chamado
# localmente pelo APScheduler/CLI: `pix_compliance.agents.orchestrator_agent.run_pipeline`
# (via `python -m pix_compliance.agents.orchestrator_agent`, empacotado
# aqui como a função Lambda alvo) — nunca um segundo caminho de disparo
# divergente (FR-008).

# Regra de agendamento propriamente dita — expressão cron equivalente à
# mesma variável de ambiente ORCHESTRATOR_SCHEDULE_CRON usada localmente
# (formato EventBridge: "cron(minuto hora dia-do-mes mes dia-da-semana ano)",
# sintaxe ligeiramente diferente do cron de 5 campos usado pelo APScheduler,
# mas semanticamente equivalente).
resource "aws_scheduler_schedule" "pipeline_orchestrator" {
  name       = "pix-compliance-orchestrator"
  group_name = "default"

  # Equivalente à ORCHESTRATOR_SCHEDULE_CRON="0 3 * * *" (diariamente às
  # 03:00) já usada pelo APScheduler local — mantenha os dois valores em
  # sincronia manualmente ao ajustar o agendamento (nenhuma automação
  # cross-ambiente existe nesta versão, FR-012).
  schedule_expression = "cron(0 3 * * ? *)"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    # Alvo conceitual: a mesma função de entrypoint do pipeline completo
    # (`orchestrator_agent.run_pipeline`), empacotada como uma função
    # Lambda (ou uma task Fargate, a depender do runtime de produção
    # escolhido — detalhe de deploy fora do escopo desta spec).
    arn      = aws_lambda_function.pipeline_orchestrator.arn
    role_arn = aws_iam_role.eventbridge_scheduler_invoke.arn

    retry_policy {
      maximum_retry_attempts = 1
    }
  }
}

# Função alvo — apenas o esqueleto de referência: o handler real é
# `pix_compliance.agents.orchestrator_agent.run_pipeline`, o mesmo módulo
# usado pelo CLI (`make run`) e pelo APScheduler local (FR-008). Empacotar
# e publicar este artefato de fato fica fora do escopo desta spec
# (documentação do caminho de produção, não implementação — FR-012).
resource "aws_lambda_function" "pipeline_orchestrator" {
  function_name = "pix-compliance-orchestrator"
  # handler aponta para o mesmo entrypoint local, adaptado a uma assinatura
  # de handler Lambda (ex. um wrapper fino chamando run_pipeline via
  # asyncio.run) — wrapper não implementado nesta spec.
  handler = "pix_compliance.agents.orchestrator_agent.run_pipeline"
  runtime = "python3.12"
  role    = aws_iam_role.pipeline_orchestrator_execution.arn
  timeout = 900 # pipeline completo pode levar minutos (scrape -> extract -> ... -> report)

  filename = "placeholder.zip" # artefato real de deploy fica fora de escopo (FR-012)
}

resource "aws_iam_role" "pipeline_orchestrator_execution" {
  name = "pix-compliance-orchestrator-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role" "eventbridge_scheduler_invoke" {
  name = "pix-compliance-eventbridge-scheduler-invoke"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
}
