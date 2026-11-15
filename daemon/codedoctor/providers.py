"""Provider presets and the connection test used by the desktop's 模型与 API page.

A preset only pre-fills an endpoint (kind, base URL, usual key variable). No model names are written here
(2026-11-10, the user's rule: such a list goes stale the day a model comes out): the models are what the service
itself lists (probe, 获取模型列表), and the user picks one of them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from codedoctor.models import text_tools
from codedoctor.models.anthropic import AnthropicClient
from codedoctor.models.base import ChatMessage, ModelError, ToolSpec
from codedoctor.models.openai_compat import OpenAICompatClient


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    kind: str  # openai_compatible | anthropic
    base_url: str
    key_env: str | None  # None: local server that needs no key
    local: bool = False
    note: str = ""


PRESETS: tuple[Preset, ...] = (
    Preset("deepseek", "DeepSeek", "openai_compatible", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    Preset("openai", "OpenAI", "openai_compatible", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    Preset("anthropic", "Anthropic Claude", "anthropic", "https://api.anthropic.com", "ANTHROPIC_API_KEY"),
    Preset("gemini", "Google Gemini", "openai_compatible", "https://generativelanguage.googleapis.com/v1beta/openai",
           "GEMINI_API_KEY", note="Gemini 的 OpenAI 兼容接口"),
    Preset("dashscope", "通义千问 (阿里云百炼)", "openai_compatible", "https://dashscope.aliyuncs.com/compatible-mode/v1",
           "DASHSCOPE_API_KEY"),
    Preset("moonshot", "Kimi (月之暗面)", "openai_compatible", "https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    Preset("zhipu", "智谱 GLM", "openai_compatible", "https://open.bigmodel.cn/api/paas/v4", "ZHIPUAI_API_KEY"),
    Preset("ark", "豆包 (火山方舟)", "openai_compatible", "https://ark.cn-beijing.volces.com/api/v3", "ARK_API_KEY",
           note="模型名填推理接入点 ID 或模型 ID"),
    Preset("qianfan", "文心 (百度千帆)", "openai_compatible", "https://qianfan.baidubce.com/v2", "QIANFAN_API_KEY"),
    Preset("hunyuan", "腾讯混元", "openai_compatible", "https://api.hunyuan.cloud.tencent.com/v1", "HUNYUAN_API_KEY"),
    Preset("siliconflow", "硅基流动 SiliconFlow", "openai_compatible", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    Preset("openrouter", "OpenRouter", "openai_compatible", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    Preset("groq", "Groq", "openai_compatible", "https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    Preset("xai", "xAI Grok", "openai_compatible", "https://api.x.ai/v1", "XAI_API_KEY"),
    Preset("mistral", "Mistral", "openai_compatible", "https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    Preset("minimax", "MiniMax", "openai_compatible", "https://api.minimaxi.com/v1", "MINIMAX_API_KEY",
           note="海外账号用 https://api.minimax.io/v1"),
    Preset("stepfun", "阶跃星辰 StepFun", "openai_compatible", "https://api.stepfun.com/v1", "STEPFUN_API_KEY"),
    Preset("baichuan", "百川 Baichuan", "openai_compatible", "https://api.baichuan-ai.com/v1", "BAICHUAN_API_KEY"),
    Preset("lingyi", "零一万物 Yi", "openai_compatible", "https://api.lingyiwanwu.com/v1", "YI_API_KEY"),
    Preset("together", "Together AI", "openai_compatible", "https://api.together.xyz/v1", "TOGETHER_API_KEY"),
    Preset("fireworks", "Fireworks AI", "openai_compatible", "https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY"),
    Preset("nvidia", "NVIDIA NIM", "openai_compatible", "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
    Preset("cerebras", "Cerebras", "openai_compatible", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"),
    Preset("perplexity", "Perplexity", "openai_compatible", "https://api.perplexity.ai", "PERPLEXITY_API_KEY",
           note="联网搜索模型；不一定支持调用工具"),
    Preset("ollama", "Ollama (本机)", "openai_compatible", "http://127.0.0.1:11434/v1", None, local=True),
    Preset("lmstudio", "LM Studio (本机)", "openai_compatible", "http://127.0.0.1:1234/v1", None, local=True),
    Preset("vllm", "vLLM", "openai_compatible", "http://127.0.0.1:8000/v1", None, local=True),
    Preset("llamacpp", "llama.cpp server", "openai_compatible", "http://127.0.0.1:8080/v1", None, local=True),
    Preset("custom", "自定义 (OpenAI 兼容)", "openai_compatible", "", None,
           note="任何兼容 /v1/chat/completions 的服务：填地址，需要密钥就填密钥"),
    Preset("custom-anthropic", "自定义 (Anthropic 兼容)", "anthropic", "", None,
           note="兼容 /v1/messages 的服务"),
)
BY_ID = {p.id: p for p in PRESETS}


def preset(pid: str) -> Preset:
    return BY_ID.get(pid) or BY_ID["custom"]


# The names above are written in 中文 where the service is Chinese; the window shows these for any other language (2026-11-13: a saved
# endpoint called "自定义 (OpenAI 兼容)" was still shown so in an English window).
ENGLISH_NAMES = {
    "dashscope": "Qwen (Alibaba Cloud Model Studio)", "moonshot": "Kimi (Moonshot AI)", "zhipu": "Zhipu GLM", "ark": "Doubao (Volcano Engine)",
    "qianfan": "ERNIE (Baidu Qianfan)", "hunyuan": "Tencent Hunyuan", "siliconflow": "SiliconFlow", "stepfun": "StepFun", "baichuan": "Baichuan",
    "lingyi": "Yi (01.AI)", "ollama": "Ollama (this computer)", "lmstudio": "LM Studio (this computer)",
    "custom": "Custom (OpenAI-compatible)", "custom-anthropic": "Custom (Anthropic-compatible)",
}


def preset_name(p: Preset, language: str = "zh") -> str:
    """The name to show for a preset: as written for 中文 (zh, zh-TW...), the English one for every other language."""
    return p.name if str(language).lower().startswith("zh") else ENGLISH_NAMES.get(p.id, p.name)


def shown_name(name: str, language: str = "zh") -> str:
    """The same for a name that was saved with an endpoint: a name that is a preset's own is shown in the window's language; one the
    user typed is left as it is."""
    if str(language).lower().startswith("zh"):
        return name
    for p in PRESETS:
        if p.name == name:
            return ENGLISH_NAMES.get(p.id, name)
    return name


@dataclass
class ProbeResult:
    reachable: bool = False
    models: list[str] = field(default_factory=list)
    models_error: str | None = None
    tool_calls: str | None = None  # native | text | none | None (not tested)
    chat_error: str | None = None
    latency_ms: int | None = None

    @property
    def ok(self) -> bool:
        return self.reachable and self.chat_error is None and self.tool_calls in ("native", "text")


_PROBE_TOOL = ToolSpec(
    name="read_file",
    description="Read a file of the project.",
    parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
)
_PROBE_PROMPT = "Connection test. Call the read_file tool with path \"README.md\". Do not reply with text."


async def probe(kind: str, base_url: str, api_key: str | None, model: str | None, *,
                timeout_s: float = 60.0, transport: httpx.AsyncBaseTransport | None = None) -> ProbeResult:
    """List models, then (if a model is given) send one fixed test prompt with one tool.
    No project data is sent."""
    res = ProbeResult()
    base_url = base_url.rstrip("/")
    if kind == "anthropic":
        client = AnthropicClient(base_url, api_key, timeout_s, transport)
    else:
        client = OpenAICompatClient(base_url, api_key, timeout_s, transport, text_tool_calls=False)
    try:
        try:
            res.models = sorted(m for m in await client.list_models() if m)
            res.reachable = True
        except ModelError as e:
            res.models_error = str(e)
            res.reachable = e.status is not None  # the server answered, it just has no /models (or refused it)
        if not model:
            return res
        t0 = time.perf_counter()
        try:
            out = await client.chat(model, [ChatMessage("user", _PROBE_PROMPT)], [_PROBE_TOOL], max_output_tokens=512)
        except ModelError as e:
            res.chat_error = str(e)
            return res
        res.reachable = True
        res.latency_ms = int((time.perf_counter() - t0) * 1000)
        if any(c.name == "read_file" for c in out.tool_calls):
            res.tool_calls = "native"
        elif text_tools.extract(out.text, ["read_file"])[0]:
            res.tool_calls = "text"
        else:
            res.tool_calls = "none"
        return res
    finally:
        await client.aclose()


@dataclass
class EmbeddingProbe:
    dimensions: int | None = None
    error: str | None = None
    latency_ms: int | None = None


_EMBED_PROBE_TEXTS = ["Code Doctor embedding test.", "Code Doctor 嵌入测试。"]


async def probe_embedding(kind: str, base_url: str, api_key: str | None, model: str, *,
                          timeout_s: float = 60.0, transport: httpx.AsyncBaseTransport | None = None) -> EmbeddingProbe:
    """Embed two fixed sentences with the chosen model (semantic memory, ADR 0007). No project data is sent."""
    if kind != "openai_compatible":
        return EmbeddingProbe(error=f"{kind} 接口没有嵌入（embeddings）功能，请选 OpenAI 兼容的服务")
    client = OpenAICompatClient(base_url.rstrip("/"), api_key, timeout_s, transport, text_tool_calls=False)
    t0 = time.perf_counter()
    try:
        vectors = await client.embed(model, _EMBED_PROBE_TEXTS)
    except ModelError as e:
        return EmbeddingProbe(error=str(e))
    finally:
        await client.aclose()
    dims = {len(v) for v in vectors}
    if len(dims) != 1 or 0 in dims:
        return EmbeddingProbe(error=f"返回的向量维度不一致：{sorted(dims)}")
    return EmbeddingProbe(dimensions=dims.pop(), latency_ms=int((time.perf_counter() - t0) * 1000))
