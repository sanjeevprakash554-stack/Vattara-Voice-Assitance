"""Call Management and Voice Interaction routes."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db_session
from app.models.call import Call
from app.models.customer import Customer
from app.models.user import User
from app.schemas.call import CallCreate, CallResponse, CallSimulateRequest

router = APIRouter()


@router.get("", response_model=list[CallResponse])
def list_calls(
    call_type: str | None = Query(None, description="incoming or outgoing"),
    call_status: str | None = Query(None, alias="status", description="completed, missed, failed"),
    search: str | None = Query(None, description="Search by caller name or phone"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[CallResponse]:
    """Retrieve filtered call logs for the business."""
    stmt = (
        select(Call)
        .where(Call.business_id == current_user.business_id)
        .order_by(Call.initiated_at.desc())
    )

    if call_type:
        stmt = stmt.where(Call.call_type == call_type)
    if call_status:
        stmt = stmt.where(Call.status == call_status)
    if search:
        search_fmt = f"%{search}%"
        stmt = stmt.where(
            or_(Call.caller_phone.ilike(search_fmt), Call.caller_name.ilike(search_fmt))
        )

    stmt = stmt.offset(offset).limit(limit)
    calls = db.scalars(stmt).all()
    return [CallResponse.model_validate(c) for c in calls]


@router.get("/{call_id}", response_model=CallResponse)
def get_call_details(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> CallResponse:
    """Retrieve full call log details, summary, and audio transcript."""
    call = db.scalar(
        select(Call).where(Call.id == call_id, Call.business_id == current_user.business_id)
    )
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call record not found.")

    return CallResponse.model_validate(call)


@router.post("/simulate", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
def simulate_call(
    payload: CallSimulateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> CallResponse:
    """Simulate an incoming or outgoing AI voice call for testing the system."""
    # Find or auto-create customer by phone
    customer = db.scalar(
        select(Customer).where(
            Customer.business_id == current_user.business_id,
            Customer.phone == payload.caller_phone,
        )
    )
    if not customer:
        customer = Customer(
            business_id=current_user.business_id,
            name=payload.caller_name,
            phone=payload.caller_phone,
            total_calls=1,
        )
        db.add(customer)
        db.flush()
    else:
        customer.total_calls += 1

    transcript_text = (
        f"AI: Hello, thank you for calling {current_user.business.name}. How can I assist you today?\n"
        f"Caller: Hi, I'm calling regarding {payload.scenario}.\n"
        f"AI: Certainly! I would be delighted to help you with {payload.scenario}. Let me check our availability and records.\n"
        f"Caller: That sounds wonderful, thank you so much for the quick response!\n"
        f"AI: You are very welcome. Have a wonderful day!"
    )

    now = datetime.now(timezone.utc)
    call = Call(
        business_id=current_user.business_id,
        customer_id=customer.id,
        caller_name=payload.caller_name,
        caller_phone=payload.caller_phone,
        call_type=payload.call_type,
        status="completed",
        duration_seconds=payload.duration_seconds,
        summary=f"Simulated {payload.call_type} call regarding {payload.scenario}.",
        transcript=transcript_text,
        recording_url="https://sample-audio.vattara.ai/recordings/demo-call.mp3",
        initiated_at=now,
        ended_at=now,
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    return CallResponse.model_validate(call)


@router.post("", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
def create_call(
    payload: CallCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> CallResponse:
    """Log a completed or active call event."""
    call = Call(
        business_id=current_user.business_id,
        customer_id=payload.customer_id,
        caller_name=payload.caller_name,
        caller_phone=payload.caller_phone,
        call_type=payload.call_type,
        status=payload.status,
        duration_seconds=payload.duration_seconds,
        summary=payload.summary,
        transcript=payload.transcript,
        recording_url=payload.recording_url,
        initiated_at=payload.initiated_at or datetime.now(timezone.utc),
        ended_at=payload.ended_at,
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return CallResponse.model_validate(call)

