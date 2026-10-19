# Pacing: the `_cancel_order` defect my review preserved

Found by the controller on `e61d278` (comment `6265227102`). Verified in the source before recording it.

## The defect

    def _cancel_order(self, exchange, sdk_coin, oid):
        with self._exchange_order_lock:
            self._wait_exchange_order_slot()        # sleeps up to 5 s INSIDE the lock
        return exchange.cancel(sdk_coin, int(oid))

    def _wait_exchange_order_slot(self):
        ...
        wait_until = max(self._last_exchange_order_ms + min_gap_ms, self._exchange_rate_limit_cooldown_until_ms)
        if wait_until > now_ms:
            time.sleep(min(5.0, (wait_until - now_ms) / 1000.0))
        self._last_exchange_order_ms = utc_now_ms()   # <-- moves the clock BACKWARDS

Two faults, both on the cancel path:

1. **The clock moves backwards.** `_place_order` now reserves a *future* slot and writes it to
   `_last_exchange_order_ms`. `_wait_exchange_order_slot` then overwrites that with `utc_now_ms()`, which is earlier.
   The next order therefore reserves `now + gap`, **earlier than slots already booked**, and the gap is broken.
2. **The lock is still held across the sleep** on the cancel path — up to 5 s. That is the exact defect the pacing
   change existed to remove; it was fixed in `_place_order` and left standing in `_cancel_order`.

## Why my review did not catch it

The review card required:

> "`_cancel_order` still takes the lock and behaves as before."

**That requirement was wrong.** `_last_exchange_order_ms` changed meaning from *"when we last called the exchange"* to
*"the next reserved slot"*. In that world, "behaves as before" is a **bug**, not a compatibility guarantee. I specified
compatibility on a sibling path when the correct requirement was **consistency with the new model**.

The test then asserted exactly what I asked for — one lock acquisition, unchanged cancel behaviour — and passed. A test
faithful to a wrong requirement is still a passing test of the wrong thing.

## The rule this yields

**When a change alters the meaning of a shared variable, every sibling reader of that variable must be re-derived, not
preserved.** "Do not change X" is only safe if X's inputs and meaning are unchanged. If they are not, "unchanged" is the
defect.

## The fix the controller specified

One shared helper `_reserve_exchange_order_slot()` containing the reservation block and returning `slot_ms`, used by
**both** `_place_order` and `_cancel_order`, each sleeping **after** the lock is released.
`_wait_exchange_order_slot` is removed or reduced to that helper. The clock must never move backwards (`max`).

Required test: a cancel between two queued reservations must not let a later order land inside the gap, and a cancel must
never sleep while holding the lock.
