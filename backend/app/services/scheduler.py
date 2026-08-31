"""
Background Scheduler Service

Periodically scans news sources and feeds articles into the Market Intel Agent
to detect supply chain threats automatically.

Improvements:
- Article deduplication across scan cycles (prevents duplicate pipeline runs)
- Pipeline run ID tracking for each auto-triggered pipeline
- Better error isolation (one article failure doesn't stop the whole scan)
- Configurable dedup window
"""
import hashlib
import logging
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.services.news_fetcher import UnifiedNewsFetcher
from app.agents.graph import app_graph

logger = logging.getLogger(__name__)

# Dedup: track processed article hashes (LRU with max size)
MAX_DEDUP_CACHE_SIZE = 500
_processed_articles = OrderedDict()


class ScanResult:
    """Stores the result of a single auto-scan run."""
    def __init__(self):
        self.timestamp: Optional[str] = None
        self.articles_fetched: int = 0
        self.threats_detected: int = 0
        self.pipelines_triggered: int = 0
        self.articles_skipped_dedup: int = 0
        self.articles: list = []
        self.pipeline_results: list = []
        self.status: str = "idle"


# Global state for the latest scan result
_latest_scan = ScanResult()
_scheduler: Optional[BackgroundScheduler] = None


def get_latest_scan() -> ScanResult:
    """Returns the latest scan result."""
    return _latest_scan


def _article_hash(title: str, description: str) -> str:
    """Generates a hash for deduplication based on article content."""
    content = f"{title.strip().lower()}|{description.strip().lower()[:200]}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _is_duplicate(article) -> bool:
    """Checks if an article has already been processed in recent scan cycles."""
    h = _article_hash(article.title, article.description)
    if h in _processed_articles:
        return True
    
    # Add to cache with LRU eviction
    _processed_articles[h] = datetime.utcnow().isoformat()
    if len(_processed_articles) > MAX_DEDUP_CACHE_SIZE:
        _processed_articles.popitem(last=False)  # Remove oldest
    
    return False


def run_auto_scan():
    """
    The core scan job:
    1. Fetch real news articles from all configured sources.
    2. Deduplicate against previously processed articles.
    3. Feed each new article through the full LangGraph agent pipeline.
    4. Store results for the status endpoint.
    """
    global _latest_scan
    logger.info("=== AUTO-SCAN STARTED ===")
    _latest_scan = ScanResult()
    _latest_scan.status = "scanning"
    _latest_scan.timestamp = datetime.utcnow().isoformat()

    try:
        articles = UnifiedNewsFetcher.fetch_real_news(max_articles=5)
        _latest_scan.articles_fetched = len(articles)
        _latest_scan.articles = [a.to_dict() for a in articles]

        for article in articles:
            # ── Deduplication check ──
            if _is_duplicate(article):
                _latest_scan.articles_skipped_dedup += 1
                logger.info(f"[auto-scan] DEDUP: Skipping already-processed article: {article.title[:60]}...")
                continue
            
            try:
                logger.info(f"[auto-scan] Processing article: {article.title[:80]}...")
                
                pipeline_run_id = f"auto-{str(uuid.uuid4())[:8]}"

                # Feed the article into the LangGraph pipeline
                initial_state = {
                    "raw_news": article.full_text,
                    "auto_triggered": True,
                    "pipeline_run_id": pipeline_run_id,
                    "started_at": datetime.utcnow().isoformat(),
                    "messages": [],
                }
                result = app_graph.invoke(initial_state)

                threat = result.get("threat_payload")
                impacted = result.get("impacted_materials", [])
                actions = result.get("recommended_actions", [])

                # Check if it was a real threat (has both threat identification and material impact)
                if threat and impacted:
                    _latest_scan.threats_detected += 1
                    _latest_scan.pipelines_triggered += 1
                    _latest_scan.pipeline_results.append({
                        "pipeline_run_id": pipeline_run_id,
                        "article_title": article.title,
                        "threat": threat,
                        "impacted_count": len(impacted),
                        "actions_taken": len(actions),
                        "risk_level": result.get("risk_level", "UNKNOWN"),
                    })
                    logger.info(
                        f"[auto-scan] THREAT DETECTED (pipeline {pipeline_run_id}): "
                        f"{threat.get('event_type')} in {threat.get('region')}"
                    )
                else:
                    logger.info(f"[auto-scan] No supply chain threat found in: {article.title[:60]}")

            except Exception as e:
                logger.error(f"[auto-scan] Error processing article '{article.title[:40]}': {e}")

        _latest_scan.status = "completed"
        logger.info(
            f"=== AUTO-SCAN COMPLETE === "
            f"Articles: {_latest_scan.articles_fetched}, "
            f"Skipped (dedup): {_latest_scan.articles_skipped_dedup}, "
            f"Threats: {_latest_scan.threats_detected}, "
            f"Pipelines triggered: {_latest_scan.pipelines_triggered}"
        )

    except Exception as e:
        _latest_scan.status = f"error: {str(e)}"
        logger.error(f"[auto-scan] Scan failed: {e}")


def start_scheduler():
    """Initialize and start the background scheduler."""
    global _scheduler

    if not settings.AUTO_SCAN_ENABLED:
        logger.info("Auto-scan is DISABLED in settings. Skipping scheduler start.")
        return

    _scheduler = BackgroundScheduler()
    interval = settings.AUTO_SCAN_INTERVAL_MINUTES

    _scheduler.add_job(
        run_auto_scan,
        trigger="interval",
        minutes=interval,
        id="auto_news_scan",
        name=f"News Auto-Scan (every {interval} min)",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(f"Background scheduler started. Auto-scan will run every {interval} minutes.")


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped.")


def trigger_manual_scan():
    """Manually trigger a scan (for the API endpoint)."""
    run_auto_scan()
    return _latest_scan
