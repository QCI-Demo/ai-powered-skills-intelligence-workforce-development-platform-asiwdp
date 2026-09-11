"""v1 HRIS integration controller."""

from __future__ import annotations

from typing import Any

from asiwdp_auth import TenantContext

from asiwdp_integration_api.controllers.base import TenantScopedController
from asiwdp_integration_api.schemas.models import EmployeeRecord, RoleRecord


class HrisV1Controller(TenantScopedController):
    api_version = "v1"

    def ingest_employee(
        self, context: TenantContext, record: EmployeeRecord
    ) -> dict[str, Any]:
        self.ensure_tenant(context, record.tenant_id)
        return self.ack(
            context=context,
            resource="hris.employee",
            source_record_id=record.source_record_id,
            message="employee accepted",
        )

    def ingest_role(self, context: TenantContext, record: RoleRecord) -> dict[str, Any]:
        self.ensure_tenant(context, record.tenant_id)
        return self.ack(
            context=context,
            resource="hris.role",
            source_record_id=record.source_record_id,
            message="role accepted",
        )

    def list_employees(self, context: TenantContext) -> dict[str, Any]:
        return {
            "apiVersion": self.api_version,
            "tenantId": context.tenant_id,
            "items": [],
            "count": 0,
        }
