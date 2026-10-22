import { get, post } from "../api.js";
import { esc } from "../components/trace.js";

const EXAMPLES = [
  "我入职第一天需要做什么？",
  "我需要准备哪些入职材料？",
  "我的电脑和账号什么时候可以领取？",
  "我应该联系谁办理工位和门禁？",
  "公司请假制度是什么？",
  "我所在岗位前三十天需要完成哪些任务？",
  "我的入职培训有哪些？",
  "我的社保、公积金什么时候开始缴纳？",
  "我需要加入哪些工作群？",
  "我的直属领导是谁？",
];

let employees = [];

export async function render(view) {
  employees = await get("/employees");
  const savedId = localStorage.getItem("employee_id");
  const currentId = employees.some(e => e.employee_id === savedId) ? savedId : employees[0].employee_id;
  localStorage.setItem("employee_id", currentId);

  view.innerHTML = `
    <div class="page-head">
      <div class="page-title">Agent 执行台</div>
      <div class="page-desc">选择模拟员工身份，输入入职相关问题。Planner 将生成执行计划，Executor 逐步调用 Skill 与 Tool，最终回复经合规审核后返回。</div>
    </div>

    <div class="card">
      <div class="row" style="align-items:flex-end">
        <label class="fld" style="max-width:320px">
          <span>模拟员工身份</span>
          <select id="emp-select">
            ${employees.map(e => `<option value="${esc(e.employee_id)}" ${e.employee_id === currentId ? "selected" : ""}>
              ${esc(e.employee_id)} · ${esc(e.name)} · ${esc(e.department)} · ${esc(e.stage_label || e.onboarding_stage)}</option>`).join("")}
          </select>
        </label>
        <label class="fld" style="flex:2">
          <span>你的问题</span>
          <textarea id="question" placeholder="例如：我入职第一天需要做什么？"></textarea>
        </label>
      </div>
      <div class="chips" id="chips">
        ${EXAMPLES.map(q => `<span class="chip">${esc(q)}</span>`).join("")}
      </div>
      <div style="margin-top:14px">
        <button class="btn" id="run-btn">提交问题，开始执行</button>
        <span id="run-state" style="margin-left:12px;color:var(--text-dim);font-size:12.5px"></span>
      </div>
    </div>

    <div id="result"></div>
  `;

  view.querySelector("#chips").addEventListener("click", (e) => {
    if (e.target.classList.contains("chip")) view.querySelector("#question").value = e.target.textContent;
  });
  view.querySelector("#emp-select").addEventListener("change", (e) => {
    localStorage.setItem("employee_id", e.target.value);
  });
  view.querySelector("#run-btn").addEventListener("click", run);

  // 已有结果则不再重复渲染能力列表（结果里包含本次执行的能力快照）
}

async function run() {
  const employeeId = localStorage.getItem("employee_id");
  const question = view.querySelector("#question").value.trim();
  const btn = view.querySelector("#run-btn");
  const state = view.querySelector("#run-state");
  const result = view.querySelector("#result");

  if (!question) { state.textContent = "请先输入问题"; return; }
  btn.disabled = true;
  state.innerHTML = `<span class="spin"></span> Planner 正在生成执行计划…`;
  result.innerHTML = "";

  const t0 = Date.now();
  const timer = setInterval(() => {
    state.innerHTML = `<span class="spin"></span> 执行中… ${((Date.now() - t0) / 1000).toFixed(1)}s`;
  }, 100);

  try {
    const r = await post("/agent/execute", { employee_id: employeeId, question });
    const { renderTrace } = await import("../components/trace.js");
    result.innerHTML = renderTrace(r);
    state.textContent = `执行完成，耗时 ${(r.duration_ms / 1000).toFixed(1)}s`;
  } catch (e) {
    state.textContent = "";
    result.innerHTML = `<div class="card"><div class="step-error">执行失败：${esc(e.message)}</div></div>`;
  } finally {
    clearInterval(timer);
    btn.disabled = false;
  }
}
