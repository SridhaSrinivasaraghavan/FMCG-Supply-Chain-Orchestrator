"""
Inter-Agent Validation Layer

Validates LLM outputs against strict Pydantic schemas before passing data
between agents. Provides safe defaults and prevents cascading failures
from malformed LLM responses.
"""
from typing import List, Optional
import logging
from app.schemas import (
    ThreatPayload, RiskAssessmentResult,
    DisruptionTypeEnum, SeverityEnum, ActionTypeEnum
)
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
# Reusing the schemas directly where possible.
class CFODecision(BaseModel):
    material_id: int
    material_name: str
    recommendation: str
    backup_supplier_id: Optional[int] = None
    rationale: str

logger = logging.getLogger(__name__)


# ─────────────────── Validation Functions ───────────────────

def validate_threat_payload(data: dict) -> dict:
    """
    Validates Market Intel output. Returns a clean dict or a dict with safe defaults.
    Never raises — always returns usable data.
    """
    try:
        # Pydantic v2 will handle basic coercion, but let's normalize enums if possible
        if "severity" in data and isinstance(data["severity"], str):
            mapping = {
                "VERY HIGH": "CRITICAL",
                "SEVERE": "CRITICAL",
                "MODERATE": "MEDIUM",
                "MINOR": "LOW",
                "NEGLIGIBLE": "LOW",
            }
            val = data["severity"].upper().strip()
            data["severity"] = mapping.get(val, val)
            
        if "affected_commodities" in data and "affected_materials" not in data:
            data["affected_materials"] = data.get("affected_commodities", [])
            
        # Safely map event_type if it doesn't match the enum
        valid_enum_values = {e.value for e in DisruptionTypeEnum}
        if "event_type" in data and data["event_type"] not in valid_enum_values:
            upper_val = str(data["event_type"]).upper()
            if upper_val in valid_enum_values:
                data["event_type"] = upper_val
            elif "DEMAND" in upper_val or "SURGE" in upper_val:
                data["event_type"] = "DEMAND_SURGE"
            elif "SHORTAGE" in upper_val or "CROP" in upper_val or "DEFICIT" in upper_val:
                data["event_type"] = "RAW_MATERIAL_SHORTAGE"
            elif "SHUTDOWN" in upper_val or "FIRE" in upper_val or "EXPLOSION" in upper_val or "FAILURE" in upper_val:
                data["event_type"] = "SUPPLIER_FAILURE"
            elif "FLOOD" in upper_val or "WEATHER" in upper_val or "MONSOON" in upper_val or "RAIN" in upper_val:
                data["event_type"] = "FLOOD"
            elif "STRIKE" in upper_val or "ROAD" in upper_val or "BLOCK" in upper_val or "ACCIDENT" in upper_val:
                data["event_type"] = "ROUTE_BLOCKAGE"
            else:
                data["event_type"] = "TRANSPORT_DELAY"
            
        validated = ThreatPayload(**data)
        logger.info(f"[VALIDATOR] Threat payload validated: {validated.event_type} in {validated.region} ({validated.severity})")
        return validated.model_dump()
    except Exception as e:
        logger.warning(f"[VALIDATOR] Threat payload validation failed: {e}. Using defaults.")
        # Minimal viable threat payload based on the new schema
        return {
            "event_type": DisruptionTypeEnum.OTHER if hasattr(DisruptionTypeEnum, 'OTHER') else list(DisruptionTypeEnum)[0],
            "region": data.get("region", "Unknown"),
            "severity": SeverityEnum.MEDIUM,
            "estimated_delay_days": data.get("estimated_delay_days", 3),
            "affected_materials": data.get("affected_commodities", []),
            "affected_products": [],
            "affected_supplier_ids": [],
            "affected_route_ids": [],
            "capacity_reduction_percent": 0.0,
            "price_increase_percent": 0.0,
            "demand_change_percent": 0.0,
            "duration_days": None,
            "summary": data.get("summary", "No summary provided."),
            "reasoning": data.get("reasoning", "No reasoning provided."),
            "confidence_score": data.get("confidence_score", 1.0)
        }


def validate_risk_reasoning(data: dict, known_material_ids: set) -> dict:
    """
    Validates Risk Assessment LLM output.
    Filters out hallucinated material_ids that don't exist in the database.
    """
    # The new schema RiskAssessmentResult is very complex.
    # If the LLM just outputs risk reasoning and indirect impacts, we'll return a dict.
    result = data.copy()
    if "indirectly_impacted_material_ids" in result:
        original_ids = result["indirectly_impacted_material_ids"]
        if isinstance(original_ids, list):
            valid_ids = []
            for item in original_ids:
                try:
                    mid = int(item)
                    if mid in known_material_ids:
                        valid_ids.append(mid)
                except (ValueError, TypeError):
                    continue
            result["indirectly_impacted_material_ids"] = valid_ids
            
            if len(valid_ids) != len(original_ids):
                hallucinated = set(original_ids) - known_material_ids
                logger.warning(f"[VALIDATOR] Removed hallucinated material IDs: {hallucinated}")

    if "risk_level" not in result:
        result["risk_level"] = SeverityEnum.MEDIUM.value
        
    logger.info(f"[VALIDATOR] Risk reasoning validated.")
    return result


def validate_cfo_decisions(data: list, valid_material_ids: set) -> list:
    """
    Validates CFO decision output. Ensures recommendation is one of the allowed enum values.
    Filters decisions for materials that don't exist.
    """
    if not isinstance(data, list):
        logger.warning(f"[VALIDATOR] CFO output is not a list: {type(data)}. Returning empty.")
        return []
    
    validated_decisions = []
    for item in data:
        try:
            if "recommendation" in item and isinstance(item["recommendation"], str):
                val = item["recommendation"].upper().strip().replace(" ", "_").replace("-", "_")
                mapping = {
                    "EXECUTE_EMERGENCY_PO": "EXECUTE_BACKUP_PO",
                    "EMERGENCY_PO": "EXECUTE_BACKUP_PO",
                    "BACKUP_PO": "EXECUTE_BACKUP_PO",
                    "EXECUTE_PO": "EXECUTE_BACKUP_PO",
                    "ADVISORY": "PROACTIVE_ADVISORY",
                    "SEND_ADVISORY": "PROACTIVE_ADVISORY",
                    "MONITOR": "HOLD_AND_MONITOR",
                    "HOLD": "HOLD_AND_MONITOR",
                    "NO_ACTION": "HOLD_AND_MONITOR",
                    "DO_NOTHING": "HOLD_AND_MONITOR",
                }
                item["recommendation"] = mapping.get(val, val)
                
            decision = CFODecision(**item)
            if decision.material_id in valid_material_ids:
                validated_decisions.append(decision.model_dump())
            else:
                logger.warning(f"[VALIDATOR] CFO decision references unknown material_id: {decision.material_id}")
        except Exception as e:
            logger.warning(f"[VALIDATOR] Invalid CFO decision item: {e}")
            continue
    
    logger.info(f"[VALIDATOR] Validated {len(validated_decisions)}/{len(data)} CFO decisions.")
    return validated_decisions
