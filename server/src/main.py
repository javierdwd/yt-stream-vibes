"""FastAPI app: mount routers for REST + SSE."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import health, lives, sessions, streams

load_dotenv()

app = FastAPI(title="yt-stream-vibes", version="0.1.0")

_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(lives.router)
app.include_router(streams.router)
app.include_router(sessions.router)
