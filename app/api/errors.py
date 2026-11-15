"""One error shape for every failure, plus a request id on every response.

Errors look like {"error": {"code": "...", "message": "...", "request_id": "..."}}. Unexpected
exceptions return a generic 500 without internals; the details go to the log with the request id.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.api")
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
          405: "method_not_allowed", 422: "invalid_request", 429: "rate_limited",
          502: "upstream_error", 503: "unavailable"}  # fmt: skip


def _body(request: Request, status: int, message, code: str | None = None) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    payload = {"error": {"code": code or _CODES.get(status, "error"), "message": message,
                         "request_id": rid}}  # fmt: skip
    return JSONResponse(payload, status_code=status)


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_and_log(request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request.state.request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        log.info(
            "%s %s -> %s in %d ms [%s]",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
            request.state.request_id,
        )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        response = _body(request, exc.status_code, exc.detail)
        for k, v in (exc.headers or {}).items():
            response.headers[k] = v
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(x) for x in e["loc"][1:]), "problem": e["msg"]}
            for e in exc.errors()
        ]
        return _body(request, 422, details)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.exception("unhandled error [%s]", getattr(request.state, "request_id", "-"))
        return _body(request, 500, "internal error", "internal_error")
