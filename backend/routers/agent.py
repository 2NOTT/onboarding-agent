"""Agent 执行相关接口。"""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core import executor, tool_registry
from backend.core.skill_registry import list_enabled as list_enabled_skills
from backend.tools.util import find_employee, load_employees

router = APIRouter()


class AgentExecuteRequest(BaseModel):
    employee_id: str = Field(..., description="当前模拟员工编号")
    question: str = Field(..., min_length=1, description="用户输入的入职问题")


@router.get("/health")
def health():
    from backend.config import settings
    return {
        "status": "ok",
        "mock_mode": settings.mock_mode,
        "llm_configured": bool(settings.LLM_API_KEY),
        "force_mock": settings.FORCE_MOCK,
        "model": settings.LLM_MODEL,
    }


@router.get("/employees")
def list_employees():
    """模拟员工身份列表（供前端身份选择器使用）。"""
    return [
        {
            "employee_id": e["employee_id"],
            "name": e["name"],
            "department": e["department"],
            "position": e["position"],
            "onboarding_stage": e["onboarding_stage"],
            "stage_label": e.get("stage_label"),
            "hire_date": e.get("hire_date"),
        }
        for e in load_employees()
    ]


@router.get("/employees/{employee_id}")
def get_employee(employee_id: str):
    emp = find_employee(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail=f"未找到员工 {employee_id}")
    return emp


@router.post("/agent/execute")
async def agent_execute(req: AgentExecuteRequest):
    """执行一次完整的 Plan + Skill + Tool 流程，返回全部可视化执行轨迹。"""
    try:
        result = await executor.execute(req.employee_id, req.question)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"执行失败：{e}")


@router.get("/capabilities")
def capabilities():
    """当前可用（已启用）的 Skill 与 Tool 列表快照。"""
    return {
        "skills": [
            {"skill_id": s["skill_id"], "type": s["type"], "name": s["name"], "description": s["description"]}
            for s in list_enabled_skills()
        ],
        "tools": [
            {"tool_id": t["tool_id"], "name": t["name"], "display_name": t.get("display_name"), "description": t["description"]}
            for t in tool_registry.list_enabled()
        ],
    }
