from langchain_core.language_models.chat_models import BaseChatModel
from app.config import settings

class FakeChatModel(BaseChatModel):
    """A mock LLM for testing without API keys or local instances."""
    
    @property
    def _llm_type(self) -> str:
        return "fake-mock-llm"
        
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatResult, ChatGeneration
        from langchain_core.messages import AIMessage
        import json
        
        # A simple fake response that satisfies the Market Intel Agent's JSON requirements
        fake_response = json.dumps({
            "event_type": "flood",
            "region": "North",
            "severity": "CRITICAL",
            "estimated_delay_days": 5,
            "affected_commodities": ["wheat", "sugar"],
            "summary": "Mock extraction of severe flooding in the North."
        })
        
        message = AIMessage(content=fake_response)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])
        
def get_llm(agent_role: str = "default") -> BaseChatModel:
    """
    Returns configured LLM based on LLM_PROVIDER env var.
    Supports per-agent overrides (e.g., MARKET_INTEL_LLM_MODEL).
    """
    provider = settings.LLM_PROVIDER.lower()
    
    # Check for agent-specific model override
    model_name = settings.LLM_MODEL
    if agent_role == "market_intel" and settings.MARKET_INTEL_LLM_MODEL:
        model_name = settings.MARKET_INTEL_LLM_MODEL

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model_name,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
            format="json" if agent_role == "market_intel" else ""
        )
        
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in environment.")
        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            temperature=settings.LLM_TEMPERATURE
        )
        
    elif provider == "groq":
        from langchain_openai import ChatOpenAI
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set in environment.")
        return ChatOpenAI(
            model=model_name,
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            temperature=settings.LLM_TEMPERATURE
        )
        
    else:
        # Default to mock if provider is 'mock' or unrecognized
        return FakeChatModel()
