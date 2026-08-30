from app.database import SyncSessionLocal
from app.models import Supplier, RawMaterial, SupplierMaterial, DisruptionLog, PurchaseOrder
from sqlalchemy.orm import joinedload
from datetime import datetime

def query_suppliers_by_region(region: str):
    """Finds all suppliers in a specific region."""
    with SyncSessionLocal() as session:
        suppliers = session.query(Supplier).filter(Supplier.location_region.ilike(f"%{region}%")).all()
        return [{"supplier_id": s.supplier_id, "name": s.name} for s in suppliers]

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
