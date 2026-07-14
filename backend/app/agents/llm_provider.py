"""Small provider boundary for structured LLM tasks.

The server keeps all API credentials on the backend. When no provider key is
configured, callers receive an explicitly marked local fallback so the product
remains usable during local demos without pretending that a model was called.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable


def generate_structured(
    *,
    task: str,
    instructions: str,
    context: str,
    schema: dict[str, Any],
    fallback: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _with_meta(fallback(), provider="local-fallback", mode="备用解析")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "你是劳动争议法律助理。只根据给出的案件材料工作，不编造事实；不确定时应明确标注。" + instructions,
                },
                {"role": "user", "content": context},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": task, "strict": True, "schema": schema},
            },
        )
        content = response.choices[0].message.content or "{}"
        return _with_meta(json.loads(content), provider="openai", mode="真实 LLM")
    except Exception as exc:  # Keeps local use possible when a key or network is unavailable.
        return _with_meta(fallback(), provider="local-fallback", mode="备用解析", error=str(exc)[:180])


def _with_meta(payload: dict[str, Any], *, provider: str, mode: str, error: str = "") -> dict[str, Any]:
    payload["_llm"] = {"provider": provider, "mode": mode, "error": error}
    return payload
