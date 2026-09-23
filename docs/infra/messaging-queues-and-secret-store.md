# Messaging Queues & Secret Store

Infrastructure for the ASIWDP **outbound webhook service**: a reliable RabbitMQ
delivery queue and an AWS Secrets Manager store for tenant HMAC signing keys.

## Components

| Concern | Tooling | Location |
|---------|---------|----------|
| Queue provisioning | Terraform module `messaging-queue` (Helm release) | `terraform/modules/messaging-queue` |
| Queue deployment values | Helm chart `rabbitmq` + env overlays | `charts/rabbitmq/values/{dev,staging,prod}.yaml` |
| Signing-key store + IAM | Terraform module `secret-store` | `terraform/modules/secret-store` |

## Delivery topology

```
webhook-service ──publish──▶ asiwdp.webhooks.delivery (topic)
                                  │
                                  ▼
                     asiwdp.webhooks.delivery.work
                                  │
              fail (attempt < 5)  │  success → ack
                                  ▼
                     asiwdp.webhooks.delivery.retry  (TTL / back-off)
                                  │
                                  └──▶ requeue to work exchange
              fail (attempt = 5)
                                  ▼
                     asiwdp.webhooks.delivery.dlq
```

Workers use the CloudEvents `id` (event ID) for idempotent delivery and
persist per-tenant status for observability. Signing keys are read from
Secrets Manager at send time — never from the queue payload.

## IAM restriction (webhook-service only)

The `secret-store` module:

1. Creates `asiwdp/<env>/webhooks/signing-keys` and reserves the
   `…/tenants/*` prefix for runtime per-tenant keys.
2. Creates an IRSA role trusted **only** by
   `system:serviceaccount:asiwdp-webhooks:webhook-service`.
3. Attaches an identity policy Allow on that prefix plus an explicit Deny
   for all other Secrets Manager ARNs.
4. Attaches a resource-based secret policy allowing that role alone.

Annotate the webhook ServiceAccount with the module output
`irsa_service_account_annotation` (`eks.amazonaws.com/role-arn`).

## Apply

See [`terraform/README.md`](../../terraform/README.md).
