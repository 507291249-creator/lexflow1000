"""Small provider boundary for structured LLM tasks.

The server keeps all API credentials on the backend. When no provider key is
configured, callers receive an explicitly marked local fallback so the product
remains usable during local demos without pretending that a model was called.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Type

from pydantic import BaseModel, ValidationError


class StructuredOutputError(RuntimeError):
    """A structured task failed after the single allowed repair attempt."""

    def __init__(self, message: str, *, code: str = "structured_output_failed", attempts: int = 0):
        super().__init__(message)
        self.code = code
        self.attempts = attempts


def generate_structured(
    *,
    task: str,
    instructions: str,
    context: str,
    schema: dict[str, Any],
    fallback: Callable[[], dict[str, Any]],
    output_model: Type[BaseModel],
) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        if not local_fallback_allowed():
            raise StructuredOutputError("未配置 OPENAI_API_KEY，且当前环境禁止本地备用解析。", code="llm_not_configured")
        return _validated_fallback(fallback, output_model, error="未配置 OPENAI_API_KEY")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    validation_error = ""
    for attempt in range(1, 3):
        try:
            repair_instruction = "" if not validation_error else f"上一次输出未通过结构校验：{validation_error}。请只返回完全符合 Schema 的 JSON。"
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "你是法律案件分析助理。只根据给出的案件材料工作，不编造事实；不确定时应明确标注。" + instructions + repair_instruction,
                    },
                    {"role": "user", "content": context},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": task, "strict": True, "schema": schema},
                },
            )
            content = response.choices[0].message.content or "{}"
            payload = output_model.model_validate(json.loads(content)).model_dump()
            return _with_meta(payload, provider="openai", execution_mode="llm", attempts=attempt)
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError, ValueError) as exc:
            validation_error = str(exc)[:360]
            if attempt == 2:
                raise StructuredOutputError("模型输出未通过结构化校验。", code="schema_validation_failed", attempts=attempt) from exc
        except Exception as exc:
            if local_fallback_allowed():
                return _validated_fallback(fallback, output_model, error=str(exc)[:180])
            raise StructuredOutputError("模型调用失败，未启用本地备用解析。", code="llm_execution_failed", attempts=attempt) from exc

    raise StructuredOutputError("模型输出执行失败。", attempts=2)


def local_fallback_allowed() -> bool:
    return os.getenv("ALLOW_LOCAL_AI_FALLBACK", "true").strip().lower() in {"1", "true", "yes", "on"}


def _validated_fallback(fallback: Callable[[], dict[str, Any]], output_model: Type[BaseModel], *, error: str = "") -> dict[str, Any]:
    try:
        payload = output_model.model_validate(fallback()).model_dump()
    except ValidationError as exc:
        raise StructuredOutputError("本地备用解析未通过结构化校验。", code="fallback_schema_failed") from exc
    return _with_meta(payload, provider="local-fallback", execution_mode="fallback", error=error, attempts=1)


def _with_meta(payload: dict[str, Any], *, provider: str, execution_mode: str, error: str = "", attempts: int = 1) -> dict[str, Any]:
    payload["_llm"] = {
        "provider": provider,
        "execution_mode": execution_mode,
        "mode": "AI 实时生成" if execution_mode == "llm" else "本地备用解析",
        "error": error,
        "attempts": attempts,
    }
    return payload
