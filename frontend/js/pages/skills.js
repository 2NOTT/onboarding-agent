import { get, put } from "../api.js";
import { esc, jsonBlock } from "../components/trace.js";

export async function render(view) {
  const skills = await get("/skills");

  view.innerHTML = `
    <div class="page-head">
      <div class="page-title">Skill 管理</div>
      <div class="page-desc">配置入职助手可调用的 Skill。保存后前台 Planner 与 Executor 立即使用最新配置；禁用后的 Skill 不会被 Planner 生成到计划中，即使手动传入 Executor 也会被拒绝执行。</div>
    </div>
    <div id="skill-list">
      ${skills.map(skillCard).join("")}
    </div>
  `;

  view.querySelectorAll("[data-toggle]").forEach(el => {
    el.addEventListener("click", async () => {
      const id = el.dataset.toggle;
      const enabled = el.dataset.enabled !== "true";
      try {
        await put(`/skills/${id}`, { enabled });
        render(view);
      } catch (e) { alert(e.message); }
    });
  });

  view.querySelectorAll("[data-expand]").forEach(el => {
    el.addEventListener("click", () => {
      const body = view.querySelector(`#detail-${el.dataset.expand}`);
      body.style.display = body.style.display === "none" ? "block" : "none";
    });
  });
}

function skillCard(s) {
  const mp = s.model_params || {};
  return `
    <div class="card">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <span class="badge dim">${esc(s.skill_id)}</span>
        <b style="font-size:15px">${esc(s.name)}</b>
        <span class="badge skill">${esc(s.type)}</span>
        <span class="badge ${s.enabled ? "on" : "off"}">${s.enabled ? "已启用" : "已禁用"}</span>
        <span style="color:var(--text-dim);font-size:12px;font-family:var(--mono)">
          model: ${esc(mp.model || "全局默认")} · temp: ${mp.temperature} · max_tokens: ${mp.max_tokens}
        </span>
        <span class="actions" style="margin-left:auto">
          <button class="btn ghost small" data-toggle="${esc(s.skill_id)}" data-enabled="${s.enabled}">
            ${s.enabled ? "禁用" : "启用"}
          </button>
          <button class="btn ghost small" data-expand="${esc(s.skill_id)}">详情</button>
          <a href="#/skills/${esc(s.skill_id)}/edit"><button class="btn ghost small">编辑</button></a>
          <a href="#/skills/${esc(s.skill_id)}/test"><button class="btn ghost small">测试</button></a>
        </span>
      </div>
      <p style="color:var(--text-dim);font-size:13px;margin-top:10px">${esc(s.description)}</p>
      <div id="detail-${esc(s.skill_id)}" style="display:none;margin-top:14px">
        <div class="io-label">Skill Prompt（保存于 skills.json，可编辑）</div>
        <div class="prompt-pre">${esc(s.prompt)}</div>
        ${lastTestHtml(s.last_test)}
      </div>
    </div>`;
}

function lastTestHtml(lt) {
  if (!lt) return `<div class="io-label">最近一次测试：<span style="color:var(--text-dim)">尚未测试</span></div>`;
  return `
    <div class="io-label">最近一次测试 <span class="badge ${lt.success ? "ok" : "fail"}">${lt.success ? "成功" : "失败"}</span>
      <span style="color:var(--text-dim);font-size:11.5px;margin-left:8px">${esc(lt.tested_at)} · ${esc(lt.engine)} · ${lt.elapsed_ms}ms</span>
    </div>
    <div class="io-label" style="font-weight:400">测试输入</div>
    ${jsonBlock(lt.input, true)}
    <div class="io-label" style="font-weight:400">测试输出</div>
    ${jsonBlock(lt.output, true)}
    ${lt.error ? `<div class="step-error">⚠ ${esc(lt.error)}</div>` : ""}`;
}
