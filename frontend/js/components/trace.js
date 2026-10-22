// 共享的执行轨迹渲染器：Agent 执行页与日志详情页共用

export function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function jsonBlock(obj, collapsed = false) {
  let text;
  try { text = JSON.stringify(obj, null, 2); } catch { text = String(obj); }
  const html = `<pre class="json">${esc(text)}</pre>`;
  if (!collapsed) return html;
  return `<details class="io"><summary>展开 / 收起 JSON</summary>${html}</details>`;
}

function badge(type, target) {
  if (type === "tool") return `<span class="badge tool">TOOL</span>`;
  if (target === "compliance_check") return `<span class="badge fail">SKILL·风控</span>`;
  return `<span class="badge skill">SKILL</span>`;
}

function statusBadge(status) {
  const map = { success: ["ok", "成功"], failed: ["fail", "失败"], skipped: ["warn", "跳过"], pending: ["dim", "待执行"] };
  const [cls, label] = map[status] || ["dim", status];
  return `<span class="badge ${cls}">${label}</span>`;
}

function riskBadge(level, passed) {
  const cls = level === "high" ? "fail" : level === "medium" ? "warn" : level === "low" ? "ok" : "dim";
  return `<span class="badge ${cls}">风险等级：${esc(level || "unknown")}</span>
          <span class="badge ${passed ? "ok" : "fail"}">${passed ? "审核通过" : "审核不通过"}</span>`;
}

function engineLabel(engine) {
  const map = { llm: "大模型", mock: "Mock", mock_fallback: "大模型失败→Mock兜底", code: "代码" };
  return map[engine] || engine || "-";
}

