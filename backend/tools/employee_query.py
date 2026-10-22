"""Tool: query_employee_info 查询员工信息。

隐私规则：仅允许查询当前员工本人的详细信息；
查询其他员工时拒绝，仅返回脱敏后的公开组织信息。
"""
from typing import Any, Dict

from backend.tools.util import completed_set, find_employee, applicable_tasks, mask_name


async def run(params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    current_id = ctx["current_employee_id"]
    requested = params.get("employee_id") or current_id

    if requested != current_id:
        other = find_employee(requested)
        if other:
            return {
                "denied": True,
                "message": "出于隐私保护，不允许跨员工查询详细信息。以下为脱敏后的公开组织信息。",
                "public_info": {
                    "name": mask_name(other.get("name", "")),
                    "department": other.get("department"),
                    "position": other.get("position"),
                    "onboarding_stage": other.get("onboarding_stage"),
                },
            }
        return {"error": f"未找到编号为 {requested} 的员工"}

    emp = find_employee(current_id)
    if not emp:
        return {"error": f"未找到当前员工 {current_id} 的信息"}

    tasks = applicable_tasks(emp)
    completed = completed_set(emp)
    pending = [t["task_id"] for t in tasks if t["task_id"] not in completed]

    return {
        "employee_id": emp["employee_id"],
        "name": emp["name"],
        "department": emp["department"],
        "position": emp["position"],
        "hire_date": emp["hire_date"],
        "work_location": emp.get("work_location"),
        "manager": emp.get("manager"),
        "hr_contact": emp.get("hr_contact"),
        "email": emp.get("email"),
        "onboarding_stage": emp.get("onboarding_stage"),
        "stage_label": emp.get("stage_label"),
        "account_status": emp.get("account_status"),
        "device_status": emp.get("device_status"),
        "access_status": emp.get("access_status"),
        "completed_tasks": emp.get("completed_tasks", []),
        "pending_tasks": pending,
        "completed_task_count": len(emp.get("completed_tasks", [])),
        "pending_task_count": len(pending),
    }
