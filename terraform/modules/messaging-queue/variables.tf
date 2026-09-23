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

variable "namespace" {
  description = "Kubernetes namespace for the RabbitMQ Helm release."
  type        = string
  default     = "asiwdp-messaging"
}

variable "create_namespace" {
  description = "Whether Terraform should create the messaging namespace."
  type        = bool
  default     = true
}

variable "chart_path" {
  description = "Path to the local RabbitMQ Helm chart (charts/rabbitmq)."
  type        = string
}

variable "values_files" {
  description = "Ordered list of Helm values files (base then environment overlay)."
  type        = list(string)
}

variable "release_name" {
  description = "Helm release name for RabbitMQ."
  type        = string
  default     = "asiwdp-rabbitmq"
}

variable "helm_timeout_seconds" {
  description = "Helm install/upgrade timeout in seconds."
  type        = number
  default     = 600
}

variable "webhook_exchange" {
  description = "Primary topic exchange for outbound webhook delivery jobs."
  type        = string
  default     = "asiwdp.webhooks.delivery"
}

variable "webhook_queue" {
  description = "Work queue consumed by the webhook delivery workers."
  type        = string
  default     = "asiwdp.webhooks.delivery.work"
}

variable "webhook_dlq" {
  description = "Dead-letter queue for exhausted webhook delivery attempts."
  type        = string
  default     = "asiwdp.webhooks.delivery.dlq"
}

variable "max_delivery_attempts" {
  description = "Maximum webhook delivery attempts before routing to the DLQ (story: 5)."
  type        = number
  default     = 5
}

variable "tags" {
  description = "Additional tags applied to AWS resources created by this module."
  type        = map(string)
  default     = {}
}
