from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime
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
    action_taken = Column(String)
    status = Column(String(50), default="PROCESSED")

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    po_id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"))
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"))
    order_quantity = Column(Numeric(10, 2), nullable=False)
    total_cost = Column(Numeric(12, 2), nullable=False)
    status = Column(String(50), default="ISSUED")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

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
    key_highways = Column(String(255)) # Comma separated list of highways
    key_cities_passed = Column(String(255)) # Comma separated list of cities
    distance_km = Column(Integer)
    normal_transit_hours = Column(Integer, nullable=False)

class DeliverySchedule(Base):
    __tablename__ = "delivery_schedules"
    schedule_id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("transport_routes.route_id"), nullable=False)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=False)
    delivery_day = Column(String(20), nullable=False) # e.g. "Monday", "Daily"
    expected_departure_time = Column(String(10), nullable=False) # e.g. "08:00"
    expected_arrival_time = Column(String(10), nullable=False) # e.g. "14:00"

class VendorCommunication(Base):
    __tablename__ = "vendor_communications"
    comm_id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    communication_type = Column(String(50), nullable=False) # 'early_dispatch_request', 'emergency_po'
    subject = Column(String(255), nullable=False)
    body = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), default="SENT")
