output "namespace" {
  description = "Kubernetes namespace hosting the RabbitMQ release."
  value       = var.namespace
}

output "helm_release_name" {
  description = "Name of the RabbitMQ Helm release."
  value       = helm_release.rabbitmq.name
}

output "helm_release_status" {
  description = "Status of the RabbitMQ Helm release."
  value       = helm_release.rabbitmq.status
}

output "amqp_host_parameter" {
  description = "SSM parameter name for the in-cluster AMQP hostname."
  value       = aws_ssm_parameter.amqp_host.name
}

output "amqp_endpoint" {
  description = "In-cluster AMQP hostname for webhook workers."
  value       = aws_ssm_parameter.amqp_host.value
}

output "webhook_topology" {
  description = "Exchange, work queue, and DLQ names for webhook delivery."
  value       = local.queue_definitions
}

output "tags" {
  description = "Tags applied by this module."
  value       = local.common_tags
}
