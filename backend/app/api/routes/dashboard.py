import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db_session
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.models.appointment import Appointment
from app.models.assistant import AssistantConfig
from app.models.call import Call
from app.models.customer import Customer
from app.models.reminder import Reminder
from app.models.user import User
from app.schemas.dashboard import (
    ActivityItem,
    AnalyticsOverview,
    AppointmentStatusDistribution,
    CallDurationReport,
    CallTrendPoint,
    DashboardStats,
)
from app.services.dashboard_events import dashboard_event_manager

logger = get_logger(__name__)
router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> DashboardStats:
    """Compute aggregate high-level metrics for the business dashboard."""
    biz_id = current_user.business_id

    # Total incoming calls
    total_in = (
        db.scalar(
            select(func.count(Call.id)).where(
                Call.business_id == biz_id, Call.call_type == "incoming"
            )
        )
        or 0
    )

    # Total outgoing calls
    total_out = (
        db.scalar(
            select(func.count(Call.id)).where(
                Call.business_id == biz_id, Call.call_type == "outgoing"
            )
        )
        or 0
    )
    total_calls = total_in + total_out

    # Total appointments
    total_appts = (
        db.scalar(select(func.count(Appointment.id)).where(Appointment.business_id == biz_id)) or 0
    )

    # Total customers
    total_cust = (
        db.scalar(select(func.count(Customer.id)).where(Customer.business_id == biz_id)) or 0
    )

    # Successful / Answered calls (completed)
    successful = (
        db.scalar(
            select(func.count(Call.id)).where(
                Call.business_id == biz_id, Call.status == "completed"
            )
        )
        or 0
    )

    # Missed calls
    missed = (
        db.scalar(
            select(func.count(Call.id)).where(
                Call.business_id == biz_id, Call.status.in_(["missed", "failed"])
            )
        )
        or 0
    )

    call_success_rate = round((successful / max(1, total_calls)) * 100, 1) if total_calls > 0 else 100.0

    # Assistant active state
    assistant = db.scalar(
        select(AssistantConfig).where(AssistantConfig.business_id == biz_id)
    )
    is_active = assistant.is_active if assistant else True

    # Upcoming, completed, cancelled appointments
    now = datetime.now(timezone.utc)
    upcoming_count = (
        db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.business_id == biz_id,
                Appointment.status.in_(["upcoming", "scheduled"]),
                Appointment.appointment_time >= now,
            )
        )
        or 0
    )
    completed_count = (
        db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.business_id == biz_id,
                Appointment.status == "completed",
            )
        )
        or 0
    )
    cancelled_count = (
        db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.business_id == biz_id,
                Appointment.status == "cancelled",
            )
        )
        or 0
    )

    # Reminder KPIs
    total_rems = (
        db.scalar(select(func.count(Reminder.id)).where(Reminder.business_id == biz_id)) or 0
    )
    pending_rems = (
        db.scalar(
            select(func.count(Reminder.id)).where(
                Reminder.business_id == biz_id,
                Reminder.status.in_(["pending", "scheduled", "calling", "retrying"]),
            )
        )
        or 0
    )
    sent_rems = (
        db.scalar(
            select(func.count(Reminder.id)).where(
                Reminder.business_id == biz_id,
                Reminder.status.in_(["sent", "completed"]),
            )
        )
        or 0
    )
    confirmed_rems = (
        db.scalar(
            select(func.count(Reminder.id)).where(
                Reminder.business_id == biz_id,
                Reminder.customer_response.ilike("%confirm%"),
            )
        )
        or 0
    )
    failed_rems = (
        db.scalar(
            select(func.count(Reminder.id)).where(
                Reminder.business_id == biz_id,
                Reminder.status == "failed",
            )
        )
        or 0
    )

    return DashboardStats(
        total_incoming_calls=total_in,
        total_outgoing_calls=total_out,
        total_calls=total_calls,
        answered_calls=successful,
        successful_calls=successful,
        missed_calls=missed,
        call_success_rate=call_success_rate,
        total_appointments=total_appts,
        upcoming_appointments_count=upcoming_count,
        completed_appointments_count=completed_count,
        cancelled_appointments_count=cancelled_count,
        total_customers=total_cust,
        active_assistant=is_active,
        total_reminders=total_rems,
        pending_reminders=pending_rems,
        sent_reminders=sent_rems,
        confirmed_reminders=confirmed_rems,
        failed_reminders=failed_rems,
        reminders_total=total_rems,
        reminders_pending=pending_rems,
        reminders_sent=sent_rems,
        reminders_confirmed=confirmed_rems,
        reminders_failed=failed_rems,
    )


@router.get("/activities", response_model=list[ActivityItem])
def get_recent_activities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[ActivityItem]:
    """Retrieve combined chronological recent activities."""
    biz_id = current_user.business_id
    activities: list[ActivityItem] = []

    # Recent calls
    recent_calls = db.scalars(
        select(Call)
        .where(Call.business_id == biz_id)
        .order_by(Call.initiated_at.desc())
        .limit(6)
    ).all()

    for call in recent_calls:
        direction = "Incoming call" if call.call_type == "incoming" else "Outgoing call"
        activities.append(
            ActivityItem(
                id=f"act-call-{call.id}",
                type="call",
                title=f"{direction} ({call.caller_phone})",
                description=call.summary or f"Call duration: {call.duration_seconds}s",
                status=call.status,
                timestamp=call.initiated_at,
            )
        )

    # Recent appointments
    recent_appts = db.scalars(
        select(Appointment)
        .where(Appointment.business_id == biz_id)
        .order_by(Appointment.created_at.desc())
        .limit(6)
    ).all()

    for appt in recent_appts:
        cust_name = appt.customer.name if appt.customer else "Customer"
        time_str = appt.appointment_time.strftime("%b %d at %I:%M %p")
        activities.append(
            ActivityItem(
                id=f"act-appt-{appt.id}",
                type="appointment",
                title=f"Appointment for {cust_name}",
                description=f"Scheduled for {time_str} ({appt.source})",
                status=appt.status,
                timestamp=appt.created_at,
            )
        )

    activities.sort(key=lambda a: a.timestamp, reverse=True)
    return activities[:10]


