"""Planner：根据用户问题与员工信息生成执行计划。

- LLM 模式：由大模型按计划规则生成 JSON 计划。
- Mock 模式 / LLM 失败：使用本地规则 Planner 兜底。
- validate_plan：对计划做确定性校验与修复（仅允许已启用的能力、
  注入缺失的必需 Tool 查询、保证最终回复前调用合规审核）。
"""
import json
from typing import Any, Dict, List, Tuple

from backend.config import settings
from backend.core import llm, tool_registry
from backend.core.skill_registry import get_by_type, list_enabled as list_enabled_skills
from backend.core.tool_registry import list_enabled as list_enabled_tools

# ---------------------------------------------------------------- 关键词与意图识别

TASK_KEYWORDS = ["任务", "待办", "第一天", "做什么", "需要完成", "前三十天", "30天", "三十天",
                 "入职流程", "办理", "什么时候可以", "领取", "安排"]
POLICY_TYPE_MAP = [
    ("请假", "leave"), ("考勤", "attendance"), ("打卡", "attendance"),
    ("报销", "reimbursement"), ("差旅", "reimbursement"),
    ("社保", "social_insurance"), ("公积金", "social_insurance"),
    ("信息安全", "infosec"), ("保密", "confidential"), ("试用期", "probation"),
    ("福利", "welfare"), ("培训制度", "training"), ("员工手册", "handbook"), ("手册", "handbook"),
]
TRAINING_KEYWORDS = ["培训", "课程"]
CONTACT_KEYWORDS = ["联系谁", "找谁", "负责人", "谁来", "对接", "联系人", "该找"]
CONTACT_ROLE_MAP = [
    ("HR", "hr"), ("人事", "hr"), ("IT", "it"), ("行政", "admin"),
    ("培训", "training"), ("财务", "finance"), ("报销", "finance"),
    ("信息安全", "security"), ("负责人", "dept_manager"), ("领导", "dept_manager"),
]
DEVICE_KEYWORDS = ["电脑", "设备", "账号", "邮箱", "门禁", "工位", "工牌", "VPN"]
PROCESS_KEYWORDS = ["流程", "怎么办理", "如何办理", "步骤", "什么时候可以", "领取"]
COZE_KEYWORDS = ["coze", "COZE", "Coze"]  # 问题中明确提到 Coze 时走外部工作流 Tool

POLICY_KEYWORDS_ALL = [k for k, _ in POLICY_TYPE_MAP]


def _has_any(text: str, words: List[str]) -> bool:
    return any(w in text for w in words)


def detect_needs(question: str) -> Dict[str, Any]:
    """基于问题关键词判断需要哪些数据查询（Tool 调用规则的确定性实现）。"""
    q = question or ""
    needs = {
        "employee": True,  # 涉及身份、部门、岗位、状态的任务问题基本都需要
        "tasks": _has_any(q, TASK_KEYWORDS + DEVICE_KEYWORDS),
        "policy": _has_any(q, POLICY_KEYWORDS_ALL),
        "training": _has_any(q, TRAINING_KEYWORDS),
        "contacts": _has_any(q, CONTACT_KEYWORDS) or _has_any(q, DEVICE_KEYWORDS),
        "process": _has_any(q, PROCESS_KEYWORDS + DEVICE_KEYWORDS),
        "coze": _has_any(q, COZE_KEYWORDS),
    }
    policy_type, policy_keyword = "", ""
    for kw, ptype in POLICY_TYPE_MAP:
        if kw in q:
            policy_type, policy_keyword = ptype, kw
            break
    contact_role = ""
    for kw, role in CONTACT_ROLE_MAP:
        if kw.lower() in q.lower():
            contact_role = role
            break
    needs["policy_type"] = policy_type
    needs["policy_keyword"] = policy_keyword
    needs["contact_role"] = contact_role
    return needs


# ---------------------------------------------------------------- LLM Planner

