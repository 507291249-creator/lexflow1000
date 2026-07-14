"""Small provider boundary for structured LLM tasks.

The server keeps all API credentials on the backend. When no provider key is
configured, callers receive an explicitly marked local fallback so the product
remains usable during local demos without pretending that a model was called.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Type

from pydantic import BaseModel, ValidationError


logger = logging.getLogger(__name__)


class StructuredOutputError(RuntimeError):
    """A structured task failed after the single allowed repair attempt."""

    def __init__(self, message: str, *, code: str = "structured_output_failed", attempts: int = 0):
        super().__init__(message)
        self.code = code
        self.attempts = attempts


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str
    model: str
    base_url: str | None
    supports_json_schema: bool


def provider_config() -> ProviderConfig:
    """Resolve the configured model provider without exposing credentials."""
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if provider in {"zhipu", "zhipuai", "glm"}:
        return ProviderConfig(
            name="zhipu",
            api_key=os.getenv("ZHIPU_API_KEY", "").strip(),
            model=os.getenv("ZHIPU_MODEL", "glm-4-flash-250414").strip(),
            base_url=os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/").strip(),
            supports_json_schema=False,
        )
    if provider in {"openai", ""}:
        return ProviderConfig(
            name="openai",
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
            base_url=None,
            supports_json_schema=True,
        )
    raise StructuredOutputError(
        "LLM_PROVIDER 仅支持 openai 或 zhipu。",
        code="unsupported_llm_provider",
    )


def generate_structured(
    *,
    task: str,
    instructions: str,
    context: str,
    schema: dict[str, Any],
    fallback: Callable[[], dict[str, Any]],
    output_model: Type[BaseModel],
) -> dict[str, Any]:
    provider = provider_config()
    if not provider.api_key:
        if not local_fallback_allowed():
            key_name = "ZHIPU_API_KEY" if provider.name == "zhipu" else "OPENAI_API_KEY"
            raise StructuredOutputError(f"未配置 {key_name}，且当前环境禁止本地备用解析。", code="llm_not_configured")
        key_name = "ZHIPU_API_KEY" if provider.name == "zhipu" else "OPENAI_API_KEY"
        return _validated_fallback(fallback, output_model, error=f"未配置 {key_name}")

    from openai import OpenAI

    client = OpenAI(api_key=provider.api_key, base_url=provider.base_url)
    validation_error = ""
    for attempt in range(1, 3):
        try:
            repair_instruction = "" if not validation_error else f"上一次输出未通过结构校验：{validation_error}。请只返回完全符合 Schema 的 JSON。"
            schema_instruction = ""
            if not provider.supports_json_schema:
                # 智谱的对话接口提供 json_object；字段完整性继续由 Pydantic 校验和一次重试保证。
                schema_instruction = f"请只返回一个 JSON 对象，必须符合以下结构定义：{json.dumps(schema, ensure_ascii=False)}"
            response_format: dict[str, Any]
            if provider.supports_json_schema:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {"name": task, "strict": True, "schema": schema},
                }
            else:
                response_format = {"type": "json_object"}
            response = client.chat.completions.create(
                model=provider.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是法律案件分析助理。只根据给出的案件材料工作，不编造事实；不确定时应明确标注。" + instructions + schema_instruction + repair_instruction,
                    },
                    {"role": "user", "content": context},
                ],
                response_format=response_format,
            )
            content = response.choices[0].message.content or "{}"
            payload = output_model.model_validate(json.loads(content)).model_dump()
            return _with_meta(payload, provider=provider.name, execution_mode="llm", attempts=attempt)
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError, ValueError) as exc:
            validation_error = str(exc)[:360]
            if attempt == 2:
                raise StructuredOutputError("模型输出未通过结构化校验。", code="schema_validation_failed", attempts=attempt) from exc
        except Exception as exc:
            # Record provider diagnostics in the server log without exposing credentials or case material.
            logger.warning(
                "LLM request failed: provider=%s model=%s task=%s attempt=%s error_type=%s detail=%s",
                provider.name,
                provider.model,
                task,
                attempt,
                type(exc).__name__,
                str(exc)[:500],
            )
            if local_fallback_allowed():
                return _validated_fallback(fallback, output_model, error=str(exc)[:180])
            raise StructuredOutputError(
                f"{provider.name} 模型调用失败（{type(exc).__name__}），请查看 Render 日志。",
                code="llm_execution_failed",
                attempts=attempt,
            ) from exc

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
