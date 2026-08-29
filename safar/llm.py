"""Single LLM wrapper — the ONLY place we call a model. Owner: mr.jarvis0.

Every agent calls llm(prompt). Swap providers here without touching agents.
Falls back to a deterministic mock so the demo never dies on a network blip.
"""
from . import config


def llm(prompt: str, system: str = "") -> str:
    provider = config.LLM_PROVIDER
    if provider == "mock" or not config.LLM_API_KEY:
        return _mock(prompt)
    # TODO(lead): implement real providers once the key is known
    # if provider == "groq":   ...
    # if provider == "gemini": ...
    # if provider == "openai": ...
    return _mock(prompt)


def _mock(prompt: str) -> str:
    """Deterministic stand-in so the pipeline runs with zero keys."""
    return "MOCK_LLM_RESPONSE"
