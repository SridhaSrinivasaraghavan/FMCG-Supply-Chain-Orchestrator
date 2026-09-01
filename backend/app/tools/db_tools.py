"""
Database Tools — SQL queries used by the agent pipeline and API endpoints.

Provides:
- Read operations: impacted materials, logistics context, inventory summaries
- Write operations: purchase orders, disruption logs (with dedup & cost ceiling)
- Update operations: PO status, inventory stock, supplier reliability
- Utility operations: dedup check, supplier email lookup, BOM impact, material ID enumeration
"""
from app.database import SyncSessionLocal
from app.models import (
    Supplier, RawMaterial, SupplierMaterial, DisruptionLog,
    PurchaseOrder, Factory, TransportRoute, DeliverySchedule, ProductBOM,
    ApprovalQueue,
)
from sqlalchemy import and_
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  READ OPERATIONS
# ═══════════════════════════════════════════════════════════

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
            "factories": [
                {
                    "name": f.name, 
                    "city": f.city, 
                    "region": f.region,
                    "receiving_window": f"{f.receiving_window_start} to {f.receiving_window_end}",
                } for f in factories
            ],
            "routes": [
                {
                    "route_id": r.route_id, 
                    "name": r.route_name, 
                    "highways": r.key_highways, 
                    "cities": r.key_cities_passed, 
                    "transit_hours": r.normal_transit_hours,
                    "distance_km": r.distance_km,
                    "supplier_id": r.supplier_id,
                } for r in routes
            ],
            "schedules": [
                {
                    "route_id": s.route_id, 
                    "material_id": s.material_id, 
                    "day": s.delivery_day, 
                    "departure": s.expected_departure_time,
                    "arrival": s.expected_arrival_time,
                } for s in schedules
            ],
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
            logger.info(f"[db_tools] No suppliers found in region '{region}'")
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


def get_all_material_ids() -> set:
    """Returns a set of all known material IDs in the database. Used for validation."""
    with SyncSessionLocal() as session:
        materials = session.query(RawMaterial.material_id).all()
        return {m.material_id for m in materials}


def get_primary_supplier_price(material_id: int) -> float:
    """Returns the actual unit price from the primary supplier for a material."""
    with SyncSessionLocal() as session:
        mapping = session.query(SupplierMaterial).filter(
            SupplierMaterial.material_id == material_id,
            SupplierMaterial.is_primary == True,
        ).first()
        if mapping:
            return float(mapping.unit_price)
        return None


def get_supplier_email(supplier_id: int) -> str:
    """Returns the contact email for a supplier. Falls back to a generated email."""
    with SyncSessionLocal() as session:
        supplier = session.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
        if supplier and supplier.contact_email:
            return supplier.contact_email
        if supplier:
            return f"orders@{supplier.name.lower().replace(' ', '')}.com"
        return "unknown@supplier.com"


def get_bom_impact(material_ids: list) -> list:
    """
    Returns BOM (Bill of Materials) impact for the given materials.
    Shows which products are affected if these materials run out.
    """
    if not material_ids:
        return []
    
    with SyncSessionLocal() as session:
        bom_entries = session.query(ProductBOM).filter(
            ProductBOM.material_id.in_(material_ids)
        ).all()
        
        results = []
        for bom in bom_entries:
            material = session.query(RawMaterial).filter(RawMaterial.material_id == bom.material_id).first()
            results.append({
                "product_name": bom.product_name,
                "material_id": bom.material_id,
                "material_name": material.name if material else "Unknown",
                "required_quantity_per_unit": float(bom.required_quantity_per_unit),
                "unit": material.unit if material else "units",
            })
        return results


# ═══════════════════════════════════════════════════════════
#  WRITE OPERATIONS (with safety guardrails)
# ═══════════════════════════════════════════════════════════

def check_existing_po(material_id: int, hours: int = 24) -> dict:
    """
    Checks if a PO already exists for this material within the last N hours.
    Returns the existing PO dict if found, None otherwise.
    Used for deduplication.
    """
    with SyncSessionLocal() as session:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        existing = session.query(PurchaseOrder).filter(
            PurchaseOrder.material_id == material_id,
            PurchaseOrder.created_at >= cutoff,
            PurchaseOrder.status.in_(["ISSUED", "CONFIRMED", "SHIPPED"]),
        ).order_by(PurchaseOrder.created_at.desc()).first()
        
        if existing:
            return {
                "po_id": existing.po_id,
                "material_id": existing.material_id,
                "supplier_id": existing.supplier_id,
                "order_quantity": float(existing.order_quantity),
                "total_cost": float(existing.total_cost),
                "status": existing.status,
                "created_at": existing.created_at.isoformat() if existing.created_at else None,
            }
        return None


