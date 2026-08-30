from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class DisruptionInput(BaseModel):
    news_text: str = Field(..., description="Raw text of the disruption event")
    region: Optional[str] = Field(None, description="Affected region, if known")

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

# Agent 3: Financial Analysis Schema
class FinancialAnalysis(BaseModel):
    material_id: int
    days_remaining: float
    depletion_date: str
    factory_idle_cost: float
    backup_premium: float
    net_savings: float
    recommendation: str  # EXECUTE_BACKUP_PO or HOLD_AND_MONITOR

# API Response Schemas
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
