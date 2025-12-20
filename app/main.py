from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from .config import load_settings
from .db import Database
from .shortcodes import generate_code

settings = load_settings()
db = Database(settings)

app = FastAPI(title="shorten", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

jinja = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


class ShortenIn(BaseModel):
    url: str
    monetize: bool = False


class ShortenOut(BaseModel):
    code: str
    short_url: str
    inactivity_days: int


class AdminLoginIn(BaseModel):
    password: str


class NeverExpireIn(BaseModel):
    value: bool


class MonetizeIn(BaseModel):
    value: bool = Field(default=False)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


def is_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def request_base_url(request: Request) -> str:
    if settings.base_url:
        return settings.base_url
    return str(request.base_url).rstrip("/")


def short_url_for(request: Request, code: str) -> str:
    return f"{request_base_url(request)}/{code}"


ADS_DEFAULT = "google.com, pub-2136022203013779, DIRECT, f08c47fec0942fa0\n"
ADS_PATH = Path("ads.txt")
try:
    ADS_CONTENT = ADS_PATH.read_text(encoding="utf-8")
except Exception:
    ADS_CONTENT = ADS_DEFAULT


SESSION_COOKIE = "admin_session"
SESSION_DURATION = timedelta(days=7)


def _sign_session(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(
        settings.admin_secret.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded}.{sig}"


def _verify_session(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    encoded, sig = token.rsplit(".", 1)
    expected = hmac.new(
        settings.admin_secret.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    padding = "=" * (-len(encoded) % 4)
    try:
        payload_raw = base64.urlsafe_b64decode(encoded + padding)
        payload = json.loads(payload_raw)
    except Exception:
        return False
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return False
    if datetime.now(tz=UTC).timestamp() > exp:
        return False
    return payload.get("sub") == "admin"


def _create_session_token() -> str:
    exp = (datetime.now(tz=UTC) + SESSION_DURATION).timestamp()
    return _sign_session({"sub": "admin", "exp": exp})


def require_admin(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if not _verify_session(token):
        raise HTTPException(status_code=401, detail="Non autorisé.")


EXPIRE_INTERVAL = timedelta(minutes=5)
_expire_lock = Lock()
_last_expire_at: datetime | None = None
UTC = timezone.utc


def maybe_expire_inactive() -> None:
    """Throttle l'expiration pour éviter un UPDATE à chaque requête."""
    global _last_expire_at
    now = datetime.now(tz=UTC)
    with _expire_lock:
        if _last_expire_at and now - _last_expire_at < EXPIRE_INTERVAL:
            return
        db.expire_inactive()
        _last_expire_at = now


async def cleanup_loop() -> None:
    while True:
        try:
            db.expire_inactive()
        except Exception:
            # Ne pas tuer l'app sur un échec ponctuel.
            pass
        await asyncio.sleep(6 * 60 * 60)  # toutes les 6h


@app.on_event("startup")
async def _startup() -> None:
    db.init_schema()
    db.expire_inactive()
    global _last_expire_at
    _last_expire_at = datetime.now(tz=UTC)
    asyncio.create_task(cleanup_loop())


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    tpl = jinja.get_template("index.html")
    return HTMLResponse(tpl.render())


@app.get("/admin", response_class=HTMLResponse)
def admin_page() -> HTMLResponse:
    tpl = jinja.get_template("admin.html")
    return HTMLResponse(tpl.render())


@app.get("/cgu", response_class=HTMLResponse)
def cgu_page() -> HTMLResponse:
    tpl = jinja.get_template("cgu.html")
    return HTMLResponse(tpl.render())


@app.get("/ads.txt")
def ads_txt() -> Response:
    return Response(ADS_CONTENT or ADS_DEFAULT, media_type="text/plain")


@app.post("/api/shorten", response_model=ShortenOut)
def shorten(body: ShortenIn, request: Request) -> ShortenOut:
    raw = body.url.strip()
    url = raw
    if not is_http_url(url):
        if "://" not in url and "." in url and " " not in url:
            candidate = f"https://{url}"
            if is_http_url(candidate):
                url = candidate
        if not is_http_url(url):
            raise HTTPException(
                status_code=400, detail="URL invalide (http/https requis)."
            )

    maybe_expire_inactive()

    recycled = db.recycle_one_inactive(target_url=url, monetize=body.monetize)
    if recycled is not None:
        return ShortenOut(
            code=recycled,
            short_url=short_url_for(request, recycled),
            inactivity_days=settings.inactivity_days,
        )

    max_tries = 30
    for _ in range(max_tries):
        code = generate_code(settings.code_length)
        try:
            created = db.upsert_inactive_or_insert(
                code=code, target_url=url, monetize=body.monetize
            )
        except Exception:
            continue
        if not created:
            continue
        return ShortenOut(
            code=code,
            short_url=short_url_for(request, code),
            inactivity_days=settings.inactivity_days,
        )
    raise HTTPException(status_code=503, detail="Impossible de générer un code, réessaie.")


@app.get("/{code}")
def redirect(code: str) -> RedirectResponse:
    maybe_expire_inactive()
    row = db.get_active(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Lien introuvable ou expiré.")

    target = str(row["target_url"])
    if not is_http_url(target):
        raise HTTPException(status_code=410, detail="Lien invalide.")

    db.touch(code)
    if row.get("monetize"):
        tpl = jinja.get_template("interstitial.html")
        return HTMLResponse(
            tpl.render(target_url=target, code=code, wait_seconds=5),
            status_code=200,
        )
    return RedirectResponse(target, status_code=307)


@app.post("/admin/api/login")
def admin_login(body: AdminLoginIn) -> JSONResponse:
    if not db.verify_admin_password(body.password):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect.")
    token = _create_session_token()
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_DURATION.total_seconds()),
        httponly=True,
        samesite="lax",
    )
    return resp


@app.get("/admin/api/me")
def admin_me(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    return {"authenticated": _verify_session(token)}


@app.get("/admin/api/links")
def admin_links(_: None = Depends(require_admin)) -> dict:
    links = db.list_all_links()
    return {"links": links}


@app.post("/admin/api/links/{code}/delete")
def admin_delete_link(code: str, _: None = Depends(require_admin)) -> dict:
    ok = db.delete_link(code)
    if not ok:
        raise HTTPException(status_code=404, detail="Lien introuvable.")
    return {"deleted": True}


@app.post("/admin/api/links/{code}/never-expires")
def admin_never_expires(
    code: str, body: NeverExpireIn, _: None = Depends(require_admin)
) -> dict:
    ok = db.set_never_expires(code, body.value)
    if not ok:
        raise HTTPException(status_code=404, detail="Lien introuvable.")
    return {"updated": True, "value": body.value}


@app.post("/admin/api/links/{code}/monetize")
def admin_monetize(
    code: str, body: MonetizeIn, _: None = Depends(require_admin)
) -> dict:
    ok = db.set_monetize(code, body.value)
    if not ok:
        raise HTTPException(status_code=404, detail="Lien introuvable.")
    return {"updated": True, "value": body.value}


@app.post("/admin/api/password")
def admin_change_password(
    body: ChangePasswordIn, _: None = Depends(require_admin)
) -> dict:
    if not db.verify_admin_password(body.current_password):
        raise HTTPException(status_code=401, detail="Mot de passe actuel invalide.")
    if len(body.new_password) < 6:
        raise HTTPException(
            status_code=400, detail="Mot de passe trop court (min 6 caractères)."
        )
    new_hash = db._hash_password(body.new_password)
    db.set_admin_password_hash(new_hash)
    return {"updated": True}
