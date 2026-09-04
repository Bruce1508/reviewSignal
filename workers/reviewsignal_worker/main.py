"""Worker entrypoint. Listens on the shared RQ queue."""

import logging

from redis import Redis
from rq import Queue, Worker

from reviewsignal_api.core.config import get_settings
from reviewsignal_api.core.constants import DEFAULT_QUEUE_NAME


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    connection = Redis.from_url(get_settings().redis_url)
    Worker([Queue(DEFAULT_QUEUE_NAME, connection=connection)], connection=connection).work()


if __name__ == "__main__":
    main()
