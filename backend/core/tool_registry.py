"""Tool 注册与调用机制。

- Tool 元数据来自 tools.json（描述、启用状态、数据源），每次读取保证即时生效。
- Tool 执行体为本地代码实现（不依赖大模型）。
"""
from typing import Any, Callable, Dict, List

from backend.services import json_store
from backend.tools import (
    coze_workflow,
    contact_query,
    employee_query,
    policy_query,
    task_query,
    task_status_calc,
    training_query,
)

# tool name -> 异步执行函数 (params, ctx) -> dict
TOOL_FUNCS: Dict[str, Callable] = {
    "query_employee_info": employee_query.run,
    "query_onboarding_tasks": task_query.run,
    "query_contacts": contact_query.run,
    "query_policies": policy_query.run,
    "query_trainings": training_query.run,
    "calc_task_status": task_status_calc.run,
    "run_coze_workflow": coze_workflow.run,
}


def load_tools() -> List[Dict[str, Any]]:
    return json_store.load("tools", {}).get("tools", [])


def list_enabled() -> List[Dict[str, Any]]:
    return [t for t in load_tools() if t.get("enabled", False)]


def get(tool_name: str) -> Dict[str, Any]:
    for t in load_tools():
        if t.get("name") == tool_name:
            return t
    return {}


def is_enabled(tool_name: str) -> bool:
    t = get(tool_name)
    return bool(t) and bool(t.get("enabled", False))


def exists(tool_name: str) -> bool:
    return tool_name in TOOL_FUNCS


async def execute(tool_name: str, params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    fn = TOOL_FUNCS.get(tool_name)
    if fn is None:
        raise ValueError(f"系统中不存在名为 {tool_name} 的 Tool")
    return await fn(params or {}, ctx)
