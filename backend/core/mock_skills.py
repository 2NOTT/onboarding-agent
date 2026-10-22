"""Mock 模式下的 Skill 本地实现。

当大模型 API 未配置或调用失败时，用确定性规则 + 真实 Tool 数据
生成各 Skill 的输出，保证项目无 Key 也可完整演示。
"""
import re
from typing import Any, Dict, List, Optional

from backend.tools.util import load_employees

# ---------------------------------------------------------------- 关键词表

TASK_KEYWORDS = [
    "任务", "待办", "第一天", "第一天需要", "做什么", "需要完成", "前三十天",
    "30天", "三十天", "入职流程", "办理", "什么时候可以", "领取",
]
POLICY_KEYWORDS = ["请假", "考勤", "打卡", "报销", "差旅", "社保", "公积金", "试用期", "保密",
                   "信息安全", "福利", "加班", "员工手册", "制度", "规定"]
TRAINING_KEYWORDS = ["培训", "课程", "学习"]
CONTACT_KEYWORDS = ["联系谁", "找谁", "负责人", "谁来", "对接", "联系人", "该找"]
DEVICE_KEYWORDS = ["电脑", "设备", "账号", "邮箱", "门禁", "工位", "工牌", "VPN"]
SENSITIVE_KEYWORDS = ["社保", "公积金", "薪酬", "薪资", "工资", "劳动合同", "绩效", "薪水", "待遇", "请假"]

INTENT_TOPIC_MAP = {
    "请假": ("query_policy", "leave_policy"),
    "考勤": ("query_policy", "attendance_policy"),
    "打卡": ("query_policy", "attendance_policy"),
    "报销": ("query_policy", "reimbursement_policy"),
    "社保": ("query_payroll_benefit", "social_insurance"),
    "公积金": ("query_payroll_benefit", "housing_fund"),
    "试用期": ("query_policy", "probation_policy"),
    "保密": ("query_policy", "confidential_policy"),
    "信息安全": ("query_policy", "infosec_policy"),
    "福利": ("query_policy", "welfare_policy"),
    "培训": ("query_training", "training_schedule"),
    "电脑": ("query_device_access", "device_pickup"),
    "设备": ("query_device_access", "device_pickup"),
    "账号": ("query_device_access", "account_activation"),
    "门禁": ("query_device_access", "access_card"),
    "工位": ("query_device_access", "workstation"),
    "联系": ("query_contact", "contact_query"),
}

JARGON_WORDS = [
    "Planner", "planner", "Skill", "skill", "Tool", "tool", "Executor", "executor",
    "JSON", "json", "Prompt", "prompt", "大模型", "模型调用", "执行链路", "内部系统",
]

PROMISE_WORDS = ["保证", "肯定", "一定会", "必须能", "绝对", "承诺"]


def _data(skill_input: Dict[str, Any], key: str) -> Dict[str, Any]:
    v = skill_input.get(key)
    return v if isinstance(v, dict) else {}


