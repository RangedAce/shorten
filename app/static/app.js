const form = document.getElementById("shorten-form");
const input = document.getElementById("url-input");
const shortenBtn = document.getElementById("shorten-btn");
const result = document.getElementById("result");
const shortUrlA = document.getElementById("short-url");
const meta = document.getElementById("meta");
const errorBox = document.getElementById("error");
const copyBtn = document.getElementById("copy-btn");
const monetizeCheckbox = document.getElementById("monetize-checkbox");
const cookieBanner = document.getElementById("cookie-banner");
const cookieAccept = document.getElementById("cookie-accept");
const cookieRefuse = document.getElementById("cookie-refuse");
const cookieSettings = document.getElementById("cookie-settings");
const cookiePrefs = document.getElementById("cookie-preferences");
const cookieAds = document.getElementById("cookie-ads");
const cookieAnalytics = document.getElementById("cookie-analytics");
const cookieSave = document.getElementById("cookie-save");

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
      body: JSON.stringify({
        url: input.value,
        monetize: monetizeCheckbox?.checked || false,
      }),
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

function setCookieConsent(preferences) {
  localStorage.setItem("cookie-consent", JSON.stringify(preferences));
}

function getCookieConsent() {
  try {
    return JSON.parse(localStorage.getItem("cookie-consent") || "{}");
  } catch {
    return {};
  }
}

function applyCookieState() {
  const prefs = getCookieConsent();
  if (prefs.choice === "accept" || prefs.choice === "refuse" || prefs.choice === "custom") {
    cookieBanner?.classList.add("hidden");
  } else {
    cookieBanner?.classList.remove("hidden");
  }
  if (cookieAds) cookieAds.checked = prefs.ads !== false;
  if (cookieAnalytics) cookieAnalytics.checked = prefs.analytics !== false;
}

cookieAccept?.addEventListener("click", () => {
  setCookieConsent({ choice: "accept", ads: true, analytics: true });
  applyCookieState();
});

cookieRefuse?.addEventListener("click", () => {
  setCookieConsent({ choice: "refuse", ads: false, analytics: false });
  applyCookieState();
});

cookieSettings?.addEventListener("click", () => {
  cookiePrefs?.classList.toggle("hidden");
});

cookieSave?.addEventListener("click", () => {
  setCookieConsent({
    choice: "custom",
    ads: cookieAds.checked,
    analytics: cookieAnalytics.checked,
  });
  applyCookieState();
});

applyCookieState();
