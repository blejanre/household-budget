"""Password-protected household budget server."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.db import (
    connect,
    create_category,
    create_transaction,
    delete_transaction,
    init_db,
    list_categories,
    list_transactions,
    month_export_rows,
    month_groups,
    month_totals,
    set_category_hidden,
    update_transaction,
)
from app.money import (
    BudgetError,
    clean_name,
    clean_notes,
    parse_amount_cents,
    parse_date,
    parse_month,
)
from app.report import export_from, render_markdown, summary_from

STATIC_DIR = Path(__file__).resolve().parent / "static"
COOKIE_NAME = "budget_session"
SESSION_SECONDS = 60 * 60 * 24 * 60
PLACEHOLDER_PREFIX = "replace-with"


class PasswordBody(BaseModel):
    password: str = ""


class CategoryIn(BaseModel):
    name: str = ""
    kind: str = ""


class CategoryHidden(BaseModel):
    hidden: bool


class TransactionIn(BaseModel):
    date: str = ""
    amount: str = ""
    kind: str = ""
    category_id: int
    notes: str = ""


def load_dotenv() -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    seen: set[Path] = set()
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"]
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        for raw in resolved.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if key:
                os.environ.setdefault(key, value)


def require_config() -> None:
    missing = [name for name in ("APP_PASSWORD", "SESSION_SECRET") if not os.environ.get(name)]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            f"Missing {names}. Set them in the environment or a .env file. See .env.example."
        )
    password = os.environ["APP_PASSWORD"]
    secret = os.environ["SESSION_SECRET"]
    if password.startswith(PLACEHOLDER_PREFIX) or secret.startswith(PLACEHOLDER_PREFIX):
        raise RuntimeError("Replace the sample APP_PASSWORD and SESSION_SECRET before starting.")
    if len(secret) < 16:
        raise RuntimeError("SESSION_SECRET must be at least 16 characters.")


def _sign(message: str) -> str:
    secret = os.environ["SESSION_SECRET"].encode()
    return hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()


def make_token() -> str:
    message = f"v1:{int(time.time()) + SESSION_SECONDS}"
    return f"{message}.{_sign(message)}"


def valid_token(token: str) -> bool:
    message, separator, mac = token.rpartition(".")
    if not separator or not hmac.compare_digest(mac, _sign(message)):
        return False
    version, _, exp = message.partition(":")
    if version != "v1":
        return False
    try:
        return int(exp) > time.time()
    except ValueError:
        return False


def password_matches(given: str) -> bool:
    expected = os.environ["APP_PASSWORD"]
    return hmac.compare_digest(
        hashlib.sha256(given.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )


def cookie_secure() -> bool:
    return os.environ.get("COOKIE_SECURE") == "1"


def set_session_cookie(response: Response) -> None:
    response.set_cookie(
        COOKIE_NAME,
        make_token(),
        max_age=SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
    )


def require_user(request: Request) -> None:
    token = request.cookies.get(COOKIE_NAME, "")
    if not token or not valid_token(token):
        raise HTTPException(status_code=401, detail="Sign in required.")


def guarded(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BudgetError as exc:
            raise HTTPException(status_code=exc.status, detail=str(exc)) from exc

    return wrapper


def _parsed_entry(body: TransactionIn) -> dict:
    if body.kind not in {"income", "spending"}:
        raise BudgetError("Choose income or spending.")
    return {
        "day": parse_date(body.date),
        "amount_cents": parse_amount_cents(body.amount),
        "kind": body.kind,
        "category_id": body.category_id,
        "notes": clean_notes(body.notes),
    }


def _full_report(month: str) -> dict:
    with connect() as conn:
        return export_from(
            month,
            month_totals(conn, month),
            month_groups(conn, month),
            month_export_rows(conn, month),
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    require_config()
    init_db()
    yield


def create_app() -> FastAPI:
    load_dotenv()
    app = FastAPI(
        title="Household budget",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def no_store_api(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(status_code=204)

    @app.post("/api/login")
    @guarded
    def login(body: PasswordBody) -> JSONResponse:
        if len(body.password) > 200 or not password_matches(body.password):
            raise HTTPException(status_code=401, detail="That password is not right.")
        response = JSONResponse({"ok": True})
        set_session_cookie(response)
        return response

    @app.post("/api/logout")
    def logout() -> JSONResponse:
        response = JSONResponse({"ok": True})
        clear_session_cookie(response)
        return response

    @app.get("/api/session")
    def session(request: Request) -> dict:
        require_user(request)
        return {"ok": True}

    @app.get("/api/categories")
    @guarded
    def get_categories(request: Request) -> list[dict]:
        require_user(request)
        with connect() as conn:
            return list_categories(conn)

    @app.post("/api/categories", status_code=201)
    @guarded
    def post_category(body: CategoryIn, request: Request) -> dict:
        require_user(request)
        if body.kind not in {"income", "spending"}:
            raise BudgetError("Choose income or spending.")
        with connect() as conn:
            return create_category(conn, clean_name(body.name), body.kind)

    @app.patch("/api/categories/{category_id}")
    @guarded
    def patch_category(category_id: int, body: CategoryHidden, request: Request) -> dict:
        require_user(request)
        with connect() as conn:
            return set_category_hidden(conn, category_id, body.hidden)

    @app.get("/api/transactions")
    @guarded
    def get_transactions(request: Request, month: str) -> list[dict]:
        require_user(request)
        month = parse_month(month)
        with connect() as conn:
            return list_transactions(conn, month)

    @app.post("/api/transactions", status_code=201)
    @guarded
    def post_transaction(body: TransactionIn, request: Request) -> dict:
        require_user(request)
        with connect() as conn:
            return create_transaction(conn, **_parsed_entry(body))

    @app.patch("/api/transactions/{tx_id}")
    @guarded
    def patch_transaction(tx_id: int, body: TransactionIn, request: Request) -> dict:
        require_user(request)
        with connect() as conn:
            return update_transaction(conn, tx_id, **_parsed_entry(body))

    @app.delete("/api/transactions/{tx_id}", status_code=204)
    @guarded
    def remove_transaction(tx_id: int, request: Request) -> Response:
        require_user(request)
        with connect() as conn:
            delete_transaction(conn, tx_id)
        return Response(status_code=204)

    @app.get("/api/summary")
    @guarded
    def get_summary(request: Request, month: str) -> dict:
        require_user(request)
        month = parse_month(month)
        with connect() as conn:
            return summary_from(month, month_totals(conn, month), month_groups(conn, month))

    @app.get("/api/export")
    @guarded
    def export_month(
        request: Request,
        month: str,
        fmt: str = Query(alias="format"),
    ) -> Response:
        require_user(request)
        month = parse_month(month)
        report = _full_report(month)
        if fmt == "json":
            body = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            media = "application/json; charset=utf-8"
            filename = f"budget-{month}.json"
        elif fmt == "md":
            body = render_markdown(report)
            media = "text/markdown; charset=utf-8"
            filename = f"budget-{month}.md"
        else:
            raise BudgetError("Format must be md or json.")
        return Response(
            content=body,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
