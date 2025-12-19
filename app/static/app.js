const form = document.getElementById("shorten-form");
const input = document.getElementById("url-input");
const shortenBtn = document.getElementById("shorten-btn");
const result = document.getElementById("result");
const shortUrlA = document.getElementById("short-url");
const meta = document.getElementById("meta");
const errorBox = document.getElementById("error");
const copyBtn = document.getElementById("copy-btn");

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.textContent = "";
  errorBox.classList.add("hidden");
}

function showResult(shortUrl, days) {
  shortUrlA.textContent = shortUrl;
  shortUrlA.href = shortUrl;
  meta.textContent = `Expire après ${days} jours sans utilisation.`;
  result.classList.remove("hidden");
}

copyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(shortUrlA.href);
    copyBtn.textContent = "Copié";
    setTimeout(() => (copyBtn.textContent = "Copier"), 900);
  } catch {
    showError("Impossible de copier automatiquement. Sélectionne et copie le lien.");
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  result.classList.add("hidden");
  shortenBtn.disabled = true;
  try {
    const res = await fetch("/api/shorten", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: input.value }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showError(data?.detail || "Erreur lors du raccourcissement.");
      return;
    }
    showResult(data.short_url, data.inactivity_days);
  } catch {
    showError("Erreur réseau.");
  } finally {
    shortenBtn.disabled = false;
  }
});

