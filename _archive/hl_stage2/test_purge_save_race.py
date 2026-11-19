#!/usr/bin/env python3
"""RACE: a cooperating writer holding `_FILE_WRITE_LOCK` must not lose an entry to a concurrent save.

`save_purged_wallets()` carries unparseable entries over from disk, and that promise only holds while
the disk read happens INSIDE the lock: a read taken before the lock is acquired merges a snapshot that
predates any write landing in between, and the save then rewrites the file without it. That window is
the whole reason the lock exists, so it is tested by a cooperating writer rather than by inspection.

Each iteration holds the lock, starts a save on another thread, lets it reach its disk read, appends an
unparseable entry under the same lock, and releases. A save that reads under the lock sees the entry and
keeps it; a save that read before owning the lock erases it. 50 iterations, 0 lost entries required.
A second phase starts a writer and a save together to cover the ordinary concurrent case.

Nothing here touches the engine, the network or a live file: PURGED_WALLETS_FILE is repointed into a
temp dir before any helper runs.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ITERATIONS = 50
BURST_ROUNDS = 20
BURST_APPENDS = 3

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + str(detail)[:400]) if detail and not ok else ""))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="purge_race_", dir=os.environ.get("TMPDIR") or None))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp / "audit"), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet"})
    import HL_Copy_App_SSOT as ui

    tomb = tmp / "purged_wallets.txt"
    ui.PURGED_WALLETS_FILE = tomb
    write(tomb, "zz-race-baseline\n")

    errors = []
    lost = []
    saves_missing = []

    def save_one(payload: set[str], label: str) -> None:
        try:
            ui.save_purged_wallets(payload)
        except BaseException as exc:                                  # noqa: BLE001 - reported, not raised
            errors.append("%s: %r" % (label, exc))

    for i in range(ITERATIONS):
        entry = "zz-race-appended-%02d" % i
        save_hash = hashlib.sha256(("race-save-%02d" % i).encode("utf-8")).hexdigest()
        t = threading.Thread(target=save_one, args=({save_hash}, "iter-%02d" % i), daemon=True)
        ui._FILE_WRITE_LOCK.acquire()                 # the cooperating writer owns the lock ...
        try:
            t.start()
            time.sleep(0.05)                          # ... while the save is already inside the call
            with tomb.open("a", encoding="utf-8", newline="") as f:
                f.write(entry + "\n")
        finally:
            ui._FILE_WRITE_LOCK.release()
        t.join(20)                                    # join OUTSIDE the lock, or the save cannot run
        lines = tomb.read_text(encoding="utf-8").split()
        if entry not in lines:
            lost.append(entry)                       # the append landed inside the save's read window
        if "zz-race-baseline" not in lines:
            lost.append("baseline@%02d" % i)
        if save_hash not in lines:
            saves_missing.append(save_hash)

    check("PURGE_RACE_APPEND_UNDER_LOCK_NOT_LOST", not lost,
          "%d of %d appends lost to a concurrent save: %r" % (len(lost), ITERATIONS, lost[:8]))
    check("PURGE_RACE_SAVE_SET_PRESENT", not saves_missing,
          "%d of %d saved tombstones absent after the write: %r"
          % (len(saves_missing), ITERATIONS, saves_missing[:4]))

    # ---- phase 2: the ordinary case - a writer and a save started together ---------------------
    burst_lost = []
    for i in range(BURST_ROUNDS):
        entries = ["zz-burst-%02d-%d" % (i, n) for n in range(BURST_APPENDS)]
        save_hash = hashlib.sha256(("burst-save-%02d" % i).encode("utf-8")).hexdigest()
        gate = threading.Barrier(2)

        def writer(entries=entries, gate=gate) -> None:
            gate.wait(20)
            for entry in entries:
                with ui._FILE_WRITE_LOCK:
                    with tomb.open("a", encoding="utf-8", newline="") as f:
                        f.write(entry + "\n")

        def saver(save_hash=save_hash, label="burst-%02d" % i, gate=gate) -> None:
            gate.wait(20)
            for _ in range(2):
                save_one({save_hash}, label)

        threads = [threading.Thread(target=writer, daemon=True), threading.Thread(target=saver, daemon=True)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        lines = tomb.read_text(encoding="utf-8").split()
        burst_lost.extend(e for e in entries if e not in lines)

    check("PURGE_RACE_BURST_NOT_LOST", not burst_lost,
          "%d entries lost with a writer and a save running together: %r"
          % (len(burst_lost), burst_lost[:8]))
    check("PURGE_RACE_NO_ERRORS_RAISED", not errors, errors[:4])
    check("PURGE_RACE_UNPARSEABLE_STILL_BLOCKED", ui.is_purged("zz-race-baseline") is True,
          "baseline=%r" % (ui.is_purged("zz-race-baseline"),))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    if failed:
        print("FAILED: " + ", ".join(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
