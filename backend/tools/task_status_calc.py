"""Tool: calc_task_status 入职任务状态计算。

纯代码实现，不依赖大模型：
- 完成率 / 未完成任务数 / 逾期判断 / 依赖阻塞判断
- 当前应优先完成任务与优先级排序
- 是否满足进入下一入职阶段的条件
"""
from datetime import timedelta
from typing import Any, Dict, List

from backend.tools.util import (
    PRIORITY_ORDER,
    STAGE_LABEL,
    STAGE_ORDER,
    applicable_tasks,
    completed_set,
    find_employee,
    parse_hire_date,
    today,
)

NEXT_STAGE = {"day_1": "week_1", "week_1": "month_1", "month_1": "probation", "probation": None}
STAGE_DEADLINE = {"day_1": 1, "week_1": 7, "month_1": 30, "probation": 90}


def _deadline(task: Dict[str, Any], hire: Any):
    days = task.get("deadline_days")
    if days is None or hire is None:
        return None
    return hire + timedelta(days=int(days))


async def run(params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    employee_id = params.get("employee_id") or ctx["current_employee_id"]
    employee = find_employee(employee_id)
    if not employee:
        return {"error": f"未找到员工 {employee_id}"}

    hire = parse_hire_date(employee.get("hire_date", ""))
    completed = completed_set(employee)
    tasks = applicable_tasks(employee)

    total = len(tasks)
    completed_tasks = [t for t in tasks if t["task_id"] in completed]
    pending = [t for t in tasks if t["task_id"] not in completed]

    # 依赖是否满足
    def deps_satisfied(t: Dict[str, Any]) -> bool:
        return all(dep in completed for dep in t.get("dependency_tasks", []))

    overdue: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    for t in pending:
        ddl = _deadline(t, hire)
        if ddl is not None and today() > ddl:
            overdue.append({
                "task_id": t["task_id"], "task_name": t["task_name"],
                "deadline": ddl.isoformat(),
                "owner": t.get("owner"), "priority": t.get("priority"),
            })
        if not deps_satisfied(t):
            blocked.append({
                "task_id": t["task_id"], "task_name": t["task_name"],
                "unmet_dependencies": [d for d in t.get("dependency_tasks", []) if d not in completed],
            })

    # 优先级排序：P0 > P1 > P2；必做优先；未被阻塞优先
    pending_sorted = sorted(
        pending,
        key=lambda t: (
            PRIORITY_ORDER.get(t.get("priority", "P2"), 2),
            0 if t.get("required") else 1,
            0 if deps_satisfied(t) else 1,
            t.get("task_id", ""),
        ),
    )
    next_priority = [t for t in pending_sorted if deps_satisfied(t)][:5]
    if not next_priority:  # 极端情况：全被阻塞，也给出前几项
        next_priority = pending_sorted[:5]

    # 阶段推进判断：当前阶段 P0 必做任务是否全部完成
    stage = employee.get("onboarding_stage", "day_1")
    stage_required_pending = [
        t for t in pending
        if t.get("stage") == stage and t.get("required") and t.get("priority") == "P0"
    ]
    next_stage = NEXT_STAGE.get(stage)
    eligible_next_stage = len(stage_required_pending) == 0 and total > 0

    progress = round(len(completed_tasks) / total, 4) if total else 0.0

    return {
        "employee_id": employee_id,
        "onboarding_stage": stage,
        "onboarding_stage_label": STAGE_LABEL.get(stage, stage),
        "next_stage": next_stage,
        "eligible_next_stage": eligible_next_stage,
        "onboarding_progress": progress,
        "completed_task_count": len(completed_tasks),
        "pending_task_count": len(pending),
        "overdue_task_count": len(overdue),
        "overdue_tasks": overdue,
        "blocked_tasks": blocked,
        "stage_required_pending": [
            {"task_id": t["task_id"], "task_name": t["task_name"], "owner": t.get("owner")}
            for t in stage_required_pending
        ],
        "next_priority_tasks": [
            {
                "task_id": t["task_id"],
                "task_name": t["task_name"],
                "priority": t.get("priority"),
                "required": t.get("required"),
                "recommended_time": t.get("recommended_time"),
                "owner": t.get("owner"),
                "description": t.get("description"),
            }
            for t in next_priority
        ],
    }
