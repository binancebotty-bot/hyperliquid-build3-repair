"""R4 v2: real on-disk append-only NO_CALL journal from exact production
_place_order -> _terminalise_pending_as_no_call -> update_send_attempt_row.

Only the low-level CSV storage adapter and external SDK/network are replaced.
The decision, write-ahead ordering, terminalisation and update functions are
compiled unchanged from the committed production source. A separate interpreter
reads the resulting journal, not the test's in-memory structures.

Run: python -m pytest -q _archive/hl_stage2/test_core_r4_durable_no_call_v2.py
"""
import ast
import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import MethodType

from test_core_r4_physical_order_no_call import (
    CORE, ExchangeSpy, build_sender, make_intent, send,
)

FIELDS = [
    "attempt_id", "intent_id", "status", "terminal_state", "reject_category",
    "operator_action", "error", "notes", "exchange_order_id",
]


def build_disk_gateway(tmp_path, withdrawable):
    sender, _, events = build_sender(tmp_path, withdrawable)
    journal = tmp_path / "send_attempts.csv"
    source = ast.parse(CORE.read_text(encoding="utf-8-sig"))
    owner = next(x for x in source.body if isinstance(x, ast.ClassDef)
                 and x.name == "SenderGateway")
    terminal = next(x for x in owner.body if isinstance(x, ast.FunctionDef)
                    and x.name == "_terminalise_pending_as_no_call")
    update = next(x for x in source.body if isinstance(x, ast.FunctionDef)
                  and x.name == "update_send_attempt_row")
    assert terminal.name == "_terminalise_pending_as_no_call"
    assert update.name == "update_send_attempt_row"

    # This is the namespace of the SAME AST-extracted production _place_order
    # and production reservation method used in the v1 positive control.
    ns = sender._place_order.__func__.__globals__

    def disk_rows():
        if not journal.exists():
            return []
        with journal.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def durable_append(path, fieldnames, row, *, durable=False):
        # Isolated file adapter: real CSV write, flush and fsync.
        # Production append_csv has a separate fallback/spill protocol;
        # that integration is NOT claimed by this isolated test.
        assert Path(path) == journal
        journal.parent.mkdir(parents=True, exist_ok=True)
        with journal.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow(row)
            f.flush()
            if durable:
                os.fsync(f.fileno())
        return True

    ns.update({
        "SEND_ATTEMPTS_CSV": journal,
        "SEND_ATTEMPT_FIELDS": FIELDS,
        "send_attempt_rows": disk_rows,
        "append_csv": durable_append,
    })
    exec(compile(ast.fix_missing_locations(ast.Module(body=[update], type_ignores=[])),
                 str(CORE), "exec"), ns)
    gate = ast.ClassDef(name="DiskGateway", bases=[], keywords=[],
                        body=[terminal], decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[gate], type_ignores=[])),
                 str(CORE), "exec"), ns)
    sender._terminalise_pending_as_no_call = MethodType(
        ns["DiskGateway"]._terminalise_pending_as_no_call, sender)

    def pre_send(intent):
        attempt_id = "attempt-" + intent.intent_id
        disk = {
            "attempt_id": attempt_id,
            "intent_id": intent.intent_id,
            "status": "pending_send",
            "terminal_state": "PENDING_SEND",
        }
        durable_append(journal, FIELDS, disk, durable=True)
        return attempt_id

    return sender, journal, pre_send, events


def read_from_fresh_process(path):
    program = (
        "import csv,json,sys;"
        "f=open(sys.argv[1],newline='',encoding='utf-8');"
        "print(json.dumps(list(csv.DictReader(f))));f.close()"
    )
    run = subprocess.run(
        [sys.executable, "-c", program, str(path)],
        capture_output=True, text=True, check=True, timeout=15,
    )
    return json.loads(run.stdout)


def assert_persisted_no_call(journal, intent):
    rows = [r for r in read_from_fresh_process(journal)
            if r["attempt_id"] == "attempt-" + intent.intent_id]
    assert len(rows) == 2  # pending + durable terminal; no rewrite
    assert rows[0]["status"] == "pending_send"
    assert rows[1]["status"] == "SEND_NOT_ATTEMPTED_MARGIN_REST_NO_COLLATERAL"
    assert rows[1]["terminal_state"] == "SEND_NOT_ATTEMPTED_MARGIN_REST_NO_COLLATERAL"
    assert rows[1]["operator_action"] == "NO_EXCHANGE_CALL"
    assert rows[1]["reject_category"] == "SEND_NOT_ATTEMPTED_MARGIN_REST_NO_COLLATERAL"
    assert rows[1]["notes"].startswith("NO_EXCHANGE_CALL:")
    assert rows[1]["exchange_order_id"] == ""


def test_production_no_call_survives_fresh_process_after_zero_collateral(tmp_path):
    sender, journal, pre_send, events = build_disk_gateway(tmp_path, withdrawable=0)
    exchange = ExchangeSpy()
    intent = make_intent("empty-margin")
    reply, timing = send(sender, exchange, intent, lambda: pre_send(intent))
    assert reply["exchange_called"] is False
    assert exchange.orders == []
    assert timing.get("exchange_order_invoked") is not True
    assert "begin" not in events
    assert_persisted_no_call(journal, intent)


def test_restart_reservation_second_order_no_call_and_positive_wire(tmp_path):
    sender, journal, pre_send, _ = build_disk_gateway(tmp_path, withdrawable=100)
    exchange = ExchangeSpy()
    first = make_intent("one")
    accepted, timing = send(sender, exchange, first, lambda: pre_send(first))
    assert accepted == {"status": "ok"}
    assert timing["exchange_order_invoked"] is True
    assert len(exchange.orders) == 1  # real production wire body, SDK spy only
    restarted, journal, second_pre_send, events = build_disk_gateway(
        tmp_path, withdrawable=100
    )
    second = make_intent("two")
    refused, after = send(restarted, exchange, second, lambda: second_pre_send(second))
    assert refused["exchange_called"] is False
    assert len(exchange.orders) == 1
    assert "begin" not in events
    assert after.get("exchange_order_invoked") is not True
    assert_persisted_no_call(journal, second)
