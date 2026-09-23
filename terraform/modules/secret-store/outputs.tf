output "secret_name_prefix" {
  description = "Secrets Manager name prefix for tenant webhook signing keys."
  value       = local.secret_name_prefix
}

output "signing_keys_root_secret_arn" {
  description = "ARN of the root webhook signing-keys secret."
  value       = aws_secretsmanager_secret.webhook_signing_keys_root.arn
}

output "signing_keys_root_secret_name" {
  description = "Name of the root webhook signing-keys secret."
  value       = aws_secretsmanager_secret.webhook_signing_keys_root.name
}

output "tenant_signing_key_arn_pattern" {
  description = "ARN pattern for per-tenant signing keys created at runtime."
  value       = "${local.secret_arn_prefix}/tenants/*"
}

output "webhook_service_role_arn" {
  description = "IAM role ARN assumed by webhook-service via IRSA (sole secret accessor)."
  value       = aws_iam_role.webhook_service.arn
}

output "webhook_service_role_name" {
  description = "IAM role name for webhook-service."
  value       = aws_iam_role.webhook_service.name
}

output "webhook_secrets_policy_arn" {
  description = "IAM policy ARN granting webhook-service scoped Secrets Manager access."
  value       = aws_iam_policy.webhook_secrets_access.arn
}

output "irsa_service_account_annotation" {
  description = "Annotation to set on the webhook-service Kubernetes ServiceAccount."
  value = {
    "eks.amazonaws.com/role-arn" = aws_iam_role.webhook_service.arn
  }
}

output "tags" {
  description = "Tags applied by this module."
  value       = local.common_tags
}
