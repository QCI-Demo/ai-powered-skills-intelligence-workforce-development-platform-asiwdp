"""Pydantic request/response models for Integration APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnvelopeBase(BaseModel):
    """Story 001 shared ingestion envelope fields."""

    model_config = ConfigDict(populate_by_name=True)

    tenant_id: UUID = Field(alias="tenantId")
    source_system: str = Field(alias="sourceSystem", min_length=1)
    source_record_id: str = Field(alias="sourceRecordId", min_length=1)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1)
    captured_at: datetime = Field(alias="capturedAt")


class EmployeeRecord(EnvelopeBase):
    employee_number: str = Field(alias="employeeNumber", min_length=1)
    display_name: str = Field(alias="displayName", min_length=1)
    email: str | None = None
    status: str = "active"


class RoleRecord(EnvelopeBase):
    role_code: str = Field(alias="roleCode", min_length=1)
    title: str = Field(min_length=1)
    status: str = "active"


class LearnerActivityRecord(EnvelopeBase):
    learner_id: str = Field(alias="learnerId", min_length=1)
    activity_type: str = Field(alias="activityType", min_length=1)
    content_id: str = Field(alias="contentId", min_length=1)
    progress_percent: float = Field(alias="progressPercent", ge=0, le=100, default=0)


class ContentCatalogRecord(EnvelopeBase):
    content_id: str = Field(alias="contentId", min_length=1)
    title: str = Field(min_length=1)
    content_type: str = Field(alias="contentType", min_length=1)
    provider: str = Field(min_length=1)


class BatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    correlation_id: str | None = Field(default=None, alias="correlationId")
    records: list[dict[str, Any]] = Field(min_length=1)


class AckResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    accepted: bool = True
    api_version: str = Field(alias="apiVersion")
    tenant_id: str = Field(alias="tenantId")
    resource: str
    source_record_id: str | None = Field(default=None, alias="sourceRecordId")
    message: str = "accepted"


class BatchAckResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    accepted: bool = True
    api_version: str = Field(alias="apiVersion")
    tenant_id: str = Field(alias="tenantId")
    resource: str
    correlation_id: str | None = Field(default=None, alias="correlationId")
    accepted_count: int = Field(alias="acceptedCount")
    status_href: str = Field(alias="statusHref")
    message: str = "batch accepted"


class CredentialRotateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: str = Field(min_length=1)
    credential_ref: str = Field(alias="credentialRef", min_length=1)


class CredentialRotateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rotated: bool = True
    provider: str
    credential_ref: str = Field(alias="credentialRef")
    api_version: str = Field(alias="apiVersion")
    message: str = "rotation scheduled in secret manager"
