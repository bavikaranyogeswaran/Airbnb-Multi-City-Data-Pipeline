"""
Groq API wrapper with disk caching.

generate() is the single entry point used by the FastAPI router.
It builds the prompt, checks the cache, calls Groq if needed,
writes the result to disk, and returns (text, was_cached).

Cache location: reports/llm_summaries/{city}_{type}.md
                reports/llm_summaries/cross_city.md
"""
from __future__ import annotations

import os
from pathlib import Path

from src.llm.prompts import SYSTEM, render

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "reports" / "llm_summaries"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Low temperature — we want factual narration, not creative variation
_TEMPERATURE = 0.3
# ~280 words × ~1.4 tokens/word + small buffer
_MAX_TOKENS = 600


def _cache_path(summary_type: str, city: str | None) -> Path:
    name = "cross_city" if summary_type == "cross_city" else f"{city}_{summary_type}"
    return CACHE_DIR / f"{name}.md"


def _call_groq(system: str, user: str, model: str) -> str:
    """Call Groq chat completions. Raises if GROQ_API_KEY is not set."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com and add it to your environment."
        )

    from groq import Groq  # import here so missing SDK gives a clear error

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=_TEMPERATURE,
        max_tokens=_MAX_TOKENS,
    )
    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("Groq returned an empty response")
    return content.strip()


def generate(
    context: dict,
    summary_type: str,
    city: str | None = None,
    model: str = DEFAULT_MODEL,
    refresh: bool = False,
) -> tuple[str, bool]:
    """
    Generate (or retrieve from cache) a natural-language summary.

    Returns:
        (summary_text, was_cached) — callers can expose was_cached to the API.
    """
    cache = _cache_path(summary_type, city)

    if not refresh and cache.exists():
        return cache.read_text(encoding="utf-8"), True

    user_prompt = render(summary_type, context)
    text = _call_groq(SYSTEM, user_prompt, model)

    cache.write_text(text, encoding="utf-8")
    return text, False
