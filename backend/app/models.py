from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime, Date, Text, Float, JSON
from sqlalchemy.sql import func
from app.database import Base

# ============================================================
# CORE ENTITIES
# ============================================================

class RawMaterial(Base):
    __tablename__ = "raw_materials"
    material_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50))
    current_stock = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    daily_consumption_rate = Column(Float, nullable=False)
    reorder_level = Column(Float, nullable=False)
    safety_stock = Column(Float, default=0.0)
    shelf_life_days = Column(Integer, nullable=False)
    unit_cost = Column(Float, default=0.0)

class Product(Base):
    __tablename__ = "products"
    product_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    product_type = Column(String(50), nullable=False)
    selling_price = Column(Float, nullable=False)
    daily_demand = Column(Float, nullable=False)
    current_finished_stock = Column(Float, nullable=False)
    shelf_life_days = Column(Integer, nullable=False)
    production_capacity_per_day = Column(Float, nullable=False)

class ProductBOM(Base):
    __tablename__ = "product_bom"
    bom_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=False)
    quantity_per_unit = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)

class Supplier(Base):
    __tablename__ = "suppliers"
    supplier_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    contact_email = Column(String(100), nullable=False)
    location_region = Column(String(100), nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    reliability_score = Column(Float, default=1.0)

class SupplierMaterial(Base):
    __tablename__ = "supplier_materials"
    mapping_id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=False)
    unit_price = Column(Float, nullable=False)
    maximum_daily_quantity = Column(Float, nullable=False, default=999999)
    is_primary = Column(Boolean, default=False)

class Factory(Base):
    """Retained from old schema for logistics mapping"""
    __tablename__ = "factories"
    factory_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    city = Column(String(100))
    region = Column(String(100), nullable=False)
    operating_hours_start = Column(String(10), nullable=False)
    operating_hours_end = Column(String(10), nullable=False)
    receiving_window_start = Column(String(10), nullable=False)
    receiving_window_end = Column(String(10), nullable=False)

class ProductionLine(Base):
    __tablename__ = "production_lines"
    production_line_id = Column(Integer, primary_key=True, index=True)
    line_name = Column(String(100), nullable=False)
    supported_products = Column(JSON, nullable=False)
    daily_capacity = Column(Float, nullable=False)
    current_capacity = Column(Float, nullable=False)
    status = Column(String(50), nullable=False)
    downtime_hours = Column(Float, default=0.0)

class Demand(Base):
    __tablename__ = "demands"
    demand_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    forecast_demand = Column(Float, nullable=False)
    actual_demand = Column(Float, nullable=True)
    forecast_date = Column(Date, nullable=False)

# ============================================================
# LOGISTICS & OPERATIONS
# ============================================================

class TransportRoute(Base):
    __tablename__ = "transport_routes"
    route_id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    factory_id = Column(Integer, ForeignKey("factories.factory_id"), nullable=False)
    route_name = Column(String(100), nullable=False)
    key_highways = Column(String(255))
    key_cities_passed = Column(String(255))
    distance_km = Column(Integer)
    normal_transit_hours = Column(Integer, nullable=False)

class DeliverySchedule(Base):
    __tablename__ = "delivery_schedules"
    schedule_id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("transport_routes.route_id"), nullable=False)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=False)
    delivery_day = Column(String(20), nullable=False)
    expected_departure_time = Column(String(10), nullable=False)
    expected_arrival_time = Column(String(10), nullable=False)
    estimated_delay_hours = Column(Float, default=0.0)
    status = Column(String(50), nullable=False, default="PLANNED")

class Shipment(Base):
    __tablename__ = "shipments"
    shipment_id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=False)
    route_id = Column(Integer, ForeignKey("transport_routes.route_id"), nullable=False)
    quantity = Column(Float, nullable=False)
    expected_delivery_date = Column(DateTime(timezone=True), nullable=False)
    actual_delivery_date = Column(DateTime(timezone=True), nullable=True)
    delay_days = Column(Integer, default=0)
    status = Column(String(50), nullable=False, default="PLANNED")

# ============================================================
# DISRUPTION & WORKFLOW STATE (INTELLIGENT LAYER)
# ============================================================

class ActiveDisruption(Base):
    """
    Tracks real-world disruption events (not articles) to prevent the same
    event from triggering multiple pipelines when multiple articles cover it.
    """
    __tablename__ = "active_disruptions"
    disruption_id = Column(Integer, primary_key=True, index=True)
    fingerprint = Column(String(64), unique=True, nullable=False, index=True)
    region = Column(String(100), nullable=False)
    event_type = Column(String(50), nullable=False)
    event_date = Column(Date, nullable=False)
    status = Column(String(20), default="ACTIVE")        # ACTIVE, RESOLVED
    action_taken = Column(Text, nullable=True)
    pipeline_run_id = Column(String(50), nullable=True)
    confidence_score = Column(Integer, default=80)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    is_test = Column(Boolean, default=False)

class DisruptionLog(Base):
    __tablename__ = "disruption_logs"
    log_id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    source_event = Column(Text, nullable=False)
    disruption_type = Column(String(50), nullable=False)
    affected_material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=True)
    affected_product_id = Column(Integer, ForeignKey("products.product_id"), nullable=True)
    severity_level = Column(String(20))
    action_taken = Column(Text, nullable=False)
    status = Column(String(50), default="PROCESSED")
    estimated_cost = Column(Float, default=0.0)
    estimated_avoided_loss = Column(Float, default=0.0)
    pipeline_run_id = Column(String(50), nullable=True)
    is_test = Column(Boolean, default=False)
    detailed_reasoning = Column(Text, nullable=True)

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    po_id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    order_quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    status = Column(String(50), default="ISSUED")
    expected_delivery_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    pipeline_run_id = Column(String(50), nullable=True)
    is_test = Column(Boolean, default=False)

class ApprovalQueue(Base):
    """
    Holds mitigation decisions that require human approval.
    """
    __tablename__ = "approval_queue"
    approval_id = Column(Integer, primary_key=True, index=True)
    pipeline_run_id = Column(String(50), nullable=True)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=False)
    material_name = Column(String(100), nullable=False)
    recommended_action = Column(String(50), nullable=False)
    backup_supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=True)
    backup_supplier_name = Column(String(100), nullable=True)
    order_quantity = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    trigger_reason = Column(String(50), nullable=False)
    confidence_score = Column(Integer, nullable=True)
    rationale = Column(Text, nullable=False)
    risk_reasoning = Column(Text, nullable=True)
    threat_summary = Column(Text, nullable=True)
    severity = Column(String(20), nullable=True)
    status = Column(String(20), default="PENDING")
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_test = Column(Boolean, default=False)
    market_intel_reasoning = Column(Text, nullable=True)

class VendorCommunication(Base):
    __tablename__ = "vendor_communications"
    comm_id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    communication_type = Column(String(50), nullable=False)
    subject = Column(Text, nullable=False)
    body = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), default="SENT")
