"""Tool 层公共工具：数据加载、任务适用性匹配、阶段判断。"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.services import json_store

STAGE_ORDER = {"day_1": 0, "week_1": 1, "month_1": 2, "probation": 3}
STAGE_LABEL = {
    "day_1": "入职第1天",
    "week_1": "入职第1周",
    "month_1": "入职第1个月",
    "probation": "试用期(30-90天)",
}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def load_employees() -> List[Dict[str, Any]]:
    return json_store.load("employees", {}).get("employees", [])


def find_employee(employee_id: str) -> Optional[Dict[str, Any]]:
    for emp in load_employees():
        if emp.get("employee_id") == employee_id:
            return emp
    return None


def load_tasks() -> List[Dict[str, Any]]:
    return json_store.load("onboarding_tasks", {}).get("tasks", [])


def load_contacts() -> List[Dict[str, Any]]:
    return json_store.load("contacts", {}).get("contacts", [])


def load_policies() -> List[Dict[str, Any]]:
    return json_store.load("policies", {}).get("policies", [])


def load_trainings() -> List[Dict[str, Any]]:
    return json_store.load("trainings", {}).get("trainings", [])


def parse_hire_date(hire_date: str) -> Optional[date]:
    try:
        return datetime.strptime(hire_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def task_applicable(task: Dict[str, Any], employee: Dict[str, Any]) -> bool:
    """任务是否适用于该员工（部门 + 岗位）。"""
    app = task.get("applicable", {}) or {}
    deps = app.get("departments", ["all"])
    poss = app.get("positions", ["all"])
    dept_ok = "all" in deps or employee.get("department") in deps
    pos_ok = "all" in poss or employee.get("position") in poss
    return dept_ok and pos_ok


def stage_reached(task_stage: str, employee_stage: str) -> bool:
    """任务所处阶段是否已到达（任务阶段序号 <= 员工阶段序号）。"""
    return STAGE_ORDER.get(task_stage, 0) <= STAGE_ORDER.get(employee_stage, 0)


def applicable_tasks(employee: Dict[str, Any], include_later_stage: bool = False) -> List[Dict[str, Any]]:
    """适用于该员工、且阶段已到达（或包含后续阶段）的任务列表。"""
    result = []
    for t in load_tasks():
        if not task_applicable(t, employee):
            continue
        if not include_later_stage and not stage_reached(t.get("stage", "day_1"), employee.get("onboarding_stage", "day_1")):
            continue
        result.append(t)
    return result


def completed_set(employee: Dict[str, Any]) -> set:
    return set(employee.get("completed_tasks", []))


def mask_name(name: str) -> str:
    if not name:
        return "*"
    if len(name) <= 1:
        return name + "*"
    return name[0] + "*" * (len(name) - 1)


def today() -> date:
    return date.today()
