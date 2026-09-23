output "rabbitmq_namespace" {
  value = module.messaging_queue.namespace
}

output "rabbitmq_release" {
  value = module.messaging_queue.helm_release_name
}

output "amqp_endpoint" {
  value = module.messaging_queue.amqp_endpoint
}

output "webhook_topology" {
  value = module.messaging_queue.webhook_topology
}

output "signing_keys_secret_name" {
  value = module.secret_store.signing_keys_root_secret_name
}

output "signing_keys_secret_arn" {
  value = module.secret_store.signing_keys_root_secret_arn
}

output "webhook_service_role_arn" {
  value = module.secret_store.webhook_service_role_arn
}

output "webhook_irsa_annotation" {
  value = module.secret_store.irsa_service_account_annotation
}
