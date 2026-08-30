"""Single LLM wrapper — the ONLY place we call a model. Owner: mr.jarvis0.

Uses NVIDIA NIM (OpenAI-compatible chat completions) via the team-provided
nvapi key (read from .env). Every agent calls llm(prompt). On any error it
falls back to a deterministic mock so the demo never dies on a network blip.
"""
import re
import requests
from . import config

_SYSTEM = "You are Safar, a concise, practical travel-planning assistant."


def llm(prompt: str, system: str = _SYSTEM,
        temperature: float = 0.4, max_tokens: int = 700) -> str:
    if config.LLM_PROVIDER == "nvidia" and config.NVIDIA_API_KEY:
        try:
            return _nvidia(prompt, system, temperature, max_tokens)
        except Exception as e:
            return _mock(prompt, note=f"(llm fallback: {e})")
    return _mock(prompt)


def _nvidia(prompt: str, system: str, temperature: float, max_tokens: int) -> str:
    url = f"{config.NVIDIA_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.NVIDIA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        # NVIDIA nemotron models are reasoning models — turn the visible
        # chain-of-thought OFF so we get just the final answer.
        "chat_template_kwargs": {"thinking": False},
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return _strip_reasoning(text).strip()


def _strip_reasoning(text: str) -> str:
    """Safety net: drop any residual <think>...</think> reasoning block."""
    return re.sub(r"(?s)<think>.*?</think>\s*", "", text)


def _mock(prompt: str, note: str = "") -> str:
    return f"MOCK_LLM_RESPONSE {note}".strip()
