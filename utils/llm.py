import json
from typing import Optional

try:
    from huggingface_hub import InferenceClient
except Exception:
    InferenceClient = None

def ask_llm(prompt: str, token: str = "", model: str = "", max_tokens: int = 3500) -> str:
    if not token or InferenceClient is None:
        return ""
    try:
        client = InferenceClient(api_key=token, timeout=90)
        response = client.chat_completion(
            messages=[
                {"role":"system","content":"You are a precise JSON-producing resume intelligence assistant. Never invent facts."},
                {"role":"user","content":prompt},
            ],
            model=model,
            temperature=0.1,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception:
        return ""

def llm_available(token: str) -> bool:
    return bool(token and InferenceClient)
