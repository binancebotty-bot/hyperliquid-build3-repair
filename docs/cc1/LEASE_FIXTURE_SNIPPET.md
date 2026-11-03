# CC1 M2 sender-lease fixture — exact Build 3 mechanism

**Contract:** CC-1 M2, GUT I08, R3, CH-1/2/4/8/9, CLOSES-SACRED. Test-only snippet; no production changes. Use on the `gpt/coda2-sender-fence` branch (starting at `522b20680fe85560be2b68767be684b80693d150`). This replaces the independent-handle `tools/testkit/lease_fixture.py` approach, which only holds an OS lock and does **not** set Core's in-module sender-authority state.

## Drop-in context manager (20 lines, including imports)

```python
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import tempfile

@contextmanager
def hold_test_lease(tmp_dir, core=None):
    if core is None:
        import HL_Live_Copy_Service_Core as core
    root = Path(tmp_dir).resolve()
    if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not root.is_dir():
        raise ValueError("requires existing, isolated tempfile directory")
    if core._GLOBAL_INSTANCE_LOCK is not None or core._GLOBAL_INSTANCE_LOCK_OWNED:
        raise RuntimeError("Core already has an active sender lease")
    with patch.object(core, "_global_instance_lock_path", return_value=root / "engine-global.lock"):
        core.acquire_global_instance_lock(root)
        try:
            yield
        finally:
            core.release_global_instance_lock()
```

Invoke explicitly at the sending fixture boundary: `with hold_test_lease(tmp_dir, core=core): ...drive SenderGateway...`. Pass **the identical imported Core module object** used to instantiate `SenderGateway`; this matters for tests loading the module via `importlib`. The default import only works when the fixture uses the regular `HL_Live_Copy_Service_Core` import. No autouse fixture, no patch of `_GLOBAL_INSTANCE_LOCK_OWNED`, no fabricated authority. The lock seam is patched to a **`pathlib.Path`** (never a string), so Core's `lock_path.parent.mkdir()`, `open()` and `_global_holder_path()` receive the expected type. The temporary directory must already exist beneath Python's system tempfile root; this deliberately rejects arbitrary live paths. The `finally` releases through Core's one release function even if the test throws. Do not use this context manager for tests whose expected outcome is no-lease refusal.

**Exact state on this branch:** `acquire_global_instance_lock()` creates and locks the OS file, assigns `_GLOBAL_INSTANCE_LOCK = fh`, then sets `_GLOBAL_INSTANCE_LOCK_OWNED = True`. `SenderGateway._place_order()` reads those **two globals from that same module object**, requiring the owned flag, a non-None handle and `not handle.closed` after `pre_send`, immediately before `exchange.order`. `release_global_instance_lock()` sets the flag `False`, clears the global handle and closes the OS descriptor. There is **no** `_global_sender_lease_held()` on `522b206`; that name belongs to the superseded `207e3af` branch revision, where it read a PID/inode/probe stack now removed by the controller's SEND-BACK2 ruling.

**Where the existing C1–C4 harness locks:** `_archive/hl_stage2/test_core_c7_sender_fence.py` sets `ROOT = Path(os.getenv("TMPDIR") or tempfile.gettempdir()) / "te_sender_fence"`, creates that root, and sets `os.environ["HL_LIVE_GLOBAL_LOCK_FILE"] = str(ROOT / "engine-global.lock")` **before** parent and child Core imports. Thus its `acquire_global_instance_lock(state_a)` opens `ROOT / "engine-global.lock"`, **not** the machine-wide production lock path; holder metadata is adjacent in the same temporary root. The builder's 15-file fixture should likewise use a unique isolated root and the patch seam above, not touch the running engine's lock or state dir.

**Unverified:** this snippet has been reviewed against source but has not been executed in this GitHub-only lane. The builder must test Windows and the full 15-file gate, and report exact SHA and outcomes. The positive ENTRY/EXIT tests remain in the separate existing fence harness; the fixture is not a PASS certification.