PLANNER_SYSTEM_PROMPT = """你是「企业入职助手」平台的 Planner（执行计划生成器）。你需要为用户新员工问题生成可执行计划。

## 可用 Tool（type=tool，只能从以下名称中选择）
{tools_desc}

## 可用 Skill（type=skill，只能从以下类型中选择）
{skills_desc}

## 员工信息
{employee_desc}

## 计划规则
1. 只能使用上面列出的能力名称，禁止生成系统中不存在的能力。
2. 涉及事实数据（员工信息、任务、制度、联系人、培训）的问题，必须先生成对应 Tool 查询步骤，不允许跳过查询直接生成结论。
3. 涉及员工身份/状态时必须包含 query_employee_info；涉及任务时包含 query_onboarding_tasks 与 calc_task_status；涉及制度时包含 query_policies；涉及培训时包含 query_trainings；涉及负责人时包含 query_contacts；用户问题明确要求使用 Coze 工作流时包含 run_coze_workflow。
4. 最终回复前必须包含 communication 技能（生成话术）与 compliance_check 技能（合规审核）；compliance_check 必须是最后一步，且依赖 communication。
5. 每一步必须输出：step_id（S1、S2…）、name（中文步骤名）、type（tool/skill）、target（tool 名称或 skill 类型）、purpose（执行目标）、input（输入参数对象）、depends_on（依赖的 step_id 数组）。
6. tool 的 input 只能包含该 tool 支持的参数；skill 的 input 只能包含少量提示性参数，Skill 实际数据由依赖步骤提供。
7. 只输出严格 JSON，结构：{{"plan_summary": "一句话计划概述", "steps": [...]}}"""


def _build_llm_messages(question, employee, skills, tools):
    tools_desc = "\n".join(
        f"- {t['name']}：{t['description']} 参数：{json.dumps(t.get('input_params', {}), ensure_ascii=False)}"
        for t in tools
    )
    skills_desc = "\n".join(f"- {s['type']}：{s['description']}" for s in skills)
    employee_desc = json.dumps(
        {k: employee.get(k) for k in ["employee_id", "name", "department", "position", "hire_date", "onboarding_stage", "manager", "hr_contact"]},
        ensure_ascii=False,
    )
    system = PLANNER_SYSTEM_PROMPT.format(tools_desc=tools_desc, skills_desc=skills_desc, employee_desc=employee_desc)
    user = f"用户问题：{question}\n\n请生成执行计划 JSON。"
    return system, user


# ---------------------------------------------------------------- Mock Planner（规则版）

