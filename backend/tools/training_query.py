"""Tool: query_trainings 查询培训计划。"""
from typing import Any, Dict

from backend.tools.util import load_trainings


async def run(params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    employee = ctx["employee"]
    dept = employee.get("department")
    completed_tasks = set(employee.get("completed_tasks", []))

    training_type = (params.get("training_type") or "").strip().lower()
    keyword = (params.get("keyword") or "").strip()

    result = []
    for t in load_trainings():
        app = t.get("applicable_departments", ["all"])
        if "all" not in app and dept not in app:
            continue
        if training_type and t.get("type") != training_type:
            continue
        if keyword:
            hay = f"{t.get('name','')}{t.get('description','')}{t.get('type_label','')}"
            if keyword not in hay:
                continue

        # 员工是否已完成该培训：通过关联任务或 completed_by 判断
        completed = employee["employee_id"] in t.get("completed_by", [])
        # 关联入职任务：信息安全培训↔T010/T036，通用↔T011 等（演示数据以 completed_by 为准，任务完成状态仅供参考）
        result.append({
            **t,
            "completed_by": None,  # 不暴露其他员工名单
            "completed": completed,
        })

    # 必修未完成优先
    result.sort(key=lambda x: (0 if (x.get("required") and not x["completed"]) else 1))

    return {
        "employee_id": employee["employee_id"],
        "filter": {"training_type": training_type, "keyword": keyword},
        "count": len(result),
        "trainings": result,
    }