def create_purchase_order(
    material_id: int,
    supplier_id: int,
    quantity: float,
    total_cost: float,
    pipeline_run_id: str = None,
    is_test: bool = False,
):
    """Creates a purchase order with pipeline tracking and test-mode support."""
    with SyncSessionLocal() as session:
        po = PurchaseOrder(
            material_id=material_id,
            supplier_id=supplier_id,
            order_quantity=quantity,
            total_cost=total_cost,
            status="ISSUED",
            pipeline_run_id=pipeline_run_id,
            is_test=is_test,
        )
        session.add(po)
        session.commit()
        session.refresh(po)
        logger.info(
            f"[db_tools] Created PO #{po.po_id} for material {material_id} "
            f"from supplier {supplier_id} {'[TEST]' if is_test else ''}"
        )
        return {"po_id": po.po_id, "status": "ISSUED"}


def log_disruption(
    source_event: str,
    material_id: int,
    severity: str,
    action_taken: str,
    pipeline_run_id: str = None,
    is_test: bool = False,
):
    """Logs a disruption event with pipeline tracking and test-mode support."""
    with SyncSessionLocal() as session:
        log = DisruptionLog(
            source_event=source_event,
            affected_material_id=material_id,
            severity_level=severity,
            action_taken=action_taken,
            pipeline_run_id=pipeline_run_id,
            is_test=is_test,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        return {"log_id": log.log_id}


# ═══════════════════════════════════════════════════════════
#  APPROVAL QUEUE OPERATIONS
# ═══════════════════════════════════════════════════════════

def create_approval_queue_item(
    pipeline_run_id: str,
    material_id: int,
    material_name: str,
    recommended_action: str,
    backup_supplier_id: int,
    backup_supplier_name: str,
    order_quantity: float,
    total_cost: float,
    trigger_reason: str,
    confidence_score: int,
    rationale: str,
    risk_reasoning: str,
    threat_summary: str,
    severity: str,
    is_test: bool = False,
) -> dict:
    """Inserts a new item into the human approval queue."""
    with SyncSessionLocal() as session:
        item = ApprovalQueue(
            pipeline_run_id=pipeline_run_id,
            material_id=material_id,
            material_name=material_name,
            recommended_action=recommended_action,
            backup_supplier_id=backup_supplier_id,
            backup_supplier_name=backup_supplier_name,
            order_quantity=order_quantity,
            total_cost=total_cost,
            trigger_reason=trigger_reason,
            confidence_score=confidence_score,
            rationale=rationale,
            risk_reasoning=risk_reasoning,
            threat_summary=threat_summary,
            severity=severity,
            status="PENDING",
            is_test=is_test,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        logger.info(
            f"[db_tools] Approval queue item #{item.approval_id} created for {material_name} "
            f"(reason: {trigger_reason}, cost: {total_cost:,.0f})"
        )
        return {"approval_id": item.approval_id, "status": "PENDING"}


def get_approval_queue(status_filter: str = None, include_test: bool = False) -> list:
    """Returns approval queue items, optionally filtered by status."""
    with SyncSessionLocal() as session:
        query = session.query(ApprovalQueue)
        if status_filter:
            query = query.filter(ApprovalQueue.status == status_filter)
        if not include_test:
            query = query.filter(ApprovalQueue.is_test == False)
        items = query.order_by(ApprovalQueue.created_at.desc()).all()
        return [
            {
                "approval_id": i.approval_id,
                "pipeline_run_id": i.pipeline_run_id,
                "material_id": i.material_id,
                "material_name": i.material_name,
                "recommended_action": i.recommended_action,
                "backup_supplier_id": i.backup_supplier_id,
                "backup_supplier_name": i.backup_supplier_name,
                "order_quantity": float(i.order_quantity),
                "total_cost": float(i.total_cost),
                "trigger_reason": i.trigger_reason,
                "confidence_score": i.confidence_score,
                "rationale": i.rationale,
                "risk_reasoning": i.risk_reasoning,
                "threat_summary": i.threat_summary,
                "severity": i.severity,
                "status": i.status,
                "reviewed_by": i.reviewed_by,
                "reviewed_at": i.reviewed_at.isoformat() if i.reviewed_at else None,
                "review_notes": i.review_notes,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ]


def process_approval(approval_id: int, decision: str, reviewed_by: str, review_notes: str = "") -> dict:
    """
    Processes a human approval decision.
    - APPROVED: creates the purchase order in the database
    - REJECTED: marks the item as rejected with notes
    """
    valid_decisions = {"APPROVED", "REJECTED"}
    if decision not in valid_decisions:
        raise ValueError(f"Invalid decision '{decision}'. Must be APPROVED or REJECTED.")

    with SyncSessionLocal() as session:
        item = session.query(ApprovalQueue).filter(ApprovalQueue.approval_id == approval_id).first()
        if not item:
            raise ValueError(f"Approval item #{approval_id} not found")
        if item.status != "PENDING":
            raise ValueError(f"Approval item #{approval_id} is already {item.status}")

        item.status = decision
        item.reviewed_by = reviewed_by
        item.reviewed_at = datetime.utcnow()
        item.review_notes = review_notes
        session.commit()

        po_id = None
        if decision == "APPROVED" and item.backup_supplier_id:
            # Create the purchase order now that human has approved
            po = PurchaseOrder(
                material_id=item.material_id,
                supplier_id=item.backup_supplier_id,
                order_quantity=item.order_quantity,
                total_cost=item.total_cost,
                status="ISSUED",
                pipeline_run_id=item.pipeline_run_id,
                is_test=item.is_test,
            )
            session.add(po)
            session.commit()
            session.refresh(po)
            po_id = po.po_id
            logger.info(
                f"[db_tools] Approval #{approval_id} APPROVED by {reviewed_by}. "
                f"PO #{po_id} created for {item.material_name}."
            )
        else:
            logger.info(
                f"[db_tools] Approval #{approval_id} REJECTED by {reviewed_by}. "
                f"Reason: {review_notes}"
            )

        return {
            "approval_id": approval_id,
            "decision": decision,
            "po_id": po_id,
            "reviewed_by": reviewed_by,
        }


# ═══════════════════════════════════════════════════════════
#  UPDATE OPERATIONS (new — full CRUD support)
# ═══════════════════════════════════════════════════════════

def update_po_status(po_id: int, new_status: str) -> dict:
    """
    Updates a PO's status. Valid transitions:
    ISSUED → CONFIRMED → SHIPPED → DELIVERED
    ISSUED → CANCELLED
    """
    valid_statuses = {"ISSUED", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {valid_statuses}")
    
    with SyncSessionLocal() as session:
        po = session.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
        if not po:
            raise ValueError(f"PO #{po_id} not found")
        
        old_status = po.status
        po.status = new_status
        session.commit()
        logger.info(f"[db_tools] PO #{po_id} status: {old_status} → {new_status}")
        return {"po_id": po_id, "old_status": old_status, "new_status": new_status}


def update_inventory_stock(material_id: int, quantity_delta: float, reason: str = "") -> dict:
    """
    Adjusts inventory stock level. Positive delta = stock increase, negative = decrease.
    Returns the new stock level.
    """
    with SyncSessionLocal() as session:
        material = session.query(RawMaterial).filter(RawMaterial.material_id == material_id).first()
        if not material:
            raise ValueError(f"Material #{material_id} not found")
        
        old_stock = float(material.current_stock)
        new_stock = max(0, old_stock + quantity_delta)  # Never go below 0
        material.current_stock = new_stock
        session.commit()
        
        logger.info(f"[db_tools] Material #{material_id} stock: {old_stock} → {new_stock} ({reason})")
        return {
            "material_id": material_id,
            "old_stock": old_stock,
            "new_stock": new_stock,
            "delta": quantity_delta,
        }


def update_supplier_reliability(supplier_id: int, new_score: float) -> dict:
    """Updates a supplier's reliability score (0.00 to 1.00)."""
    if not 0.0 <= new_score <= 1.0:
        raise ValueError(f"Reliability score must be between 0.00 and 1.00, got {new_score}")
    
    with SyncSessionLocal() as session:
        supplier = session.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()
        if not supplier:
            raise ValueError(f"Supplier #{supplier_id} not found")
        
        old_score = float(supplier.reliability_score)
        supplier.reliability_score = new_score
        session.commit()
        
        logger.info(f"[db_tools] Supplier #{supplier_id} reliability: {old_score} → {new_score}")
        return {
            "supplier_id": supplier_id,
            "name": supplier.name,
            "old_score": old_score,
            "new_score": new_score,
        }


# ═══════════════════════════════════════════════════════════
#  COMPREHENSIVE KEYWORD DATA (for news fetcher)
# ═══════════════════════════════════════════════════════════

def get_all_searchable_entities() -> dict:
    """
    Returns ALL searchable entities from the database for comprehensive news keyword building.
    Includes: factory cities, route highways, route cities, supplier regions, 
    material names, material categories, and supplier names.
    """
    with SyncSessionLocal() as session:
        factories = session.query(Factory).all()
        routes = session.query(TransportRoute).all()
        materials = session.query(RawMaterial).all()
        suppliers = session.query(Supplier).all()
        
        return {
            "factory_cities": [f.city for f in factories if f.city],
            "factory_regions": [f.region for f in factories if f.region],
            "route_highways": [
                hw.strip() 
                for r in routes if r.key_highways 
                for hw in r.key_highways.split(",")
            ],
            "route_cities": [
                city.strip() 
                for r in routes if r.key_cities_passed 
                for city in r.key_cities_passed.split(",")
            ],
            "route_names": [r.route_name for r in routes],
            "supplier_regions": [s.location_region for s in suppliers],
            "supplier_names": [s.name for s in suppliers],
            "material_names": [m.name for m in materials],
            "material_categories": list(set(m.category for m in materials if m.category)),
        }
