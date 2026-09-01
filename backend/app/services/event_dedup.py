"""
Event-Level Deduplication Service

Prevents the same real-world disruption from triggering multiple pipelines
when multiple news articles cover the same event (e.g., 3 articles about
the same Chennai flood from different outlets).

Fingerprint = SHA256(region + event_type + YYYY-MM-DD)

This is distinct from article-level dedup (which hashes article text).
Event-level dedup catches semantically identical events from different articles.
"""
import hashlib
import logging
from datetime import date, datetime
from app.database import SyncSessionLocal
from app.models import ActiveDisruption

logger = logging.getLogger(__name__)


def make_event_fingerprint(region: str, event_type: str, event_date: date = None) -> str:
    """
    Creates a stable fingerprint for a real-world disruption event.
    Same event reported by 10 different outlets → same fingerprint.
    """
    if event_date is None:
        event_date = date.today()
    raw = f"{region.lower().strip()}|{event_type.lower().strip()}|{event_date.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def is_event_already_handled(
    region: str,
    event_type: str,
    is_test: bool = False,
) -> dict:
    """
    Checks if this real-world event has already been processed today.
    Returns the existing ActiveDisruption record if found, else None.

    Test-mode events are isolated — they never block production events.
    """
    fingerprint = make_event_fingerprint(region, event_type)

    with SyncSessionLocal() as session:
        existing = session.query(ActiveDisruption).filter(
            ActiveDisruption.fingerprint == fingerprint,
            ActiveDisruption.status == "ACTIVE",
            ActiveDisruption.is_test == is_test,
        ).first()

        if existing:
            return {
                "disruption_id": existing.disruption_id,
                "fingerprint": existing.fingerprint,
                "region": existing.region,
                "event_type": existing.event_type,
                "pipeline_run_id": existing.pipeline_run_id,
                "action_taken": existing.action_taken,
                "detected_at": existing.detected_at.isoformat() if existing.detected_at else None,
            }
        return None


def register_active_disruption(
    region: str,
    event_type: str,
    pipeline_run_id: str,
    action_taken: str = "",
    confidence_score: int = 80,
    is_test: bool = False,
) -> dict:
    """
    Registers a new real-world event in the active_disruptions table.
    Called after the pipeline has completed and taken action.
    """
    fingerprint = make_event_fingerprint(region, event_type)

    with SyncSessionLocal() as session:
        # Upsert: update if exists (shouldn't happen, but safe)
        existing = session.query(ActiveDisruption).filter(
            ActiveDisruption.fingerprint == fingerprint,
            ActiveDisruption.is_test == is_test,
        ).first()

        if existing:
            existing.action_taken = action_taken
            existing.pipeline_run_id = pipeline_run_id
            session.commit()
            return {"disruption_id": existing.disruption_id, "created": False}

        disruption = ActiveDisruption(
            fingerprint=fingerprint,
            region=region,
            event_type=event_type,
            event_date=date.today(),
            status="ACTIVE",
            action_taken=action_taken,
            pipeline_run_id=pipeline_run_id,
            confidence_score=confidence_score,
            is_test=is_test,
        )
        session.add(disruption)
        session.commit()
        session.refresh(disruption)
        logger.info(
            f"[event_dedup] Registered new active disruption: "
            f"{event_type} in {region} (fingerprint: {fingerprint}, pipeline: {pipeline_run_id})"
        )
        return {"disruption_id": disruption.disruption_id, "created": True}


def resolve_disruption(disruption_id: int) -> dict:
    """Marks an active disruption as resolved, lifting all dedup blocks for this event."""
    with SyncSessionLocal() as session:
        disruption = session.query(ActiveDisruption).filter(
            ActiveDisruption.disruption_id == disruption_id
        ).first()
        if not disruption:
            raise ValueError(f"Disruption #{disruption_id} not found")

        disruption.status = "RESOLVED"
        disruption.resolved_at = datetime.utcnow()
        session.commit()
        logger.info(f"[event_dedup] Disruption #{disruption_id} marked RESOLVED")
        return {"disruption_id": disruption_id, "status": "RESOLVED"}


def get_all_active_disruptions(include_test: bool = False) -> list:
    """Returns all currently active disruptions for the dashboard."""
    with SyncSessionLocal() as session:
        query = session.query(ActiveDisruption).filter(ActiveDisruption.status == "ACTIVE")
        if not include_test:
            query = query.filter(ActiveDisruption.is_test == False)
        disruptions = query.order_by(ActiveDisruption.detected_at.desc()).all()
        return [
            {
                "disruption_id": d.disruption_id,
                "region": d.region,
                "event_type": d.event_type,
                "event_date": d.event_date.isoformat() if d.event_date else None,
                "status": d.status,
                "action_taken": d.action_taken,
                "pipeline_run_id": d.pipeline_run_id,
                "confidence_score": d.confidence_score,
                "detected_at": d.detected_at.isoformat() if d.detected_at else None,
                "is_test": d.is_test,
            }
            for d in disruptions
        ]
