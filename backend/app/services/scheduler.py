"""
Background Scheduler Service
Periodically scans news sources and feeds articles into the Market Intel Agent
to detect supply chain threats automatically.
"""
import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.services.news_fetcher import UnifiedNewsFetcher
from app.agents.graph import app_graph

logger = logging.getLogger(__name__)


class ScanResult:
    """Stores the result of a single auto-scan run."""
    def __init__(self):
        self.timestamp: Optional[str] = None
        self.articles_fetched: int = 0
        self.threats_detected: int = 0
        self.pipelines_triggered: int = 0
        self.articles: list = []
        self.pipeline_results: list = []
        self.status: str = "idle"


# Global state for the latest scan result
_latest_scan = ScanResult()
_scheduler: Optional[BackgroundScheduler] = None


def get_latest_scan() -> ScanResult:
    """Returns the latest scan result."""
    return _latest_scan


def run_auto_scan():
    """
    The core scan job:
    1. Fetch real news articles from all configured sources.
    2. Feed each article through the full LangGraph agent pipeline.
    3. Store results for the status endpoint.
    """
    global _latest_scan
    logger.info("=== AUTO-SCAN STARTED ===")
    _latest_scan.status = "scanning"
    _latest_scan.timestamp = datetime.utcnow().isoformat()

    try:
        articles = UnifiedNewsFetcher.fetch_real_news(max_articles=5)
        _latest_scan.articles_fetched = len(articles)
        _latest_scan.articles = [a.to_dict() for a in articles]
        _latest_scan.threats_detected = 0
        _latest_scan.pipelines_triggered = 0
        _latest_scan.pipeline_results = []

        for article in articles:
            try:
                logger.info(f"Processing article: {article.title[:80]}...")

                # Feed the article into the LangGraph pipeline
                initial_state = {
                    "raw_news": article.full_text,
                    "auto_triggered": True,
                    "messages": [],
                }
                result = app_graph.invoke(initial_state)

                threat = result.get("threat_payload")
                impacted = result.get("impacted_materials", [])
                actions = result.get("recommended_actions", [])

                # Check if it was a real threat
                if threat and impacted:
                    _latest_scan.threats_detected += 1
                    _latest_scan.pipelines_triggered += 1
                    _latest_scan.pipeline_results.append({
                        "article_title": article.title,
                        "threat": threat,
                        "impacted_count": len(impacted),
                        "actions_taken": len(actions),
                    })
                    logger.info(f"THREAT DETECTED: {threat.get('event_type')} in {threat.get('region')}")
                else:
                    logger.info(f"No supply chain threat found in: {article.title[:60]}")

            except Exception as e:
                logger.error(f"Error processing article '{article.title[:40]}': {e}")

        _latest_scan.status = "completed"
        logger.info(
            f"=== AUTO-SCAN COMPLETE === "
            f"Articles: {_latest_scan.articles_fetched}, "
            f"Threats: {_latest_scan.threats_detected}, "
            f"Pipelines triggered: {_latest_scan.pipelines_triggered}"
        )

    except Exception as e:
        _latest_scan.status = f"error: {str(e)}"
        logger.error(f"Auto-scan failed: {e}")


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
