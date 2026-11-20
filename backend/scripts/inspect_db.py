import sqlite3

conn = sqlite3.connect('backend/vattara.db')
c = conn.cursor()

print("--- ALL CUSTOMERS ---")
c.execute("SELECT id, name, phone, created_at FROM customers")
for r in c.fetchall():
    print(r)

print("\n--- ALL APPOINTMENTS ---")
c.execute("SELECT id, customer_id, appointment_time, status, created_at FROM appointments")
for r in c.fetchall():
    print(r)

print("\n--- ALL SESSIONS ---")
c.execute("SELECT call_sid, caller_phone, customer_name, step, created_at FROM conversation_sessions")
for r in c.fetchall():
    print(r)

print("\n--- ALL CALLS ---")
c.execute("SELECT id, caller_name, caller_phone, status, created_at FROM calls")
for r in c.fetchall():
    print(r)
