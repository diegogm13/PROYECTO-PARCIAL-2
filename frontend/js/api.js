// Cliente mínimo de la API (NGINX envía /api/* al backend)
const TOKEN_KEY = "sa_token";
const USER_KEY = "sa_user";

const session = {
  get token() { return localStorage.getItem(TOKEN_KEY); },
  get user() {
    try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
  },
  save(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (session.token) headers.Authorization = `Bearer ${session.token}`;
  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  let payload = {};
  try { payload = await res.json(); } catch { /* respuesta sin JSON */ }
  if (res.status === 401 && session.token && !path.startsWith("/auth/login")) {
    session.clear();
    window.location.href = "/index.html?expired=1";
  }
  if (!res.ok) throw new Error(payload.error || `Error ${res.status}`);
  return payload.data;
}

function showAlert(el, message, type = "error") {
  el.textContent = message;
  el.className = `alert ${type}`;
}

function hideAlert(el) {
  el.className = "alert hidden";
}
