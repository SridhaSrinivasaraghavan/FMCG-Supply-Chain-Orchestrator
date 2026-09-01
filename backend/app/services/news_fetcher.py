"""
News Ingestion Service
Fetches real-time disruption alerts from multiple sources:
1. NewsAPI.org (primary - requires API key)
2. Google News RSS (fallback - no key needed)
3. Mock events (always available for testing)
"""
import random
import logging
import httpx
import feedparser
from datetime import datetime, timedelta
from typing import List, Optional

from app.config import settings
from app.tools.keyword_builder import get_dynamic_news_keywords

logger = logging.getLogger(__name__)


class FetchedArticle:
    """Represents a single news article fetched from any source."""
    def __init__(self, title: str, description: str, source: str, url: str = "", published_at: str = ""):
        self.title = title
        self.description = description
        self.source = source
        self.url = url
        self.published_at = published_at
        self.full_text = f"{title}. {description}"

    def to_dict(self):
        return {
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "url": self.url,
            "published_at": self.published_at,
            "full_text": self.full_text,
        }


class NewsAPIFetcher:
    """Fetches articles from NewsAPI.org (free tier: 100 requests/day)."""
    BASE_URL = "https://newsapi.org/v2/everything"

    @staticmethod
    def fetch(keywords: List[str], max_articles: int = 10) -> List[FetchedArticle]:
        api_key = settings.NEWSAPI_KEY
        if not api_key:
            logger.warning("NEWSAPI_KEY not set. Skipping NewsAPI fetch.")
            return []

        query = " OR ".join(keywords)
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            response = httpx.get(
                NewsAPIFetcher.BASE_URL,
                params={
                    "q": query,
                    "from": yesterday,
                    "sortBy": "relevancy",
                    "pageSize": max_articles,
                    "language": "en",
                    "apiKey": api_key,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()

            articles = []
            for item in data.get("articles", []):
                articles.append(
                    FetchedArticle(
                        title=item.get("title", ""),
                        description=item.get("description", "") or "",
                        source=f"NewsAPI:{item.get('source', {}).get('name', 'Unknown')}",
                        url=item.get("url", ""),
                        published_at=item.get("publishedAt", ""),
                    )
                )
            logger.info(f"NewsAPI returned {len(articles)} articles for query: {query[:60]}...")
            return articles

        except Exception as e:
            logger.error(f"NewsAPI fetch failed: {e}")
            return []


class GoogleNewsRSSFetcher:
    """Fetches articles from Google News RSS feeds (no API key needed)."""
    BASE_URL = "https://news.google.com/rss/search"

    @staticmethod
    def fetch(keywords: List[str], max_articles: int = 10) -> List[FetchedArticle]:
        from urllib.parse import quote_plus
        query = " OR ".join(keywords)
        encoded_query = quote_plus(query)  # Fix: encode spaces and special chars in URL
        try:
            feed = feedparser.parse(f"{GoogleNewsRSSFetcher.BASE_URL}?q={encoded_query}&hl=en-US&gl=US&ceid=US:en")
            articles = []
            for entry in feed.entries[:max_articles]:
                articles.append(
                    FetchedArticle(
                        title=entry.get("title", ""),
                        description=entry.get("summary", "") or entry.get("title", ""),
                        source=f"GoogleRSS:{entry.get('source', {}).get('title', 'Unknown')}",
                        url=entry.get("link", ""),
                        published_at=entry.get("published", ""),
                    )
                )
            logger.info(f"Google News RSS returned {len(articles)} articles.")
            return articles

        except Exception as e:
            logger.error(f"Google News RSS fetch failed: {e}")
            return []


class MockDisruptionStreamer:
    """Provides realistic mock disruption events for testing and demo purposes."""

    MOCK_EVENTS = [
        {
            "news_text": "Massive monsoon floods in the North region have completely washed out major highways. Freight transport is halted for at least 2 weeks.",
            "region": "North",
        },
        {
            "news_text": "Port workers strike in the West region delays all incoming oil and fat shipments for at least 10 days.",
            "region": "West",
        },
        {
            "news_text": "Sudden heatwave and crop failure in the East severely impacts sugar yield, driving up local prices and tightening supply for 3 weeks.",
            "region": "East",
        },
        {
            "news_text": "Major railway derailment in the South causes a multi-day backlog for all industrial additives and baking supplies. Estimated delays of 8 days.",
            "region": "South",
        },
        {
            "news_text": "Critical chemical spill at a North region flour processing facility forces emergency shutdown. Wheat flour production halted for an estimated 12 days.",
            "region": "North",
        },
    ]

    @classmethod
    def get_random(cls) -> dict:
        """Returns a random mock disruption event for demo/testing."""
        return random.choice(cls.MOCK_EVENTS)


class UnifiedNewsFetcher:
    """
    Orchestrates fetching from all available sources.
    Priority: NewsAPI (if key set) → Google RSS (fallback) → Mock (always available)
    """

    @staticmethod
    def fetch_real_news(max_articles: int = 10) -> List[FetchedArticle]:
        """Fetches real news using dynamic keywords from our DB and generic keywords from .env."""
        # Get generic keywords from .env
        env_keywords = [kw.strip() for kw in settings.SUPPLY_CHAIN_KEYWORDS.split(",")]
        
        # Get highly specific dynamic keywords from the database (highways, cities, materials)
        try:
            dynamic_keywords = get_dynamic_news_keywords(max_keywords=4)
        except Exception as e:
            logger.error(f"Failed to fetch dynamic DB keywords: {e}")
            dynamic_keywords = []
            
        # Combine them (prioritize dynamic database keywords)
        keywords = dynamic_keywords + env_keywords[:2]
        
        all_articles = []

        # Try NewsAPI first
        newsapi_articles = NewsAPIFetcher.fetch(keywords, max_articles)
        all_articles.extend(newsapi_articles)

        # If NewsAPI returned nothing, try Google RSS
        if not all_articles:
            rss_articles = GoogleNewsRSSFetcher.fetch(keywords, max_articles)
            all_articles.extend(rss_articles)

        if not all_articles:
            logger.warning("No real news fetched from any source. Use /api/simulate-news for mock testing.")

        return all_articles

    @staticmethod
    def get_mock_event() -> dict:
        """Returns a random mock event for manual testing."""
        return MockDisruptionStreamer.get_random()
