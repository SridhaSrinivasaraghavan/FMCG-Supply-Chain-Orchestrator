from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


# ─────────────────── Enums ───────────────────

class RecommendationEnum(str, Enum):
    EXECUTE_BACKUP_PO = "EXECUTE_BACKUP_PO"
    PROACTIVE_ADVISORY = "PROACTIVE_ADVISORY"
    HOLD_AND_MONITOR = "HOLD_AND_MONITOR"


class POStatusEnum(str, Enum):
    ISSUED = "ISSUED"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


# ─────────────────── Input Schemas ───────────────────

class DisruptionInput(BaseModel):
    news_text: str = Field(..., description="Raw text of the disruption event")
    region: Optional[str] = Field(None, description="Affected region, if known")


# ─────────────────── Agent Schemas ───────────────────

# Agent 1: Market Intel Schema
class ThreatPayload(BaseModel):
    event_type: str = Field(description="Type of disruption: flood, strike, shortage, accident, etc.")
    region: str = Field(description="Region affected (e.g., North, South, East, West)")
    severity: str = Field(description="LOW, MEDIUM, HIGH, CRITICAL")
    estimated_delay_days: int = Field(description="Estimated delay in days")
    affected_commodities: List[str] = Field(description="List of generic commodities affected (e.g., wheat, sugar)")
    summary: str = Field(description="A short summary of the event")

# Agent 2: Risk Assessment Schema
class AlternateSupplier(BaseModel):
    supplier_id: int
    name: str
    unit_price: float
    lead_time_days: int
    reliability_score: float

class ImpactedMaterialInfo(BaseModel):
    material_id: int
    name: str
    current_stock: float
    daily_consumption_rate: float
    primary_supplier_id: int
    primary_supplier_name: str
    alternate_suppliers: List[AlternateSupplier]

# Agent 3: Financial Analysis Schema (updated to match actual output)
class FinancialAnalysisResult(BaseModel):
    material_id: int
    material_name: str
    recommendation: str  # EXECUTE_BACKUP_PO, PROACTIVE_ADVISORY, HOLD_AND_MONITOR
    rationale: str
    days_remaining: float
    delay_days: int
    factory_idle_cost: float
    order_qty: float = 0.0
    total_cost: float = 0.0
    primary_supplier_id: Optional[int] = None
    primary_supplier_name: Optional[str] = None
    best_alternate: Optional[dict] = None


# ─────────────────── API Response Schemas ───────────────────

class SupplierResponse(BaseModel):
    supplier_id: int
    name: str
    contact_email: str
    location_region: str
    lead_time_days: int
    reliability_score: float
    
    class Config:
        from_attributes = True

class MaterialInventoryResponse(BaseModel):
    material_id: int
    name: str
    current_stock: float
    unit: str
    days_remaining: float
    
    class Config:
        from_attributes = True

class DisruptionLogResponse(BaseModel):
    log_id: int
    timestamp: datetime
    source_event: str
    affected_material_id: int
    severity_level: str
    action_taken: str
    status: str
    pipeline_run_id: Optional[str] = None
    
    class Config:
        from_attributes = True

class PurchaseOrderResponse(BaseModel):
    po_id: int
    material_id: int
    supplier_id: int
    order_quantity: float
    total_cost: float
    status: str
    created_at: datetime
    pipeline_run_id: Optional[str] = None
    
    class Config:
        from_attributes = True

class TransportRouteResponse(BaseModel):
    route_id: int
    supplier_id: int
    factory_id: int
    route_name: str
    key_highways: Optional[str]
    key_cities_passed: Optional[str]
    distance_km: Optional[int]
    normal_transit_hours: int
    
    class Config:
        from_attributes = True

class DeliveryScheduleResponse(BaseModel):
    schedule_id: int
    route_id: int
    material_id: int
    delivery_day: str
    expected_departure_time: str
    expected_arrival_time: str
    
    class Config:
        from_attributes = True

class VendorCommunicationResponse(BaseModel):
    comm_id: int
    supplier_id: int
    communication_type: str
    subject: str
    sent_at: datetime
    status: str
    
    class Config:
        from_attributes = True


# ─────────────────── CRUD Request Schemas (new) ───────────────────

class UpdatePOStatusRequest(BaseModel):
    status: POStatusEnum = Field(..., description="New PO status")

class UpdateInventoryRequest(BaseModel):
    quantity_delta: float = Field(..., description="Stock change amount (+/-)")
    reason: str = Field("Manual adjustment", description="Reason for the adjustment")

class UpdateSupplierReliabilityRequest(BaseModel):
    reliability_score: float = Field(..., ge=0.0, le=1.0, description="New reliability score (0.00-1.00)")

class CreateSupplierRequest(BaseModel):
    name: str = Field(..., description="Supplier name")
    contact_email: str = Field(..., description="Contact email")
    location_region: str = Field(..., description="Region (e.g., North (Delhi/NCR))")
    lead_time_days: int = Field(..., ge=0, description="Lead time in days")
    reliability_score: float = Field(1.0, ge=0.0, le=1.0, description="Reliability score")

class CreateMaterialRequest(BaseModel):
    name: str = Field(..., description="Material name")
    category: Optional[str] = Field(None, description="Material category")
    current_stock: float = Field(..., ge=0, description="Current stock")
    unit: str = Field(..., description="Unit of measurement")
    reorder_level: float = Field(..., ge=0, description="Reorder level")
    daily_consumption_rate: float = Field(..., ge=0, description="Daily consumption rate")
    shelf_life_days: int = Field(..., ge=1, description="Shelf life in days")
