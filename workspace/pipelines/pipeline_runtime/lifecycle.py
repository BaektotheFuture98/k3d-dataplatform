"""Let Spark drain its active micro-batch when Kubernetes sends SIGTERM."""
import signal
from contextlib import contextmanager


@contextmanager
def stop_on_signal(query):
    previous = {}

    def stop(_signum, _frame):
        query.stop()

    for signum in (signal.SIGTERM, signal.SIGINT):
        previous[signum] = signal.signal(signum, stop)
    try:
        yield query
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
