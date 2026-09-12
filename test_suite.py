import httpx
import json

def test_api():
    base = "http://localhost:8000"
    client = httpx.Client(timeout=10.0)

    print("[1] Testing Webhook Verification Handshake...")
    res = client.get(f"{base}/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "my_secure_custom_verify_token_123",
        "hub.challenge": "1158201444"
    })
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    assert res.text == "1158201444", f"Expected '1158201444', got {res.text}"
    print("    -> SUCCESS! Returned challenge correctly.\n")

    print("[2] Testing Dashboard Login...")
    login_res = client.post(f"{base}/api/auth/login", json={"password": "admin123"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    print(f"    -> SUCCESS! Received JWT token: {token[:25]}...\n")

    headers = {"Authorization": f"Bearer {token}"}

    print("[3] Testing Stats Endpoint...")
    stats_res = client.get(f"{base}/api/stats", headers=headers)
    assert stats_res.status_code == 200, f"Stats failed: {stats_res.text}"
    stats = stats_res.json()
    print(f"    -> SUCCESS! Stats: {stats}\n")

    print("[4] Testing Rules List...")
    rules_res = client.get(f"{base}/api/rules", headers=headers)
    assert rules_res.status_code == 200
    rules = rules_res.json()
    print(f"    -> SUCCESS! Found {len(rules)} rules.\n")

    print("[5] Testing Simulated Webhook DM Event (Keyword: 'guide')...")
    fake_payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "17841400000000000",
                "time": 1726012800,
                "messaging": [
                    {
                        "sender": {"id": "test_user_999"},
                        "recipient": {"id": "17841400000000000"},
                        "timestamp": 1726012800,
                        "message": {
                            "mid": "m_test12345",
                            "text": "Hello, can I get the guide please?"
                        }
                    }
                ]
            }
        ]
    }
    import hmac, hashlib
    from config import settings

    payload_bytes = json.dumps(fake_payload).encode("utf-8")
    wh_headers = {"Content-Type": "application/json"}
    if settings.META_APP_SECRET:
        sig = hmac.new(settings.META_APP_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        wh_headers["X-Hub-Signature-256"] = f"sha256={sig}"

    wh_res = client.post(f"{base}/webhook", content=payload_bytes, headers=wh_headers)
    assert wh_res.status_code == 200, f"Expected 200, got {wh_res.status_code}: {wh_res.text}"
    print("    -> SUCCESS! Webhook event received and processed.\n")

    print("[6] Checking Activity Logs for Processed Event...")
    logs_res = client.get(f"{base}/api/logs", headers=headers)
    assert logs_res.status_code == 200, f"Expected 200, got {logs_res.status_code}: {logs_res.text}"
    logs = logs_res.json()
    print(f"    -> SUCCESS! Latest log event: [{logs[0]['event_type']}] {logs[0]['details']}\n")

    print("========================================")
    print(" ALL BACKEND AUTOMATION TESTS PASSED! ")
    print("========================================")

if __name__ == "__main__":
    test_api()
