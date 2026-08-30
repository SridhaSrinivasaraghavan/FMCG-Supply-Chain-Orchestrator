from app.database import SyncSessionLocal
from app.models import Supplier, RawMaterial, SupplierMaterial, DisruptionLog, PurchaseOrder, Factory, TransportRoute, DeliverySchedule
from sqlalchemy.orm import joinedload
from datetime import datetime

def query_suppliers_by_region(region: str):
    """Finds all suppliers in a specific region."""
    with SyncSessionLocal() as session:
        suppliers = session.query(Supplier).filter(Supplier.location_region.ilike(f"%{region}%")).all()
        return [{"supplier_id": s.supplier_id, "name": s.name} for s in suppliers]

def get_full_logistics_context():
    """Returns the complete map of factories, transport routes, and delivery schedules."""
    with SyncSessionLocal() as session:
        factories = session.query(Factory).all()
        routes = session.query(TransportRoute).all()
        schedules = session.query(DeliverySchedule).all()
        
        context = {
            "factories": [{"name": f.name, "city": f.city, "receiving_window": f"{f.receiving_window_start} to {f.receiving_window_end}"} for f in factories],
            "routes": [{"route_id": r.route_id, "name": r.route_name, "highways": r.key_highways, "cities": r.key_cities_passed, "transit_hours": r.normal_transit_hours} for r in routes],
            "schedules": [{"route_id": s.route_id, "material_id": s.material_id, "day": s.delivery_day, "arrival": s.expected_arrival_time} for s in schedules]
        }
        return context

def get_all_materials_summary():
    """Returns a summary of all raw materials with current stock levels and days remaining."""
    with SyncSessionLocal() as session:
        materials = session.query(RawMaterial).all()
        summary = []
        for m in materials:
            days_remaining = float(m.current_stock) / float(m.daily_consumption_rate) if m.daily_consumption_rate > 0 else 999
            # Get the primary supplier for context
            primary_mapping = session.query(SupplierMaterial).filter(
                SupplierMaterial.material_id == m.material_id,
                SupplierMaterial.is_primary == True
            ).first()
            primary_supplier_name = "Unknown"
            primary_region = "Unknown"
            if primary_mapping:
                supplier = session.query(Supplier).filter(Supplier.supplier_id == primary_mapping.supplier_id).first()
                if supplier:
                    primary_supplier_name = supplier.name
                    primary_region = supplier.location_region
            summary.append({
                "material_id": m.material_id,
                "name": m.name,
                "category": m.category,
                "current_stock": float(m.current_stock),
                "unit": m.unit,
                "daily_consumption_rate": float(m.daily_consumption_rate),
                "days_remaining": round(days_remaining, 1),
                "reorder_level": float(m.reorder_level),
                "primary_supplier": primary_supplier_name,
                "primary_supplier_region": primary_region,
            })
        return summary
