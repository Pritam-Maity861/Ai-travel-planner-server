from functools import lru_cache

from langchain_groq import ChatGroq

from app.core.config import get_settings


@lru_cache
def get_llm() -> ChatGroq:
    s = get_settings()
    return ChatGroq(
        model=s.groq_model,
        api_key=s.groq_api_key,
        temperature=0.2,
        max_tokens=8192,
        timeout=60,
        max_retries=2,
    )
