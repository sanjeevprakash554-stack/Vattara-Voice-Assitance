import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

def request(method, path, data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            resp_body = res.read().decode("utf-8")
            return res.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = err_body
        return e.code, parsed
    except Exception as e:
        return 0, str(e)

def main():
    print("=== Testing All Vattara Backend Modules ===")
    
    # 1. Health
    status, body = request("GET", "/health")
    print(f"1. Health: {status} -> {body}")
    assert status == 200, f"Health check failed: {body}"
    
    # 2. Auth Login
    status, body = request("POST", "/auth/login", {"email": "admin@vattara.com", "password": "Admin@123"})
    print(f"2. Auth Login: {status}")
    assert status == 200, f"Login failed: {body}"
    token = body["access_token"]
    user = body["user"]
    print(f"   Logged in as: {user['full_name']} ({user['email']}), Business: {body.get('business', {}).get('name')}")
    
    # 3. Auth Me
    status, body = request("GET", "/auth/me", token=token)
    print(f"3. Auth Me: {status} -> User: {body.get('user', {}).get('email')}")
    assert status == 200, f"Auth me failed: {body}"
    
    # 4. Dashboard Stats
    status, body = request("GET", "/dashboard/stats", token=token)
    print(f"4. Dashboard Stats: {status} -> {body}")
    assert status == 200, f"Dashboard stats failed: {body}"
    
    # 5. Dashboard Activities & Analytics
    status, body = request("GET", "/dashboard/activities", token=token)
    print(f"5. Dashboard Activities: {status} -> Count: {len(body) if isinstance(body, list) else body}")
    assert status == 200, f"Dashboard activity failed: {body}"

    status, body = request("GET", "/dashboard/analytics?days=7", token=token)
    print(f"   Dashboard Analytics: {status} -> Trends: {len(body.get('call_trends', []))}")
    assert status == 200, f"Dashboard analytics failed: {body}"
    
    # 6. Assistant Config
    status, body = request("GET", "/assistant", token=token)
    print(f"6. Assistant Config: {status} -> Name: {body.get('assistant_name')}, Voice: {body.get('voice')}, Lang: {body.get('language')}")
    assert status == 200, f"Assistant config get failed: {body}"
    
    # Assistant Services & FAQs
    status, services = request("GET", "/assistant/services", token=token)
    print(f"   Services: {status} -> Count: {len(services) if isinstance(services, list) else services}")
    assert status == 200
    
    status, faqs = request("GET", "/assistant/faqs", token=token)
    print(f"   FAQs: {status} -> Count: {len(faqs) if isinstance(faqs, list) else faqs}")
    assert status == 200
    
    # 7. Calls
    status, calls = request("GET", "/calls", token=token)
    print(f"7. Calls: {status} -> Total: {len(calls) if isinstance(calls, list) else calls}")
    assert status == 200
    
    # 8. Appointments
    status, appts = request("GET", "/appointments", token=token)
    print(f"8. Appointments: {status} -> Total: {len(appts) if isinstance(appts, list) else appts}")
    assert status == 200
    
    # 9. Customers
    status, custs = request("GET", "/customers", token=token)
    print(f"9. Customers: {status} -> Total: {len(custs) if isinstance(custs, list) else custs}")
    assert status == 200
    
    # 10. Reminders
    status, rems = request("GET", "/reminders", token=token)
    print(f"10. Reminders: {status} -> Total: {len(rems) if isinstance(rems, list) else rems}")
    assert status == 200
    
    # 11. Reports Summary
    status, reports = request("GET", "/reports/summary?range_type=7d", token=token)
    print(f"11. Reports Summary: {status} -> Total calls: {reports.get('total_calls')}, Appts: {reports.get('total_appointments')}")
    assert status == 200
    
    print("\nALL 11 BACKEND MODULE CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    main()
