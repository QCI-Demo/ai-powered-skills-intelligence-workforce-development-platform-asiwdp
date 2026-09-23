variable "project" {
  description = "Project short name used in resource naming (e.g. asiwdp)."
  type        = string
  default     = "asiwdp"
}

variable "environment" {
  description = "Deployment environment name (dev | staging | prod)."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region for Secrets Manager and IAM resources."
  type        = string
}

variable "webhook_service_name" {
  description = "Canonical name of the outbound webhook microservice."
  type        = string
  default     = "webhook-service"
}

variable "webhook_service_namespace" {
  description = "Kubernetes namespace where the webhook service runs (IRSA)."
  type        = string
  default     = "asiwdp-webhooks"
}

variable "webhook_service_account_name" {
  description = "Kubernetes ServiceAccount name used by the webhook service."
  type        = string
  default     = "webhook-service"
}

variable "oidc_provider_arn" {
  description = "EKS OIDC provider ARN used for IRSA trust (required for IAM role)."
  type        = string
}

variable "oidc_provider_url" {
  description = "EKS OIDC provider URL without https:// (e.g. oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE)."
  type        = string
}

variable "kms_key_arn" {
  description = "Optional customer-managed KMS key ARN for Secrets Manager. Empty uses the AWS-managed key."
  type        = string
  default     = ""
}

variable "recovery_window_in_days" {
  description = "Secrets Manager recovery window (0 = immediate delete; prod should be 7–30)."
  type        = number
  default     = 7
}

variable "tags" {
  description = "Additional tags applied to AWS resources created by this module."
  type        = map(string)
  default     = {}
}