@router.get("/analytics", response_model=AnalyticsOverview)
def get_analytics_overview(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> AnalyticsOverview:
    """Retrieve full analytics payload with daily trends and distribution charts calculated from actual DB records."""
    stats = get_dashboard_stats(current_user=current_user, db=db)
    biz_id = current_user.business_id
    now = datetime.now(timezone.utc)

    # 1. Daily call trend points for past N days (actual database counts)
    trend_points: list[CallTrendPoint] = []
    for d in range(days - 1, -1, -1):
        target_date = (now - timedelta(days=d)).date()
        date_str = target_date.strftime("%b %d")

        calls = db.scalars(
            select(Call).where(
                Call.business_id == biz_id,
                func.date(Call.initiated_at) == target_date,
            )
        ).all()

        inc = sum(1 for c in calls if c.call_type == "incoming")
        outg = sum(1 for c in calls if c.call_type == "outgoing")
        missed = sum(1 for c in calls if c.status in ["missed", "failed"])

        trend_points.append(CallTrendPoint(date=date_str, incoming=inc, outgoing=outg, missed=missed))

    # 2. Appointment status distribution (actual database counts)
    statuses = ["upcoming", "completed", "cancelled", "rescheduled"]
    appt_breakdown: list[AppointmentStatusDistribution] = []
    for st in statuses:
        count = (
            db.scalar(
                select(func.count(Appointment.id)).where(
                    Appointment.business_id == biz_id, Appointment.status == st
                )
            )
            or 0
        )
        appt_breakdown.append(AppointmentStatusDistribution(status=st.capitalize(), count=count))

    # 3. Call duration distribution computed from actual Call records
    all_calls = db.scalars(select(Call).where(Call.business_id == biz_id)).all()
    d_under_1 = sum(1 for c in all_calls if 0 < c.duration_seconds < 60)
    d_1_to_2 = sum(1 for c in all_calls if 60 <= c.duration_seconds < 120)
    d_2_to_3 = sum(1 for c in all_calls if 120 <= c.duration_seconds < 180)
    d_3_to_5 = sum(1 for c in all_calls if 180 <= c.duration_seconds < 300)
    d_over_5 = sum(1 for c in all_calls if c.duration_seconds >= 300)

    duration_distribution = [
        CallDurationReport(range_label="< 1 min", count=d_under_1),
        CallDurationReport(range_label="1 - 2 mins", count=d_1_to_2),
        CallDurationReport(range_label="2 - 3 mins", count=d_2_to_3),
        CallDurationReport(range_label="3 - 5 mins", count=d_3_to_5),
        CallDurationReport(range_label="> 5 mins", count=d_over_5),
    ]

    return AnalyticsOverview(
        stats=stats,
        call_trends=trend_points,
        appointment_breakdown=appt_breakdown,
        duration_distribution=duration_distribution,
    )


# ==============================================================================
# Real-Time Dashboard WebSocket Endpoint
# ==============================================================================

@router.websocket("/ws")
async def dashboard_websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(None),
    db: Session = Depends(get_db_session),
):
    """Authenticated real-time WebSocket for business dashboard telemetry.
    
    Protocol:
    - Client connects: wss://.../api/v1/dashboard/ws?token=<JWT>
    - Server validates JWT, extracts user and business_id
    - Server accepts connection and registers with dashboard_event_manager
    - Server sends initial 'CONNECTED' event with tenant metadata
    - Server handles client 'ping' with 'PONG'
    - Broadcasts live events: CALL_STARTED, TRANSCRIPT_RECEIVED, AI_RESPONSE_GENERATED,
      LANGUAGE_DETECTED, APPOINTMENT_CREATED, CALL_COMPLETED, etc.
    """
    if not token:
        token = websocket.query_params.get("token")

    if not token:
        logger.warning("Rejected dashboard WebSocket connection: missing access token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = decode_access_token(token)
    if not payload:
        logger.warning("Rejected dashboard WebSocket connection: invalid or expired access token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload.get("sub")
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active or not user.business_id:
        logger.warning("Rejected dashboard WebSocket connection: user inactive or missing business.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    biz_id = user.business_id
    await websocket.accept()

    await dashboard_event_manager.register(biz_id, websocket)

    # Send initial welcome confirmation
    try:
        await websocket.send_text(
            json.dumps({
                "event": "CONNECTED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "business_id": biz_id,
                "data": {
                    "user_id": user.id,
                    "business_id": biz_id,
                    "role": user.role,
                    "message": "Real-time dashboard telemetry channel established.",
                },
            })
        )
    except Exception as exc:
        logger.warning("Failed to send welcome message on dashboard WebSocket: %s", exc)

    try:
        while True:
            raw_text = await websocket.receive_text()
            if raw_text == "ping":
                await websocket.send_text(
                    json.dumps({
                        "event": "PONG",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                )
    except WebSocketDisconnect:
        logger.info("Dashboard WebSocket client disconnected for business %s", biz_id)
    except Exception as exc:
        logger.error("Error in dashboard WebSocket for business %s: %s", biz_id, exc)
    finally:
        await dashboard_event_manager.unregister(biz_id, websocket)


