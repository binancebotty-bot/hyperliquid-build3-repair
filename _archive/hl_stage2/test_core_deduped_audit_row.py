#!/usr/bin/env python3
"""Unit test for the row emitted for a deduplicated poll fill.

This verifies the helper's row contents only; it does not exercise the poll-dispatch branch.
"""
from __future__ import annotations

from types import SimpleNamespace

import HL_Live_Copy_Service_Core as core


class Recorder:
    def __init__(self):
        self.rows = []

    def append_reconciliation(self, *args, **kwargs):
        self.rows.append((args, kwargs))


def main() -> None:
    stub = object.__new__(core.LiveCopyCore)
    stub.audit = Recorder()
    fill = SimpleNamespace(
        leader_wallet="0xleader",
        leader_fill_id="0xabc:7",
        coin="BTC",
        side="buy",
        size=0.25,
        price=65000.0,
        timestamp_ms=123456789,
    )

    stub._write_deduped_audit_row(fill)

    assert len(stub.audit.rows) == 1, stub.audit.rows
    args, kwargs = stub.audit.rows[0]
    assert args == ("SEND_TERMINAL", "COLLAPSED_STALE"), args
    assert kwargs["leader_fill_id"] == "0xabc:7", kwargs
    assert kwargs["leader_wallet"] == "0xleader", kwargs
    assert kwargs["coin"] == "BTC", kwargs
    assert kwargs["terminal_state"] == "COLLAPSED_STALE", kwargs
    assert kwargs["engine_can_send"] == "False", kwargs
    assert "deduplicated in poll dispatch" in kwargs["notes"], kwargs
    print("RESULT::deduped_audit_row_PASS")


if __name__ == "__main__":
    main()
