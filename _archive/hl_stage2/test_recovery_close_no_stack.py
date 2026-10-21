import importlib.util
import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('core', HERE / 'HL_Live_Copy_Service_Core.py')
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


class Ledger:
    def __init__(self):
        self.position = {'signed_size': 0.027}

    def sleeve(self, wallet, coin):
        return self.position


class Audit:
    def __init__(self):
        self.rows = []

    def append_reconciliation(self, *args, **kwargs):
        self.rows.append((args, kwargs))


class Exchange:
    def __init__(self):
        self.orders = {}
        self.next_oid = 63322509225
        self.cancelled = []
        self.fail_cancel = False
        self.fail_place = False

    def open_orders(self, coin):
        return [{'coin': coin, 'oid': oid, 'reduceOnly': True} for oid in self.orders]

    def cancel(self, coin, oid):
        if self.fail_cancel:
            return {'status': 'err'}
        self.cancelled.append(int(oid))
        self.orders.pop(int(oid), None)
        return {'status': 'ok'}

    def place(self, coin, is_buy, size, px, tif, reduce_only):
        if self.fail_place:
            return {'status': 'err'}
        oid = self.next_oid
        self.next_oid += 1
        self.orders[oid] = {'coin': coin, 'oid': oid, 'reduceOnly': reduce_only, 'px': px}
        return {'status': 'ok', 'oid': oid}


def gateway(exchange):
    gw = core.SenderGateway.__new__(core.SenderGateway)
    gw.ledger = Ledger()
    gw.audit = Audit()
    gw.cfg = SimpleNamespace(marketable_bps=lambda: 20.0)
    gw._untradeable_coins = {}
    gw._recovery_orders = {}
    gw._recovery_backoff = {}
    gw._recovery_next_attempt_ms = {}
    gw._place_order = lambda _exchange, coin, is_buy, size, px, tif, reduce_only: exchange.place(coin, is_buy, size, px, tif, reduce_only)
    gw._parse_hl_response = lambda response: (response.get('status') == 'ok', response.get('status', ''), response.get('oid', ''), '')
    return gw


def intent():
    return SimpleNamespace(
        sleeve_id='sleeve-xyz-skhx', reduce_only_intended=True, copy_side='SELL', copy_size=0.027,
        fill=SimpleNamespace(leader_wallet='0x7717a7a2', leader_fill_id='f1', coin='XYZ:SKHX', price=893.01),
        intent_id='i1', position_id='p1',
    )


def queue(gw, exchange):
    gw._queue_exit_recovery_if_needed(exchange, 'XYZ:SKHX', intent(), 893.01, 0.027, {}, 'IOC_NO_IMMEDIATE_MATCH')


def test_eight_cycle_trace_never_stacks():
    exchange = Exchange()
    gw = gateway(exchange)
    core.BOOK_FETCHER = lambda coin: {'bid': 893.00, 'ask': 893.02}
    for _ in range(8):
        gw._recovery_next_attempt_ms['sleeve-xyz-skhx'] = 0
        queue(gw, exchange)
        assert len(exchange.orders) <= 1
    assert len(exchange.orders) == 1
    assert len(exchange.cancelled) == 7
    assert exchange.orders[next(iter(exchange.orders))]['px'] == 893.0


def test_restart_and_cancel_failure_fail_closed():
    exchange = Exchange()
    exchange.orders[63322509225] = {'coin': 'XYZ:SKHX', 'oid': 63322509225, 'reduceOnly': True}
    gw = gateway(exchange)
    core.BOOK_FETCHER = lambda coin: {'bid': 893.00, 'ask': 893.02}
    queue(gw, exchange)
    assert exchange.cancelled == [63322509225]
    assert len(exchange.orders) == 1
    exchange.fail_cancel = True
    gw._recovery_next_attempt_ms['sleeve-xyz-skhx'] = 0
    before = set(exchange.orders)
    queue(gw, exchange)
    assert set(exchange.orders) == before


def test_backoff_grows_caps_and_blocks_failed_producer_retry():
    gw = gateway(Exchange())
    delays = [gw._recovery_backoff_delay('sleeve-xyz-skhx', True) for _ in range(8)]
    assert delays == sorted(delays)
    assert delays[0] < delays[-1] == core.SenderGateway.RECOVERY_BACKOFF_CAP_SEC
    exchange = Exchange()
    exchange.fail_place = True
    gw = gateway(exchange)
    core.BOOK_FETCHER = lambda coin: {'bid': 893.00, 'ask': 893.02}
    queue(gw, exchange)
    assert gw._recovery_next_attempt_ms['sleeve-xyz-skhx'] > 0
    before = len(exchange.orders)
    queue(gw, exchange)
    assert len(exchange.orders) == before


def test_no_book_is_counted_and_stops():
    exchange = Exchange()
    gw = gateway(exchange)
    core.BOOK_FETCHER = lambda coin: {'bid': 0, 'ask': 0}
    queue(gw, exchange)
    assert not exchange.orders
    assert gw._untradeable_coins['xyz:skhx'] == 'NO_BOOK'
    assert gw.audit.rows[-1][0][0] == 'BLOCKED_CLO_ENTRY_DISPATCH'


def test_no_book_preserves_existing_recovery():
    exchange = Exchange()
    exchange.orders[63322509225] = {'coin': 'XYZ:SKHX', 'oid': 63322509225, 'reduceOnly': True}
    gw = gateway(exchange)
    core.BOOK_FETCHER = lambda coin: {'bid': 0, 'ask': 0}
    queue(gw, exchange)
    assert set(exchange.orders) == {63322509225}
    assert not exchange.cancelled


def test_slippage_bound_and_successful_fill_clear_state():
    exchange = Exchange()
    gw = gateway(exchange)
    core.BOOK_FETCHER = lambda coin: {'bid': 890.0, 'ask': 890.2}
    queue(gw, exchange)
    assert not exchange.orders
    assert gw.audit.rows[-1][0][1] == 'EXIT_RECOVERY_PRICE_OUT_OF_BOUNDS'
    gw._recovery_backoff['sleeve-xyz-skhx'] = 3
    gw._recovery_next_attempt_ms['sleeve-xyz-skhx'] = 9999999999999
    gw._recovery_orders['sleeve-xyz-skhx'] = {'oid': 99}
    assert 'clear_recovery_state(intent.sleeve_id)' in inspect.getsource(core.SenderGateway._send_real)
    gw.clear_recovery_state('sleeve-xyz-skhx')
    assert not gw._recovery_backoff and not gw._recovery_next_attempt_ms and not gw._recovery_orders


if __name__ == '__main__':
    failed = 0
    for test in (test_eight_cycle_trace_never_stacks, test_restart_and_cancel_failure_fail_closed,
                 test_backoff_grows_caps_and_blocks_failed_producer_retry, test_no_book_is_counted_and_stops,
                 test_no_book_preserves_existing_recovery, test_slippage_bound_and_successful_fill_clear_state):
        try:
            test()
            print('PASS', test.__name__)
        except Exception as exc:
            failed += 1
            print('FAIL', test.__name__, type(exc).__name__, repr(exc))
    raise SystemExit(failed)

