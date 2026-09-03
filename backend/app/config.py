from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # LLM Configuration
    LLM_PROVIDER: str = "ollama"  # 'ollama', 'openai', 'groq', 'mock'
    LLM_MODEL: str = "llama3.2:3b"
    LLM_TEMPERATURE: float = 0.0
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    
    # Per-Agent Overrides
    MARKET_INTEL_LLM_MODEL: Optional[str] = None
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fmcg_supply_chain"
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/fmcg_supply_chain"
    
    # External APIs
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: str = "no-reply@fmcg-corp.com"
    OPENWEATHER_API_KEY: Optional[str] = None
    NEWSAPI_KEY: Optional[str] = None
    
    # Auto-Scan Configuration
    AUTO_SCAN_INTERVAL_MINUTES: int = 30
    AUTO_SCAN_ENABLED: bool = True
    SUPPLY_CHAIN_KEYWORDS: str = "supply chain disruption,port strike,flood logistics,raw material shortage,freight delay,commodity price surge"
    
    # Business Logic
    FACTORY_IDLE_COST_PER_DAY: float = 15000.0
    MAX_AUTO_PO_COST: float = 100000.0  # POs above this amount will be flagged for human review
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
