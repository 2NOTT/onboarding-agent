// Skill 编辑页：编辑名称 / 描述 / Prompt / 模型参数 / 启用状态，保存后立即写入 skills.json
import { get, put } from "../api.js";
import { esc } from "../components/trace.js";
import { showToast } from "../components/toast.js";

export async function render(view, skillId) {
  const s = await get(`/skills/${skillId}`);
  const mp = s.model_params || {};

  view.innerHTML = `
    <a class="back-link" href="#/skills">← 返回 Skill 管理</a>
    <div class="page-head">
      <div class="page-title">编辑 Skill <span class="badge dim">${esc(s.skill_id)}</span></div>
      <div class="page-desc">保存后立即写入 skills.json —— 前台 Planner 与 Executor 在下一次执行时即刻使用最新配置（JSON 每次执行都会重新读取，无需重启服务）。</div>
    </div>
    <div class="card">
      <div class="row">
        <label class="fld"><span>Skill 名称</span>
          <input type="text" id="f-name" value="${esc(s.name)}" /></label>
        <label class="fld"><span>Skill 类型（type，系统内置标识，不可修改）</span>
          <input type="text" value="${esc(s.type)}" disabled /></label>
      </div>
      <label class="fld"><span>Skill 描述</span>
        <input type="text" id="f-desc" value="${esc(s.description)}" /></label>
      <label class="fld"><span>Skill Prompt（大模型模式的系统提示词；Mock 模式下仅作配置演示，不参与生成）</span>
        <textarea id="f-prompt" class="mono" rows="10">${esc(s.prompt)}</textarea></label>
      <div class="row">
        <label class="fld"><span>模型名称（留空使用 .env 中的全局默认模型）</span>
          <input type="text" id="f-model" value="${esc(mp.model || "")}" placeholder="例如 gpt-4o-mini" /></label>
        <label class="fld"><span>temperature（0 ~ 2）</span>
          <input type="number" id="f-temp" min="0" max="2" step="0.1" value="${mp.temperature}" /></label>
        <label class="fld"><span>max_tokens（64 ~ 8192）</span>
          <input type="number" id="f-maxtok" min="64" max="8192" step="1" value="${mp.max_tokens}" /></label>
      </div>
      <label class="fld" style="display:flex;align-items:center;gap:10px">
        <input type="checkbox" id="f-enabled" ${s.enabled ? "checked" : ""} style="width:auto" />
        <span style="margin:0;font-size:13px;color:var(--text)">启用该 Skill（禁用后 Planner 不会将其生成到计划中，手动传入 Executor 也会被拒绝执行）</span>
      </label>
      <div style="display:flex;gap:10px;margin-top:6px">
        <button class="btn" id="save-btn">保存配置</button>
        <a href="#/skills/${esc(s.skill_id)}/test"><button class="btn ghost">前往测试</button></a>
      </div>
    </div>`;

  view.querySelector("#save-btn").addEventListener("click", async (e) => {
    const btn = e.target;
    btn.disabled = true;
    try {
      await put(`/skills/${skillId}`, {
        name: view.querySelector("#f-name").value.trim(),
        description: view.querySelector("#f-desc").value.trim(),
        prompt: view.querySelector("#f-prompt").value,
        model_params: {
          model: view.querySelector("#f-model").value.trim(),
          temperature: parseFloat(view.querySelector("#f-temp").value),
          max_tokens: parseInt(view.querySelector("#f-maxtok").value, 10),
        },
        enabled: view.querySelector("#f-enabled").checked,
      });
      showToast("Skill 配置已保存，前台执行立即生效");
      setTimeout(() => { location.hash = "#/skills"; }, 600);
    } catch (err) {
      showToast(err.message, "err");
      btn.disabled = false;
    }
  });
}
