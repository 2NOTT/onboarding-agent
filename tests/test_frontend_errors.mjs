import assert from "node:assert/strict";

const view = { innerHTML: "", offsetWidth: 0, classList: { add() {}, remove() {} } };
const badge = { classList: { add() {} }, style: {} };
globalThis.document = {
  getElementById: id => id === "view" ? view : badge,
  querySelectorAll: () => []
};
globalThis.window = { addEventListener() {} };
globalThis.location = { hash: "#/logs/%3Cimg%20src=x%20onerror=alert(1)%3E" };
globalThis.fetch = async url => ({
  ok: url === "/api/health",
  json: async () => url === "/api/health"
    ? { mock_mode: true, model: "mock" }
    : { detail: "未找到执行日志 <img src=x onerror=alert(1)>" }
});
await import("../frontend/js/app.js");
await new Promise(resolve => setImmediate(resolve));
assert.ok(view.innerHTML.includes("&lt;img src=x onerror=alert(1)&gt;"));
assert.ok(!view.innerHTML.includes("<img"));
console.log("Frontend API error rendering check passed: HTML payload is displayed as text.");