def get_impacted_materials(region: str):
    """
    Finds materials that are primarily supplied by suppliers in the affected region,
    and also finds alternate backup suppliers for those materials.
    """
    with SyncSessionLocal() as session:
        # 1. Find suppliers in the affected region
        impacted_suppliers = session.query(Supplier).filter(Supplier.location_region.ilike(f"%{region}%")).all()
        impacted_supplier_ids = [s.supplier_id for s in impacted_suppliers]
        
        if not impacted_supplier_ids:
            return []

        # 2. Find primary materials for these suppliers
        primary_mappings = session.query(SupplierMaterial).filter(
            SupplierMaterial.supplier_id.in_(impacted_supplier_ids),
            SupplierMaterial.is_primary == True
        ).all()
        
        impacted_material_ids = [m.material_id for m in primary_mappings]
        
        if not impacted_material_ids:
            return []
            
        # 3. For each impacted material, gather stock info and alternate suppliers
        results = []
        for mat_id in impacted_material_ids:
            material = session.query(RawMaterial).filter(RawMaterial.material_id == mat_id).first()
            if not material:
                continue
                
            # Primary supplier mapping
            primary_mapping = next(m for m in primary_mappings if m.material_id == mat_id)
            primary_supplier = session.query(Supplier).filter(Supplier.supplier_id == primary_mapping.supplier_id).first()
            
            # Alternate suppliers (not in impacted region)
            alt_mappings = session.query(SupplierMaterial).join(Supplier).filter(
                SupplierMaterial.material_id == mat_id,
                Supplier.location_region.not_ilike(f"%{region}%")
            ).all()
            
            alternates = []
            for alt_m in alt_mappings:
                alt_supplier = session.query(Supplier).filter(Supplier.supplier_id == alt_m.supplier_id).first()
                if alt_supplier:
                    alternates.append({
                        "supplier_id": alt_supplier.supplier_id,
                        "name": alt_supplier.name,
                        "unit_price": float(alt_m.unit_price),
                        "lead_time_days": alt_supplier.lead_time_days,
                        "reliability_score": float(alt_supplier.reliability_score)
                    })
            
            results.append({
                "material_id": material.material_id,
                "name": material.name,
                "current_stock": float(material.current_stock),
                "daily_consumption_rate": float(material.daily_consumption_rate),
                "primary_supplier_id": primary_supplier.supplier_id,
                "primary_supplier_name": primary_supplier.name,
                "alternate_suppliers": alternates
            })
            
        return results

def get_materials_with_alternates(material_ids: list):
    """
    Given a list of material IDs, returns their full details and alternate suppliers,
    matching the format of get_impacted_materials.
    """
    if not material_ids:
        return []
        
    results = []
    with SyncSessionLocal() as session:
        for mat_id in material_ids:
            material = session.query(RawMaterial).filter(RawMaterial.material_id == mat_id).first()
            if not material:
                continue
                
            # Primary supplier mapping
            primary_mapping = session.query(SupplierMaterial).filter(
                SupplierMaterial.material_id == mat_id,
                SupplierMaterial.is_primary == True
            ).first()
            
            primary_supplier = session.query(Supplier).filter(Supplier.supplier_id == primary_mapping.supplier_id).first() if primary_mapping else None
            
            # Alternate suppliers
            alt_mappings = session.query(SupplierMaterial).filter(
                SupplierMaterial.material_id == mat_id,
                SupplierMaterial.is_primary == False
            ).all()
            
            alternates = []
            for alt_m in alt_mappings:
                alt_supplier = session.query(Supplier).filter(Supplier.supplier_id == alt_m.supplier_id).first()
                if alt_supplier:
                    alternates.append({
                        "supplier_id": alt_supplier.supplier_id,
                        "name": alt_supplier.name,
                        "unit_price": float(alt_m.unit_price),
                        "lead_time_days": alt_supplier.lead_time_days,
                        "reliability_score": float(alt_supplier.reliability_score)
                    })
            
            results.append({
                "material_id": material.material_id,
                "name": material.name,
                "current_stock": float(material.current_stock),
                "daily_consumption_rate": float(material.daily_consumption_rate),
                "primary_supplier_id": primary_supplier.supplier_id if primary_supplier else None,
                "primary_supplier_name": primary_supplier.name if primary_supplier else "Unknown",
                "alternate_suppliers": alternates
            })
            
        return results

def create_purchase_order(material_id: int, supplier_id: int, quantity: float, total_cost: float):
    with SyncSessionLocal() as session:
        po = PurchaseOrder(
            material_id=material_id,
            supplier_id=supplier_id,
            order_quantity=quantity,
            total_cost=total_cost,
            status="ISSUED"
        )
        session.add(po)
        session.commit()
        session.refresh(po)
        return {"po_id": po.po_id, "status": "ISSUED"}

def log_disruption(source_event: str, material_id: int, severity: str, action_taken: str):
    with SyncSessionLocal() as session:
        log = DisruptionLog(
            source_event=source_event,
            affected_material_id=material_id,
            severity_level=severity,
            action_taken=action_taken
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        return {"log_id": log.log_id}
