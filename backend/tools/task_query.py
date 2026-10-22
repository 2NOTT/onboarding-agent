"""Tool: query_onboarding_tasks 查询入职任务。"""
from typing import Any, Dict

from backend.tools.util import applicable_tasks, completed_set, find_employee


async def run(params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    employee = ctx["employee"]
    include_later = bool(params.get("include_later_stage", False))

    tasks = applicable_tasks(employee, include_later_stage=include_later)
    completed = completed_set(employee)

    task_id = params.get("task_id")
    keyword = (params.get("keyword") or "").strip()
    stage = params.get("stage")

    if task_id:
        tasks = [t for t in tasks if t.get("task_id") == task_id]
    if stage:
        tasks = [t for t in tasks if t.get("stage") == stage]
    if keyword:
        tasks = [
            t for t in tasks
            if keyword in t.get("task_name", "") or keyword in t.get("description", "")
        ]

    items = []
    for t in tasks:
        items.append({
            **t,
            "completed": t["task_id"] in completed,
            "stage_label": {
                "day_1": "入职第1天", "week_1": "入职第1周",
                "month_1": "入职第1个月", "probation": "试用期(30-90天)",
            }.get(t.get("stage"), t.get("stage")),
        })

    return {
        "employee_id": employee["employee_id"],
        "filter": {
            "task_id": task_id, "stage": stage, "keyword": keyword,
            "include_later_stage": include_later,
        },
        "count": len(items),
        "tasks": items,
    }
