variable "project" {
  type    = string
  default = "asiwdp"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "messaging_namespace" {
  type    = string
  default = "asiwdp-messaging"
}

variable "rabbitmq_release_name" {
  type    = string
  default = "asiwdp-rabbitmq"
}

variable "webhook_service_name" {
  type    = string
  default = "webhook-service"
}

variable "webhook_service_namespace" {
  type    = string
  default = "asiwdp-webhooks"
}

variable "webhook_service_account_name" {
  type    = string
  default = "webhook-service"
}

variable "oidc_provider_arn" {
  description = "EKS OIDC provider ARN for IRSA."
  type        = string
}

variable "oidc_provider_url" {
  description = "EKS OIDC provider URL without https://."
  type        = string
}

variable "kms_key_arn" {
  type    = string
  default = ""
}

variable "secret_recovery_window_in_days" {
  type    = number
  default = 7
}

variable "tags" {
  type    = map(string)
  default = {}
}
