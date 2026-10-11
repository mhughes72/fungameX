from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import run_migrations
from .jobs import start_scheduler_thread
from .logging_setup import setup_logging
from .routers import items, misc, posts, sources


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    run_migrations()
    # Without Redis there is no separate worker, so the API process schedules polls itself.
    if get_settings().jobs_mode == "thread":
        start_scheduler_thread()
    yield


app = FastAPI(title="X Post Generator", lifespan=lifespan)
app.include_router(misc.router)
app.include_router(sources.router)
app.include_router(items.router)
app.include_router(posts.router)
