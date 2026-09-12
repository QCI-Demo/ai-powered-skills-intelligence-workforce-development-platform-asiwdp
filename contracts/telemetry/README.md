# Telemetry Event Contracts

Canonical JSON Schemas for events published to the centralized telemetry
event bus (`asiwdp.telemetry.*` channels).

| Contract | Type | Channel | Partition key |
| --- | --- | --- | --- |
| `v1/tenant-provisioned.schema.json` | `com.asiwdp.tenant.provisioned` | `asiwdp.telemetry.tenant-events` | `tenantId` |

All telemetry events are **tenant-scoped**: envelope `tenantId`, payload
`data.tenantId`, and bus `partition_key` must match.
