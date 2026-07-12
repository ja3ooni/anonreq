"""Trust Center public endpoints — no auth required, rate-limited, config-gated."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from anonreq.trust_center.schemas import (
    TrustCompliance,
    TrustMetrics,
    TrustSecurity,
    TrustStatus,
)
from anonreq.trust_center.service import TrustCenterService, TrustCenterRateLimiter

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/trust", tags=["trust"])


async def trust_center_enabled(request: Request) -> None:
    """FastAPI dependency to block access when Trust Center is disabled."""
    if not getattr(request.app.state, "trust_center_enabled", False):
        raise HTTPException(status_code=404, detail="Not Found")


async def get_trust_service(request: Request) -> TrustCenterService:
    """Dependency to retrieve the TrustCenterService from app state."""
    service: TrustCenterService | None = getattr(
        request.app.state, "trust_center_service", None
    )
    if service is None:
        raise HTTPException(status_code=503, detail="service_unavailable")
    return service


async def get_rate_limiter(request: Request) -> TrustCenterRateLimiter:
    """Dependency to retrieve the TrustCenterRateLimiter from app state."""
    limiter: TrustCenterRateLimiter | None = getattr(
        request.app.state, "trust_center_rate_limiter", None
    )
    if limiter is None:
        raise HTTPException(status_code=503, detail="service_unavailable")
    return limiter


async def _check_rate(
    request: Request,
    limiter: TrustCenterRateLimiter = Depends(get_rate_limiter),
) -> None:
    """FastAPI dependency to execute rate limit checks."""
    await limiter(request)


@router.get(
    "/status",
    response_model=TrustStatus,
    dependencies=[Depends(trust_center_enabled), Depends(_check_rate)],
)
async def get_trust_status(
    service: TrustCenterService = Depends(get_trust_service),
) -> TrustStatus:
    """Get the overall compliance and SLO status."""
    status = await service.get_status()
    if status is None:
        raise HTTPException(status_code=503, detail="service_unavailable")
    return status


@router.get(
    "/compliance",
    response_model=TrustCompliance,
    dependencies=[Depends(trust_center_enabled), Depends(_check_rate)],
)
async def get_trust_compliance(
    service: TrustCenterService = Depends(get_trust_service),
) -> TrustCompliance:
    """Get compliance framework information."""
    compliance = await service.get_compliance()
    if compliance is None:
        raise HTTPException(status_code=503, detail="service_unavailable")
    return compliance


@router.get(
    "/metrics",
    response_model=TrustMetrics,
    dependencies=[Depends(trust_center_enabled), Depends(_check_rate)],
)
async def get_trust_metrics(
    service: TrustCenterService = Depends(get_trust_service),
) -> TrustMetrics:
    """Get anonymization and gateway metrics."""
    return service.get_metrics()


@router.get(
    "/security",
    response_model=TrustSecurity,
    dependencies=[Depends(trust_center_enabled), Depends(_check_rate)],
)
async def get_trust_security(
    service: TrustCenterService = Depends(get_trust_service),
) -> TrustSecurity:
    """Get security posture and feature metadata."""
    return service.get_security()
