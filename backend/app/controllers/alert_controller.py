"""Alerts on suspicious badge use (reports.view) and the walking times between posts (zones.manage)."""

from fastapi import APIRouter, Depends, Query, status

from app.controllers.deps import get_alert_service, get_badge_service, require
from app.domain.enums import AlertStatus, AlertType
from app.domain.permissions import Permission
from app.models import User
from app.schemas.dto import AlertAckIn, AlertCountOut, AlertOut, AlertRevokeIn, TravelTimeIn, TravelTimeOut
from app.services.alert_service import AlertService
from app.services.badge_service import BadgeService

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    status_: AlertStatus | None = Query(None, alias="status"),
    type_: AlertType | None = Query(None, alias="type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: User = Depends(require(Permission.REPORTS_VIEW)),
    service: AlertService = Depends(get_alert_service),
):
    """Newest first."""
    return service.search(status_, type_, limit, offset)


@router.get("/alerts/count", response_model=AlertCountOut)
def count_alerts(
    _: User = Depends(require(Permission.REPORTS_VIEW)), service: AlertService = Depends(get_alert_service)
):
    """Alerts still « nouvelle » (menu badge, dashboard)."""
    return AlertCountOut(new=service.count_new())


@router.post("/alerts/{alert_id}/ack", response_model=AlertOut)
def acknowledge(
    alert_id: int,
    body: AlertAckIn,
    actor: User = Depends(require(Permission.REPORTS_VIEW)),
    service: AlertService = Depends(get_alert_service),
):
    return service.acknowledge(actor.id, alert_id, body.note)


@router.post("/alerts/{alert_id}/revoke-badge", response_model=AlertOut)
def revoke_from_alert(
    alert_id: int,
    body: AlertRevokeIn,
    actor: User = Depends(require(Permission.REPORTS_VIEW)),
    _: User = Depends(require(Permission.BADGES_REVOKE)),
    service: AlertService = Depends(get_alert_service),
    badges: BadgeService = Depends(get_badge_service),
):
    """Revoke the badge concerned, then mark the alert as handled (FR-93)."""
    badge = service.badge_of(alert_id)
    badges.revoke(actor.id, badge.id, body.reason, body.note)
    return service.acknowledge(actor.id, alert_id, f"Badge révoqué : {body.note or body.reason.value}")


@router.get("/travel-times", response_model=list[TravelTimeOut])
def travel_times(
    _: User = Depends(require(Permission.REPORTS_VIEW)), service: AlertService = Depends(get_alert_service)
):
    return service.travel_times()


@router.put("/travel-times", response_model=TravelTimeOut)
def set_travel_time(
    body: TravelTimeIn,
    actor: User = Depends(require(Permission.ZONES_MANAGE)),
    service: AlertService = Depends(get_alert_service),
):
    """Minimum walking time between two posts (both ways); 0 disables the check for this pair."""
    return service.set_travel_time(actor.id, body.checkpoint_a_id, body.checkpoint_b_id, body.minutes)


@router.delete("/travel-times/{travel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_travel_time(
    travel_id: int,
    actor: User = Depends(require(Permission.ZONES_MANAGE)),
    service: AlertService = Depends(get_alert_service),
):
    service.delete_travel_time(actor.id, travel_id)
