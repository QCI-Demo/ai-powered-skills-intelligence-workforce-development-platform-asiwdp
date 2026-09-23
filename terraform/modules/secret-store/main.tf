data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project}-${var.environment}"

  # Tenant webhook HMAC signing keys live under this prefix only.
  # Example path: asiwdp/dev/webhooks/tenants/{tenant_id}/signing-key
  secret_name_prefix = "${var.project}/${var.environment}/webhooks"

  secret_arn_prefix = format(
    "arn:aws:secretsmanager:%s:%s:secret:%s",
    var.aws_region,
    data.aws_caller_identity.current.account_id,
    local.secret_name_prefix,
  )

  common_tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      Component   = "secret-store"
      ManagedBy   = "terraform"
      Service     = var.webhook_service_name
    },
    var.tags,
  )

  oidc_subject = "system:serviceaccount:${var.webhook_service_namespace}:${var.webhook_service_account_name}"
}

# ---------------------------------------------------------------------------
# Secrets Manager — tenant webhook signing-key store
# ---------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "webhook_signing_keys_root" {
  name                    = "${local.secret_name_prefix}/signing-keys"
  description             = "Root secret for ASIWDP tenant webhook HMAC signing-key metadata (${var.environment}). Per-tenant keys use the tenants/* prefix."
  recovery_window_in_days = var.recovery_window_in_days
  kms_key_id              = var.kms_key_arn != "" ? var.kms_key_arn : null

  tags = merge(local.common_tags, {
    "asiwdp.io/secret-purpose" = "webhook-signing-keys"
  })
}

# Placeholder JSON documents structure only — no real signing keys are stored
# in Terraform state. The webhook service creates/rotates per-tenant secrets
# at runtime under the IAM-scoped prefix.
resource "aws_secretsmanager_secret_version" "webhook_signing_keys_root" {
  secret_id = aws_secretsmanager_secret.webhook_signing_keys_root.id
  secret_string = jsonencode({
    schemaVersion = 1
    purpose       = "webhook-hmac-signing-keys"
    keyPrefix     = "${local.secret_name_prefix}/tenants/"
    algorithm     = "HMAC-SHA256"
    note          = "Per-tenant signing keys are managed by webhook-service at runtime; never commit key material."
  })
}

# ---------------------------------------------------------------------------
# IAM — IRSA role exclusive to webhook-service
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "webhook_irsa_trust" {
  statement {
    sid     = "WebhookServiceAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = [local.oidc_subject]
    }
  }
}

resource "aws_iam_role" "webhook_service" {
  name               = "${local.name_prefix}-${var.webhook_service_name}"
  description        = "IRSA role for ${var.webhook_service_name}; sole principal allowed to access webhook signing-key secrets."
  assume_role_policy = data.aws_iam_policy_document.webhook_irsa_trust.json
  tags               = local.common_tags
}

# Least-privilege access: only webhook signing-key secrets under the env prefix.
# Explicit Deny for unrelated secret prefixes hardens against future policy sprawl.
data "aws_iam_policy_document" "webhook_secrets_access" {
  statement {
    sid    = "AllowWebhookSigningKeySecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
      "secretsmanager:CreateSecret",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecret",
      "secretsmanager:DeleteSecret",
      "secretsmanager:TagResource",
      "secretsmanager:UntagResource",
      "secretsmanager:ListSecretVersionIds",
    ]
    resources = [
      aws_secretsmanager_secret.webhook_signing_keys_root.arn,
      "${local.secret_arn_prefix}/tenants/*",
    ]
  }

  statement {
    sid    = "DenyNonWebhookSecrets"
    effect = "Deny"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:PutSecretValue",
      "secretsmanager:CreateSecret",
      "secretsmanager:DeleteSecret",
      "secretsmanager:UpdateSecret",
    ]
    not_resources = [
      aws_secretsmanager_secret.webhook_signing_keys_root.arn,
      "${local.secret_arn_prefix}/tenants/*",
    ]
  }

  dynamic "statement" {
    for_each = var.kms_key_arn != "" ? [1] : []
    content {
      sid    = "AllowKmsForWebhookSecrets"
      effect = "Allow"
      actions = [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:GenerateDataKey",
        "kms:DescribeKey",
      ]
      resources = [var.kms_key_arn]
    }
  }
}

resource "aws_iam_policy" "webhook_secrets_access" {
  name        = "${local.name_prefix}-${var.webhook_service_name}-secrets"
  description = "Restrict Secrets Manager access for tenant webhook signing keys to ${var.webhook_service_name} only."
  policy      = data.aws_iam_policy_document.webhook_secrets_access.json
  tags        = local.common_tags
}

resource "aws_iam_role_policy_attachment" "webhook_secrets_access" {
  role       = aws_iam_role.webhook_service.name
  policy_arn = aws_iam_policy.webhook_secrets_access.arn
}

# Resource-based policy: even if another principal receives an identity policy,
# Secrets Manager still requires the secret resource policy to allow them.
# Only the webhook IRSA role is permitted.
data "aws_iam_policy_document" "signing_keys_resource_policy" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["secretsmanager:*"]
    resources = [
      aws_secretsmanager_secret.webhook_signing_keys_root.arn,
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "AllowWebhookServiceOnly"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.webhook_service.arn]
    }
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecret",
      "secretsmanager:DeleteSecret",
      "secretsmanager:ListSecretVersionIds",
    ]
    resources = [
      aws_secretsmanager_secret.webhook_signing_keys_root.arn,
    ]
  }
}

resource "aws_secretsmanager_secret_policy" "webhook_signing_keys_root" {
  secret_arn = aws_secretsmanager_secret.webhook_signing_keys_root.arn
  policy     = data.aws_iam_policy_document.signing_keys_resource_policy.json
}
