"""
Centralized LLM client. All AI services call this instead of Groq directly.
Switch models by changing this one file.
"""

import json
import re
import logging

import requests

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"


def call_llm(
    system_prompt: str,
    user_content: str,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    model: str | None = None,
) -> dict | None:
    """Call OpenAI API. Returns {"text": str, "usage": dict} or None."""
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        return None

    use_model = model or DEFAULT_MODEL

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": use_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    logger.info(f"Calling OpenAI API ({use_model})...")
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
    except requests.RequestException as e:
        logger.error(f"OpenAI API request failed: {e}")
        return None

    if r.status_code != 200:
        logger.error(f"OpenAI API returned {r.status_code}: {r.text[:500]}")
        return None

    data = r.json()
    choices = data.get("choices", [])
    if not choices:
        logger.error("No choices in OpenAI response")
        return None

    text = choices[0].get("message", {}).get("content", "")
    usage = data.get("usage", {})
    logger.info(f"OpenAI response: {len(text)} chars, model={use_model}, tokens={usage}")
    return {"text": text, "usage": usage}


def call_llm_json(
    system_prompt: str,
    user_content: str,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    model: str | None = None,
) -> dict | list | None:
    """Call OpenAI API expecting JSON response. Parses the result."""
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        return None

    use_model = model or DEFAULT_MODEL

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": use_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    logger.info(f"Calling OpenAI API JSON ({use_model})...")
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
    except requests.RequestException as e:
        logger.error(f"OpenAI API request failed: {e}")
        return None

    if r.status_code != 200:
        logger.error(f"OpenAI API returned {r.status_code}: {r.text[:500]}")
        return None

    data = r.json()
    choices = data.get("choices", [])
    if not choices:
        logger.error("No choices in OpenAI response")
        return None

    text = choices[0].get("message", {}).get("content", "")
    usage = data.get("usage", {})
    logger.info(f"OpenAI JSON response: {len(text)} chars, tokens={usage}")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try extracting JSON array
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        logger.error(f"Failed to parse JSON: {text[:200]}")
        return None
