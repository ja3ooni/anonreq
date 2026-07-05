"""Breach notification data models.

Per D-026 through D-029:
- BreachTemplate: Configurable notification templates per framework/region
- BreachNotification: Outbound notification record with delivery tracking
- RegulatorQueueItem: Regulator notification queue entry
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class BreachTemplate(BaseModel):
    """A breach notification template.

    Templates are keyed by framework + region + language and support
    variable substitution via ``{{variable_name}}`` syntax.
    """

    id: str = ""
    framework: str
    region: str
    subject_template: str
    body_template: str
    language: str = "en"

    model_config = {"extra": "ignore", "from_attributes": True}


class BreachNotification(BaseModel):
    """A single breach notification sent to a target.

    Tracks delivery status for retry and audit purposes.
    """

    id: str = ""
    breach_id: str
    target_type: Literal["regulator", "tenant"]
    target_id: str
    channel: str = "email"
    template_id: str = ""
    rendered_subject: str = ""
    rendered_body: str = ""
    status: str = "pending"
    sent_at: datetime | None = None
    delivery_status: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None

    model_config = {"extra": "ignore", "from_attributes": True}


class RegulatorQueueItem(BaseModel):
    """A regulator notification queued for delivery.

    Prioritized queue for regulator notifications per D-027.
    """

    id: str = ""
    regulator_id: str
    notification_id: str
    status: str = "pending"
    priority: int = 0
    created_at: datetime | None = None

    model_config = {"extra": "ignore", "from_attributes": True}
