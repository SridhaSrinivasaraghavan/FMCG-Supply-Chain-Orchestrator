import requests
import json
import sseclient

API_BASE_URL = "http://localhost:8000/api"

def get_inventory():
    response = requests.get(f"{API_BASE_URL}/inventory")
    return response.json() if response.status_code == 200 else []

def get_logs():
    response = requests.get(f"{API_BASE_URL}/logs")
    return response.json() if response.status_code == 200 else []

def get_auto_scan_status():
    response = requests.get(f"{API_BASE_URL}/auto-scan/status")
    return response.json() if response.status_code == 200 else {}

def get_routes():
    response = requests.get(f"{API_BASE_URL}/routes")
    return response.json() if response.status_code == 200 else []

def get_schedules():
    response = requests.get(f"{API_BASE_URL}/schedules")
    return response.json() if response.status_code == 200 else []

def stream_disruption(news_text: str):
    """
    Yields events from the backend streaming endpoint.
    """
    url = f"{API_BASE_URL}/stream-disruption"
    headers = {'Accept': 'text/event-stream'}
    payload = {"news_text": news_text, "region": "Global"}
    
    # We use requests with stream=True
    response = requests.post(url, json=payload, headers=headers, stream=True)
    
    client = sseclient.SSEClient(response)
    for event in client.events():
        if event.data:
            data = json.loads(event.data)
            yield data
            if data.get("agent") == "done" or data.get("agent") == "error":
                break
