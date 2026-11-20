import sqlite3
import json

conn = sqlite3.connect('backend/vattara.db')
c = conn.cursor()

c.execute("SELECT call_sid, caller_phone, customer_name, step, intent, booking_id, dialog_history, metadata_json, created_at FROM conversation_sessions WHERE booking_id = '8dffec3d-74f7-4e30-98ed-757f6debcb27'")
row = c.fetchone()
print("Call SID:", row[0])
print("Caller Phone in session:", row[1])
print("Customer Name in session:", row[2])
print("Booking ID:", row[5])
print("Created At:", row[8])
print("\nDialog History:")
history = json.loads(row[6])
for h in history:
    print(f"[{h['role']}]: {h['text']}")

print("\nMetadata:")
print(json.loads(row[7]))

print("\nCall details:")
c.execute("SELECT * FROM calls WHERE id = ?", (row[0],))
print(c.fetchone())
