import sqlite3
import json

conn = sqlite3.connect('backend/vattara.db')
c = conn.cursor()

cust_id = '38aa501f-cdfa-435a-b53f-f92921ed8fe2'
print("=== CUSTOMER DETAILS ===")
c.execute("SELECT * FROM customers WHERE id = ?", (cust_id,))
print(c.fetchone())

print("\n=== APPOINTMENTS FOR CUSTOMER ===")
c.execute("SELECT * FROM appointments WHERE customer_id = ?", (cust_id,))
for row in c.fetchall():
    print(row)

print("\n=== REMINDERS FOR APPOINTMENT ===")
c.execute("SELECT * FROM reminders WHERE customer_id = ?", (cust_id,))
for row in c.fetchall():
    print(row)

print("\n=== CALLS AROUND 2026-11-17 09:40 - 10:05 ===")
c.execute("SELECT id, caller_name, caller_phone, status, summary, transcript, created_at FROM calls WHERE created_at LIKE '2026-11-17 09:%' OR created_at LIKE '2026-11-18 09:%'")
for row in c.fetchall():
    print(row[:5], row[6])
    if row[5]:
        print("Transcript:", row[5][:200])

print("\n=== CONVERSATION SESSIONS ===")
c.execute("SELECT call_sid, caller_phone, customer_name, step, intent, booking_id, dialog_history, metadata_json, created_at FROM conversation_sessions WHERE caller_phone LIKE '%7904743468%' OR caller_phone LIKE '%70904743468%' OR booking_id = '8dffec3d-74f7-4e30-98ed-757f6debcb27'")
for row in c.fetchall():
    print(row[:6], row[8])
    print("Metadata:", row[7])
    print("Dialog History:", row[6])
