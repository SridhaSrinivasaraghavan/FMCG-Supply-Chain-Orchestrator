import requests
import json
import time
import sys

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000"

DISRUPTIONS = [
    {
        "id": "D1",
        "name": "Monsoon flooding",
        "category": "Weather / logistics",
        "expected_impact": "Shipment delay",
        "expected_region": "West",
        "expected_type": ["FLOOD", "MONSOON_FLOODING", "ROUTE_BLOCKAGE", "TRANSPORT_DELAY", "SUPPLIER_FAILURE"],
        "news": "Severe monsoon flooding and continuous torrential rainfall have submerged key sections of NH-48 and port access roads in the West region near Mumbai. Over 150 freight transit trucks are stranded in floodwaters, causing an estimated 5-day shipment delay for vegetable oil and industrial fats consignments.",
    },
    {
        "id": "D2",
        "name": "Transport strike",
        "category": "Logistics",
        "expected_impact": "Delivery disruption",
        "expected_region": "South",
        "expected_type": ["ROUTE_BLOCKAGE", "TRANSPORT_DELAY", "TRANSPORT_STRIKE", "SUPPLIER_FAILURE"],
        "news": "The All-India Motor Transport Congress has commenced a 4-day statewide indefinite truckers and logistics strike across Karnataka and South region transit corridors. Truck movement is halted and toll gates are blockaded, causing severe delivery disruption to Chennai manufacturing facilities.",
    },
    {
        "id": "D3",
        "name": "Primary supplier shutdown",
        "category": "Supplier",
        "expected_impact": "Material unavailability",
        "expected_region": "East",
        "expected_type": ["SUPPLIER_FAILURE", "SUPPLIER_SHUTDOWN", "PRODUCTION_STOPPAGE"],
        "news": "A massive catastrophic boiler explosion and electrical fire has forced an indefinite factory shutdown at SweetLife Sugar Co in Kolkata (East region). All refining and dispatch operations are suspended for at least 15 days, resulting in acute material unavailability of refined sugar for contract FMCG bakeries.",
    },
    {
        "id": "D4",
        "name": "Wheat flour shortage",
        "category": "Raw material",
        "expected_impact": "Production constraint",
        "expected_region": "North",
        "expected_type": ["RAW_MATERIAL_SHORTAGE", "CROP_FAILURE_SHORTAGE", "SUPPLIER_FAILURE", "ROUTE_BLOCKAGE"],
        "news": "Unseasonal crop devastation and sudden government export curbs have triggered an acute Grade-A wheat flour shortage across Delhi-NCR and Punjab milling clusters in the North region. Regional Agro Farms has announced a force majeure with a 12-day supply deficit, imposing severe production constraints on commercial biscuit and cookie lines.",
    },
    {
        "id": "D5",
        "name": "Unexpected demand surge",
        "category": "Demand",
        "expected_impact": "Increased production requirement",
        "expected_region": "South",
        "expected_type": ["DEMAND_SURGE", "RAW_MATERIAL_SHORTAGE", "TRANSPORT_DELAY"],
        "news": "A nationwide festive retail campaign and flash e-commerce promotion have triggered an unexpected 100% demand surge for biscuits and cookies across Bangalore and South region hubs. Production requirements have doubled immediately, which will exhaust current raw material inventory buffers within 48 hours unless expedited backup replenishment is secured.",
    },
]

def run_single(item):
    print(f"\n{'='*70}")
    print(f"RUNNING {item['id']}: {item['name']} ({item['category']})")
    print(f"Expected: {item['expected_impact']} in {item['expected_region']}")
    print(f"{'='*70}")
    
    payload = {"news_text": item["news"]}
    t0 = time.time()
    resp = requests.post(f"{BASE_URL}/api/trigger-disruption?test_mode=true", json=payload, timeout=300)
    dur = round(time.time() - t0, 1)
    
    if resp.status_code != 200:
        print(f"[FAIL] HTTP {resp.status_code}: {resp.text}")
        return {"id": item["id"], "success": False, "error": resp.text}
        
    data = resp.json()
    threat = data.get("threat_assessed") or {}
    event_type = threat.get("event_type", "UNKNOWN")
    region = threat.get("region", "UNKNOWN")
    delay = threat.get("estimated_delay_days", 0)
    conf = data.get("confidence_score", 0)
    impacted = data.get("impacted_materials", [])
    risk_lvl = data.get("risk_level", "N/A")
    financial = data.get("financial_analysis", [])
    approvals = data.get("approval_items", [])
    actions = data.get("actions_taken", [])
    summary = data.get("executive_summary", "")

    print(f"[DONE] Completed in {dur}s")
    print(f"  [1. Market Intel] Threat Type: {event_type} | Region: {region} | Delay: {delay}d | Confidence: {conf}%")
    print(f"  [2. Risk Assess]  Risk Level: {risk_lvl} | Impacted Materials: {[m.get('name') for m in impacted]}")
    print(f"  [3. CFO Finance]  Decisions: {[f.get('recommendation') for f in financial]} | Approvals: {len(approvals)}")
    print(f"  [4. Execution]    Actions Taken: {[a.get('action_type') for a in actions]}")
    if summary:
        print(f"  [Summary]        {summary[:160]}...")
        
    # Evaluate accuracy
    region_ok = item["expected_region"].lower() in region.lower()
    type_ok = any(e in event_type.upper() for e in item["expected_type"])
    
    return {
        "id": item["id"],
        "name": item["name"],
        "category": item["category"],
        "expected_impact": item["expected_impact"],
        "expected_region": item["expected_region"],
        "detected_type": event_type,
        "detected_region": region,
        "detected_delay_days": delay,
        "confidence_score": conf,
        "risk_level": risk_lvl,
        "impacted_materials_count": len(impacted),
        "impacted_material_names": [m.get("name") for m in impacted],
        "financial_decisions": [f.get("recommendation") for f in financial],
        "approvals_count": len(approvals),
        "actions_count": len(actions),
        "actions": [a.get("action_type") for a in actions],
        "type_match": type_ok,
        "region_match": region_ok,
        "success": True,
        "duration_seconds": dur,
        "executive_summary": summary,
    }

def main():
    all_results = []
    for item in DISRUPTIONS:
        res = run_single(item)
        all_results.append(res)
        # small pause between heavy local LLM runs
        time.sleep(2)
        
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
        
    print("\n" + "=" * 80)
    print("ALL 5 DISRUPTIONS TEST RUN COMPLETED - SAVED TO test_results.json")
    print("=" * 80)

if __name__ == "__main__":
    main()
