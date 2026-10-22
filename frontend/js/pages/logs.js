// 执行日志页：日志列表 + 日志详情（复用 renderTrace 渲染完整执行轨迹）
import { get } from "../api.js";
import { esc, renderTrace } from "../components/trace.js";

export async function render(view) {
  const logs = await get("/logs");

  view.innerHTML = `
    <div class="page-head">
      <div class="page-title">执行日志</div>
      <div class="page-desc">每次用户提问都会产生一条执行日志，记录 Planner 计划、每一步 Skill / Tool 的输入输出、最终回复与风控审核结果。点击行查看完整执行轨迹。</div>
    </div>
    <div class="card">
      ${logs.length ? `<table class="tbl">
        <thead><tr>
          <th>时间</th><th>日志编号</th><th>员工</th><th>问题</th>
          <th>风险审核</th><th>步骤</th><th>耗时</th><th>模式</th>
        </tr></thead>
        <tbody>${logs.map(logRow).join("")}</tbody>
      </table>` : `<div class="empty">暂无执行日志。前往 <a href="#/">Agent 执行台</a> 提问后即可生成。</div>`}
    </div>`;

  view.querySelectorAll(".log-row").forEach(tr => {
    tr.addEventListener("click", () => { location.hash = `#/logs/${tr.dataset.id}`; });
  });
}

function riskBadge(level, passed) {
  const cls = level === "high" ? "fail" : level === "medium" ? "warn" : level === "low" ? "ok" : "dim";
  return `<span class="badge ${cls}">${esc(level || "unknown")}</span>
          <span class="badge ${passed ? "ok" : "fail"}">${passed ? "通过" : "不通过"}</span>`;
}

function logRow(l) {
  return `
    <tr class="log-row" data-id="${esc(l.log_id)}" style="cursor:pointer">
      <td style="white-space:nowrap;font-size:12px">${esc(l.created_at)}</td>
      <td style="font-family:var(--mono);font-size:12px">${esc(l.log_id)}</td>
      <td>${esc(l.employee_name || "")} <span style="color:var(--text-dim);font-size:11px;font-family:var(--mono)">${esc(l.employee_id || "")}</span></td>
      <td style="max-width:320px">${esc(l.question)}</td>
      <td>${riskBadge(l.risk_level, l.passed)}</td>
      <td>${l.step_count ?? "-"}</td>
      <td>${l.duration_ms ?? "-"} ms</td>
      <td>${l.mock_mode ? `<span class="badge warn">Mock</span>` : `<span class="badge ok">大模型</span>`}</td>
    </tr>`;
}

export async function renderDetail(view, logId) {
  const r = await get(`/logs/${logId}`);
  view.innerHTML = `
    <a class="back-link" href="#/logs">← 返回执行日志</a>
    <div class="page-head">
      <div class="page-title">执行日志详情 <span class="badge dim">${esc(r.log_id)}</span></div>
      <div class="page-desc">用户问题「${esc(r.question)}」的完整执行轨迹（Planner 计划 → 逐步执行 → 最终回复 → 风控审核）。</div>
    </div>
    ${renderTrace(r)}`;
}
