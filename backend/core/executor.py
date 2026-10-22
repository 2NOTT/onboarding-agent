"""Executor：按 Planner 计划逐步执行 Skill / Tool，并完成风控收尾。

关键规则：
- 只执行当前已启用且存在的 Skill / Tool（禁用能力即使被传入也拒绝执行）。
- Tool 查询结果作为后续 Skill 的输入数据。
- 最终回复必须经过「合规与风险审核 Skill」。
"""
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.config import settings
from backend.core import logger, mock_skills, planner, risk_control
from backend.core import skill_registry, tool_registry
from backend.core.llm import LLMError
from backend.tools.util import find_employee

EMPLOYEE_KEYS = ["employee_id", "name", "department", "position", "hire_date",
                 "onboarding_stage", "stage_label", "manager", "hr_contact", "email"]


def _emp_summary(employee: Dict[str, Any]) -> Dict[str, Any]:
    return {k: employee.get(k) for k in EMPLOYEE_KEYS}


def _extract_reply(output: Any) -> str:
    if not isinstance(output, dict):
        return str(output or "")
    return str(
        output.get("reply")
        or output.get("final_reply")
        or output.get("text")
        or output.get("_raw")
        or ""
    )


class _StepFailed(Exception):
    pass


async def _run_tool(tool_name: str, params: Dict[str, Any], employee_id: str, employee: Dict[str, Any], question: str = "") -> Dict[str, Any]:
    ctx = {"current_employee_id": employee_id, "employee": employee, "question": question}
    return await tool_registry.execute(tool_name, params, ctx)


async def _run_skill(skill_cfg: Dict[str, Any], skill_input: Dict[str, Any]) -> Tuple[Dict[str, Any], str, float, str]:
    """执行单个 Skill。返回 (output, engine, elapsed_ms, error)。

    engine: llm / mock / mock_fallback
    Mock 模式或 LLM 调用失败时，回退到本地 Mock 实现，保证可演示。
    """
    skill_type = skill_cfg.get("type")
    mp = skill_cfg.get("model_params", {}) or {}
    t0 = time.perf_counter()
    user_payload = json.dumps(skill_input, ensure_ascii=False, indent=2)

    if settings.mock_mode:
        output = await mock_skills.mock_output(skill_type, skill_input, {"employee": skill_input.get("employee", {})})
        return output, "mock", round((time.perf_counter() - t0) * 1000, 1), ""

    try:
        output = await skill_registry_chat(skill_cfg, user_payload, mp)
        if isinstance(output, dict) and set(output.keys()) == {"_raw"}:
            raise LLMError("大模型输出无法解析为 JSON")
        return output, "llm", round((time.perf_counter() - t0) * 1000, 1), ""
    except Exception as e:
        output = await mock_skills.mock_output(skill_type, skill_input, {"employee": skill_input.get("employee", {})})
        return output, "mock_fallback", round((time.perf_counter() - t0) * 1000, 1), f"LLM 调用失败已回退 Mock: {e}"


async def skill_registry_chat(skill_cfg: Dict[str, Any], user_payload: str, mp: Dict[str, Any]) -> Any:
    from backend.core import llm
    return await llm.chat_json(
        skill_cfg.get("prompt", ""),
        user_payload,
        temperature=float(mp.get("temperature", 0.3)),
        max_tokens=int(mp.get("max_tokens", 1024)),
        model=(mp.get("model") or None),
    )


