// Exercise the shipped inline script with a minimal DOM and localStorage stub.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

async function main() {
  const root = path.resolve(__dirname, "..");
  const html = fs.readFileSync(path.join(root, "docs/index.html"), "utf8");
  const offline = fs.readFileSync(path.join(root, "docs/onboarding-demo.html"), "utf8");
  assert.equal(html, offline, "Online and offline pages must match.");
  assert.ok(html.includes("connect-src 'none'"));
  assert.ok(!/\bfetch\s*\(|XMLHttpRequest|new WebSocket/.test(html));
  const source = html.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/\nroute\(\);\s*$/, "");
  const storage = new Map();
  const listeners = {};
  const downloads = [];
  let link;
  const elements = {
    view: {}, toast: {},
    "export-config": { addEventListener(type, callback) { listeners.config = callback; } }
  };
  const context = vm.createContext({
    console, Blob, performance,
    localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
    document: {
      getElementById: id => elements[id],
      addEventListener(type, callback) { listeners.document = callback; },
      createElement() { link = { click() {}, remove() {} }; return link; },
      body: { appendChild() {} }
    },
    window: { addEventListener() {} },
    URL: { createObjectURL(blob) { downloads.push(blob); return "blob:local-demo"; }, revokeObjectURL() {} },
    setTimeout() { return 1; }, clearTimeout() {}
  });
  vm.runInContext(source + "\nglobalThis.demo = { execute, getLogs, esc, skills, SAFE_FALLBACK };", context);
  const demo = context.demo;
  const result = demo.execute("E001", "我入职第一天需要做什么？");
  assert.ok(result.final_reply && result.risk_result.passed);
  assert.ok(result.steps.some(step => step.target === "calc_task_status"));
  for (const step of result.plan.steps) {
    for (const dependency of step.depends_on) {
      assert.ok(result.plan.steps.findIndex(item => item.step_id === dependency) < result.plan.steps.indexOf(step));
    }
  }
  assert.ok(demo.esc('<script>"').includes("&lt;script&gt;&quot;"));
  listeners.config();
  const config = JSON.parse(await downloads.at(-1).text());
  assert.equal(config.format, "onboarding-capabilities/v1");
  assert.equal(config.skills.length, 6);
  assert.equal(config.tools.length, 7);
  assert.ok(config.skills.every(skill => !("last_test" in skill)));
  listeners.document({ target: { closest: () => ({ dataset: { exportLog: result.log_id } }) } });
  const record = JSON.parse(await downloads.at(-1).text());
  assert.equal(record.format, "onboarding-execution/v1");
  assert.equal(record.log_id, result.log_id);
  assert.equal(record.plan.steps.length, result.plan.steps.length);
  assert.equal(record.steps.length, result.steps.length);
  assert.equal(record.final_reply, result.final_reply);
  assert.ok(link.download.endsWith(".json"));
  const count = downloads.length;
  listeners.document({ target: { closest: () => ({ dataset: { exportLog: "missing" } }) } });
  assert.equal(downloads.length, count);
  demo.skills.find(skill => skill.type === "compliance_check").enabled = false;
  const blocked = demo.execute("E001", "公司请假制度是什么？");
  assert.equal(blocked.risk_result.passed, false);
  assert.equal(blocked.final_reply, demo.SAFE_FALLBACK);
  console.log("Static demo checks passed: task flow, dependencies, HTML escaping, config export, complete trace export, missing record, audit block, offline parity.");
}

main().catch(error => { console.error(error); process.exitCode = 1; });
