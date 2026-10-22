const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  let data = {};
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || res.statusText);
    throw new Error(detail);
  }
  return data;
}

export const get = (p) => request(p);
export const post = (p, body) => request(p, { method: "POST", body });
export const put = (p, body) => request(p, { method: "PUT", body });