export function renderTrace(r) {
  const emp = r.employee || {};
  const empHtml = `
    <div class="card">
      <h3>当前员工基础信息 <span class="cnt">${esc(emp.employee_id || "")}</span></h3>
      <div class="emp-grid">
        <div><span class="k">姓名</span>${esc(emp.name)}</div>
        <div><span class="k">部门</span>${esc(emp.department)}</div>
        <div><span class="k">岗位</span>${esc(emp.position)}</div>
        <div><span class="k">入职日期</span>${esc(emp.hire_date)}</div>
        <div><span class="k">入职阶段</span>${esc(emp.stage_label || emp.onboarding_stage)}</div>
        <div><span class="k">直属领导</span>${esc(emp.manager)}</div>
        <div><span class="k">HR对接人</span>${esc(emp.hr_contact)}</div>
        <div><span class="k">企业邮箱</span>${esc(emp.email)}</div>
      </div>
    </div>`;

  const skills = r.available_skills || [];
  const tools = r.available_tools || [];
  const capHtml = `
    <div class="card">
      <h3>本次执行可调用的能力 <span class="cnt">仅包含已启用项</span></h3>
      <div class="cap-list">
        <div>${skills.map(s => `<div class="cap-item"><b>${esc(s.name)}</b>${esc(s.description)}</div>`).join("") || '<div class="empty">无</div>'}</div>
        <div>${tools.map(t => `<div class="cap-item"><b>${esc(t.display_name || t.name)}</b>${esc(t.description)}</div>`).join("") || '<div class="empty">无</div>'}</div>
      </div>
    </div>`;

  const plan = r.plan || {};
  const planRows = (plan.steps || []).map(s => `
    <tr>
      <td style="font-family:var(--mono)">${esc(s.step_id)}</td>
      <td>${badge(s.type, s.target)}</td>
      <td style="font-family:var(--mono);font-size:12px">${esc(s.target)}</td>
      <td>${esc(s.name)}</td>
      <td style="color:var(--text-dim);font-size:12px">${esc(s.purpose)}</td>
      <td style="font-family:var(--mono);font-size:12px">${esc((s.depends_on || []).join(", ")) || "-"}</td>
    </tr>`).join("");
  const planHtml = `
    <div class="card">
      <h3>Planner 执行计划
        <span class="cnt">生成引擎：${esc(engineLabel(r.planner_engine))}</span>
      </h3>
      <p style="color:var(--text-dim);font-size:13px;margin-bottom:10px">${esc(plan.plan_summary || "")}</p>
      <table class="tbl">
        <thead><tr><th>步骤</th><th>类型</th><th>目标</th><th>名称</th><th>执行目标说明</th><th>依赖</th></tr></thead>
        <tbody>${planRows}</tbody>
      </table>
    </div>`;

  const stepsHtml = (r.steps || []).map(s => `
    <div class="step-card">
      <div class="step-head" onclick="this.parentElement.querySelector('.step-body').style.display =
        this.parentElement.querySelector('.step-body').style.display === 'none' ? 'block' : 'none'">
        <span class="sid">${esc(s.step_id)}</span>
        ${badge(s.type, s.target)}
        <span class="sname">${esc(s.name)}</span>
        <span class="target">${esc(s.target)}</span>
        <span class="right">
          ${s.engine ? `<span class="badge code">${esc(engineLabel(s.engine))}</span>` : ""}
          ${s.elapsed_ms ? `<span>${s.elapsed_ms} ms</span>` : ""}
          ${statusBadge(s.status)}
        </span>
      </div>
      <div class="step-body">
        ${s.purpose ? `<div class="step-purpose">目的 · ${esc(s.purpose)}</div>` : ""}
        <div class="io-label">输入 JSON</div>
        ${jsonBlock(s.input, true)}
        <div class="io-label">输出 JSON</div>
        ${s.output != null ? jsonBlock(s.output, true) : `<pre class="json">（无输出）</pre>`}
        ${s.error ? `<div class="step-error">${esc(s.error)}</div>` : ""}
      </div>
    </div>`).join("");

  const risk = r.risk_result || {};
  const riskHtml = `
    <div class="card">
      <h3>合规与风险审核结果</h3>
      <div class="risk-grid">
        <div class="k">审核结论</div><div>${riskBadge(risk.risk_level, risk.passed)}</div>
        <div class="k">发现的问题</div>
        <div>${(risk.issues || []).length ? `<ul class="plain">${risk.issues.map(i => `<li>${esc(i)}</li>`).join("")}</ul>` : '<span style="color:var(--text-dim)">无</span>'}</div>
        <div class="k">建议</div>
        <div>${(risk.suggestions || []).length ? `<ul class="plain">${risk.suggestions.map(i => `<li>${esc(i)}</li>`).join("")}</ul>` : "-"}</div>
      </div>
    </div>`;

  const warnHtml = ((r.warnings || []).length || (r.errors || []).length) ? `
    <div class="card">
      <h3>执行日志与异常信息</h3>
      <ul class="plain">
        ${(r.warnings || []).map(w => `<li style="color:var(--warn)">提示：${esc(w)}</li>`).join("")}
        ${(r.errors || []).map(w => `<li style="color:var(--danger)">异常：${esc(w)}</li>`).join("")}
      </ul>
    </div>` : "";

  return `
    <div class="meta-line">
      <span class="badge ${r.mock_mode ? "warn" : "ok"}">${r.mock_mode ? "Mock 模式" : "大模型模式"}</span>
      <span>日志编号：${esc(r.log_id || "-")}</span>
      <span>时间：${esc(r.created_at || "")}</span>
      <span>总耗时：${r.duration_ms ?? "-"} ms</span>
      <span>执行步骤：${(r.steps || []).length}</span>
    </div>
    ${empHtml}
    ${capHtml}
    ${planHtml}
    <div class="card"><h3>Executor 执行轨迹 <span class="cnt">点击卡片可折叠</span></h3>${stepsHtml}</div>
    <div class="card">
      <h3>最终生成的入职助手回复 <span class="cnt">已通过合规审核后才允许返回</span></h3>
      <div class="reply-box">${esc(r.final_reply)}</div>
    </div>
    ${riskHtml}
    ${warnHtml}
  `;
}
