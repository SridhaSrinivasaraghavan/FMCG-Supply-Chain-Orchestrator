import requests
import json
import sseclient

API_BASE_URL = "http://localhost:8000/api"

# ─── Inventory & Materials ───

def get_inventory():
    r = requests.get(f"{API_BASE_URL}/inventory")
    return r.json() if r.status_code == 200 else []

def update_inventory(material_id: int, quantity_delta: float, reason: str = "Manual adjustment"):
    r = requests.patch(f"{API_BASE_URL}/inventory/{material_id}", json={"quantity_delta": quantity_delta, "reason": reason})
    return r.json() if r.status_code == 200 else None

# ─── Suppliers ───

def get_suppliers():
    r = requests.get(f"{API_BASE_URL}/suppliers")
    return r.json() if r.status_code == 200 else []

def update_supplier_reliability(supplier_id: int, score: float):
    r = requests.patch(f"{API_BASE_URL}/suppliers/{supplier_id}", json={"reliability_score": score})
    return r.json() if r.status_code == 200 else None

# ─── Disruption Logs ───

def get_logs():
    r = requests.get(f"{API_BASE_URL}/logs")
    return r.json() if r.status_code == 200 else []

# ─── Purchase Orders ───

def get_purchase_orders():
    r = requests.get(f"{API_BASE_URL}/purchase-orders")
    return r.json() if r.status_code == 200 else []

def update_po_status(po_id: int, new_status: str):
    r = requests.patch(f"{API_BASE_URL}/purchase-orders/{po_id}", json={"status": new_status})
    return r.json() if r.status_code == 200 else None

# ─── Transport & Schedules ───

def get_routes():
    r = requests.get(f"{API_BASE_URL}/routes")
    return r.json() if r.status_code == 200 else []

def get_schedules():
    r = requests.get(f"{API_BASE_URL}/schedules")
    return r.json() if r.status_code == 200 else []

# ─── Auto Scan ───

def get_auto_scan_status():
    r = requests.get(f"{API_BASE_URL}/auto-scan/status")
    return r.json() if r.status_code == 200 else {}

# ─── Approval Queue ───

def get_approvals(status: str = None):
    params = {"status": status} if status else {}
    r = requests.get(f"{API_BASE_URL}/approvals", params=params)
    return r.json() if r.status_code == 200 else []

def decide_approval(approval_id: int, decision: str, reviewed_by: str, review_notes: str = ""):
    payload = {"decision": decision, "reviewed_by": reviewed_by, "review_notes": review_notes}
    r = requests.patch(f"{API_BASE_URL}/approvals/{approval_id}", json=payload)
    return r.json() if r.status_code == 200 else {"error": r.text}

# ─── Active Disruptions ───

def get_active_disruptions():
    r = requests.get(f"{API_BASE_URL}/active-disruptions")
    return r.json() if r.status_code == 200 else []

def resolve_disruption(disruption_id: int):
    r = requests.patch(f"{API_BASE_URL}/active-disruptions/{disruption_id}/resolve")
    return r.json() if r.status_code == 200 else {"error": r.text}

# ─── Disruption Pipeline ───

def stream_disruption(news_text: str, test_mode: bool = False):
    """Yields parsed SSE events from the backend streaming endpoint."""
    url = f"{API_BASE_URL}/stream-disruption"
    params = {"test_mode": "true" if test_mode else "false"}
    headers = {"Accept": "text/event-stream"}
    payload = {"news_text": news_text}

    response = requests.post(url, json=payload, params=params, headers=headers, stream=True)

    client = sseclient.SSEClient(response)
    for event in client.events():
        if event.data:
            data = json.loads(event.data)
            yield data
            if data.get("agent") in ("done", "error"):
                break
