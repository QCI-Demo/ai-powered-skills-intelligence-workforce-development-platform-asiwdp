terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 3.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.25"
    }
  }

  # Backend configuration is supplied at init time per environment.
  # backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Configure these providers against the target EKS cluster before apply.
# Both providers default to the local kubeconfig when attributes are omitted.
provider "kubernetes" {}

provider "helm" {
  # Helm provider v3 uses an attribute (not a nested block) for kubernetes.
  # Example when wiring to EKS explicitly:
  # kubernetes = {
  #   host                   = data.aws_eks_cluster.this.endpoint
  #   cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
  #   token                  = data.aws_eks_cluster_auth.this.token
  # }
}

locals {
  repo_root   = abspath("${path.module}/../../..")
  chart_path  = "${local.repo_root}/charts/rabbitmq"
  values_base = "${local.chart_path}/values.yaml"
  values_env  = "${local.chart_path}/values/${var.environment}.yaml"
}

module "messaging_queue" {
  source = "../../modules/messaging-queue"

  project               = var.project
  environment           = var.environment
  namespace             = var.messaging_namespace
  chart_path            = local.chart_path
  values_files          = [local.values_base, local.values_env]
  release_name          = var.rabbitmq_release_name
  max_delivery_attempts = 5

  tags = var.tags
}

module "secret_store" {
  source = "../../modules/secret-store"

  project                      = var.project
  environment                  = var.environment
  aws_region                   = var.aws_region
  webhook_service_name         = var.webhook_service_name
  webhook_service_namespace    = var.webhook_service_namespace
  webhook_service_account_name = var.webhook_service_account_name
  oidc_provider_arn            = var.oidc_provider_arn
  oidc_provider_url            = var.oidc_provider_url
  kms_key_arn                  = var.kms_key_arn
  recovery_window_in_days      = var.secret_recovery_window_in_days

  tags = var.tags
}
