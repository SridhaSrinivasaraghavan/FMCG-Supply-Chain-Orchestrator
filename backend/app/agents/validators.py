"""
Inter-Agent Validation Layer

Validates LLM outputs against strict Pydantic schemas before passing data
between agents. Provides safe defaults and prevents cascading failures
from malformed LLM responses.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ─────────────────── Enums ───────────────────

class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendationAction(str, Enum):
    EXECUTE_BACKUP_PO = "EXECUTE_BACKUP_PO"
    PROACTIVE_ADVISORY = "PROACTIVE_ADVISORY"
    HOLD_AND_MONITOR = "HOLD_AND_MONITOR"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ─────────────────── Schemas ───────────────────

class ValidatedThreatPayload(BaseModel):
    """Strict schema for Market Intel Agent output."""
    event_type: str = Field(default="other")
    region: str = Field(default="Unknown")
    severity: SeverityLevel = Field(default=SeverityLevel.MEDIUM)
    estimated_delay_days: int = Field(default=3, ge=0, le=90)
    affected_commodities: List[str] = Field(default_factory=list)
    summary: str = Field(default="No summary provided.")

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v):
        if isinstance(v, str):
            v = v.upper().strip()
            # Map common LLM hallucinations
            mapping = {
                "VERY HIGH": "CRITICAL",
                "SEVERE": "CRITICAL",
                "MODERATE": "MEDIUM",
                "MINOR": "LOW",
                "NEGLIGIBLE": "LOW",
            }
            v = mapping.get(v, v)
        return v

    @field_validator("region", mode="before")
    @classmethod
    def normalize_region(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return "Unknown"
        return v

    @field_validator("estimated_delay_days", mode="before")
    @classmethod
    def clamp_delay(cls, v):
        if isinstance(v, (int, float)):
            return max(0, min(int(v), 90))
        try:
            return max(0, min(int(v), 90))
        except (ValueError, TypeError):
            return 3


class RiskReasoningOutput(BaseModel):
    """Strict schema for Risk Assessment LLM output."""
    reasoning: str = Field(default="No analysis provided.")
    indirectly_impacted_material_ids: List[int] = Field(default_factory=list)
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM)

    @field_validator("indirectly_impacted_material_ids", mode="before")
    @classmethod
    def ensure_int_list(cls, v):
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            try:
                result.append(int(item))
            except (ValueError, TypeError):
                continue
        return result


class CFODecision(BaseModel):
    """Strict schema for a single CFO decision."""
    material_id: int
    material_name: str = Field(default="Unknown Material")
    recommendation: RecommendationAction = Field(default=RecommendationAction.HOLD_AND_MONITOR)
    rationale: str = Field(default="No rationale provided.")

    @field_validator("recommendation", mode="before")
    @classmethod
    def normalize_recommendation(cls, v):
        if isinstance(v, str):
            v = v.upper().strip().replace(" ", "_").replace("-", "_")
            # Map common LLM hallucinations
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
            v = mapping.get(v, v)
        return v


# ─────────────────── Validation Functions ───────────────────

def validate_threat_payload(data: dict) -> dict:
    """
    Validates Market Intel output. Returns a clean dict or a dict with safe defaults.
    Never raises — always returns usable data.
    """
    try:
        validated = ValidatedThreatPayload(**data)
        logger.info(f"[VALIDATOR] Threat payload validated: {validated.event_type} in {validated.region} ({validated.severity})")
        return validated.model_dump()
    except Exception as e:
        logger.warning(f"[VALIDATOR] Threat payload validation failed: {e}. Using defaults.")
        defaults = ValidatedThreatPayload()
        # Try to salvage what we can from the raw data
        if isinstance(data, dict):
            for key in ["event_type", "region", "summary"]:
                if key in data and isinstance(data[key], str):
                    setattr(defaults, key, data[key])
        return defaults.model_dump()


def validate_risk_reasoning(data: dict, known_material_ids: set) -> dict:
    """
    Validates Risk Assessment LLM output.
    Filters out hallucinated material_ids that don't exist in the database.
    """
    try:
        validated = RiskReasoningOutput(**data)
        # Filter out IDs that don't exist in our database
        original_ids = validated.indirectly_impacted_material_ids
        validated.indirectly_impacted_material_ids = [
            mid for mid in original_ids if mid in known_material_ids
        ]
        if len(validated.indirectly_impacted_material_ids) != len(original_ids):
            hallucinated = set(original_ids) - known_material_ids
            logger.warning(f"[VALIDATOR] Removed hallucinated material IDs: {hallucinated}")
        
        logger.info(f"[VALIDATOR] Risk reasoning validated. Indirect impacts: {validated.indirectly_impacted_material_ids}")
        return validated.model_dump()
    except Exception as e:
        logger.warning(f"[VALIDATOR] Risk reasoning validation failed: {e}. Using defaults.")
        return RiskReasoningOutput().model_dump()


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
