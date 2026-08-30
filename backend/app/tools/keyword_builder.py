from app.database import SyncSessionLocal
from app.models import Supplier, RawMaterial, Factory, TransportRoute
import random

def get_dynamic_news_keywords(max_keywords: int = 5):
    """
    Pulls real entities from the database (materials, supplier regions, highways)
    to dynamically build specific news search keywords.
    """
    with SyncSessionLocal() as session:
        keywords = set()
        
        # 1. Add Factory Cities
        factories = session.query(Factory).all()
        for f in factories:
            if f.city:
                keywords.add(f"{f.city} logistics")
                keywords.add(f"{f.city} traffic")
                
        # 2. Add Key Highways
        routes = session.query(TransportRoute).all()
        for r in routes:
            if r.key_highways:
                for hw in r.key_highways.split(","):
                    hw_clean = hw.strip()
                    if hw_clean:
                        keywords.add(f"{hw_clean} road closure")
                        keywords.add(f"{hw_clean} traffic")
                        keywords.add(f"{hw_clean} accident")
                        
        # 3. Add Raw Materials
        materials = session.query(RawMaterial).all()
        for m in materials:
            keywords.add(f"{m.name.split()[0]} shortage") # e.g. "Wheat shortage"
            
        # 4. Add Supplier Regions
        suppliers = session.query(Supplier).all()
        for s in suppliers:
            # e.g., "North (Delhi/NCR)" -> extract just the first word "North" or "Delhi"
            clean_region = s.location_region.replace("(", "").replace(")", "").split()[0]
            keywords.add(f"{clean_region} supply chain")
            
        keyword_list = list(keywords)
        # Randomly select a subset to avoid overwhelming the NewsAPI query limits
        if len(keyword_list) > max_keywords:
            return random.sample(keyword_list, max_keywords)
        return keyword_list