def mock_plan(question: str, employee: Dict[str, Any]) -> Dict[str, Any]:
    needs = detect_needs(question)
    steps: List[Dict[str, Any]] = []
    sid = [0]

    # 跨员工查询检测：问题中出现其他员工编号或姓名时，向 Tool 传入该员工编号，
    # 由 Tool 层执行隐私拦截（拒绝详情、仅返回脱敏公开信息）。
    other_ref = ""
    import re as _re
    m = _re.search(r"E\d{3}", question or "")
    if m and m.group(0) != employee.get("employee_id"):
        other_ref = m.group(0)
    else:
        from backend.tools.util import load_employees
        for e in load_employees():
            if e.get("name") and e.get("name") != employee.get("name") and e["name"] in (question or ""):
                other_ref = e["employee_id"]
                break

    def add(name, stype, target, purpose, inp, deps):
        sid[0] += 1
        steps.append({
            "step_id": f"S{sid[0]}", "name": name, "type": stype, "target": target,
            "purpose": purpose, "input": inp, "depends_on": list(deps),
        })
        return steps[-1]["step_id"]

    s1 = add("问题结构化", "skill", "question_structuring", "将用户问题解析为结构化意图，指导后续查询。", {}, [])
    emp_input = {"employee_id": other_ref} if other_ref else {}
    s2 = add("查询员工信息", "tool", "query_employee_info", "获取员工身份、部门、岗位、入职阶段与账号设备状态。", emp_input, [s1])

    task_steps: List[str] = []
    if needs["tasks"]:
        s3 = add("查询入职任务", "tool", "query_onboarding_tasks", "获取适用于该员工的入职任务清单与完成状态。", {}, [s2])
        s4 = add("计算任务状态", "tool", "calc_task_status", "以代码计算完成率、逾期与阻塞情况，得出优先级排序。", {}, [s3])
        task_steps = [s3, s4]
    if needs["policy"]:
        inp = {}
        if needs["policy_type"]:
            inp["policy_type"] = needs["policy_type"]
        if needs["policy_keyword"]:
            inp["keyword"] = needs["policy_keyword"]
        add("查询制度知识库", "tool", "query_policies", "检索与问题相关的公司制度原文与版本。", inp, [s2])
    if needs["training"]:
        add("查询培训计划", "tool", "query_trainings", "获取适用于该员工的培训安排与完成状态。", {}, [s2])
    if needs["contacts"]:
        inp = {}
        if needs["contact_role"]:
            inp["role"] = needs["contact_role"]
        add("查询公司联系人", "tool", "query_contacts", "获取可对接的负责人及企业联系方式。", inp, [s2])
    if needs.get("coze"):
        add("调用 Coze 工作流", "tool", "run_coze_workflow",
            "将用户问题转发给外部 Coze 工作流，获取 answer / status / risk_level。",
            {"user_input": question}, [s2])

    policy_step_id = ""
    contacts_step_id = ""
    for s in steps:
        if s["target"] == "query_policies":
            policy_step_id = s["step_id"]
        elif s["target"] == "query_contacts":
            contacts_step_id = s["step_id"]

    if needs["tasks"]:
        add("入职任务决策", "skill", "task_decision", "基于任务数据判断当前应优先完成的事项。", {}, [s2] + task_steps)
    if needs["policy"]:
        add("制度与知识问答", "skill", "policy_qa", "基于检索到的制度原文生成带版本标注的解释。", {}, [s2, policy_step_id])
    if needs["process"]:
        add("入职流程解释", "skill", "process_explainer", "生成面向新员工的步骤化流程说明。", {}, [s2] + task_steps + ([contacts_step_id] if contacts_step_id else []))

    # communication 依赖全部前置步骤，确保汇总所有查询数据
    comm_deps = [s["step_id"] for s in steps]
    add("生成沟通话术", "skill", "communication", "汇总所有查询与技能结果，生成面向员工的最终回复。", {}, comm_deps)
    add("合规与风险审核", "skill", "compliance_check", "审核最终回复的合规与风险，通过后才允许返回。", {}, [steps[-1]["step_id"]])

    return {
        "plan_summary": f"针对「{question[:30]}…」的结构化问答计划：先结构化问题，再查询相关数据，最后生成回复并完成合规审核。",
        "steps": steps,
    }


# ---------------------------------------------------------------- 计划校验与修复

def _validate_steps(raw_steps: List[Dict[str, Any]], warnings: List[str]) -> List[Dict[str, Any]]:
    """剔除不存在或已禁用的能力步骤。"""
    valid: List[Dict[str, Any]] = []
    used_ids = set()
    for idx, raw in enumerate(raw_steps or [], 1):
        if not isinstance(raw, dict):
            continue
        stype = raw.get("type")
        target = raw.get("target")
        if stype == "tool":
            if not tool_registry.exists(target):
                warnings.append(f"Planner 生成了系统中不存在的 Tool「{target}」，已剔除。")
                continue
            if not tool_registry.is_enabled(target):
                warnings.append(f"Tool「{target}」已被禁用，已从计划中剔除。")
                continue
        elif stype == "skill":
            if get_by_type(target) is None:
                warnings.append(f"Planner 生成了系统中不存在的 Skill「{target}」，已剔除。")
                continue
            if not get_by_type(target).get("enabled", False):
                warnings.append(f"Skill「{target}」已被禁用，已从计划中剔除。")
                continue
        else:
            warnings.append(f"计划步骤类型非法（{stype}），已剔除。")
            continue
        step_id = str(raw.get("step_id") or "").strip()
        if not step_id or step_id in used_ids:
            step_id = f"S_auto_{idx}"
            while step_id in used_ids:
                step_id += "_x"
        used_ids.add(step_id)
        valid.append({
            "step_id": step_id,
            "name": str(raw.get("name") or target),
            "type": stype,
            "target": target,
            "purpose": str(raw.get("purpose") or ""),
            "input": raw.get("input") if isinstance(raw.get("input"), dict) else {},
            "depends_on": [d for d in (raw.get("depends_on") or []) if isinstance(d, str)],
        })
    return valid


