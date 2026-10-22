// Skill 单独测试页：按 Skill 类型预填示例输入，运行后展示输出与引擎信息
import { get, post } from "../api.js";
import { esc, jsonBlock } from "../components/trace.js";
import { showToast } from "../components/toast.js";

// 各类型 Skill 的示例输入（未提供 employee 时后端自动注入 E001 作为演示上下文）
const SAMPLE_INPUTS = {
  question_structuring: {
    question: "我入职第一天需要做什么？",
  },
  task_decision: {
    question: "我前三十天需要完成哪些任务？",
    calc_task_status: {
      onboarding_progress: 0.45,
      pending_task_count: 6,
      overdue_task_count: 1,
      overdue_tasks: [],
      next_priority_tasks: [
        {
          task_id: "T001",
          task_name: "领取办公电脑并完成设备签收",
          priority: "P0",
          required: true,
          recommended_time: "入职当天上午",
          owner: "IT服务台",
          description: "携带工牌到 IT 服务台领取设备并完成签收。",
        },
      ],
    },
    query_onboarding_tasks: {
      tasks: [
        {
          task_id: "T001",
          task_name: "领取办公电脑并完成设备签收",
          priority: "P0",
          required: true,
          recommended_time: "入职当天上午",
          dependency_tasks: [],
          owner: "IT服务台",
          description: "携带工牌到 IT 服务台领取设备并完成签收。",
        },
      ],
    },
  },
  process_explainer: {
    question: "我的电脑和账号什么时候可以领取？",
    query_contacts: {
      contacts: [
        { name: "王建成", title: "IT服务台负责人", role: "it", email: "it.service@company.com" },
      ],
    },
  },
  policy_qa: {
    question: "公司请假制度是什么？",
    query_policies: {
      policies: [
        {
          policy_id: "P003",
          name: "请假管理制度",
          version: "v3.1",
          effective_date: "2026-01-01",
          scope: "全体员工",
          content: "员工请假需提前 1 个工作日在 OA 系统提交申请，1 天以内由直属领导审批，3 天以上需部门负责人加签。",
        },
      ],
    },
  },
  communication: {
    question: "我入职第一天需要做什么？",
    task_decision: {
      recommended_tasks: [
        {
          task_id: "T001",
          task_name: "领取办公电脑并完成设备签收",
          priority: "P0",
          required: true,
          recommended_time: "入职当天上午",
          owner: "IT服务台",
        },
      ],
      summary: "当前入职完成率约 45%，还有 6 项任务未完成。建议按优先级顺序推进。",
    },
  },
  compliance_check: {
    question: "公司请假制度是什么？",
    draft_reply:
      "你好！根据公司《请假管理制度 v3.1》，员工请假需提前 1 个工作日在 OA 系统提交申请，具体审批结果以直属领导确认为准。",
  },
};

export async function render(view, skillId) {
  const s = await get(`/skills/${skillId}`);
  const sample = SAMPLE_INPUTS[s.type] || { question: "我入职第一天需要做什么？" };

  view.innerHTML = `
    <a class="back-link" href="#/skills">← 返回 Skill 管理</a>
    <div class="page-head">
      <div class="page-title">测试 Skill
        <span class="badge dim">${esc(s.skill_id)}</span>
        <span class="badge skill">${esc(s.type)}</span>
        <span class="badge ${s.enabled ? "on" : "off"}">${s.enabled ? "已启用" : "已禁用"}</span>
      </div>
      <div class="page-desc">单独测试该 Skill：输入 JSON 直接传入 Skill 执行（与 Executor 内部调用方式一致）。未提供 employee 字段时自动注入员工 E001 作为演示上下文；测试记录会保存到 skills.json 的 last_test 字段。已禁用的 Skill 会被拒绝测试（与 Executor 行为一致）。</div>
    </div>
    <div class="card">
      <div class="io-label">Skill 输入 JSON（可编辑）</div>
      <textarea id="t-input" class="mono" rows="14">${esc(JSON.stringify(sample, null, 2))}</textarea>
      <div style="margin-top:12px;display:flex;gap:10px">
        <button class="btn" id="run-btn">▶ 运行测试</button>
        <button class="btn ghost" id="fill-btn">恢复示例输入</button>
      </div>
    </div>
    <div id="t-result"></div>`;

  view.querySelector("#fill-btn").addEventListener("click", () => {
    view.querySelector("#t-input").value = JSON.stringify(sample, null, 2);
  });

  view.querySelector("#run-btn").addEventListener("click", async (e) => {
    const btn = e.target;
    const box = view.querySelector("#t-result");
    let input;
    try {
      input = JSON.parse(view.querySelector("#t-input").value);
    } catch (err) {
      showToast("输入 JSON 解析失败：" + err.message, "err");
      return;
    }
    btn.disabled = true;
    btn.textContent = "运行中…";
    box.innerHTML = "";
    try {
      const r = await post(`/skills/${skillId}/test`, { input });
      box.innerHTML = `
        <div class="card">
          <h3>测试结果
            <span class="badge ${r.success ? "ok" : "fail"}">${r.success ? "成功" : "失败"}</span>
            <span class="cnt">${esc(r.engine)} 引擎 · ${r.elapsed_ms} ms</span>
          </h3>
          <div class="io-label">输出 JSON</div>
          ${jsonBlock(r.output)}
          ${r.error ? `<div class="step-error">${esc(r.error)}</div>` : ""}
          <p style="color:var(--text-dim);font-size:12px;margin-top:10px">最近一次测试的输入与输出已保存，可在 Skill 管理页「详情」中查看。</p>
        </div>`;
      showToast("测试完成");
    } catch (err) {
      // 例如：已禁用的 Skill 返回 400「已被禁用，拒绝测试」
      box.innerHTML = `
        <div class="card">
          <h3>测试被拒绝</h3>
          <div class="step-error">${esc(err.message)}</div>
        </div>`;
      showToast(err.message, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "▶ 运行测试";
    }
  });
}
