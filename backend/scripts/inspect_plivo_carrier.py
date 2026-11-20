"""Inspect Plivo Carrier Configuration, Application URL, and Live CDR Logs."""

import json
from pathlib import Path
import sys
import httpx

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.database.connection import SessionLocal
from app.models.call import Call
from app.models.conversation_session import ConversationSession
from app.models.appointment import Appointment


def inspect_plivo():
    auth = (settings.PLIVO_AUTH_ID, settings.PLIVO_AUTH_TOKEN)
    base = f"https://api.plivo.com/v1/Account/{settings.PLIVO_AUTH_ID}"

    print("=" * 70)
    print("PLIVO CARRIER ACCOUNT & PSTN NUMBER INSPECTION")
    print("=" * 70)

    # 1. Account
    r = httpx.get(f"{base}/", auth=auth, timeout=10.0)
    if r.status_code == 200:
        d = r.json()
        print(f"Account Name: {d.get('name')}")
        print(f"Account State: {d.get('state')}")
        print(f"Account Type: {d.get('account_type')}")
        print(f"Cash Credits: {d.get('cash_credits')}")
    else:
        print(f"Account fetch failed: HTTP {r.status_code} - {r.text}")

    # 2. Number
    num_clean = settings.PLIVO_PHONE_NUMBER.replace("+", "")
    r = httpx.get(f"{base}/Number/{num_clean}/", auth=auth, timeout=10.0)
    app_id = None
    if r.status_code == 200:
        d = r.json()
        print(f"\nPhone Number: +{d.get('number')}")
        print(f"Carrier: {d.get('carrier')}")
        print(f"Region: {d.get('region')}")
        print(f"Type: {d.get('type')}")
        app_id = d.get("app_id")
        print(f"Linked Application ID: {app_id}")
    else:
        print(f"\nNumber fetch failed: HTTP {r.status_code} - {r.text}")

    # 3. Application
    target_app = app_id or settings.PLIVO_APP_ID
    if target_app:
        r = httpx.get(f"{base}/Application/{target_app}/", auth=auth, timeout=10.0)
        if r.status_code == 200:
            d = r.json()
            print(f"\nApplication Name: {d.get('app_name')}")
            print(f"Answer URL: {d.get('answer_url')}")
            print(f"Answer Method: {d.get('answer_method')}")
            print(f"Hangup URL: {d.get('hangup_url')}")
            print(f"Hangup Method: {d.get('hangup_method')}")
            print(f"Fallback Answer URL: {d.get('fallback_answer_url')}")
        else:
            print(f"\nApp fetch failed: HTTP {r.status_code} - {r.text}")

    # 4. Recent Calls on Plivo
    print("\n" + "=" * 70)
    print("RECENT CARRIER CALL RECORDS (PSTN CDRs) ON PLIVO")
    print("=" * 70)
    r = httpx.get(f"{base}/Call/?limit=10", auth=auth, timeout=10.0)
    plivo_calls = []
    if r.status_code == 200:
        plivo_calls = r.json().get("objects", [])
        if not plivo_calls:
            print("No call records found on Plivo.")
        for idx, c in enumerate(plivo_calls, 1):
            print(
                f"{idx}. UUID: {c.get('call_uuid')} | "
                f"From: {c.get('from_number')} | "
                f"To: {c.get('to_number')} | "
                f"Direction: {c.get('call_direction')} | "
                f"Status: {c.get('call_status')} | "
                f"Duration: {c.get('total_duration')}s | "
                f"Time: {c.get('initiation_time')}"
            )
    else:
        print(f"Failed to fetch calls: HTTP {r.status_code} - {r.text}")

    # 5. Database Calls
    print("\n" + "=" * 70)
    print("DATABASE CALLS TABLE & CONVERSATION SESSIONS")
    print("=" * 70)
    db = SessionLocal()
    try:
        calls = db.query(Call).order_by(Call.created_at.desc()).limit(10).all()
        print(f"Total Calls in DB: {db.query(Call).count()}")
        for c in calls:
            print(
                f"Call ID: {c.id} | From: {c.caller_phone} | "
                f"Status: {c.status} | "
                f"Duration: {c.duration_seconds}s | Created: {c.created_at}"
            )

        print("\nRecent Completed Appointments:")
        appts = db.query(Appointment).order_by(Appointment.created_at.desc()).limit(5).all()
        for a in appts:
            cname = a.customer.name if a.customer else "Unknown"
            cphone = a.customer.phone if a.customer else "Unknown"
            sname = a.service.name if a.service else "Unknown"
            print(
                f"Appt ID: {a.id} | Customer: {cname} ({cphone}) | "
                f"Service: {sname} | Time: {a.appointment_time} | Status: {a.status}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    inspect_plivo()
