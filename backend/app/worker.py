"""Worker process for production (REDIS_URL set): schedules feed polls and runs RQ jobs.

Run with: python -m app.worker
"""
from redis import Redis
from rq import Queue, Worker

from .config import get_settings
from .db import run_migrations
from .jobs import start_scheduler_thread
from .logging_setup import setup_logging


def main() -> None:
    setup_logging()
    s = get_settings()
    if not s.redis_url:
        raise SystemExit("REDIS_URL is not set; locally the API runs jobs itself, no worker needed.")
    run_migrations()
    start_scheduler_thread()
    conn = Redis.from_url(s.redis_url)
    Worker([Queue("default", connection=conn)], connection=conn).work()


if __name__ == "__main__":
    main()
