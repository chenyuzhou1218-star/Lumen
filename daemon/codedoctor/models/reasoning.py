"""思考强度 (thinking strength) for every provider: one user-facing level, each provider's own parameter.

Levels: off / low / medium / high / max. None (not set) sends nothing: the provider's default.
Checked against the providers' documentation (2026-10): DeepSeek `thinking` + `reasoning_effort`; Gemini's OpenAI
endpoint `reasoning_effort` (mapped to its thinking budget or level); Qwen (DashScope, SiliconFlow) `enable_thinking`
+ `thinking_budget`; OpenRouter `reasoning: {effort}`; Anthropic `thinking: {budget_tokens}`. For the rest the usual
parameter is sent; a provider that rejects it is asked again without it, once, and remembered (the request never
fails because of the level). A thinking model that calls tools must get its earlier thinking back unchanged
(DeepSeek's reasoning_content, Anthropic's signed thinking blocks): the clients keep it on the assistant message.
"""

from __future__ import annotations

from urllib.parse import urlparse

LEVELS = ("off", "low", "medium", "high", "max")
LEVEL_CN = {"off": "不思考", "low": "低", "medium": "中", "high": "高", "max": "最高"}
BUDGET = {"low": 2048, "medium": 8192, "high": 24576, "max": 32768}  # thinking tokens, for budget-style providers

_BY_HOST = {"api.deepseek.com": "deepseek", "generativelanguage.googleapis.com": "gemini", "api.openai.com": "openai",
            "dashscope.aliyuncs.com": "qwen", "dashscope-intl.aliyuncs.com": "qwen", "api.siliconflow.cn": "qwen",
            "open.bigmodel.cn": "zhipu", "ark.cn-beijing.volces.com": "ark", "openrouter.ai": "openrouter",
            "api.x.ai": "openai", "api.groq.com": "openai", "api.hunyuan.cloud.tencent.com": "qwen",
            "api.moonshot.cn": "none", "api.mistral.ai": "none"}
_BY_PROVIDER = {"deepseek": "deepseek", "gemini": "gemini", "openai": "openai", "dashscope": "qwen", "siliconflow": "qwen",
                "zhipu": "zhipu", "ark": "ark", "openrouter": "openrouter", "xai": "openai", "groq": "openai",
                "hunyuan": "qwen", "qianfan": "openai", "moonshot": "none", "mistral": "none", "ollama": "openai",
                "lmstudio": "openai", "vllm": "qwen", "llamacpp": "none", "minimax": "none", "stepfun": "none",
                "baichuan": "none", "lingyi": "none", "together": "openai", "fireworks": "openai", "nvidia": "openai",
                "cerebras": "openai", "perplexity": "openai"}


def style(provider: str, base_url: str) -> str:
    """How this endpoint takes a thinking level: the preset it was made from, else its host, else the common way."""
    if provider in _BY_PROVIDER:
        return _BY_PROVIDER[provider]
    host = (urlparse(base_url).hostname or "").lower()
    return _BY_HOST.get(host, "openai")


def openai_fields(how: str, level: str | None) -> dict:
    """Extra request fields of an OpenAI-compatible request for this level ({} when nothing is to be sent)."""
    if not level or how == "none":
        return {}
    off = level == "off"
    if how == "deepseek":
        if off:
            return {"thinking": {"type": "disabled"}}
        return {"thinking": {"type": "enabled"},
                "reasoning_effort": {"low": "low", "medium": "high", "high": "high", "max": "max"}[level]}
    if how == "gemini":
        return {"reasoning_effort": "none" if off else {"max": "high"}.get(level, level)}
    if how == "qwen":
        return {"enable_thinking": False} if off else {"enable_thinking": True, "thinking_budget": BUDGET[level]}
    if how in ("zhipu", "ark"):
        return {"thinking": {"type": "disabled" if off else "enabled"}}
    if how == "openrouter":
        return {"reasoning": {"effort": "none"}} if off else {"reasoning": {"effort": {"max": "high"}.get(level, level)}}
    # OpenAI and the many servers that follow it
    return {"reasoning_effort": "minimal" if off else {"max": "high"}.get(level, level)}


def rejected(status: int | None, body: str, fields: dict) -> bool:
    """A 400/422 that names one of the thinking fields (or says an argument is unknown): ask again without them."""
    if status not in (400, 422) or not fields:
        return False
    text = body.lower()
    names = set(fields) | {k2 for v in fields.values() if isinstance(v, dict) for k2 in v}
    return any(n.lower() in text for n in names) or any(w in text for w in ("unrecognized", "unknown param", "not support",
                                                                            "extra inputs", "unexpected"))


def anthropic_thinking(level: str | None, max_output: int) -> tuple[dict | None, int]:
    """(the `thinking` field or None, max_tokens). The budget must stay below max_tokens."""
    if not level or level == "off":
        return None, max_output
    budget = BUDGET[level]
    return {"type": "enabled", "budget_tokens": budget}, budget + max_output