def _inject_required_tools(steps: List[Dict[str, Any]], question: str, warnings: List[str]) -> List[Dict[str, Any]]:
    """按 Tool 调用规则注入缺失的必需查询步骤（插入在第一个 Skill 之前）。"""
    needs = detect_needs(question)
    present = {s["target"] for s in steps if s["type"] == "tool"}

    required: List[Tuple[str, str, Dict[str, Any]]] = []  # (target, purpose, input)
    if needs["tasks"] and "query_onboarding_tasks" not in present:
        required.append(("query_onboarding_tasks", "（规则注入）问题涉及任务，必须先查询入职任务数据。", {}))
    if needs["tasks"] and "calc_task_status" not in present:
        required.append(("calc_task_status", "（规则注入）问题涉及任务状态，必须进行任务状态计算。", {}))
    if needs["policy"] and "query_policies" not in present:
        inp = {}
        if needs["policy_type"]:
            inp["policy_type"] = needs["policy_type"]
        if needs["policy_keyword"]:
            inp["keyword"] = needs["policy_keyword"]
        required.append(("query_policies", "（规则注入）问题涉及制度，必须查询制度知识库。", inp))
    if needs["training"] and "query_trainings" not in present:
        required.append(("query_trainings", "（规则注入）问题涉及培训，必须查询培训计划。", {}))
    if needs["contacts"] and "query_contacts" not in present:
        inp = {"role": needs["contact_role"]} if needs["contact_role"] else {}
        required.append(("query_contacts", "（规则注入）问题涉及负责人，必须查询公司联系人。", inp))
    if "query_employee_info" not in present:
        required.append(("query_employee_info", "（规则注入）涉及员工身份与状态，必须查询员工信息。", {}))

    if not required:
        return steps

    first_skill_idx = next((i for i, s in enumerate(steps) if s["type"] == "skill"), len(steps))
    inserted = []
    used_ids = {s["step_id"] for s in steps}
    for index, (target, purpose, inp) in enumerate(required, 1):
        step_id = f"S_required_{index}"
        while step_id in used_ids:
            step_id += "_x"
        used_ids.add(step_id)
        inserted.append({
            "step_id": step_id, "name": target, "type": "tool", "target": target,
            "purpose": purpose, "input": inp, "depends_on": [],
        })
        warnings.append(f"按 Tool 调用规则自动补充必需查询步骤：{target}。")
    required_inputs = {
        "task_decision": {"query_onboarding_tasks", "calc_task_status"},
        "process_explainer": {"query_onboarding_tasks", "query_contacts"},
        "policy_qa": {"query_policies"},
    }
    for step in steps:
        for query in inserted:
            if query["target"] in required_inputs.get(step["target"], set()):
                step["depends_on"].append(query["step_id"])
    steps = steps[:first_skill_idx] + inserted + steps[first_skill_idx:]
    return steps


def _ensure_final_skills(steps: List[Dict[str, Any]], warnings: List[str]) -> List[Dict[str, Any]]:
    """确保 communication 汇总全部前置数据、compliance_check 为最后一步（强制规则）。"""
    def has(target):
        return any(s["target"] == target and s["type"] == "skill" for s in steps)

    missing_comm = not has("communication")
    missing_comp = not has("compliance_check")

    # 剥离旧的 communication / compliance 步骤后按统一规则重建：
    # communication 依赖全部前置步骤（保证拿到所有 Tool/Skill 输出），compliance 依赖 communication。
    steps = [s for s in steps if s["target"] not in ("communication", "compliance_check")]

    all_ids = [s["step_id"] for s in steps if s["step_id"]]
    comm_id = f"S_comm_{len(steps) + 1}"
    steps.append({
        "step_id": comm_id, "name": "生成沟通话术", "type": "skill", "target": "communication",
        "purpose": "汇总所有查询与技能结果，生成面向员工的最终回复。",
        "input": {}, "depends_on": all_ids,
    })
    steps.append({
        "step_id": f"S_comp_{len(steps) + 1}", "name": "合规与风险审核", "type": "skill",
        "target": "compliance_check",
        "purpose": "审核最终回复的合规与风险，通过后才允许返回（强制规则）。",
        "input": {}, "depends_on": [comm_id],
    })
    if missing_comm or missing_comp:
        warnings.append("已按强制规则在计划末尾补充沟通话术与合规审核步骤。")
    return steps


