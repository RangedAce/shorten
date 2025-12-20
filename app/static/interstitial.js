const cfg = window.INTERSTITIAL_CONFIG || {};
const btn = document.getElementById("continue-btn");
const countdownEl = document.getElementById("countdown");
const cookieBanner = document.getElementById("cookie-banner");
const cookieAccept = document.getElementById("cookie-accept");
const cookieRefuse = document.getElementById("cookie-refuse");
const cookieSettings = document.getElementById("cookie-settings");
const cookiePrefs = document.getElementById("cookie-preferences");
const cookieAds = document.getElementById("cookie-ads");
const cookieAnalytics = document.getElementById("cookie-analytics");
const cookieSave = document.getElementById("cookie-save");

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

function startCountdown() {
  let remaining = cfg.waitSeconds || 5;
  function tick() {
    countdownEl.textContent = `Redirection possible dans ${remaining} seconde(s)...`;
    if (remaining <= 0) {
      btn.classList.remove("hidden");
      btn.disabled = false;
      countdownEl.textContent = "Vous pouvez continuer.";
    } else {
      remaining -= 1;
      setTimeout(tick, 1000);
    }
  }
  tick();
}

btn?.addEventListener("click", () => {
  if (cfg.targetUrl) {
    window.location.href = cfg.targetUrl;
  }
});

startCountdown();
