"""FastAPI routers for governance and approval endpoints.

Aggregates domain-specific sub-routers into ``governance_router`` and
re-exports ``approval_router`` for backward-compatible inclusion in ``main.py``.
"""

from __future__ import annotations

from fastapi import APIRouter

from anonreq.governance.router_approval import approval_router as approval_router
from anonreq.governance.router_breach import (
    router as _breach_domain_router,
)
from anonreq.governance.router_dsar import (
    router as _dsar_domain_router,
)
from anonreq.governance.router_legal_hold import (
    router as _legal_hold_domain_router,
)
from anonreq.governance.router_records import (
    router as _records_domain_router,
)
from anonreq.governance.router_risk import (
    router as _risk_domain_router,
)
from anonreq.governance.router_supplier import (
    router as _supplier_domain_router,
)

governance_router = APIRouter(prefix="/v1/governance", tags=["governance"])

governance_router.include_router(_records_domain_router)
governance_router.include_router(_risk_domain_router)
governance_router.include_router(_legal_hold_domain_router)
governance_router.include_router(_supplier_domain_router)
governance_router.include_router(_dsar_domain_router)
governance_router.include_router(_breach_domain_router)