async def execute(employee_id: str, question: str) -> Dict[str, Any]:
    start = time.perf_counter()
    errors: List[str] = []

    employee = find_employee(employee_id)
    if not employee:
        raise ValueError(f"未找到员工 {employee_id}，请先选择有效的模拟员工身份")
    question = (question or "").strip()
    if not question:
        raise ValueError("问题不能为空")

    # ---- 快照当前可用能力（仅启用项） ----
    enabled_skills = skill_registry.list_enabled()
    enabled_tools = tool_registry.list_enabled()

    # ---- 1. Planner 生成计划 ----
    plan, planner_engine, warnings = await planner.make_plan(question, employee)
    steps = plan["steps"]

    # ---- 2. Executor 按依赖顺序执行 ----
    trace_steps: List[Dict[str, Any]] = []
    results: Dict[str, Dict[str, Any]] = {}   # step_id -> {"status","output"}
    data_by_target: Dict[str, Any] = {}       # target -> 最近一次输出
    draft_reply = ""
    compliance_output: Any = None
    compliance_input: Dict[str, Any] = {}

    async def run_skill_fn(skill_type: str, skill_input: Dict[str, Any]):
        skill_cfg = skill_registry.get_by_type(skill_type)
        if not skill_cfg:
            raise ValueError(f"系统中不存在类型为 {skill_type} 的 Skill")
        if not skill_registry.is_enabled(skill_cfg["skill_id"]):
            raise ValueError(f"Skill「{skill_cfg.get('name')}」已被禁用，拒绝执行")
        out, engine, elapsed, _err = await _run_skill(skill_cfg, skill_input)
        return out, engine, elapsed

    for step in steps:
        t0 = time.perf_counter()
        entry: Dict[str, Any] = {
            "step_id": step["step_id"],
            "name": step["name"],
            "type": step["type"],
            "target": step["target"],
            "purpose": step["purpose"],
            "depends_on": step["depends_on"],
            "input": None,
            "output": None,
            "status": "pending",
            "error": "",
            "engine": "",
            "elapsed_ms": 0,
        }

        # 依赖检查
        failed_deps = [
            d for d in step["depends_on"]
            if results.get(d, {}).get("status") != "success"
        ]
        if failed_deps:
            entry.update(status="skipped", error=f"依赖步骤执行失败或被跳过：{', '.join(failed_deps)}")
            trace_steps.append(entry)
            results[step["step_id"]] = {"status": "skipped", "output": None}
            continue

        try:
            if step["type"] == "tool":
                tool_cfg = tool_registry.get(step["target"])
                entry["display_name"] = tool_cfg.get("display_name", step["target"])
                # 执行时再次校验启用状态：禁用 Tool 即使被传入也拒绝执行
                if not tool_registry.is_enabled(step["target"]):
                    entry.update(status="skipped", error="该 Tool 已被禁用，Executor 拒绝执行。")
                    results[step["step_id"]] = {"status": "skipped", "output": None}
                    trace_steps.append(entry)
                    errors.append(entry["error"])
                    continue

                params = dict(step.get("input") or {})
                if step["target"] in ("query_employee_info", "calc_task_status"):
                    params.setdefault("employee_id", employee_id)
                entry["input"] = params
                output = await _run_tool(step["target"], params, employee_id, employee, question)
                entry.update(output=output, status="success", engine="code",
                             elapsed_ms=round((time.perf_counter() - t0) * 1000, 1))
                data_by_target[step["target"]] = output
                results[step["step_id"]] = {"status": "success", "output": output}

            else:  # skill
                skill_cfg = skill_registry.get_by_type(step["target"])
                entry["display_name"] = (skill_cfg or {}).get("name", step["target"])
                # 执行时再次校验启用状态：禁用 Skill 即使被手动传入也必须拒绝执行
                if not skill_cfg:
                    entry.update(status="skipped", error="系统中不存在该 Skill，拒绝执行。")
                elif not skill_registry.is_enabled(skill_cfg["skill_id"]):
                    entry.update(status="skipped", error=f"Skill「{skill_cfg.get('name')}」已被禁用，Executor 拒绝执行。")
                    errors.append(entry["error"])
                else:
                    skill_input: Dict[str, Any] = {
                        "question": question,
                        "employee": _emp_summary(employee),
                        "params": dict(step.get("input") or {}),
                    }
                    for dep in step["depends_on"]:
                        dep_step = next((s for s in steps if s["step_id"] == dep), None)
                        if dep_step is not None:
                            skill_input[dep_step["target"]] = results.get(dep, {}).get("output")

                    if step["target"] == "compliance_check":
                        skill_input["draft_reply"] = draft_reply
                        compliance_input = skill_input

                    output, engine, elapsed, fallback_err = await _run_skill(skill_cfg, skill_input)
                    if fallback_err:
                        errors.append(f"步骤 {step['step_id']}（{step['target']}）：{fallback_err}")
                    entry.update(output=output, status="success", engine=engine,
                                 elapsed_ms=round((time.perf_counter() - t0) * 1000, 1))
                    data_by_target[step["target"]] = output
                    results[step["step_id"]] = {"status": "success", "output": output}

                    if step["target"] == "communication":
                        draft_reply = _extract_reply(output)
                    elif step["target"] == "compliance_check":
                        compliance_output = output

        except Exception as e:
            entry.update(status="failed", error=str(e),
                         elapsed_ms=round((time.perf_counter() - t0) * 1000, 1))
            results[step["step_id"]] = {"status": "failed", "output": None}
            errors.append(f"步骤 {step['step_id']}（{step['target']}）执行失败：{e}")

        trace_steps.append(entry)

    # ---- 3. 风控收尾：最终回复必须通过合规审核 ----
    final_reply, risk_result, trace_steps = await risk_control.finalize(
        question=question,
        employee=employee,
        draft_reply=draft_reply,
        compliance_output=compliance_output,
        compliance_input=compliance_input,
        trace_steps=trace_steps,
        run_skill_fn=run_skill_fn,
    )
    if not (final_reply or "").strip():
        final_reply = "当前系统未查询到相关信息，暂时无法回答该问题。请你联系 HR 对接人进一步确认。"

    duration_ms = round((time.perf_counter() - start) * 1000, 1)

    result = {
        "log_id": logger.new_log_id(),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "employee_id": employee_id,
        "employee": employee,
        "question": question,
        "mock_mode": settings.mock_mode,
        "available_skills": [
            {"skill_id": s["skill_id"], "type": s["type"], "name": s["name"], "description": s["description"]}
            for s in enabled_skills
        ],
        "available_tools": [
            {"tool_id": t["tool_id"], "name": t["name"], "display_name": t.get("display_name"), "description": t["description"]}
            for t in enabled_tools
        ],
        "plan": plan,
        "planner_engine": planner_engine,
        "steps": trace_steps,
        "final_reply": final_reply,
        "risk_result": risk_result,
        "warnings": warnings,
        "errors": errors,
        "duration_ms": duration_ms,
    }

    # ---- 4. 持久化执行日志 ----
    logger.save_execution(result)
    return result
