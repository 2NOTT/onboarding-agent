"""大模型 API 调用模块（OpenAI 兼容接口）。

- 未配置 API Key 或 FORCE_MOCK=true 时处于 Mock 模式，直接抛出 LLMError，
  由上层（Skill 执行器 / Planner）回退到本地 Mock 实现，保证项目可演示。
"""
import json
import re
from typing import Any, Optional

import httpx

from backend.config import settings


class LLMError(Exception):
    pass


def extract_json(text: str) -> Optional[Any]:
    """从大模型返回文本中尽力提取 JSON（支持代码围栏与混杂文本）。"""
    if not text:
        return None
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    for pattern in (r"\{.*\}", r"\[.*\]"):
        m = re.search(pattern, text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except (json.JSONDecodeError, ValueError):
                continue
    return None


async def chat(
    system: str,
    user: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    model: Optional[str] = None,
) -> str:
    """调用大模型 chat/completions 接口，返回文本内容。"""
    if settings.mock_mode:
        raise LLMError("当前为 Mock 模式（未配置大模型 API 或 FORCE_MOCK=true）")

    payload = {
        "model": model or settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.LLM_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
    except httpx.HTTPError as e:
        raise LLMError(f"大模型 API 网络错误: {e}") from e

    if resp.status_code != 200:
        raise LLMError(f"大模型 API 返回 {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError(f"大模型 API 响应格式异常: {e}") from e

    if not content:
        raise LLMError("大模型 API 返回空内容")
    return content


async def chat_json(
    system: str,
    user: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    model: Optional[str] = None,
) -> Any:
    """调用大模型并解析为 JSON；解析失败时返回 {"_raw": 原文}。"""
    text = await chat(system, user, temperature, max_tokens, model)
    parsed = extract_json(text)
    if parsed is None:
        return {"_raw": text}
    return parsed
