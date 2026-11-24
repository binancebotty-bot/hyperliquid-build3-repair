"""Crash-loss fix: ids are persisted only after their work is on record; an uncommitted copy-fill claim is recovered."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TMP = tempfile.mkdtemp(prefix="crash_loss_")
os.environ.update({
    "HL_LIVE_AUDIT_DIR": TMP,
    "HL_LIVE_ENV_FILE": os.path.join(TMP, "missing.env"),
    "HL_LIVE_MOCK_SEND": "1",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
})
import HL_Live_Copy_Service_Core as c

WALLET = "0x" + "a" * 40
DEAD_PID = 2_000_000_000  # no such process


def restart_dedupe(d: Path) -> "c.DedupeStore":
    """What a restart does: build a fresh store from the files on disk."""
    return c.DedupeStore({}, state_dir=d)


def write_claim(copy_id: str, pid: int) -> Path:
    mdir = c.AUDIT_DIR / "copy_fill_claims"
    mdir.mkdir(parents=True, exist_ok=True)
    m = mdir / (c._safe_marker_name(copy_id) + ".claim")
    m.write_text(f"copy_fill_id={copy_id}\nclaimed_at=x\npid={pid}\n", encoding="utf-8")
    return m


def legacy_claim(copy_id: str) -> bool:
    """The pre-fix claim: first writer wins forever, no recovery."""
    mdir = c.AUDIT_DIR / "copy_fill_claims"
    mdir.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(mdir / (c._safe_marker_name(copy_id) + ".claim")), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False


class LeaderIdPersistence(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="dd_", dir=TMP))

    def test_c1_crash_after_accept_before_intent_replays_on_restart(self):
        st = c.DedupeStore({}, state_dir=self.d)
        self.assertTrue(st.accept_leader("fill-1"))
        st.flush_jsonl()  # a cycle-end state write lands between accept and the intent row
        # ... process dies here: confirm_leader never ran ...
        again = restart_dedupe(self.d)
        self.assertNotIn("fill-1", again.processed)
        self.assertTrue(again.accept_leader("fill-1"))  # replayed, not lost

    def test_c1_negative_control_old_behaviour_loses_the_fill(self):
        st = c.DedupeStore({}, state_dir=self.d)
        st.accept_leader("fill-1")
        st._jsonl_new_leader.append("fill-1")  # what the old accept_leader did: persist at accept
        st.flush_jsonl()
        self.assertIn("fill-1", restart_dedupe(self.d).processed)  # i.e. lost: restart refuses it

    def test_c2_confirmed_after_intent_is_not_replayed(self):
        st = c.DedupeStore({}, state_dir=self.d)
        st.accept_leader("fill-2")
        st.confirm_leader("fill-2")
        st.flush_jsonl()
        again = restart_dedupe(self.d)
        self.assertIn("fill-2", again.processed)
        self.assertFalse(again.accept_leader("fill-2"))  # no double send

    def test_c3_release_removes_from_persist_queue(self):
        st = c.DedupeStore({}, state_dir=self.d)
        st.accept_leader("fill-3")
        st.release_leader("fill-3")
        st.confirm_leader("fill-3")  # a late confirm of a released id must not resurrect it
        st.flush_jsonl()
        self.assertNotIn("fill-3", restart_dedupe(self.d).processed)
        self.assertTrue(st.accept_leader("fill-3"))

    def test_c4_pending_ids_are_not_in_exported_state(self):
        st = c.DedupeStore({}, state_dir=self.d)
        st.accept_leader("p1")
        st.accept_copy("cp1")
        st.accept_leader("p2")
        st.confirm_leader("p2")
        ex = st.export()
        self.assertEqual(ex["processed_leader_fill_ids"], ["p2"])
        self.assertEqual(ex["processed_copy_fill_ids"], [])
        self.assertFalse(st.accept_leader("p1"))  # in-process dedupe still holds


class CopyIdPersistence(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="dd_", dir=TMP))

    def test_c5_crash_between_accept_and_apply_replays_copy_fill(self):
        st = c.DedupeStore({}, state_dir=self.d)
        self.assertTrue(st.accept_copy("cf-1"))
        st.flush_jsonl()
        again = restart_dedupe(self.d)
        self.assertNotIn("cf-1", again.processed_copy)
        self.assertTrue(again.accept_copy("cf-1"))

    def test_c6_confirmed_copy_fill_is_not_replayed(self):
        st = c.DedupeStore({}, state_dir=self.d)
        st.accept_copy("cf-2")
        st.confirm_copy("cf-2")
        st.flush_jsonl()
        self.assertFalse(restart_dedupe(self.d).accept_copy("cf-2"))


class ClaimRecovery(unittest.TestCase):
    def test_h1_crash_after_claim_before_apply_is_recovered(self):
        write_claim("cf-claim-1", DEAD_PID)
        self.assertFalse(legacy_claim("cf-claim-1"))  # negative control: the old guard drops the fill for ever
        self.assertTrue(c.claim_copy_fill_process_marker("cf-claim-1", lambda _id: False))
        self.assertFalse(c.claim_copy_fill_process_marker("cf-claim-1", lambda _id: False))  # now held by us
        c._INFLIGHT_CLAIMS.discard("cf-claim-1")

    def test_h2_crash_after_ledger_apply_never_applies_twice(self):
        write_claim("cf-claim-2", DEAD_PID)
        self.assertFalse(c.claim_copy_fill_process_marker("cf-claim-2", lambda _id: True))  # ledger already has it
        self.assertTrue((c.AUDIT_DIR / "copy_fill_claims" / "cf-claim-2.done").exists())
        self.assertFalse(c.claim_copy_fill_process_marker("cf-claim-2", lambda _id: False))  # and stays closed

    def test_h3_claim_held_by_a_live_process_is_respected(self):
        import subprocess
        import sys
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])  # a real live process of our own
        try:
            write_claim("cf-claim-3", child.pid)
            self.assertFalse(c.claim_copy_fill_process_marker("cf-claim-3", lambda _id: False))
        finally:
            child.kill()
            child.wait()
        # once it is dead, the same claim is recoverable
        self.assertTrue(c.claim_copy_fill_process_marker("cf-claim-3", lambda _id: False))
        c._INFLIGHT_CLAIMS.discard("cf-claim-3")

    def test_h7_empty_claim_file_is_not_stolen(self):
        m = write_claim("cf-claim-7", 0)
        m.write_text("", encoding="utf-8")  # writer died / is between create and write
        self.assertFalse(c.claim_copy_fill_process_marker("cf-claim-7", lambda _id: False))
        self.assertTrue(m.exists())

    def test_h8_half_written_claim_is_not_stolen(self):
        m = write_claim("cf-claim-8", 0)
        m.write_text(f"copy_fill_id=cf-claim-8\nclaimed_at=x\npid={DEAD_PID}", encoding="utf-8")  # torn: no final newline
        self.assertFalse(c.claim_copy_fill_process_marker("cf-claim-8", lambda _id: False))

    def test_h9_old_empty_claim_is_recoverable_after_the_grace(self):
        m = write_claim("cf-claim-9", 0)
        m.write_text("", encoding="utf-8")
        old = os.path.getmtime(m) - 3600
        os.utime(m, (old, old))
        self.assertTrue(c.claim_copy_fill_process_marker("cf-claim-9", lambda _id: False))
        c._INFLIGHT_CLAIMS.discard("cf-claim-9")

    def test_h10_windows_probe_never_signals_the_process(self):
        from unittest.mock import patch
        def boom(*_a):
            raise AssertionError("os.kill must not be used as a Windows liveness probe")
        with patch.object(os, "name", "nt"), patch.object(os, "kill", boom):
            self.assertIsInstance(c._pid_alive(4242), bool)  # ctypes.WinDLL is absent here: falls back to "alive", no signal

    def test_h11_liquidation_recovery_flags_partial_application(self):
        self.assertTrue(callable(c.CopyFillMatcher._try_apply_liquidation))
        import inspect
        self.assertIn("LIQUIDATION_RECOVERY_CHECK_ALL_SLEEVES", inspect.getsource(c.CopyFillMatcher._try_apply_liquidation))

    def test_h4_committed_claim_is_permanent(self):
        self.assertTrue(c.claim_copy_fill_process_marker("cf-claim-4"))
        c.commit_copy_fill_process_marker("cf-claim-4")
        c._INFLIGHT_CLAIMS.discard("cf-claim-4")
        self.assertFalse(c.claim_copy_fill_process_marker("cf-claim-4", lambda _id: False))

    def test_h5_in_flight_claim_in_this_process_is_not_stolen(self):
        self.assertTrue(c.claim_copy_fill_process_marker("cf-claim-5"))
        self.assertFalse(c.claim_copy_fill_process_marker("cf-claim-5", lambda _id: False))
        c._INFLIGHT_CLAIMS.discard("cf-claim-5")

    def test_h6_two_recoverers_only_one_wins(self):
        write_claim("cf-claim-6", DEAD_PID)
        first = c.claim_copy_fill_process_marker("cf-claim-6", lambda _id: False)
        second = c.claim_copy_fill_process_marker("cf-claim-6", lambda _id: False)
        self.assertEqual((first, second), (True, False))
        c._INFLIGHT_CLAIMS.discard("cf-claim-6")


class LedgerProof(unittest.TestCase):
    def test_l1_applied_id_is_saved_with_the_position(self):
        path = Path(tempfile.mkdtemp(prefix="led_", dir=TMP)) / "pos.json"
        led = c.ManualLedger(path)
        fill = c.LeaderFill("f", WALLET, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "T")
        intent = c.Intent("i1", fill, "BUY", 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "", c.ManualLedger.sleeve_id(WALLET, "BTC"),
                          "", "", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=ENTRY")
        led.apply_copy_fill(intent, {"side": "BUY", "size": 1.0, "price": 100.0, "copy_fill_id": "cf-led-1"})
        reloaded = c.ManualLedger(path)  # a restart
        self.assertTrue(reloaded.has_applied_copy_fill("cf-led-1"))
        self.assertFalse(reloaded.has_applied_copy_fill("cf-led-2"))


class MatcherWrapper(unittest.TestCase):
    def matcher(self, outcome):
        m = object.__new__(c.CopyFillMatcher)
        m.copy_fill_id = lambda raw: raw["id"]
        done = []
        m.on_complete = done.append
        if isinstance(outcome, Exception):
            def boom(*_a):
                raise outcome
            m._match_and_apply = boom
        else:
            m._match_and_apply = lambda *_a: outcome
        return m, done

    def test_m1_success_commits_and_confirms(self):
        c.claim_copy_fill_process_marker("cf-m1")
        m, done = self.matcher(True)
        self.assertTrue(m.match_and_apply({"id": "cf-m1"}, {}))
        self.assertEqual(done, ["cf-m1"])
        self.assertTrue((c.AUDIT_DIR / "copy_fill_claims" / "cf-m1.done").exists())

    def test_m2_exception_confirms_nothing_and_releases_the_in_flight_hold(self):
        c.claim_copy_fill_process_marker("cf-m2")
        m, done = self.matcher(RuntimeError("crash mid-apply"))
        with self.assertRaises(RuntimeError):
            m.match_and_apply({"id": "cf-m2"}, {})
        self.assertEqual(done, [])
        self.assertFalse((c.AUDIT_DIR / "copy_fill_claims" / "cf-m2.done").exists())
        # the failed claim is recoverable in this same process: it replays
        self.assertTrue(c.claim_copy_fill_process_marker("cf-m2", lambda _id: False))
        c._INFLIGHT_CLAIMS.discard("cf-m2")

    def test_m3_unmatched_outcome_still_confirms_id(self):
        m, done = self.matcher(False)
        self.assertFalse(m.match_and_apply({"id": "cf-m3"}, {}))
        self.assertEqual(done, ["cf-m3"])


if __name__ == "__main__":
    unittest.main()