def _emp(skill_input: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    emp = skill_input.get("employee")
    if isinstance(emp, dict) and emp.get("employee_id"):
        return emp
    return ctx.get("employee", {})


def _question(skill_input: Dict[str, Any]) -> str:
    return str(skill_input.get("question") or "")


def _has_any(text: str, words: List[str]) -> bool:
    return any(w in text for w in words)


def _task_detail_map(tasks_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for t in tasks_data.get("tasks", []) or []:
        if isinstance(t, dict) and t.get("task_id"):
            out[t["task_id"]] = t
    return out


def sanitize_reply(draft: str) -> str:
    """去除内部技术词汇等敏感表述（合规兜底清洗）。"""
    text = draft or ""
    for w in JARGON_WORDS:
        text = text.replace(w, "系统")
    text = re.sub(r"\s{2,}", "\n", text)
    return text.strip()


# ---------------------------------------------------------------- 各 Skill 的 Mock 实现

def _mock_question_structuring(skill_input: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    emp = _emp(skill_input, ctx)
    q = _question(skill_input)
    intent, topic = "general_onboarding_consult", "general_onboarding"
    for kw, (i, t) in INTENT_TOPIC_MAP.items():
        if kw in q:
            intent, topic = i, t
            break
    if not any(v[0] == intent for v in INTENT_TOPIC_MAP.values()) and _has_any(q, TASK_KEYWORDS):
        intent, topic = "query_onboarding_tasks", "first_day_tasks"

    return {
        "intent": intent,
        "topic": topic,
        "employee_id": emp.get("employee_id"),
        "department": emp.get("department"),
        "position": emp.get("position"),
        "onboarding_stage": emp.get("onboarding_stage"),
        "need_employee_profile": True,
        "need_onboarding_task_query": _has_any(q, TASK_KEYWORDS + DEVICE_KEYWORDS + TRAINING_KEYWORDS) or intent == "query_onboarding_tasks",
        "need_policy_query": _has_any(q, POLICY_KEYWORDS),
        "need_contact_query": _has_any(q, CONTACT_KEYWORDS + DEVICE_KEYWORDS) or intent == "query_contact",
        "need_training_query": _has_any(q, TRAINING_KEYWORDS),
        "sensitive_topic": _has_any(q, SENSITIVE_KEYWORDS),
        "need_follow_up": not q.strip(),
        "missing_fields": [] if q.strip() else ["question"],
    }


def _mock_task_decision(skill_input: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    status = _data(skill_input, "calc_task_status")
    tasks_data = _data(skill_input, "query_onboarding_tasks")
    detail = _task_detail_map(tasks_data)

    if not status and not tasks_data:
        return {
            "recommended_tasks": [],
            "summary": "缺少任务数据（未执行任务查询或状态计算 Tool），无法给出可靠推荐，建议先完成数据查询。",
        }

    recommended = []
    for t in status.get("next_priority_tasks", []):
        tid = t.get("task_id")
        d = detail.get(tid, {})
        overdue_ids = {o["task_id"] for o in status.get("overdue_tasks", [])}
        reason = d.get("description") or t.get("description") or "该任务属于当前阶段必办事项。"
        if tid in overdue_ids:
            reason = "该任务已逾期，请尽快完成。" + reason
        recommended.append({
            "task_id": tid,
            "task_name": t.get("task_name") or d.get("task_name"),
            "priority": t.get("priority") or d.get("priority") or "P1",
            "required": t.get("required", d.get("required", True)),
            "recommended_time": t.get("recommended_time") or d.get("recommended_time") or "尽快",
            "dependency_tasks": d.get("dependency_tasks", []),
            "owner": t.get("owner") or d.get("owner") or "HR对接人",
            "reason": reason,
        })

    overdue = status.get("overdue_task_count", 0)
    summary = (
        f"当前入职完成率约 {status.get('onboarding_progress', 0):.0%}，"
        f"还有 {status.get('pending_task_count', 0)} 项任务未完成"
        + (f"，其中 {overdue} 项已逾期" if overdue else "")
        + "。建议按下方优先级顺序推进。"
    ) if status else "已根据查询到的任务列表给出建议。"

    return {"recommended_tasks": recommended, "summary": summary}


def _mock_process_explainer(skill_input: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    q = _question(skill_input)
    contacts_data = _data(skill_input, "query_contacts")
    contacts = contacts_data.get("contacts", []) or []
    tasks_data = _data(skill_input, "query_onboarding_tasks")
    tasks = tasks_data.get("tasks", []) or []

    def contact_by_role(role: str) -> Dict[str, Any]:
        for c in contacts:
            if c.get("role") == role:
                return c
        return {}

    it = contact_by_role("it")
    admin = contact_by_role("admin")
    hr = contact_by_role("hr")

    def who(c: Dict[str, Any], fallback: str) -> str:
        if not c:
            return fallback
        return f"{c.get('name')}（{c.get('title')}，{c.get('email')}）"

    if _has_any(q, ["电脑", "设备", "领取"]):
        steps = [
            {"step_no": 1, "action": "前往 IT 服务台领取办公电脑", "owner": who(it, "IT服务台"),
             "materials": "工牌或入职通知", "expected_time": "入职当天上午", "result_state": "设备已签收"},
            {"step_no": 2, "action": "核对设备编号并完成签收登记", "owner": "本人与IT服务台",
             "materials": "无", "expected_time": "领取时当场完成", "result_state": "签收记录已归档"},
            {"step_no": 3, "action": "激活企业邮箱与IM账号，完成办公软件配置", "owner": who(it, "IT服务台"),
             "materials": "设备签收记录", "expected_time": "入职当天下午", "result_state": "账号可正常登录"},
        ]
        name = "办公电脑与账号开通流程"
    elif _has_any(q, ["门禁", "工牌", "工位"]):
        steps = [
            {"step_no": 1, "action": "到行政前台办理工牌并拍摄照片", "owner": who(admin, "行政前台"),
             "materials": "身份证或入职通知", "expected_time": "入职当天上午", "result_state": "工牌已发放"},
            {"step_no": 2, "action": "同步开通办公区大门与楼层门禁权限", "owner": who(admin, "行政前台"),
             "materials": "工牌", "expected_time": "当天完成", "result_state": "门禁已开通"},
            {"step_no": 3, "action": "确认工位位置并领取办公用品", "owner": who(admin, "行政前台"),
             "materials": "工牌", "expected_time": "入职当天下午", "result_state": "工位可用"},
        ]
        name = "工牌门禁与工位办理流程"
    elif _has_any(q, ["请假", "考勤", "打卡", "报销"]):
        steps = [
            {"step_no": 1, "action": "在 OA 系统中发起对应申请（请假/补卡/报销）", "owner": "本人",
             "materials": "相关证明材料", "expected_time": "事前或事项发生后尽快", "result_state": "申请已提交"},
            {"step_no": 2, "action": "等待直属领导与相关审批人审批", "owner": "直属领导/审批人",
             "materials": "无", "expected_time": "一般1-3个工作日", "result_state": "审批完成"},
            {"step_no": 3, "action": "按审批结果执行并留存记录", "owner": "本人",
             "materials": "无", "expected_time": "视事项而定", "result_state": "流程闭环"},
        ]
        name = "OA 申请类流程（请假/考勤/报销）"
    else:
        matched = [t for t in tasks if _has_any(q, t.get("task_name", "") + t.get("description", ""))][:4]
        if not matched:
            matched = tasks[:4]
        steps = [
            {"step_no": i + 1, "action": t.get("task_name", ""), "owner": who({}, t.get("owner", "HR对接人")),
             "materials": "", "expected_time": t.get("recommended_time", "尽快"),
             "result_state": "任务完成"}
            for i, t in enumerate(matched)
        ]
        name = "入职相关流程"

    if not steps:
        return {"process_name": "无法确定流程", "steps": [], "notes": "输入数据不足，具体流程以 HR / 行政确认为准。"}

    return {
        "process_name": name,
        "steps": steps,
        "notes": "以上流程基于系统内查询到的任务与联系人数据整理，具体安排以对应负责人确认为准。" + (f"可联系 HR：{who(hr, 'HR对接人')}" if hr else ""),
    }


def _mock_policy_qa(skill_input: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    policies_data = _data(skill_input, "query_policies")
    policies = policies_data.get("policies", []) or []

    if not policies:
        return {
            "found": False,
            "answer": "当前系统未查询到相关制度，无法提供准确信息。建议联系 HR 对接人确认，或稍后再次提问。",
            "referenced_policies": [],
        }

    parts = []
    referenced = []
    for p in policies[:2]:
        parts.append(
            f"【{p.get('name')} {p.get('version')}（{p.get('effective_date')} 生效，适用范围：{p.get('scope')}）】\n{p.get('content', '')}"
        )
        referenced.append({
            "policy_id": p.get("policy_id"),
            "name": p.get("name"),
            "version": p.get("version"),
            "effective_date": p.get("effective_date"),
        })
    return {
        "found": True,
        "answer": "\n\n".join(parts) + "\n\n注：如制度之间存在冲突，以上为最新生效版本；涉及个人具体情况请以 HR 确认为准。",
        "referenced_policies": referenced,
    }


def _mock_communication(skill_input: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    emp = _emp(skill_input, ctx)
    q = _question(skill_input)
    name = emp.get("name", "同学")

    # 风控修订模式：基于上一版回复与审核意见输出修订版
    if skill_input.get("revision_instructions") and skill_input.get("previous_reply"):
        revised = sanitize_reply(str(skill_input["previous_reply"]))
        return {
            "reply": revised,
            "revision_note": "已根据合规审核建议对回复进行修订：移除内部技术信息与不当表述。",
        }

    lines: List[str] = [f"你好，{name}！关于「{q}」，为你整理如下信息："]
    has_content = False

    # 隐私拦截：跨员工查询被拒绝时，仅提示脱敏公开信息
    emp_info = _data(skill_input, "query_employee_info")
    if emp_info.get("denied"):
        pub = emp_info.get("public_info", {}) or {}
        lines = [
            f"你好，{name}！关于「{q}」：",
            "",
            f"出于隐私保护，当前系统不允许查询其他员工的详细信息，仅可提供脱敏后的公开组织信息：{pub.get('name', '该同事')}（{pub.get('department', '')}·{pub.get('position', '')}）。",
            "如需了解该同事的工作安排，建议你直接通过企业IM与其本人或其所在部门负责人沟通。",
            "如还有其他问题，随时问我。",
        ]
        return {"reply": "\n".join(lines), "privacy_denied": True}

    decision = _data(skill_input, "task_decision")
    tasks = decision.get("recommended_tasks", [])
    if tasks:
        has_content = True
        lines.append("")
        lines.append("一、建议你优先完成的事项")
        for i, t in enumerate(tasks, 1):
            req = "必做" if t.get("required") else "选做"
            lines.append(
                f"{i}.（{t.get('priority')}·{req}）{t.get('task_name')}｜建议时间：{t.get('recommended_time')}｜负责人：{t.get('owner')}"
            )
        if decision.get("summary"):
            lines.append(f"小结：{decision['summary']}")

    process = _data(skill_input, "process_explainer")
    steps = process.get("steps", [])
    if steps:
        has_content = True
        lines.append("")
        lines.append(f"二、{process.get('process_name', '相关流程')}")
        for s in steps:
            lines.append(f"{s.get('step_no')}. {s.get('action')}（负责人：{s.get('owner')}；预计：{s.get('expected_time')}）")

    policy = _data(skill_input, "policy_qa")
    if policy.get("found"):
        has_content = True
        lines.append("")
        lines.append("三、相关制度说明")
        for p in policy.get("referenced_policies", []):
            lines.append(f"· {p.get('name')} {p.get('version')}（{p.get('effective_date')} 生效）")
        lines.append(str(policy.get("answer", "")).split("注：")[0].strip())
    elif "policy_qa" in skill_input and not policy.get("found"):
        has_content = True
        lines.append("")
        lines.append("三、相关制度说明")
        lines.append("当前系统未查询到相关制度，建议你联系 HR 对接人确认。")

    trainings = _data(skill_input, "query_trainings")
    trs = [t for t in (trainings.get("trainings", []) or []) if t.get("required") and not t.get("completed")]
    if trs:
        has_content = True
        lines.append("")
        lines.append("四、你还需要完成的必修培训")
        for t in trs[:3]:
            lines.append(f"· {t.get('name')}｜时间：{t.get('scheduled_time')}｜形式：{t.get('format')}｜负责人：{t.get('owner')}")

    contacts = _data(skill_input, "query_contacts")
    cls = contacts.get("contacts", []) or []
    if cls:
        has_content = True
        lines.append("")
        lines.append("五、你可以联系的人")
        for c in cls[:4]:
            lines.append(f"· {c.get('name')}（{c.get('title')}）｜邮箱：{c.get('email')}｜电话：{c.get('phone')}")

    if not has_content:
        lines.append("")
        lines.append("当前系统未查询到与该问题直接相关的信息，建议你联系 HR 对接人进一步确认。")

    lines.append("")
    lines.append("以上信息以系统内最新数据为准，涉及个人具体安排请以 HR 或直属领导确认为准。如还有其他问题，随时问我。")

    return {"reply": "\n".join(lines)}


def _mock_compliance_check(skill_input: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    draft = str(skill_input.get("draft_reply") or skill_input.get("reply") or "")
    q = _question(skill_input)
    emp = _emp(skill_input, ctx)
    own_name = emp.get("name", "")

    # 审核对象是助手生成的内容：排除对用户问题原文的引用，避免误判
    audit_text = draft.replace(q, "") if q else draft

    issues: List[str] = []
    suggestions: List[str] = []

    # 1. 其他员工姓名泄露
    for e in load_employees():
        other = e.get("name", "")
        if other and other != own_name and other in audit_text:
            issues.append(f"回复中出现其他员工姓名「{other}」，涉嫌泄露他人个人信息。")
            suggestions.append("移除其他员工的姓名与个人信息。")

    # 2. 内部技术信息泄露
    found_jargon = [w for w in JARGON_WORDS if w in audit_text]
    if found_jargon:
        issues.append(f"回复泄露系统内部技术信息（出现：{'、'.join(found_jargon[:5])}）。")
        suggestions.append("移除 Planner / Skill / Tool / JSON 等内部执行细节。")

    # 3. 薪资等敏感数字
    if re.search(r"(薪资|工资|月薪|底薪|薪水)[^\n]{0,12}\d+", audit_text):
        issues.append("回复中出现具体薪资数字，存在敏感信息泄露风险。")
        suggestions.append("移除具体薪资数字，如需说明请引导员工联系 HR。")

    # 4. 不当承诺
    if _has_any(audit_text, PROMISE_WORDS) and _has_any(q + audit_text, SENSITIVE_KEYWORDS):
        issues.append("对薪酬、社保、公积金等敏感事项作出了确定性承诺。")
        suggestions.append("改为提示“以 HR 确认为准”，避免确定性承诺。")

    # 5. 制度问答无数据但未声明
    policy = _data(skill_input, "policy_qa")
    if skill_input.get("policy_qa") is not None and policy.get("found") is False and "未查询到" not in draft:
        issues.append("制度查询无结果，但回复未明确说明“未查询到相关信息”，存在编造风险。")
        suggestions.append("明确告知员工当前系统未查询到相关制度。")

    # 6. 敏感话题标记
    sensitive = _has_any(q, SENSITIVE_KEYWORDS)

    if any("泄露" in i and "内部技术" not in i for i in issues) or any("编造" in i for i in issues):
        risk_level = "high"
    elif issues or sensitive:
        risk_level = "medium"
    else:
        risk_level = "low"

    passed = risk_level != "high"
    if passed and not issues:
        suggestions.append("回复内容基于当前可查询的入职任务、制度与联系人数据生成，未发现明显合规风险。")
        if sensitive:
            suggestions.append("该问题涉及敏感政策，回复已避免确定性承诺，请注意保持口径。")

    final_reply = sanitize_reply(draft) if (issues and passed) else draft
    if not passed:
        final_reply = sanitize_reply(draft)

    return {
        "risk_level": risk_level,
        "passed": passed,
        "issues": issues,
        "suggestions": suggestions,
        "final_reply": final_reply,
    }


_MOCK_IMPLS = {
    "question_structuring": _mock_question_structuring,
    "task_decision": _mock_task_decision,
    "process_explainer": _mock_process_explainer,
    "policy_qa": _mock_policy_qa,
    "communication": _mock_communication,
    "compliance_check": _mock_compliance_check,
}


async def mock_output(skill_type: str, skill_input: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    impl = _MOCK_IMPLS.get(skill_type)
    if impl is None:
        return {"error": f"未知的 Skill 类型: {skill_type}"}
    return impl(skill_input or {}, ctx or {})
