const loginSection = document.getElementById("login-section");
const dashboard = document.getElementById("dashboard");
const passwordSection = document.getElementById("password-section");
const loginForm = document.getElementById("login-form");
const adminPasswordInput = document.getElementById("admin-password");
const errorBox = document.getElementById("admin-error");
const statsBox = document.getElementById("stats");
const refreshBtn = document.getElementById("refresh-btn");
const linksTableBody = document.querySelector("#links-table tbody");
const passwordForm = document.getElementById("password-form");
const currentPasswordInput = document.getElementById("current-password");
const newPasswordInput = document.getElementById("new-password");

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.textContent = "";
  errorBox.classList.add("hidden");
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

async function checkAuth() {
  const res = await fetch("/admin/api/me");
  const data = await res.json().catch(() => ({}));
  if (data?.authenticated) {
    loginSection.classList.add("hidden");
    dashboard.classList.remove("hidden");
    passwordSection.classList.remove("hidden");
    await loadLinks();
  } else {
    loginSection.classList.remove("hidden");
    dashboard.classList.add("hidden");
    passwordSection.classList.add("hidden");
  }
}

async function loadLinks() {
  clearError();
  try {
    const res = await fetch("/admin/api/links");
    if (res.status === 401) {
      loginSection.classList.remove("hidden");
      dashboard.classList.add("hidden");
      passwordSection.classList.add("hidden");
      return;
    }
    const data = await res.json();
    renderLinks(data.links || []);
  } catch (err) {
    showError("Impossible de charger les liens.");
  }
}

function renderLinks(links) {
  linksTableBody.innerHTML = "";
  if (!links.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.textContent = "Aucun lien pour l'instant.";
    row.appendChild(cell);
    linksTableBody.appendChild(row);
    statsBox.textContent = "";
    return;
  }

  const total = links.length;
  const active = links.filter((l) => l.active).length;
  const clicks = links.reduce((sum, l) => sum + (l.click_count || 0), 0);
  statsBox.textContent = `Total: ${total} | Actifs: ${active} | Clics: ${clicks}`;

  for (const link of links) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><strong>${link.code}</strong></td>
      <td class="truncate" title="${link.target_url}">${link.target_url}</td>
      <td>${formatDate(link.created_at)}</td>
      <td>${formatDate(link.last_access_at)}</td>
      <td>${link.click_count ?? 0}</td>
      <td>${link.monetize ? "Oui" : "Non"}</td>
      <td>${renderStatus(link)}</td>
      <td class="actions"></td>
    `;
    const actionsCell = row.querySelector(".actions");
    const toggleBtn = document.createElement("button");
    toggleBtn.className = "secondary small";
    toggleBtn.textContent = link.never_expires ? "Rendre expirables" : "Ne jamais expirer";
    toggleBtn.onclick = () => toggleNeverExpires(link.code, !link.never_expires);

    const monetizeBtn = document.createElement("button");
    monetizeBtn.className = "secondary small";
    monetizeBtn.textContent = link.monetize ? "Désactiver pub" : "Activer pub";
    monetizeBtn.onclick = () => toggleMonetize(link.code, !link.monetize);

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "secondary small danger";
    deleteBtn.textContent = "Supprimer";
    deleteBtn.onclick = () => deleteLink(link.code);

    actionsCell.append(toggleBtn, monetizeBtn, deleteBtn);
    linksTableBody.appendChild(row);
  }
}

function renderStatus(link) {
  const badge = document.createElement("span");
  badge.className = "badge";
  if (!link.active) {
    badge.textContent = "Expiré";
    badge.classList.add("badge-muted");
  } else if (link.never_expires) {
    badge.textContent = "Permanent";
    badge.classList.add("badge-success");
  } else {
    badge.textContent = "Actif";
    badge.classList.add("badge-primary");
  }
  return badge.outerHTML;
}

async function toggleNeverExpires(code, value) {
  clearError();
  try {
    const res = await fetch(`/admin/api/links/${code}/never-expires`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      showError(data?.detail || "Impossible de mettre à jour le lien.");
      return;
    }
    await loadLinks();
  } catch {
    showError("Erreur réseau.");
  }
}

async function deleteLink(code) {
  clearError();
  if (!confirm(`Supprimer le lien ${code} ?`)) return;
  try {
    const res = await fetch(`/admin/api/links/${code}/delete`, { method: "POST" });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      showError(data?.detail || "Impossible de supprimer le lien.");
      return;
    }
    await loadLinks();
  } catch {
    showError("Erreur réseau.");
  }
}

async function toggleMonetize(code, value) {
  clearError();
  try {
    const res = await fetch(`/admin/api/links/${code}/monetize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      showError(data?.detail || "Impossible de mettre à jour la monétisation.");
      return;
    }
    await loadLinks();
  } catch {
    showError("Erreur réseau.");
  }
}

loginForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  try {
    const res = await fetch("/admin/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: adminPasswordInput.value }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showError(data?.detail || "Connexion impossible.");
      return;
    }
    adminPasswordInput.value = "";
    await checkAuth();
  } catch {
    showError("Erreur réseau.");
  }
});

refreshBtn?.addEventListener("click", loadLinks);

passwordForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  try {
    const res = await fetch("/admin/api/password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: currentPasswordInput.value,
        new_password: newPasswordInput.value,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showError(data?.detail || "Impossible de mettre à jour le mot de passe.");
      return;
    }
    currentPasswordInput.value = "";
    newPasswordInput.value = "";
    alert("Mot de passe mis à jour.");
  } catch {
    showError("Erreur réseau.");
  }
});

checkAuth();