def _topo_sort(steps: List[Dict[str, Any]], warnings: List[str]) -> List[Dict[str, Any]]:
    """按依赖关系做稳定拓扑排序，并重新编号。"""
    by_id = {}
    for s in steps:
        if s["step_id"]:
            by_id[s["step_id"]] = s

    # 修复非法依赖
    for s in steps:
        s["depends_on"] = [d for d in s["depends_on"] if d in by_id and d != s["step_id"]]

    ordered: List[Dict[str, Any]] = []
    visited: set = set()

    def visit(s: Dict[str, Any]):
        # 注入的步骤可能没有 step_id，用对象 id 兜底，避免互相覆盖
        key = s["step_id"] or f"__anon_{id(s)}"
        if key in visited:
            return
        visited.add(key)
        for dep in s["depends_on"]:
            if dep in by_id:
                visit(by_id[dep])
        ordered.append(s)

    for s in steps:
        visit(s)

    # 重新编号 S1..Sn
    id_map = {}
    for i, s in enumerate(ordered, 1):
        id_map[s["step_id"] or f"__anon_{id(s)}"] = f"S{i}"
    order_index = {new_id: i for i, new_id in enumerate(id_map.values())}
    for s in ordered:
        deps = {id_map[d] for d in s["depends_on"]}
        s["depends_on"] = sorted(deps, key=lambda x: order_index[x])
        s["step_id"] = id_map[s["step_id"] or f"__anon_{id(s)}"]
    ordered.sort(key=lambda x: int(x["step_id"][1:]))
    return ordered


def validate_plan(raw_plan: Dict[str, Any], question: str, warnings: List[str]) -> Dict[str, Any]:
    steps = _validate_steps(raw_plan.get("steps"), warnings)
    if not steps:
        warnings.append("Planner 计划为空或全部步骤非法，已回退为规则计划。")
        raw_plan = mock_plan(question, {})
        steps = _validate_steps(raw_plan["steps"], warnings)
    steps = _inject_required_tools(steps, question, warnings)
    steps = _ensure_final_skills(steps, warnings)
    steps = _topo_sort(steps, warnings)
    summary = raw_plan.get("plan_summary") or "执行计划"
    return {"plan_summary": summary, "steps": steps}


# ---------------------------------------------------------------- 对外入口

async def make_plan(question: str, employee: Dict[str, Any]) -> Tuple[Dict[str, Any], str, List[str]]:
    """生成计划。返回 (plan, engine, warnings)。engine: llm / mock_fallback / mock。"""
    warnings: List[str] = []
    skills = list_enabled_skills()
    tools = list_enabled_tools()

    if settings.mock_mode:
        plan = mock_plan(question, employee)
        plan = validate_plan(plan, question, warnings)
        return plan, "mock", warnings

    try:
        system, user = _build_llm_messages(question, employee, skills, tools)
        raw = await llm.chat_json(system, user, temperature=0.2, max_tokens=2048)
        if not isinstance(raw, dict) or "steps" not in raw:
            raise llm.LLMError("Planner 输出不是有效计划 JSON")
        plan = validate_plan(raw, question, warnings)
        return plan, "llm", warnings
    except Exception as e:  # LLM 调用失败 → 规则兜底，保证可演示
        warnings.append(f"LLM Planner 调用失败（{e}），已回退到本地规则 Planner。")
        plan = mock_plan(question, employee)
        plan = validate_plan(plan, question, warnings)
        return plan, "mock_fallback", warnings
