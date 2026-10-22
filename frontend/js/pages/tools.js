// Tool 管理页：展示 Tool 列表、数据源与输入参数，支持启用/禁用（保存后立即生效）
import { get, put } from "../api.js";
import { esc } from "../components/trace.js";
import { showToast } from "../components/toast.js";

export async function render(view) {
  const tools = await get("/tools");

  view.innerHTML = `
    <div class="page-head">
      <div class="page-title">Tool 管理</div>
      <div class="page-desc">Tool 负责所有事实数据查询（员工、任务、制度、联系人、培训）与纯代码计算。禁用后的 Tool 不会出现在前台可调用能力列表中，Planner 不会生成对应步骤，Executor 也会拒绝执行。启用状态保存到 tools.json，立即生效。</div>
    </div>
    <div class="card" style="padding:6px 16px">
      <table class="tbl">
        <thead><tr>
          <th style="width:190px">Tool</th>
          <th style="width:170px">数据源</th>
          <th>说明</th>
          <th style="width:290px">输入参数</th>
          <th style="width:76px">状态</th>
          <th style="width:70px">操作</th>
        </tr></thead>
        <tbody>${tools.map(toolRow).join("")}</tbody>
      </table>
    </div>
    <div class="card">
      <h3>说明</h3>
      <ul class="plain" style="color:var(--text-dim);font-size:12.5px">
        <li>Tool 的业务逻辑由代码实现（backend/tools/），大模型不参与事实查询。</li>
        <li>query_employee_info 内置隐私保护：查询其他员工时拒绝返回详细信息，仅提供脱敏公开信息。</li>
        <li>calc_task_status 为纯代码实现：完成率、逾期、依赖阻塞、优先级排序均不依赖大模型。</li>
        <li>MVP 阶段 Tool 仅支持启用/禁用配置；如需扩展参数，编辑 backend/data/tools.json 并重启服务。</li>
      </ul>
    </div>`;

  view.querySelectorAll("[data-toggle]").forEach(el => {
    el.addEventListener("click", async () => {
      const name = el.dataset.toggle;
      const enabled = el.dataset.enabled !== "true";
      try {
        await put(`/tools/${name}`, { enabled });
        render(view);
      } catch (e) { showToast(e.message, "err"); }
    });
  });
}

function toolRow(t) {
  const params = Object.entries(t.input_params || {})
    .map(([k, v]) => `<div style="margin-bottom:4px"><span style="font-family:var(--mono);font-size:11.5px;color:var(--signal)">${esc(k)}</span><span style="color:var(--text-dim);font-size:11.5px"> — ${esc(v)}</span></div>`)
    .join("") || '<span style="color:var(--text-dim);font-size:12px">无参数</span>';
  return `
    <tr>
      <td>
        <b style="font-size:13.5px">${esc(t.display_name || t.name)}</b><br />
        <span style="font-family:var(--mono);font-size:11px;color:var(--text-dim)">${esc(t.tool_id)} · ${esc(t.name)}</span>
      </td>
      <td style="font-family:var(--mono);font-size:11.5px;color:var(--text-dim)">${esc(t.data_source)}</td>
      <td style="font-size:12.5px;color:var(--text-dim)">${esc(t.description)}</td>
      <td>${params}</td>
      <td><span class="badge ${t.enabled ? "on" : "off"}">${t.enabled ? "已启用" : "已禁用"}</span></td>
      <td>
        <button class="btn ghost small" data-toggle="${esc(t.name)}" data-enabled="${t.enabled}">
          ${t.enabled ? "禁用" : "启用"}
        </button>
      </td>
    </tr>`;
}
