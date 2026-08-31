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
    DeliveryScheduleResponse, VendorCommunicationResponse,
    UpdatePOStatusRequest, UpdateInventoryRequest, UpdateSupplierReliabilityRequest,
    CreateSupplierRequest, CreateMaterialRequest,
)
from app.services.news_fetcher import UnifiedNewsFetcher
from app.services.scheduler import start_scheduler, stop_scheduler, get_latest_scan, trigger_manual_scan
from app.tools.db_tools import update_po_status, update_inventory_stock, update_supplier_reliability
from app.agents.graph import app_graph

import json
import asyncio
import uuid
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Semaphore to prevent concurrent pipeline executions (max 2 simultaneous)
_pipeline_semaphore = asyncio.Semaphore(2)


# Application lifespan (startup + shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting System. Using LLM Provider: {settings.LLM_PROVIDER}")
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="FMCG Autonomous Supply Chain System",
    description="Multi-Agent AI system for real-time supply chain disruption detection and autonomous mitigation.",
    version="3.0.0",
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
        "version": "3.0.0",
    }


# ──────────────────────── Inventory & Data (READ) ────────────────────────

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


# ──────────────────────── CRUD Operations (UPDATE/CREATE) ────────────────────────

@app.patch("/api/purchase-orders/{po_id}")
async def patch_purchase_order(po_id: int, request: UpdatePOStatusRequest):
    """Update a purchase order's status (ISSUED → CONFIRMED → SHIPPED → DELIVERED or CANCELLED)."""
    try:
        result = update_po_status(po_id, request.status.value)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/inventory/{material_id}")
async def patch_inventory(material_id: int, request: UpdateInventoryRequest):
    """Adjust inventory stock level for a material."""
    try:
        result = update_inventory_stock(material_id, request.quantity_delta, request.reason)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/suppliers/{supplier_id}")
async def patch_supplier_reliability(supplier_id: int, request: UpdateSupplierReliabilityRequest):
    """Update a supplier's reliability score."""
    try:
        result = update_supplier_reliability(supplier_id, request.reliability_score)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/suppliers", response_model=SupplierResponse)
async def create_supplier(request: CreateSupplierRequest, db: AsyncSession = Depends(get_db)):
    """Add a new supplier to the database."""
    from app.models import Supplier as SupplierModel
    new_supplier = SupplierModel(
        name=request.name,
        contact_email=request.contact_email,
        location_region=request.location_region,
        lead_time_days=request.lead_time_days,
        reliability_score=request.reliability_score,
    )
    db.add(new_supplier)
    await db.commit()
    await db.refresh(new_supplier)
    return new_supplier


@app.post("/api/inventory", response_model=MaterialInventoryResponse)
async def create_material(request: CreateMaterialRequest, db: AsyncSession = Depends(get_db)):
    """Add a new raw material to the inventory."""
    from app.models import RawMaterial as MaterialModel
    new_material = MaterialModel(
        name=request.name,
        category=request.category,
        current_stock=request.current_stock,
        unit=request.unit,
        reorder_level=request.reorder_level,
        daily_consumption_rate=request.daily_consumption_rate,
        shelf_life_days=request.shelf_life_days,
    )
    db.add(new_material)
    await db.commit()
    await db.refresh(new_material)
    
    days_remaining = float(new_material.current_stock) / float(new_material.daily_consumption_rate) if new_material.daily_consumption_rate > 0 else 0
    return {
        "material_id": new_material.material_id,
        "name": new_material.name,
        "current_stock": float(new_material.current_stock),
        "unit": new_material.unit,
        "days_remaining": days_remaining,
    }


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
    
    Uses asyncio.to_thread() to prevent blocking the event loop,
    and a semaphore to limit concurrent pipeline executions.
    """
    pipeline_run_id = str(uuid.uuid4())[:12]
    
    initial_state = {
        "raw_news": payload.news_text,
        "auto_triggered": False,
        "pipeline_run_id": pipeline_run_id,
        "started_at": datetime.utcnow().isoformat(),
        "messages": [],
    }

    logger.info(f"Pipeline {pipeline_run_id}: Triggering with news: {payload.news_text[:80]}...")

    try:
        # Acquire semaphore to prevent too many concurrent pipelines
        async with _pipeline_semaphore:
            # Run the synchronous LangGraph in a thread to avoid blocking the event loop
            final_state = await asyncio.to_thread(app_graph.invoke, initial_state)

        return {
            "status": "success",
            "pipeline_run_id": pipeline_run_id,
            "threat_assessed": final_state.get("threat_payload"),
            "impacted_materials": final_state.get("impacted_materials", []),
            "risk_reasoning": final_state.get("risk_reasoning"),
            "risk_level": final_state.get("risk_level"),
            "financial_analysis": final_state.get("financial_analysis", []),
            "actions_taken": final_state.get("recommended_actions", []),
            "executive_summary": final_state.get("executive_summary"),
            "errors": final_state.get("error"),
        }
    except Exception as e:
        logger.error(f"Pipeline {pipeline_run_id}: Failed — {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stream-disruption")
async def stream_disruption(payload: DisruptionInput):
    """
    Kicks off the LangGraph pipeline and streams the output of each agent live 
    using Server-Sent Events (SSE).
    """
    pipeline_run_id = str(uuid.uuid4())[:12]
    
    initial_state = {
        "raw_news": payload.news_text,
        "auto_triggered": False,
        "pipeline_run_id": pipeline_run_id,
        "started_at": datetime.utcnow().isoformat(),
        "messages": [],
    }

    async def event_generator():
        try:
            # Send pipeline metadata first
            yield f"data: {json.dumps({'agent': 'pipeline_start', 'data': {'pipeline_run_id': pipeline_run_id}})}\n\n"
            
            # Run LangGraph stream in a thread to avoid blocking
            def run_stream():
                results = []
                for output in app_graph.stream(initial_state):
                    results.append(output)
                return results
            
            async with _pipeline_semaphore:
                stream_results = await asyncio.to_thread(run_stream)
            
            for output in stream_results:
                for node_name, state_update in output.items():
                    event_data = {
                        "agent": node_name,
                        "data": state_update,
                        "pipeline_run_id": pipeline_run_id,
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                    await asyncio.sleep(0.3)
                    
            yield f"data: {json.dumps({'agent': 'done', 'data': {'pipeline_run_id': pipeline_run_id}})}\n\n"
        except Exception as e:
            logger.error(f"Pipeline {pipeline_run_id}: Streaming error — {e}")
            yield f"data: {json.dumps({'agent': 'error', 'error': str(e), 'pipeline_run_id': pipeline_run_id})}\n\n"

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
        scan = await asyncio.to_thread(trigger_manual_scan)
        return {
            "status": "scan_complete",
            "articles_fetched": scan.articles_fetched,
            "threats_detected": scan.threats_detected,
            "pipelines_triggered": scan.pipelines_triggered,
            "pipeline_results": scan.pipeline_results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
