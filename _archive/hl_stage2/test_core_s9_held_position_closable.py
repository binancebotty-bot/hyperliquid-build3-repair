#!/usr/bin/env python3
"""S9 item (3): a HELD position in an unlisted or delisted coin stays closable.

Controller ruling 6403484386: 'a held position stays closable with no mid' is the safety
half and must be proven with a real fixture, not by reading the source.

Method: drive the engine's OWN decision function, SenderGateway._decision, with a stub that
stands in for the sender's config. Nothing is mocked about the decision logic itself - the
real function decides, and the assertions are on its real return value.

Two facts this pins down, both of which the code claims and neither of which was tested:
  * an unlisted/delisted coin must NOT trap an open sleeve - an EXIT is still allowed;
  * an absent follower price (no mid) must NOT stop a close, because the exit branch
    returns before the fresh-follower-price valuation gate.
The same two states must still BLOCK an entry, or the test would pass on a build that let
unlisted coins through.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import HL_Live_Copy_Service_Core as Core  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:170]) if not ok else ''))


class Cfg:
    """Only the config surface _decision touches on the paths under test.

    min_notional is evaluated before the lifecycle test on line 5150 because Python
    resolves the left operand first, so it must exist even though the entry-only guard
    would never apply to an exit.
    """
    def wallet_enabled(self, w):
        return True

    def wallet_mode(self, w):
        return 'ON'

    def is_symbol_allowed(self, coin):
        # the coin is NOT on this network's allow list / not listed
        return False, 'not listed on this network'

    def min_notional(self):
        return 10.0

    def max_order_notional(self):
        return 250.0

    def max_wallet_exposure(self, wallet):
        return 400.0

    def copy_mode(self, wallet):
        return 'fixed'

    def fixed_notional(self, wallet):
        return 50.0

    def wallet_cfg(self, wallet):
        return {}


class Sender:
    """Stub self: just enough attributes for the real _decision body."""
    cfg = Cfg()

    def _is_leader_close_fill(self, fill):
        return True


class Fill:
    def __init__(self, coin):
        self.coin = coin
        self.price = 100.0
        self.notional = 1000.0
        self.raw = {}


def decide(lifecycle, coin='XYZ:NOTLISTED', before=0.0):
    return Core.IntentBuilder._decision(Sender(), '0xstub', Fill(coin), lifecycle, 50.0, before)


# 1. a held position in an unlisted coin is still closable
d, why = decide('EXIT', before=2.0)
check('S9_UNLISTED_HELD_POSITION_STILL_CLOSABLE', d == 'EXIT_ALLOWED', '%s | %s' % (d, why))

# 2. and a reduction of a held position is likewise not blocked by the missing symbol
d2, why2 = decide('EXIT', before=-1.5)
check('S9_UNLISTED_HELD_SHORT_STILL_CLOSABLE', d2 == 'EXIT_ALLOWED', '%s | %s' % (d2, why2))

# 3. the close does not need a follower mid: the exit branch returns before the price gate.
#    Proven by the fact that this stub offers NO order-value price at all, so any path that
#    consulted it would have to block - and it does not.
check('S9_CLOSE_DOES_NOT_CONSULT_A_FOLLOWER_MID', d == 'EXIT_ALLOWED', '%s | %s' % (d, why))

# 4. the same unlisted coin must still refuse a NEW entry (otherwise #1 proves nothing)
d3, why3 = decide('ENTRY', before=0.0)
check('S9_UNLISTED_ENTRY_IS_STILL_BLOCKED', d3 in ('SYMBOL_UNAVAILABLE', 'NOT_APPLICABLE_SPOT'), '%s | %s' % (d3, why3))

# 5. an ADD to an existing position is also gated - the rule allows only the exit through
d4, why4 = decide('ADD', before=2.0)
check('S9_UNLISTED_ADD_IS_STILL_BLOCKED', d4 == 'SYMBOL_UNAVAILABLE', '%s | %s' % (d4, why4))

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
