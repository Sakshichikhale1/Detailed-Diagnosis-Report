from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from config import settings

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG_MODE)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve extracted images
app.mount("/api/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

from api import upload, process, export

app.include_router(upload.router, prefix="/api")
app.include_router(process.router, prefix="/api")
app.include_router(export.router, prefix="/api")
