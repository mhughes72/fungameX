"""Background job dispatch.

- rq:     REDIS_URL is set; jobs go to Redis and `python -m app.worker` runs them.
- thread: local dev; jobs run on a thread pool inside the API process.
- sync:   tests; jobs run inline.
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from .config import get_settings

log = logging.getLogger("app.jobs")

_pool: ThreadPoolExecutor | None = None
_queue = None


def _get_queue():
    global _queue
    if _queue is None:
        from redis import Redis
        from rq import Queue

        _queue = Queue("default", connection=Redis.from_url(get_settings().redis_url))
    return _queue


def _run_logged(fn, *args):
    try:
        fn(*args)
    except Exception:
        log.exception("job failed", extra={"job": fn.__name__, "args": args})


def enqueue(fn, *args) -> None:
    mode = get_settings().jobs_mode
    if mode == "sync":
        _run_logged(fn, *args)
    elif mode == "rq":
        _get_queue().enqueue(fn, *args, job_timeout=300)
    else:
        global _pool
        if _pool is None:
            _pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="job")
        _pool.submit(_run_logged, fn, *args)


def enqueue_due_polls() -> int:
    """Enqueue a poll for every active RSS source whose interval has elapsed."""
    from .db import SessionLocal
    from .models import Source
    from .services.ingest import poll_source

    now = datetime.now(timezone.utc)
    due = []
    with SessionLocal() as db:
        for s in db.query(Source).filter(Source.type == "rss", Source.active.is_(True)).all():
            last = s.last_polled_at
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last is None or now - last >= timedelta(minutes=max(10, s.poll_interval_min)):
                due.append(s.id)
    for sid in due:
        enqueue(poll_source, sid)
    return len(due)


def start_scheduler_thread() -> threading.Thread:
    tick = get_settings().scheduler_tick_s

    def loop():
        while True:
            try:
                n = enqueue_due_polls()
                if n:
                    log.info("scheduled polls", extra={"count": n})
            except Exception:
                log.exception("scheduler tick failed")
            time.sleep(tick)

    t = threading.Thread(target=loop, name="scheduler", daemon=True)
    t.start()
    return t
