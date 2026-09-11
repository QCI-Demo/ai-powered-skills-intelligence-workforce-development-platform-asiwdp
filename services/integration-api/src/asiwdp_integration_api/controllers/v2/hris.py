"""v2 HRIS integration controller (batch + status)."""

from __future__ import annotations

from typing import Any

from asiwdp_auth import TenantContext

from asiwdp_integration_api.controllers.base import TenantScopedController
from asiwdp_integration_api.schemas.models import BatchRequest, EmployeeRecord


class HrisV2Controller(TenantScopedController):
    api_version = "v2"

    def ingest_employee_batch(
        self, context: TenantContext, batch: BatchRequest
    ) -> dict[str, Any]:
        accepted = 0
        for raw in batch.records:
            record = EmployeeRecord.model_validate(raw)
            self.ensure_tenant(context, record.tenant_id)
            accepted += 1
        correlation = batch.correlation_id or f"hris-batch-{context.tenant_id[:8]}"
        return self.batch_ack(
            context=context,
            resource="hris.employee",
            accepted_count=accepted,
            correlation_id=correlation,
            status_href=f"/api/v2/hris/employees/batches/{correlation}/status",
        )

    def batch_status(
        self, context: TenantContext, correlation_id: str
    ) -> dict[str, Any]:
        return {
            "apiVersion": self.api_version,
            "tenantId": context.tenant_id,
            "correlationId": correlation_id,
            "status": "accepted",
            "resource": "hris.employee",
        }
