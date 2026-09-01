from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime, Date, Text
from sqlalchemy.sql import func
from app.database import Base

class RawMaterial(Base):
    __tablename__ = "raw_materials"
    material_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50))
    current_stock = Column(Numeric(10, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    reorder_level = Column(Numeric(10, 2), nullable=False)
    daily_consumption_rate = Column(Numeric(10, 2), nullable=False)
    shelf_life_days = Column(Integer, nullable=False)

class Supplier(Base):
    __tablename__ = "suppliers"
    supplier_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    contact_email = Column(String(100), nullable=False)
    location_region = Column(String(100), nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    reliability_score = Column(Numeric(3, 2), default=1.00)

class SupplierMaterial(Base):
    __tablename__ = "supplier_materials"
    mapping_id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"))
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"))
    unit_price = Column(Numeric(10, 2), nullable=False)
    is_primary = Column(Boolean, default=False)
    min_order_qty = Column(Numeric(10, 2), default=0)        # Minimum order quantity (MOQ)
    max_supply_capacity = Column(Numeric(10, 2), default=999999)  # Max units supplier can deliver

class ProductBOM(Base):
    __tablename__ = "products_bom"
    bom_id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(100), nullable=False)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"))
    required_quantity_per_unit = Column(Numeric(10, 4), nullable=False)

class DisruptionLog(Base):
    __tablename__ = "disruption_logs"
    log_id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    source_event = Column(String(255), nullable=False)
    affected_material_id = Column(Integer, ForeignKey("raw_materials.material_id"))
    severity_level = Column(String(20))
    action_taken = Column(Text)
    status = Column(String(50), default="PROCESSED")
    pipeline_run_id = Column(String(50), nullable=True)
    is_test = Column(Boolean, default=False)             # True if triggered from test mode

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    po_id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"))
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"))
    order_quantity = Column(Numeric(10, 2), nullable=False)
    total_cost = Column(Numeric(12, 2), nullable=False)
    status = Column(String(50), default="ISSUED")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    pipeline_run_id = Column(String(50), nullable=True)
    is_test = Column(Boolean, default=False)             # True if triggered from test mode

class Factory(Base):
    __tablename__ = "factories"
    factory_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    city = Column(String(100))
    region = Column(String(100), nullable=False)
    operating_hours_start = Column(String(10), nullable=False)
    operating_hours_end = Column(String(10), nullable=False)
    receiving_window_start = Column(String(10), nullable=False)
    receiving_window_end = Column(String(10), nullable=False)

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

class VendorCommunication(Base):
    __tablename__ = "vendor_communications"
    comm_id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    communication_type = Column(String(50), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), default="SENT")

# ─── NEW: Event-Level Deduplication ───
class ActiveDisruption(Base):
    """
    Tracks real-world disruption events (not articles) to prevent the same
    event from triggering multiple pipelines when multiple articles cover it.
    
    Fingerprint = SHA256(region + event_type + date)
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

# ─── NEW: Human Approval Queue ───
class ApprovalQueue(Base):
    """
    Holds POs that require human approval before being placed.
    Triggered when: total_cost > MAX_AUTO_PO_COST OR confidence_score < 60.
    """
    __tablename__ = "approval_queue"
    approval_id = Column(Integer, primary_key=True, index=True)
    pipeline_run_id = Column(String(50), nullable=True)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=False)
    material_name = Column(String(100), nullable=False)
    recommended_action = Column(String(50), nullable=False)       # EXECUTE_BACKUP_PO
    backup_supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=True)
    backup_supplier_name = Column(String(100), nullable=True)
    order_quantity = Column(Numeric(10, 2), nullable=False)
    total_cost = Column(Numeric(12, 2), nullable=False)
    trigger_reason = Column(String(50), nullable=False)           # COST_CEILING, LOW_CONFIDENCE
    confidence_score = Column(Integer, nullable=True)
    rationale = Column(Text, nullable=False)
    risk_reasoning = Column(Text, nullable=True)
    threat_summary = Column(Text, nullable=True)
    severity = Column(String(20), nullable=True)
    status = Column(String(20), default="PENDING")                # PENDING, APPROVED, REJECTED
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_test = Column(Boolean, default=False)
