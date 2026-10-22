// SPA 入口：hash 路由 + 导航高亮 + 后端健康检查（Mock 模式标识）
import { get } from "./api.js";
import { esc } from "./components/trace.js";
import { render as renderAgent } from "./pages/agent.js";
import { render as renderSkills } from "./pages/skills.js";
import { render as renderTools } from "./pages/tools.js";
import { render as renderSkillEdit } from "./pages/skillEdit.js";
import { render as renderSkillTest } from "./pages/skillTest.js";
import { render as renderLogs, renderDetail as renderLogDetail } from "./pages/logs.js";

const view = document.getElementById("view");

function setNav(active) {
  document.querySelectorAll("#nav a").forEach(a => {
    a.classList.toggle("active", a.dataset.nav === active);
  });
}

async function checkHealth() {
  const badge = document.getElementById("mock-badge");
  try {
    const h = await get("/health");
    badge.textContent = h.mock_mode ? `Mock 模式 · ${h.model || "默认模型"}` : `已接入大模型 · ${h.model || ""}`;
    badge.classList.add(h.mock_mode ? "mock" : "live");
  } catch {
    badge.textContent = "后端服务未连接";
    badge.style.color = "var(--danger)";
  }
}

function render404() {
  setNav("");
  view.innerHTML = `
    <div class="card">
      <h3>404 · 页面不存在</h3>
      <p style="color:var(--text-dim)">请从左侧导航选择页面，或 <a href="#/">返回 Agent 执行台</a>。</p>
    </div>`;
}

async function route() {
  const parts = (location.hash.replace(/^#/, "") || "/").split("/").filter(Boolean);
  // 重放页面切换淡入动画
  view.classList.remove("page-enter");
  void view.offsetWidth;
  view.classList.add("page-enter");
  view.innerHTML = `<div class="card" style="color:var(--text-dim)">加载中…</div>`;
  try {
    if (parts.length === 0) { setNav("agent"); await renderAgent(view); return; }
    if (parts[0] === "skills" && parts.length === 1) { setNav("skills"); await renderSkills(view); return; }
    if (parts[0] === "tools" && parts.length === 1) { setNav("tools"); await renderTools(view); return; }
    if (parts[0] === "skills" && parts.length === 3 && parts[2] === "edit") { setNav("skills"); await renderSkillEdit(view, parts[1]); return; }
    if (parts[0] === "skills" && parts.length === 3 && parts[2] === "test") { setNav("skills"); await renderSkillTest(view, parts[1]); return; }
    if (parts[0] === "logs" && parts.length === 1) { setNav("logs"); await renderLogs(view); return; }
    if (parts[0] === "logs" && parts.length === 2) { setNav("logs"); await renderLogDetail(view, parts[1]); return; }
    render404();
  } catch (e) {
    view.innerHTML = `
      <div class="card">
        <h3>页面加载失败</h3>
        <div class="step-error">⚠ ${esc(e.message || e)}</div>
        <p style="margin-top:10px"><a href="#/">返回 Agent 执行台</a></p>
      </div>`;
  }
}

window.addEventListener("hashchange", route);
checkHealth();
route();
