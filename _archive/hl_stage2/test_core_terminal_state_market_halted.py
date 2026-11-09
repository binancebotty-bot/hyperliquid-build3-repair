#!/usr/bin/env python3
"""A known reject category must never be reported as an UNKNOWN terminal state.

CC1 ruling 2026-11-09 (Boss-approved): `MARKET_HALTED` was absent from the ENTRY mapping in
`classify_terminal_state`, so it fell through `mapping.get(category, "MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN")`
and a KNOWN venue halt was recorded as an unknown rejection. In the R3 snapshot that produced two rows of
`MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN` with `reject_category=MARKET_HALTED` and
`error="Trading is halted."`, which a cert reader cannot distinguish from a genuinely unattributed reject.

FAILING FIRST on integration/r1-ffcc0b0 (776ac33): classify_terminal_state returns ..._UNKNOWN for MARKET_HALTED.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:200]) if not ok else ''))


def classify(category, lifecycle="ENTRY"):
    return C.classify_terminal_state("ORDER_REJECTED", category, lifecycle)


# 1. the fix itself
got = classify("MARKET_HALTED")
check("MARKET_HALTED_IS_KNOWN", got == "MISSED_ENTRY_MARKET_HALTED", 'got %r' % (got,))
check("MARKET_HALTED_NOT_UNKNOWN", got != "MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN", 'got %r' % (got,))

# 2. no category-regression: the other known categories keep their exact states
for cat, want in (("IOC_NO_IMMEDIATE_MATCH", "MISSED_ENTRY_IOC_NO_MATCH"),
                  ("INSUFFICIENT_MARGIN", "MISSED_ENTRY_INSUFFICIENT_MARGIN"),
                  ("PRICE_OR_TICK_REJECTED", "MISSED_ENTRY_PRICE_OR_TICK_REJECTED"),
                  ("SIZE_OR_NOTIONAL_REJECTED", "MISSED_ENTRY_SIZE_OR_NOTIONAL_REJECTED"),
                  ("SYMBOL_OR_ASSET_REJECTED", "MISSED_ENTRY_SYMBOL_OR_ASSET_REJECTED"),
                  ("EXCHANGE_REJECTED_UNKNOWN", "MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN")):
    v = classify(cat)
    check("KEEP_" + cat, v == want, 'want %r got %r' % (want, v))

# 3. a genuinely unattributed reject still falls back to UNKNOWN (the fallback must stay reachable)
v = classify("SOMETHING_WE_HAVE_NEVER_SEEN")
check("TRULY_UNKNOWN_STILL_FALLS_BACK", v == "MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN", 'got %r' % (v,))

# 4. the new name is a declared terminal row name, so the diagnostic list does not call it UNCLASSIFIED
check("NEW_NAME_IN_TERMINAL_SET", "MISSED_ENTRY_MARKET_HALTED" in C.TERMINAL_ROW_NAMES,
      'classify_terminal_row -> %r' % (C.classify_terminal_row("MISSED_ENTRY_MARKET_HALTED"),))
check("NEW_NAME_CLASSIFIES_TERMINAL", C.classify_terminal_row("MISSED_ENTRY_MARKET_HALTED") == "TERMINAL",
      'got %r' % (C.classify_terminal_row("MISSED_ENTRY_MARKET_HALTED"),))

# 5. the pairing rule the cert contract will assert: terminal_state is a pure function of reject_category
same = {classify("MARKET_HALTED") for _ in range(3)}
check("PURE_FUNCTION_OF_CATEGORY", len(same) == 1, 'got %r' % (same,))

failed = [n for n, ok in results if not ok]
print("SUMMARY %d checks, %d failed%s" % (len(results), len(failed), (' -> ' + ','.join(failed)) if failed else ''))
sys.exit(1 if failed else 0)
