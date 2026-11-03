import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount

from app.mcp_server.server import mcp


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

api_key = os.getenv("MCP_API_KEY", "").strip()
public_host = os.getenv("MCP_PUBLIC_HOST", "").strip()

if len(api_key) < 32:
    raise RuntimeError(
        "Set MCP_API_KEY to a generated secret of at least 32 characters."
    )

if (
    not public_host
    or "/" in public_host
    or ":" in public_host
    or "*" in public_host
):
    raise RuntimeError(
        "MCP_PUBLIC_HOST must be the exact forwarded hostname only."
    )

mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "127.0.0.1:*",
        "localhost:*",
        public_host,
        f"{public_host}:443",
    ],
    allowed_origins=[
        f"https://{public_host}",
    ],
)

mcp_http_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield


class ApiKeyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            supplied_key = headers.get(b"x-api-key", b"")

            if not secrets.compare_digest(
                supplied_key,
                api_key.encode("utf-8"),
            ):
                response = JSONResponse(
                    {"detail": "Unauthorized"},
                    status_code=401,
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


application = Starlette(
    routes=[
        Mount("/", app=mcp_http_app),
    ],
    lifespan=lifespan,
)

application.add_middleware(ApiKeyMiddleware)


if __name__ == "__main__":
    uvicorn.run(
        application,
        host="0.0.0.0",
        port=8001,
    )