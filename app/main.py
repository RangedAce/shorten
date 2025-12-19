from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

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


class ShortenOut(BaseModel):
    code: str
    short_url: str
    inactivity_days: int


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
    asyncio.create_task(cleanup_loop())


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    tpl = jinja.get_template("index.html")
    return HTMLResponse(tpl.render())


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

    db.expire_inactive()

    recycled = db.recycle_one_inactive(target_url=url)
    if recycled is not None:
        return ShortenOut(
            code=recycled,
            short_url=short_url_for(request, recycled),
            inactivity_days=settings.inactivity_days,
        )

    max_tries = 30
    for _ in range(max_tries):
        code = generate_code(settings.code_length)
        if db.is_active_code(code):
            continue
        try:
            db.reuse_or_insert(code=code, target_url=url)
            return ShortenOut(
                code=code,
                short_url=short_url_for(request, code),
                inactivity_days=settings.inactivity_days,
            )
        except Exception:
            continue
    raise HTTPException(status_code=503, detail="Impossible de générer un code, réessaie.")


@app.get("/{code}")
def redirect(code: str) -> RedirectResponse:
    db.expire_inactive()
    row = db.get_active(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Lien introuvable ou expiré.")

    target = str(row["target_url"])
    if not is_http_url(target):
        raise HTTPException(status_code=410, detail="Lien invalide.")

    db.touch(code)
    return RedirectResponse(target, status_code=307)

