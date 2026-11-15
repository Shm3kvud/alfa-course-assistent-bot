import logging
import os
import time

import psycopg

from rag.ingest import ingest

log = logging.getLogger("init-rag")


def pg_url() -> str:
    return os.environ["VECTOR_DATABASE_URL"].replace("+psycopg", "")


def wait_for_db(url: str, attempts: int = 60) -> None:
    for attempt in range(1, attempts + 1):
        try:
            with psycopg.connect(url, connect_timeout=5):
                return
        except Exception as exc:
            log.warning(
                "база не готова (%s), попытка %d/%d",
                exc,
                attempt,
                attempts,
            )
            time.sleep(2)
    raise SystemExit("база не поднялась за отведённое время")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    url = pg_url()
    wait_for_db(url)

    with psycopg.connect(url) as conn:
        table = conn.execute(
            "SELECT to_regclass('public.langchain_pg_embedding')"
        ).fetchone()[0]
        count = (
            conn.execute("SELECT count(*) FROM langchain_pg_embedding").fetchone()[0]
            if table
            else 0
        )

    if count:
        log.info("коллекция уже заполнена: %d документов", count)
        return

    log.info("коллекция пуста, запускаю ingest")
    ingest()
    log.info("ingest завершён")


if __name__ == "__main__":
    main()
