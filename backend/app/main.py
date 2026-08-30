from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from contextlib import asynccontextmanager

from app.config import settings
from app.database import get_db, async_engine, Base
from app.models import RawMaterial, Supplier, DisruptionLog, PurchaseOrder, TransportRoute, DeliverySchedule, VendorCommunication
from app.schemas import (
    DisruptionInput, MaterialInventoryResponse, DisruptionLogResponse, 
    PurchaseOrderResponse, SupplierResponse, TransportRouteResponse,
    DeliveryScheduleResponse, VendorCommunicationResponse
)
from app.services.news_fetcher import UnifiedNewsFetcher
from app.services.scheduler import start_scheduler, stop_scheduler, get_latest_scan, trigger_manual_scan
from app.agents.graph import app_graph

import logging
logging.basicConfig(level=logging.INFO)


# Application lifespan (startup + shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting System. Using LLM Provider: {settings.LLM_PROVIDER}")
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="FMCG Autonomous Supply Chain System",
    description="Multi-Agent AI system for real-time supply chain disruption detection and autonomous mitigation.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────── Health & Status ────────────────────────

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "auto_scan_enabled": settings.AUTO_SCAN_ENABLED,
        "auto_scan_interval_minutes": settings.AUTO_SCAN_INTERVAL_MINUTES,
        "database": "connected",
    }


# ──────────────────────── Inventory & Data ────────────────────────

@app.get("/api/inventory", response_model=list[MaterialInventoryResponse])
async def get_inventory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RawMaterial))
    materials = result.scalars().all()

    response = []
    for m in materials:
        response.append({
            "material_id": m.material_id,
            "name": m.name,
            "current_stock": float(m.current_stock),
            "unit": m.unit,
            "days_remaining": float(m.current_stock) / float(m.daily_consumption_rate) if m.daily_consumption_rate > 0 else 0,
        })
    return response


@app.get("/api/suppliers", response_model=list[SupplierResponse])
async def get_suppliers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier))
    return result.scalars().all()


@app.get("/api/logs", response_model=list[DisruptionLogResponse])
async def get_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DisruptionLog).order_by(DisruptionLog.timestamp.desc()))
    return result.scalars().all()


@app.get("/api/purchase-orders", response_model=list[PurchaseOrderResponse])
async def get_purchase_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()))
    return result.scalars().all()


@app.get("/api/routes", response_model=list[TransportRouteResponse])
async def get_routes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TransportRoute))
    return result.scalars().all()


@app.get("/api/schedules", response_model=list[DeliveryScheduleResponse])
async def get_schedules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DeliverySchedule))
    return result.scalars().all()


@app.get("/api/communications", response_model=list[VendorCommunicationResponse])
async def get_communications(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VendorCommunication).order_by(VendorCommunication.sent_at.desc()))
    return result.scalars().all()


# ──────────────────────── Disruption Pipeline ────────────────────────

@app.post("/api/simulate-news")
async def simulate_news():
    """Fetches a random mock disruption event for manual testing."""
    return UnifiedNewsFetcher.get_mock_event()


@app.post("/api/trigger-disruption")
async def trigger_disruption(payload: DisruptionInput):
    """
    Kicks off the LangGraph autonomous multi-agent pipeline.
    This is the MANUAL trigger — user provides the news text directly.
    """
    initial_state = {
        "raw_news": payload.news_text,
        "auto_triggered": False,
        "messages": [],
    }

    print(f"Triggering pipeline with news: {payload.news_text[:50]}...")

    try:
        # Run graph
        final_state = app_graph.invoke(initial_state)

        # Format an enriched response to the client
        return {
            "status": "success",
            "threat_assessed": final_state.get("threat_payload"),
            "impacted_materials": final_state.get("impacted_materials", []),
            "risk_reasoning": final_state.get("risk_reasoning"),
            "financial_analysis": final_state.get("financial_analysis", []),
            "actions_taken": final_state.get("recommended_actions", []),
            "executive_summary": final_state.get("executive_summary"),
            "errors": final_state.get("error"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import json
import asyncio

@app.post("/api/stream-disruption")
async def stream_disruption(payload: DisruptionInput):
    """
    Kicks off the LangGraph pipeline and streams the output of each agent live 
    using Server-Sent Events (SSE).
    """
    initial_state = {
        "raw_news": payload.news_text,
        "auto_triggered": False,
        "messages": [],
    }

    async def event_generator():
        try:
            # LangGraph .stream() yields dicts: {node_name: {state_updates}}
            for output in app_graph.stream(initial_state):
                for node_name, state_update in output.items():
                    # We only want to stream the specific output of the agent, not the whole state history
                    # We will package it as an SSE message
                    event_data = {
                        "agent": node_name,
                        "data": state_update
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                    # Give a small artificial delay so the UI can process the stream elegantly
                    await asyncio.sleep(0.5)
                    
            yield "data: {\"agent\": \"done\", \"data\": {}}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'agent': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ──────────────────────── Auto-Scan Endpoints ────────────────────────

@app.get("/api/auto-scan/status")
async def auto_scan_status():
    """Returns the status and results of the most recent automatic news scan."""
    scan = get_latest_scan()
    return {
        "status": scan.status,
        "last_scan_timestamp": scan.timestamp,
        "articles_fetched": scan.articles_fetched,
        "threats_detected": scan.threats_detected,
        "pipelines_triggered": scan.pipelines_triggered,
        "auto_scan_enabled": settings.AUTO_SCAN_ENABLED,
        "scan_interval_minutes": settings.AUTO_SCAN_INTERVAL_MINUTES,
    }


@app.get("/api/auto-scan/results")
async def auto_scan_results():
    """Returns detailed results from the most recent auto-scan, including articles and pipeline outcomes."""
    scan = get_latest_scan()
    return {
        "status": scan.status,
        "last_scan_timestamp": scan.timestamp,
        "articles": scan.articles,
        "pipeline_results": scan.pipeline_results,
    }


@app.post("/api/auto-scan/trigger")
async def manual_trigger_scan():
    """
    Manually triggers the auto-scanner NOW (instead of waiting for the next scheduled run).
    Useful for testing the news → pipeline flow on demand.
    """
    try:
        scan = trigger_manual_scan()
        return {
            "status": "scan_complete",
            "articles_fetched": scan.articles_fetched,
            "threats_detected": scan.threats_detected,
            "pipelines_triggered": scan.pipelines_triggered,
            "pipeline_results": scan.pipeline_results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
