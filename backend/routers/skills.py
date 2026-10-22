"""Skill 管理接口：列表 / 详情 / 编辑 / 单独测试。"""
import json
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.core import mock_skills, skill_registry
from backend.core.executor import EMPLOYEE_KEYS
from backend.core.llm import chat_json
from backend.tools.util import find_employee

router = APIRouter()


class SkillUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    model_params: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class SkillTestRequest(BaseModel):
    input: Dict[str, Any]


def _with_runtime(skill: Dict[str, Any]) -> Dict[str, Any]:
    s = dict(skill)
    s["effective_model"] = (s.get("model_params", {}) or {}).get("model") or settings.LLM_MODEL
    return s


@router.get("/skills")
def list_skills():
    return [_with_runtime(s) for s in skill_registry.load_skills()]


@router.get("/skills/{skill_id}")
def get_skill(skill_id: str):
    skill = skill_registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"未找到 Skill {skill_id}")
    return _with_runtime(skill)


@router.put("/skills/{skill_id}")
def update_skill(skill_id: str, req: SkillUpdateRequest):
    skill = skill_registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"未找到 Skill {skill_id}")
    try:
        updated = skill_registry.update(skill_id, req.model_dump(exclude_none=True, exclude_unset=True))
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 每次保存即时生效：前台 Planner / Executor 每次执行都会从 skills.json 重新读取
    return _with_runtime(updated)


@router.post("/skills/{skill_id}/test")
async def test_skill(skill_id: str, req: SkillTestRequest):
    """单独测试某一个 Skill。已禁用的 Skill 拒绝测试（与 Executor 行为一致）。"""
    skill = skill_registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"未找到 Skill {skill_id}")
    if not skill_registry.is_enabled(skill_id):
        raise HTTPException(status_code=400, detail=f"Skill「{skill.get('name')}」已被禁用，拒绝测试。请先启用该 Skill。")

    skill_input = req.input or {}
    # 测试输入未带员工信息时，默认注入第一位员工作为演示上下文
    if "employee" not in skill_input:
        emp = find_employee("E001")
        if emp:
            skill_input["employee"] = {k: emp.get(k) for k in EMPLOYEE_KEYS}

    mp = skill.get("model_params", {}) or {}
    t0 = time.perf_counter()
    success = True
    output: Any = None
    error = ""
    engine = "mock"

    if settings.mock_mode:
        output = await mock_skills.mock_output(skill.get("type"), skill_input, {"employee": skill_input.get("employee", {})})
    else:
        try:
            from backend.core.executor import skill_registry_chat
            output = await skill_registry_chat(
                skill, json.dumps(skill_input, ensure_ascii=False, indent=2), mp
            )
            engine = "llm"
        except Exception as e:  # noqa: BLE001
            output = await mock_skills.mock_output(skill.get("type"), skill_input, {"employee": skill_input.get("employee", {})})
            engine = "mock_fallback"
            error = f"LLM 调用失败已回退 Mock: {e}"

    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    if isinstance(output, dict) and output.get("error"):
        success = False
        error = output["error"]

    test_record = {
        "tested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input": req.input,
        "output": output,
        "success": success,
        "engine": engine,
        "error": error,
        "elapsed_ms": elapsed,
    }
    skill_registry.save_last_test(skill_id, test_record)
    return test_record
