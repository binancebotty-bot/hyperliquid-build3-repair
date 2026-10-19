"""Offline concurrency measurements for SenderGateway order-slot pacing.
Run with: python test_core_order_pacing.py
No real exchange SDK/order is used; FakeExchange.order records a nonce at call time.
"""
from __future__ import annotations
import os
import threading
import time
import tempfile
os.environ.update({'HL_LIVE_AUDIT_DIR': tempfile.mkdtemp(prefix='pacing_'),
                    'HL_LIVE_ENV_FILE': os.path.join(tempfile.gettempdir(), 'pacing-no-env'),
                    'HL_LEADER_NETWORK': 'mainnet', 'HL_FOLLOWER_NETWORK': 'testnet',
                    'HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS': '100'})
import HL_Live_Copy_Service_Core as c

class TimedLock:
    def __init__(self):
        self.lock = threading.Lock()
        self.samples = []
    def __enter__(self):
        self.lock.acquire()
        self.started = time.perf_counter_ns()
        return self
    def __exit__(self, *args):
        self.samples.append((time.perf_counter_ns() - self.started) / 1000)
        self.lock.release()

class FakeExchange:
    def __init__(self):
        self.mu = threading.Lock()
        self.calls = []
    def order(self, *args, **kwargs):
        with self.mu:
            nonce = len(self.calls) + 1
            self.calls.append((time.perf_counter_ns(), nonce))
        return {'response': {'data': {'statuses': ['resting']}}}


def run():
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    lock = TimedLock()
    gw._exchange_order_lock = lock
    ex = FakeExchange()
    barrier = threading.Barrier(32)
    errors = []
    def worker(i):
        try:
            barrier.wait()
            gw._place_order(ex, 'BTC', True, 0.001, 1.0, 'Ioc', False)
        except BaseException as exc:
            errors.append(repr(exc))
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(32)]
    for t in threads: t.start()
    for t in threads: t.join(8)
    assert not any(t.is_alive() for t in threads), 'workers timed out'
    assert not errors, errors
    observed = [(b[0]-a[0])/1e6 for a,b in zip(ex.calls, ex.calls[1:])]
    assert len(ex.calls) == 32
    assert min(observed) >= 80, min(observed)
    max_hold = max(lock.samples)
    assert max_hold < 1000, max_hold

    # A future cooldown must delay every order until its deadline. Fix the clock to a stable epoch
    # and use a real sleep; no exchange request is made beyond the stub.
    gw2 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    lock2 = TimedLock(); gw2._exchange_order_lock = lock2
    start = c.utc_now_ms()
    gw2._exchange_rate_limit_cooldown_until_ms = start + 120
    ex2 = FakeExchange()
    before = time.perf_counter()
    gw2._place_order(ex2, 'BTC', True, 0.001, 1.0, 'Ioc', False)
    elapsed_ms = (time.perf_counter()-before)*1000
    assert elapsed_ms >= 100, elapsed_ms
    margin = elapsed_ms - 120

    # Cancel path: instrument lock entry and ensure exchange.cancel receives normalized integer oid.
    class CancelExchange:
        def cancel(self, coin, oid): return (coin, oid)
    cancel_lock = TimedLock(); gw2._exchange_order_lock = cancel_lock
    # Bypass pacing wait's real time-dependent slot by replacing it with a no-op, preserving the
    # production lock acquisition path exactly.
    gw2._wait_exchange_order_slot = lambda: None
    result = gw2._cancel_order(CancelExchange(), 'BTC', '123')
    assert result == ('BTC', 123) and len(cancel_lock.samples) == 1

    # Cooldown contention: establish an active cooldown; 8 concurrent calls all reserve after the
    # same deadline except first, count calls whose elapsed duration includes a cooldown wait.
    gw3 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw3._exchange_order_lock = TimedLock()
    gw3._exchange_rate_limit_cooldown_until_ms = c.utc_now_ms() + 100
    ex3 = FakeExchange(); waited = []
    def cooldown_worker():
        before = time.perf_counter()
        gw3._place_order(ex3, 'BTC', True, .001, 1., 'Ioc', False)
        waited.append((time.perf_counter()-before)*1000 >= 80)
    ts = [threading.Thread(target=cooldown_worker) for _ in range(8)]
    for t in ts: t.start()
    for t in ts: t.join(5)
    assert len(waited) == 8
    strict = all(ex3.calls[i][1] < ex3.calls[i+1][1] for i in range(len(ex3.calls)-1))
    print('RESULT::pacing_32_count=%d min_spacing_ms=%.3f' % (len(observed)+1, min(observed)))
    print('RESULT::max_lock_hold_us=%.3f' % max_hold)
    print('RESULT::cooldown_margin_ms=%.3f' % margin)
    print('RESULT::cancel_lock_entries=%d cancel_result=%r' % (len(cancel_lock.samples), result))
    print('RESULT::nonce_count=%d fake_nonce_call_order_strict=%s' % (len(ex3.calls), strict))
    print('RESULT::cooldown_waited_count=%d of %d' % (sum(waited), len(waited)))
    print('NOTE::nonce values are stub-assigned at exchange.order call time; actual SDK signing nonce is not produced by this offline seam.')

if __name__ == '__main__': run()
