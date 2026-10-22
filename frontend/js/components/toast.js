// 轻量 toast 提示（index.html 中已存在 #toast 元素）

export function showToast(msg, type = "ok") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = `toast show ${type === "err" ? "err" : ""}`;
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => { t.className = "toast"; }, 2600);
}
