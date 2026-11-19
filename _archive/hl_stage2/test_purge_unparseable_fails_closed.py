#!/usr/bin/env python3
"""FAIL-CLOSED guard: a tombstone entry the reader cannot parse must be treated as PURGED.

purged_wallets.txt is the app's only block list, so an entry it cannot read is an entry it cannot
honour: dropping that line silently unblocks whatever wallet it was written for. This suite seeds a
tombstone file with the only shapes that reach it - a plaintext address left by an older build, a
64-hex tombstone this build writes, and two entries nothing can parse (`zz-not-a-wallet` and a
truncated 60-hex hash) - and requires that all four answer TRUE, that the unparseable ones are
counted and alerted BY NAME, and that no save can quietly rewrite them out of the file.

Nothing here touches the engine, the network or a live file: PURGED_WALLETS_FILE is repointed into a
temp dir before any helper runs.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
P = "0x" + "a" * 40                                            # plaintext address, older build
H = hashlib.sha256(("0x" + "b" * 40).encode("utf-8")).hexdigest()  # 64-hex tombstone, this build
B = "0x" + "f" * 40                                            # bystander: never purged
GARBAGE = "zz-not-a-wallet"                                    # nothing can parse this
TRUNCATED = "c" * 60                                           # a 64-hex tombstone cut short


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + str(detail)[:400]) if detail and not ok else ""))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="purge_unparseable_", dir=os.environ.get("TMPDIR") or None))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp / "audit"), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet"})
    import HL_Copy_App_SSOT as ui

    tomb = tmp / "purged_wallets.txt"
    ui.PURGED_WALLETS_FILE = tomb
    # a real file ends with a newline: the trailing blank must not be mistaken for a bad entry
    write(tomb, "\n".join([P, H, GARBAGE, TRUNCATED, ""]))

    err = io.StringIO()
    with contextlib.redirect_stdout(err), contextlib.redirect_stderr(err):
        loaded = ui.load_purged_wallets()
    alert = err.getvalue()
    counted = list(getattr(ui, "PURGE_UNPARSEABLE_ENTRIES", []))

    check("PURGE_UNPARSEABLE_PLAINTEXT_STILL_BLOCKS", ui.is_purged(P) is True, "loaded=%r" % (sorted(loaded),))
    check("PURGE_UNPARSEABLE_HASHED_TOMBSTONE_BLOCKS", ui.is_purged(H) is True, "loaded=%r" % (sorted(loaded),))

    # ---- the defect: an unparseable entry was skipped, so it blocked nothing ------------------
    check("PURGE_UNPARSEABLE_GARBAGE_ENTRY_BLOCKS", ui.is_purged(GARBAGE) is True,
          "an unparseable line was dropped and left %r unblocked; loaded=%r" % (GARBAGE, sorted(loaded)))
    check("PURGE_UNPARSEABLE_TRUNCATED_HEX_BLOCKS", ui.is_purged(TRUNCATED) is True,
          "a truncated tombstone was dropped and left its entry unblocked; loaded=%r" % (sorted(loaded),))

    # ---- the drop must be visible, not silent -----------------------------------------------
    check("PURGE_UNPARSEABLE_COUNTED_AND_ALERTED",
          len(counted) == 2 and GARBAGE in counted and TRUNCATED in counted
          and "PURGE_UNPARSEABLE" in alert and tomb.name in alert,
          "count=%d entries=%r alert=%r" % (len(counted), counted, alert[:300]))

    # blocking on garbage must not reach a wallet that is genuinely not on the list
    check("PURGE_UNPARSEABLE_BYSTANDER_NOT_BLOCKED",
          ui.is_purged(B) is False and ui.is_purged("0x" + "e" * 40) is False,
          "B=%r other=%r" % (ui.is_purged(B), ui.is_purged("0x" + "e" * 40)))

    # ---- save: plaintext becomes a hash, the unparseable lines survive verbatim --------------
    ui.save_purged_wallets(loaded)
    rewritten = tomb.read_text(encoding="utf-8")
    lines = rewritten.split()
    check("PURGE_UNPARSEABLE_SAVE_KEEPS_ENTRIES",
          GARBAGE in lines and TRUNCATED in lines
          and hashlib.sha256(P.encode("utf-8")).hexdigest() in lines and P not in rewritten,
          "lines=%r" % (lines,))
    check("PURGE_UNPARSEABLE_STILL_BLOCKED_AFTER_SAVE",
          ui.is_purged(GARBAGE) is True and ui.is_purged(TRUNCATED) is True,
          "after save garbage=%r truncated=%r" % (ui.is_purged(GARBAGE), ui.is_purged(TRUNCATED)))

    # Construction invariant: save's disk read must run while the shared writer lock is owned.
    # This makes a cooperating concurrent append serialize before or after the entire save transaction.
    # The observation is bound to the READ itself, not to a helper called after it: hoisting only
    # `read_text` above `with _FILE_WRITE_LOCK:` leaves every later call inside the lock, so a hook on
    # a helper passes while a cooperating append is lost (test_purge_save_race.py loses 50 of 50).
    owned_during_save_read = []

    class ObservedTombstonePath(type(tomb)):
        def read_text(self, *args, **kwargs):
            owned_during_save_read.append(ui._FILE_WRITE_LOCK._is_owned())
            return super().read_text(*args, **kwargs)

    real_path = ui.PURGED_WALLETS_FILE
    ui.PURGED_WALLETS_FILE = ObservedTombstonePath(real_path)
    try:
        # a caller that only ever saw hashes must not be able to erase an entry it cannot read
        ui.save_purged_wallets({hashlib.sha256(B.encode("utf-8")).hexdigest()})
    finally:
        ui.PURGED_WALLETS_FILE = real_path
    check("PURGE_UNPARSEABLE_SAVE_READ_UNDER_LOCK", bool(owned_during_save_read) and all(owned_during_save_read),
          "lock ownership at the disk read=%r" % (owned_during_save_read,))
    lines = tomb.read_text(encoding="utf-8").split()
    check("PURGE_UNPARSEABLE_SAVE_CANNOT_DROP", GARBAGE in lines and TRUNCATED in lines,
          "a save from a hashes-only set dropped the unreadable entries: %r" % (lines,))

    # ---- a control character must not let ONE supplied value become several records -------------
    # Written verbatim, "broken\n0x..." persists as two lines, so one supplied value becomes two
    # records and the tail is a plaintext address the next load hashes into the valid set.
    promoted = "0x" + "d" * 40
    hostile = "broken\n" + promoted
    noisy = io.StringIO()
    with contextlib.redirect_stdout(noisy), contextlib.redirect_stderr(noisy):
        ui.save_purged_wallets({hashlib.sha256(B.encode("utf-8")).hexdigest(), hostile})
    rejected_alert = noisy.getvalue()
    raw_lines = [line.strip().lower() for line in tomb.read_text(encoding="utf-8").splitlines()]
    check("PURGE_UNPARSEABLE_CONTROL_CHARS_NOT_WRITTEN",
          hostile not in raw_lines and promoted not in raw_lines
          and GARBAGE in raw_lines and TRUNCATED in raw_lines,
          "one supplied value carrying a newline was persisted as %r" % (raw_lines,))
    check("PURGE_UNPARSEABLE_CONTROL_CHARS_ALERTED",
          "PURGE_UNPARSEABLE_CONTROL_REJECTED" in rejected_alert
          and hostile in list(getattr(ui, "PURGE_UNPARSEABLE_REJECTED", [])),
          "alert=%r rejected=%r" % (rejected_alert[:200], getattr(ui, "PURGE_UNPARSEABLE_REJECTED", [])))
    check("PURGE_UNPARSEABLE_CONTROL_ENTRY_TAIL_NOT_BLOCKING",
          ui.is_purged(promoted) is False,
          "the address smuggled in the rejected entry answers is_purged=%r" % (ui.is_purged(promoted),))

    poisoned = tmp / "poisoned_purged_wallets.txt"
    write(poisoned, "zz\u0000hidden\n")
    ui.PURGED_WALLETS_FILE = poisoned
    disk_noise = io.StringIO()
    with contextlib.redirect_stdout(disk_noise), contextlib.redirect_stderr(disk_noise):
        loaded_poisoned = ui.load_purged_wallets()
    check("PURGE_UNPARSEABLE_CONTROL_FROM_DISK_REJECTED",
          "zz\u0000hidden" not in loaded_poisoned
          and "PURGE_UNPARSEABLE_CONTROL_REJECTED" in disk_noise.getvalue(),
          "loaded=%r alert=%r" % (sorted(loaded_poisoned), disk_noise.getvalue()[:200]))
    ui.PURGED_WALLETS_FILE = tomb

    # ---- the operator's real file is clean: no false alarm -----------------------------------
    clean = tmp / "clean_purged_wallets.txt"
    ui.PURGED_WALLETS_FILE = clean
    write(clean, hashlib.sha256(B.encode("utf-8")).hexdigest() + "\n")
    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
        ui.load_purged_wallets()
    check("PURGE_UNPARSEABLE_CLEAN_FILE_NO_ALERT",
          len(getattr(ui, "PURGE_UNPARSEABLE_ENTRIES", [])) == 0 and "PURGE_UNPARSEABLE" not in quiet.getvalue(),
          "count=%d stderr=%r" % (len(getattr(ui, "PURGE_UNPARSEABLE_ENTRIES", [])), quiet.getvalue()[:200]))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    if failed:
        print("FAILED: " + ", ".join(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
