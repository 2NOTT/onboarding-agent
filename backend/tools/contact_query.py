"""Tool: query_contacts 查询公司联系人。

权限规则：仅返回当前员工有权限联系的业务联系人（公开且对其部门开放），
仅返回姓名、岗位、企业邮箱、企业联系方式等业务必要信息。
"""
from typing import Any, Dict

from backend.tools.util import load_contacts


async def run(params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    employee = ctx["employee"]
    dept = employee.get("department")
    role = (params.get("role") or "").strip().lower()
    keyword = (params.get("keyword") or "").strip()

    contacts = load_contacts()
    result = []
    for c in contacts:
        if not c.get("is_public", False):
            continue
        avail = c.get("available_departments", ["all"])
        if "all" not in avail and dept not in avail:
            continue
        if role and c.get("role") != role:
            continue
        if keyword:
            hay = f"{c.get('name','')}{c.get('title','')}{c.get('description','')}{c.get('department','')}"
            if keyword not in hay:
                continue
        result.append({
            "contact_id": c.get("contact_id"),
            "name": c.get("name"),
            "role": c.get("role"),
            "title": c.get("title"),
            "department": c.get("department"),
            "email": c.get("email"),
            "phone": c.get("phone"),
            "description": c.get("description"),
        })

    return {
        "employee_id": employee["employee_id"],
        "filter": {"role": role, "keyword": keyword},
        "count": len(result),
        "contacts": result,
        "note": "仅返回业务公开联系人，已过滤无关员工的私人联系方式。",
    }
