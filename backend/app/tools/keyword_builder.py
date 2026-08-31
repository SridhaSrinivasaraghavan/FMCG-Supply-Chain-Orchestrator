"""
Dynamic Keyword Builder

Builds comprehensive, highly specific news search queries by pulling
ALL relevant entities from the database: factory cities, transport route
highways and cities, supplier regions, material names, and categories.

This ensures the news scanner catches disruptions relevant to ANY part
of our supply chain — not just generic supply chain keywords.
"""
from app.tools.db_tools import get_all_searchable_entities
import random
import logging

logger = logging.getLogger(__name__)

# Templates for building search queries from DB entities
KEYWORD_TEMPLATES = {
    "factory_cities": [
        "{} logistics disruption",
        "{} factory shutdown",
        "{} industrial area flood",
        "{} power outage",
    ],
    "route_highways": [
        "{} road closure",
        "{} traffic jam",
        "{} accident highway",
        "{} road block",
        "{} construction delay",
    ],
    "route_cities": [
        "{} supply chain delay",
        "{} freight disruption",
        "{} transport blocked",
    ],
    "supplier_regions": [
        "{} supply chain disruption",
        "{} flood logistics",
        "{} strike factory",
        "{} warehouse fire",
    ],
    "material_names": [
        "{} shortage",
        "{} price surge",
        "{} supply disruption",
    ],
    "material_categories": [
        "{} commodity shortage",
        "{} raw material crisis",
    ],
}


def get_dynamic_news_keywords(max_keywords: int = 8) -> list:
    """
    Pulls real entities from the database (materials, supplier regions, highways,
    factory cities, route cities) to dynamically build specific news search keywords.
    
    Returns a prioritized list of search keywords covering:
    1. Factory locations (highest priority — direct production risk)
    2. Transport route highways and cities (route disruptions)
    3. Supplier regions (supplier-side disruptions)
    4. Material names and categories (commodity-level disruptions)
    
    Keywords are randomized within each priority tier to provide varied coverage
    across scan cycles.
    """
    try:
        entities = get_all_searchable_entities()
    except Exception as e:
        logger.error(f"[keyword_builder] Failed to fetch DB entities: {e}")
        return _get_fallback_keywords()
    
    all_keywords = []
    
    # Priority 1: Factory cities (direct production risk)
    for city in entities.get("factory_cities", []):
        if city:
            all_keywords.extend([
                f"{city} logistics disruption",
                f"{city} flood",
                f"{city} power outage industrial",
            ])
    
    # Priority 2: Route highways (transport disruptions)
    for highway in entities.get("route_highways", []):
        if highway and len(highway) > 1:
            all_keywords.extend([
                f"{highway} road closure",
                f"{highway} traffic accident",
                f"{highway} road block",
            ])
    
    # Priority 3: Route cities (transit point disruptions)
    for city in entities.get("route_cities", []):
        if city and len(city) > 2:
            all_keywords.append(f"{city} freight delay")
    
    # Priority 4: Supplier regions (supplier-side disruptions)
    seen_regions = set()
    for region in entities.get("supplier_regions", []):
        if region:
            # Extract clean region name: "North (Delhi/NCR)" → "Delhi"
            clean = region.replace("(", "").replace(")", "").replace("/", " ")
            parts = clean.split()
            for part in parts:
                if len(part) > 2 and part not in seen_regions:
                    seen_regions.add(part)
                    all_keywords.append(f"{part} supply chain disruption")
    
    # Priority 5: Material names (commodity-level disruptions)
    for material_name in entities.get("material_names", []):
        if material_name:
            # Use first word of material name: "Grade-A Wheat Flour" → "Wheat"
            words = material_name.split()
            for word in words:
                clean_word = word.replace("-", "").replace("'", "")
                if len(clean_word) > 3 and clean_word[0].isupper():
                    all_keywords.append(f"{clean_word} shortage")
                    break
    
    # Priority 6: Material categories
    for category in entities.get("material_categories", []):
        if category:
            all_keywords.append(f"{category} commodity crisis")
    
    # Deduplicate and limit
    unique_keywords = list(dict.fromkeys(all_keywords))  # Preserves order
    
    if len(unique_keywords) > max_keywords:
        # Ensure at least one keyword from each priority tier
        selected = []
        # Take first from each priority group (factory, highway, city, region, material)
        priority_bounds = [
            len(entities.get("factory_cities", [])) * 3,
            len(entities.get("route_highways", [])) * 3,
            len(entities.get("route_cities", [])),
        ]
        
        idx = 0
        for bound in priority_bounds:
            if idx < len(unique_keywords):
                selected.append(unique_keywords[idx])
                idx += bound
        
        # Fill remaining with random selection from the rest
        remaining = [kw for kw in unique_keywords if kw not in selected]
        random.shuffle(remaining)
        selected.extend(remaining[:max_keywords - len(selected)])
        
        return selected[:max_keywords]
    
    return unique_keywords


def _get_fallback_keywords() -> list:
    """Fallback keywords when DB is unavailable."""
    return [
        "supply chain disruption India",
        "freight delay highway",
        "raw material shortage",
        "factory shutdown flood",
        "port strike logistics",
    ]
