locals {
  name_prefix = "${var.project}-${var.environment}-rabbitmq"
  common_tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      Component   = "messaging-queue"
      ManagedBy   = "terraform"
      Service     = "webhook-service"
    },
    var.tags,
  )

  # Topology consumed by webhook workers (retries + DLQ). Secrets never land here.
  queue_definitions = {
    exchange              = var.webhook_exchange
    work_queue            = var.webhook_queue
    dead_letter_queue     = var.webhook_dlq
    max_delivery_attempts = var.max_delivery_attempts
    routing_key           = "webhook.delivery"
  }
}

resource "kubernetes_namespace_v1" "messaging" {
  count = var.create_namespace ? 1 : 0

  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/part-of"   = var.project
      "app.kubernetes.io/component" = "messaging-queue"
      "asiwdp.io/environment"       = var.environment
    }
  }
}

resource "helm_release" "rabbitmq" {
  name             = var.release_name
  chart            = var.chart_path
  namespace        = var.namespace
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true
  wait             = true
  timeout          = var.helm_timeout_seconds

  values = [for f in var.values_files : file(f)]

  set = [
    {
      name  = "asiwdp.environment"
      value = var.environment
    },
    {
      name  = "asiwdp.webhook.exchange"
      value = var.webhook_exchange
    },
    {
      name  = "asiwdp.webhook.workQueue"
      value = var.webhook_queue
    },
    {
      name  = "asiwdp.webhook.deadLetterQueue"
      value = var.webhook_dlq
    },
    {
      name  = "asiwdp.webhook.maxDeliveryAttempts"
      value = tostring(var.max_delivery_attempts)
    },
  ]

  depends_on = [kubernetes_namespace_v1.messaging]
}

# SSM parameters expose non-secret connection endpoints to the webhook service.
# Credentials and signing keys live exclusively in the secret-store module.
resource "aws_ssm_parameter" "amqp_host" {
  name = "/${var.project}/${var.environment}/messaging/rabbitmq/host"
  type = "String"
  value = format(
    "%s.%s.svc.cluster.local",
    var.release_name,
    var.namespace,
  )
  description = "In-cluster AMQP hostname for ASIWDP webhook delivery queue"
  tags        = local.common_tags
}

resource "aws_ssm_parameter" "amqp_port" {
  name        = "/${var.project}/${var.environment}/messaging/rabbitmq/port"
  type        = "String"
  value       = "5672"
  description = "AMQP port for ASIWDP webhook delivery queue"
  tags        = local.common_tags
}

resource "aws_ssm_parameter" "webhook_topology" {
  name        = "/${var.project}/${var.environment}/messaging/rabbitmq/webhook-topology"
  type        = "String"
  value       = jsonencode(local.queue_definitions)
  description = "Exchange/queue/DLQ names for outbound webhook delivery"
  tags        = local.common_tags
}
