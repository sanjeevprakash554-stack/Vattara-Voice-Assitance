import sqlite3

conn = sqlite3.connect('backend/vattara.db')
c = conn.cursor()

print("--- APPOINTMENTS CREATED ON 2026-11-18 ---")
c.execute("SELECT id, customer_id, appointment_time, end_time, status, created_at, notes FROM appointments WHERE created_at LIKE '2026-11-18%'")
for r in c.fetchall():
    print(r)

print("\n--- SESSIONS ON 2026-11-18 ---")
c.execute("SELECT call_sid, caller_phone, appointment_datetime_iso, step, booking_id, created_at FROM conversation_sessions WHERE created_at LIKE '2026-11-18%'")
for r in c.fetchall():
    print(r)
