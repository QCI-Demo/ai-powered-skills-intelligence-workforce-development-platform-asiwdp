# ASIWDP Messaging Queues & Secret Store

Terraform modules and Helm values that provision the **RabbitMQ** delivery
queue and **AWS Secrets Manager** store used by the outbound webhook service
(HMAC signing keys, retry / DLQ topology).

## Layout

```
terraform/
  modules/
    messaging-queue/   # Helm-driven RabbitMQ + SSM connection metadata
    secret-store/      # Secrets Manager + IAM (webhook-service only)
  environments/
    dev|staging|prod/  # Environment stacks composing both modules
charts/rabbitmq/
  values.yaml
  values/{dev,staging,prod}.yaml
```

## Why RabbitMQ

Webhook delivery needs a work-queue with per-message retry, exponential
back-off (up to five attempts), and a dead-letter queue — a better fit than
Kafka for this story. Platform telemetry remains on the separate event bus.

## Apply (example: staging)

```bash
cd terraform/environments/staging
cp terraform.tfvars.example terraform.tfvars   # fill OIDC / KMS values
terraform init
terraform plan
terraform apply
```

Wire the webhook ServiceAccount with the IRSA annotation from
`webhook_irsa_annotation` output:

```yaml
serviceAccount:
  annotations:
    eks.amazonaws.com/role-arn: <webhook_service_role_arn>
```

## Secret access model

| Principal | Access |
|-----------|--------|
| `webhook-service` IRSA role | Allow on `asiwdp/<env>/webhooks/*` only |
| All other principals | Denied by identity Deny + secret resource policy |

No signing-key material is stored in Terraform state or Helm values.
