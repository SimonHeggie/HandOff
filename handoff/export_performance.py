"""Low-overhead export timings; never changes artwork or requires a dependency."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import sys
import time

_CURRENT = ContextVar('compio_export_performance', default=None)


@contextmanager
def stage(name):
    report = _CURRENT.get()
    if report is None:
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        row = report['stages'].setdefault(name, dict(seconds=0.0, calls=0))
        row['seconds'] += time.perf_counter() - start
        row['calls'] += 1


def timed(name):
    def decorate(fn):
        @wraps(fn)
        def call(*args, **kwargs):
            with stage(name):
                return fn(*args, **kwargs)
        return call
    return decorate


def profile_export(fn):
    @wraps(fn)
    def call(job, *args, **kwargs):
        report = dict(stages={})
        token = _CURRENT.set(report)
        start = time.perf_counter()
        try:
            return fn(job, *args, **kwargs)
        finally:
            report['total_seconds'] = time.perf_counter() - start
            try:
                import resource
                divisor = 1024**2 if sys.platform == 'darwin' else 1024
                report['peak_process_rss_mib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / divisor
            except ImportError:
                pass
            job['_performance'] = report
            _CURRENT.reset(token)
    return call
