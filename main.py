import uvicorn
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os

from config import settings
from core.database import init_db
from api.routes_webhook import router as webhook_router
from api.routes_auth import router as auth_router
from api.routes_rules import router as rules_router
from api.routes_logs import router as logs_router
from api.routes_settings import router as settings_router

# Setup logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    logger.info("Initializing SQLite database...")
    init_db()
    logger.info(f"Instagram Auto is running on http://{settings.HOST}:{settings.PORT}")
    logger.info(f"Webhook verify token: {settings.META_VERIFY_TOKEN}")
    yield
    # Shutdown
    logger.info("Shutting down Instagram Auto...")

app = FastAPI(
    title="Instagram Creator Automator API",
    description="Self-hosted Instagram Automation Suite with Official Meta Graph API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(webhook_router)
app.include_router(auth_router)
app.include_router(rules_router)
app.include_router(logs_router)
app.include_router(settings_router)

# Mount frontend directory for static assets and dashboard
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

from fastapi import Request, Response
from bot.webhook import verify_hub_token

from fastapi.responses import FileResponse

@app.get("/privacy")
async def privacy_policy():
    return FileResponse(os.path.join(frontend_dir, "privacy.html"))

@app.get("/data-deletion")
@app.get("/data_deletion")
async def data_deletion():
    return FileResponse(os.path.join(frontend_dir, "data_deletion.html"))

@app.get("/")
async def root(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if verify_hub_token(mode, token) and challenge:
        logger.info("Webhook verification received on / (root) -> returning challenge")
        return Response(content=challenge, media_type="text/plain")
    return RedirectResponse(url="/static/index.html")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
