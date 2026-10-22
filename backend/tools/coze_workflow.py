"""Coze 工作流 Tool：将外部 Coze Workflow 封装为平台可调用的 Tool。

- 工作流输入：user_id / CONVERSATION_NAME / USER_INPUT
- 工作流预期输出：answer / status / risk_level
- 工作流含「问答节点」时首次运行会 interrupt（挂起追问），此时返回追问内容
  与续跑凭据（execute_id / event_id）；后续可将 resume_data 传入本 Tool 续跑。
- 未配置 COZE_API_TOKEN 时返回本地 Mock 输出，保证无 Key 也可完整演示。
- 接口：POST {base}/v1/workflow/run，响应 data 字段为结束节点输出变量的 JSON 字符串。
"""
import json
import time
from typing import Any, Dict, Optional

import httpx

from backend.config import settings

DEFAULT_WORKFLOW_ID = "7694957124648747008"


def _parse_data_field(data: Any) -> Optional[Dict[str, Any]]:
    """解析响应的 data 字段（JSON 字符串或对象）。"""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return None
    return data if isinstance(data, dict) else None


def _interrupt_question(interrupt: Dict[str, Any]) -> str:
    """从 interrupt_data 中提取追问文本。"""
    try:
        payload = json.loads(interrupt.get("data") or "{}")
        for m in payload.get("messages", []):
            if m.get("content"):
                return str(m["content"])
    except Exception:
        pass
    required = interrupt.get("required_parameters") or {}
    for name, meta in required.items():
        if isinstance(meta, dict) and meta.get("description"):
            return f"工作流需要补充参数 {name}：{meta['description']}"
    return "工作流在问答节点挂起，需要补充信息后才能继续执行。"


async def run(params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """执行 Coze 工作流。

    params 支持键：
    - user_input(USER_INPUT) / user_id / conversation_name(CONVERSATION_NAME) / workflow_id
    - resume_data（dict 或 JSON 字符串，用于问答节点续跑）、execute_id / event_id / interrupt_type
    缺省值从 ctx 取：user_id ← 当前员工编号，USER_INPUT ← 用户原始问题。
    """
    p = params or {}
    user_input = str(
        p.get("user_input") or p.get("USER_INPUT") or ctx.get("question") or ""
    ).strip()
    user_id = str(p.get("user_id") or ctx.get("current_employee_id") or "").strip()
    workflow_id = str(p.get("workflow_id") or settings.COZE_WORKFLOW_ID or DEFAULT_WORKFLOW_ID)

    payload: Dict[str, Any] = {"workflow_id": workflow_id, "is_async": False}

    # 续跑模式：需要 execute_id + event_id + resume_data
    resume_data = p.get("resume_data")
    if resume_data is not None or p.get("execute_id"):
        if not (resume_data is not None and p.get("execute_id") and p.get("event_id")):
            return {"error": "续跑需要同时提供 resume_data、execute_id 与 event_id。"}
        payload["resume_data"] = (
            resume_data if isinstance(resume_data, str) else json.dumps(resume_data, ensure_ascii=False)
        )
        payload["execute_id"] = str(p["execute_id"])
        payload["event_id"] = str(p["event_id"])
        payload["interrupt_type"] = int(p.get("interrupt_type") or 2)
    else:
        conversation_name = str(
            p.get("conversation_name") or p.get("CONVERSATION_NAME") or f"onboarding-{user_id}"
        ).strip()
        if not user_input:
            return {"error": "缺少 USER_INPUT 输入，无法执行 Coze 工作流。"}
        if not user_id:
            return {"error": "缺少 user_id，无法执行 Coze 工作流。"}
        payload["parameters"] = {
            "user_id": user_id,
            "CONVERSATION_NAME": conversation_name,
            "USER_INPUT": user_input,
        }

    if not settings.COZE_API_TOKEN:
        return _mock_output(user_id, user_input, workflow_id, bool(p.get("execute_id")))

    headers = {
        "Authorization": f"Bearer {settings.COZE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.COZE_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.COZE_API_BASE}/v1/workflow/run", json=payload, headers=headers
            )
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:  # noqa: BLE001
        return {"error": f"Coze 工作流调用失败：{e}"}

    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    if body.get("code") not in (0, "0", None):
        return {
            "error": f"Coze 工作流返回错误 code={body.get('code')}：{body.get('msg')}",
            "workflow_id": workflow_id,
        }

    base = {
        "workflow_id": workflow_id,
        "execute_id": str(body.get("execute_id") or ""),
        "elapsed_ms": elapsed,
    }

    # 问答节点挂起：返回追问内容与续跑凭据
    interrupt = body.get("interrupt_data")
    if isinstance(interrupt, dict) and interrupt.get("event_id"):
        return {
            **base,
            "answer": _interrupt_question(interrupt),
            "status": "interrupt",
            "risk_level": "low",
            "interrupt": {
                "event_id": str(interrupt.get("event_id")),
                "interrupt_type": interrupt.get("type"),
                "required_parameters": interrupt.get("required_parameters") or {},
                "resume_hint": "将用户补充的内容作为 resume_data（如 {\"QUESTION_DATA\": \"...\"}）连同 execute_id / event_id 传入本 Tool 续跑。",
            },
        }

    # 正常结束：解析结束节点输出变量
    data = _parse_data_field(body.get("data"))
    if data is not None and (data.get("answer") or data.get("output")):
        return {
            **base,
            "answer": str(data.get("answer") if data.get("answer") is not None else data.get("output")),
            "status": str(data.get("status") or "success"),
            "risk_level": str(data.get("risk_level") or "unknown"),
        }

    # 执行成功但未取到输出：多为结束节点未配置输出变量
    return {
        **base,
        "answer": str(body.get("data") or ""),
        "status": "empty_output",
        "risk_level": "unknown",
        "hint": "工作流执行成功但未返回输出变量：请在 Coze 工作流的「结束节点」中将 answer / status / risk_level 配置为输出变量后重试。",
    }


def _mock_output(user_id: str, user_input: str, workflow_id: str, resume: bool) -> Dict[str, Any]:
    """未配置 COZE_API_TOKEN 时的本地确定性输出，保证演示链路可用。"""
    answer = (
        f"已收到你的问题「{user_input}」。当前平台未配置 COZE_API_TOKEN，"
        "Coze 工作流以本地 Mock 模式返回参考建议："
        "请优先完成入职材料提交、企业账号激活与办公设备领取等基础事项；"
        "涉及制度、社保公积金等具体办理口径，请以 HR 对接人确认为准。"
    )
    return {
        "answer": answer,
        "status": "success",
        "risk_level": "low",
        "workflow_id": workflow_id,
        "user_id": user_id,
        "mock": True,
    }
