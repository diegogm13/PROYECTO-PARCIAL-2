// CRUD de usuarios
if (!session.token) window.location.href = "/index.html";

const form = document.getElementById("user-form");
const alertBox = document.getElementById("alert");
const rows = document.getElementById("rows");
const fields = {
  id: document.getElementById("user-id"),
  name: document.getElementById("name"),
  email: document.getElementById("email"),
  password: document.getElementById("password"),
  role: document.getElementById("role"),
  active: document.getElementById("active"),
};
let users = [];

document.querySelector("[data-testid=current-user]").textContent = session.user ? session.user.email : "";
document.getElementById("logout").addEventListener("click", () => {
  session.clear();
  window.location.href = "/index.html";
});
document.getElementById("cancel").addEventListener("click", resetForm);

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function render() {
  document.getElementById("count").textContent = users.length;
  rows.innerHTML = users.map((u) => `
    <tr data-testid="user-row" data-email="${escapeHtml(u.email)}">
      <td>${u.id}</td>
      <td data-testid="cell-name">${escapeHtml(u.name)}</td>
      <td data-testid="cell-email">${escapeHtml(u.email)}</td>
      <td><span class="badge ${u.role}" data-testid="cell-role">${u.role}</span></td>
      <td><span class="badge ${u.active ? "on" : "off"}" data-testid="cell-active">
        ${u.active ? "Activo" : "Inactivo"}</span></td>
      <td><div class="actions">
        <button class="secondary" data-action="edit" data-id="${u.id}" data-testid="edit-user">Editar</button>
        <button class="danger" data-action="delete" data-id="${u.id}" data-testid="delete-user">Eliminar</button>
      </div></td>
    </tr>`).join("");
}

async function load() {
  try {
    users = await api("/users");
    render();
  } catch (err) {
    showAlert(alertBox, err.message);
  }
}

function resetForm() {
  form.reset();
  fields.id.value = "";
  document.getElementById("form-title").textContent = "Nuevo usuario";
  document.getElementById("save").textContent = "Crear usuario";
  document.getElementById("pwd-hint").textContent = "(obligatoria)";
  document.getElementById("cancel").classList.add("hidden");
}

function startEdit(user) {
  fields.id.value = user.id;
  fields.name.value = user.name;
  fields.email.value = user.email;
  fields.password.value = "";
  fields.role.value = user.role;
  fields.active.value = String(user.active);
  document.getElementById("form-title").textContent = `Editar usuario #${user.id}`;
  document.getElementById("save").textContent = "Guardar cambios";
  document.getElementById("pwd-hint").textContent = "(dejar vacía para no cambiar)";
  document.getElementById("cancel").classList.remove("hidden");
  fields.name.focus();
}

rows.addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const user = users.find((u) => u.id === Number(btn.dataset.id));
  if (btn.dataset.action === "edit") return startEdit(user);
  if (!confirm(`¿Eliminar a ${user.name}?`)) return;
  try {
    await api(`/users/${user.id}`, { method: "DELETE" });
    showAlert(alertBox, "Usuario eliminado", "success");
    await load();
  } catch (err) {
    showAlert(alertBox, err.message);
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlert(alertBox);
  const body = {
    name: fields.name.value,
    email: fields.email.value,
    role: fields.role.value,
    active: fields.active.value === "true",
  };
  if (fields.password.value) body.password = fields.password.value;
  const id = fields.id.value;
  try {
    if (id) {
      await api(`/users/${id}`, { method: "PUT", body });
      showAlert(alertBox, "Usuario actualizado", "success");
    } else {
      await api("/users", { method: "POST", body });
      showAlert(alertBox, "Usuario creado", "success");
    }
    resetForm();
    await load();
  } catch (err) {
    showAlert(alertBox, err.message);
  }
});

load();
