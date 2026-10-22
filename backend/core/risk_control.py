"""风控审核收尾模块。

规则：
1. 最终回复必须经过「合规与风险审核 Skill」。
2. 审核不通过时，不允许直接返回原始回复。
3. 审核发现问题后，自动根据审核建议重新生成回复（最多 2 轮）。
4. 仍然不通过时，返回安全兜底话术。
"""
from typing import Any, Awaitable, Callable, Dict, List, Tuple

SAFE_FALLBACK = (
    "抱歉，该回复未能通过合规与风险审核，暂时无法提供完整答复。"
    "请你联系 HR 对接人获取准确信息，或稍后再次提问。"
)


def _emp_summary(employee: Dict[str, Any]) -> Dict[str, Any]:
    return {k: employee.get(k) for k in ["employee_id", "name", "department", "position", "onboarding_stage", "manager", "hr_contact"]}


def _extract_reply(output: Dict[str, Any]) -> str:
    if not isinstance(output, dict):
        return str(output or "")
    return str(
        output.get("reply")
        or output.get("final_reply")
        or output.get("text")
        or output.get("_raw")
        or ""
    )


async def finalize(
    question: str,
    employee: Dict[str, Any],
    draft_reply: str,
    compliance_output: Any,
    compliance_input: Dict[str, Any],
    trace_steps: List[Dict[str, Any]],
    run_skill_fn: Callable[[str, Dict[str, Any]], Awaitable[Tuple[Dict[str, Any], str, float]]],
) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]]]:
    """返回 (final_reply, risk_result, trace_steps)。"""

    if not isinstance(compliance_output, dict) or "passed" not in compliance_output:
        risk_result = {
            "risk_level": "unknown",
            "passed": False,
            "issues": ["合规与风险审核步骤未执行或输出无效，已拦截原始回复。"],
            "suggestions": ["请检查「合规与风险审核」Skill 的配置与启用状态。"],
        }
        return SAFE_FALLBACK, risk_result, trace_steps

    passed = bool(compliance_output.get("passed"))
    risk_result = {
        "risk_level": compliance_output.get("risk_level", "unknown"),
        "passed": passed,
        "issues": compliance_output.get("issues", []) or [],
        "suggestions": compliance_output.get("suggestions", []) or [],
    }

    if passed:
        final = str(compliance_output.get("final_reply") or draft_reply or "").strip()
        return (final or SAFE_FALLBACK), risk_result, trace_steps

    # ---- 审核不通过：按审核建议自动重新生成（最多 2 轮） ----
    issues = list(risk_result["issues"])
    suggestions = list(risk_result["suggestions"])
    current_draft = draft_reply

    for attempt in (1, 2):
        revision_input = {
            "question": question,
            "employee": _emp_summary(employee),
            "previous_reply": current_draft,
            "revision_instructions": issues + suggestions,
        }
        import time
        t0 = time.perf_counter()
        out, engine, _elapsed = await run_skill_fn("communication", revision_input)
        revised = _extract_reply(out)
        trace_steps.append({
            "step_id": f"R{attempt}-1",
            "name": "沟通话术重生成（风控修订）",
            "type": "skill",
            "target": "communication",
            "display_name": "入职沟通话术生成",
            "purpose": f"（第 {attempt} 轮）根据合规审核建议自动修订回复。",
            "depends_on": [],
            "input": revision_input,
            "output": out,
            "status": "success" if revised else "failed",
            "error": "" if revised else "修订输出为空",
            "engine": engine,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        })

        if not revised:
            break

        recheck_input = dict(compliance_input or {})
        recheck_input["draft_reply"] = revised
        t1 = time.perf_counter()
        out2, engine2, _e2 = await run_skill_fn("compliance_check", recheck_input)
        trace_steps.append({
            "step_id": f"R{attempt}-2",
            "name": "合规复审",
            "type": "skill",
            "target": "compliance_check",
            "display_name": "合规与风险审核",
            "purpose": f"（第 {attempt} 轮）复审修订后的回复。",
            "depends_on": [],
            "input": recheck_input,
            "output": out2,
            "status": "success" if isinstance(out2, dict) else "failed",
            "error": "" if isinstance(out2, dict) else "复审输出无效",
            "engine": engine2,
            "elapsed_ms": round((time.perf_counter() - t1) * 1000, 1),
        })

        if isinstance(out2, dict) and out2.get("passed"):
            risk_result = {
                "risk_level": out2.get("risk_level", "unknown"),
                "passed": True,
                "issues": out2.get("issues", []) or [],
                "suggestions": (out2.get("suggestions", []) or []) + [f"已按第 {attempt} 轮审核建议自动修订回复。"],
            }
            final = str(out2.get("final_reply") or revised).strip()
            return (final or SAFE_FALLBACK), risk_result, trace_steps

        current_draft = revised
        if isinstance(out2, dict):
            issues = out2.get("issues", []) or issues
            suggestions = out2.get("suggestions", []) or suggestions

    risk_result["suggestions"] = list(risk_result["suggestions"]) + [
        "多轮修订后仍未通过审核，已返回安全兜底话术，不向用户暴露原始回复。"
    ]
    return SAFE_FALLBACK, risk_result, trace_steps
