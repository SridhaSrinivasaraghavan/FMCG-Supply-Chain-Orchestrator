from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db, async_engine, Base
from app.models import RawMaterial, Supplier, DisruptionLog, PurchaseOrder
from app.schemas import (
    DisruptionInput, MaterialInventoryResponse, DisruptionLogResponse, 
    PurchaseOrderResponse, SupplierResponse
)
from app.services.news_fetcher import DisruptionStreamer
from app.agents.graph import app_graph

app = FastAPI(title="FMCG Autonomous Supply Chain System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    print(f"Starting System. Using LLM Provider: {settings.LLM_PROVIDER}")
    # In production, use Alembic. For this prototype, we rely on seed.py to create tables.

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "llm_provider": settings.LLM_PROVIDER,
        "database": "connected"
    }

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
            "days_remaining": float(m.current_stock) / float(m.daily_consumption_rate) if m.daily_consumption_rate > 0 else 0
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

@app.post("/api/simulate-news")
async def simulate_news():
    """Fetches a mock news event to use for testing."""
    return DisruptionStreamer.get_latest()

@app.post("/api/trigger-disruption")
async def trigger_disruption(payload: DisruptionInput):
    """
    Kicks off the LangGraph autonomous multi-agent pipeline.
    """
    initial_state = {
        "raw_news": payload.news_text,
        "messages": []
    }
    
    print(f"Triggering pipeline with news: {payload.news_text[:50]}...")
    
    try:
        # Run graph
        final_state = app_graph.invoke(initial_state)
        
        # Format a clean response to the client
        return {
            "status": "success",
            "threat_assessed": final_state.get("threat_payload"),
            "impacted_materials": final_state.get("impacted_materials", []),
            "financial_analysis": final_state.get("financial_analysis", []),
            "actions_taken": final_state.get("recommended_actions", []),
            "errors": final_state.get("error")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
