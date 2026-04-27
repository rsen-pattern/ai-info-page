"""Bi Frost LLM gateway client."""
import os
import json
from pathlib import Path
from openai import OpenAI


def get_api_key(user_provided: str = "") -> str:
    """Three-tier precedence: user input → st.secrets → env var."""
    if user_provided and user_provided.strip():
        return user_provided.strip()
    try:
        import streamlit as st
        return st.secrets.get("BIFROST_API_KEY") or st.secrets.get("BIFROST_KEY", "")
    except Exception:
        pass
    return os.environ.get("BIFROST_API_KEY") or os.environ.get("BIFROST_KEY", "")


def get_client(api_key: str) -> OpenAI:
    base_url = "https://bifrost.pattern.com"
    if not base_url.rstrip("/").endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"
    return OpenAI(api_key=api_key, base_url=base_url)


def load_models() -> dict:
    models_path = Path(__file__).parent.parent / "config" / "models.json"
    with open(models_path) as f:
        return json.load(f)


def call(client: OpenAI, model: str, system: str, user: str, max_tokens: int = 2000) -> str:
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content


def call_with_fallback(
    client: OpenAI, model: str, system: str, user: str, max_tokens: int = 2000
) -> tuple[str, str]:
    models_cfg = load_models()
    fallback_chain = [model] + [
        m for m in models_cfg.get("fallback_chain", []) if m != model
    ]
    last_err = None
    for m in fallback_chain:
        try:
            result = call(client, m, system, user, max_tokens)
            return result, m
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"All models failed. Last error: {last_err}")
