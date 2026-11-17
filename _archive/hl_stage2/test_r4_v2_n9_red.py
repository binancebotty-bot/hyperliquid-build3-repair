"""R4 v2 / N9 RED gate: pytest-collectable, N9-only execution of the real Run 3 fixture.

The original test_core_run3_fixes.py has two N9 checks inside main() and
terminates via os._exit, so pytest cannot collect those checks as tests.
This subprocess runs the SAME fixture and REAL SenderGateway._send_real,
intercepts ONLY the two N9 results, and exits before the unrelated G1
mainnet-guard fixture. Network and SDK orders are mocked by that fixture.

Host RED gate:
    python -m pytest -q -s _archive/hl_stage2/test_r4_v2_n9_red.py
"""
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "test_core_run3_fixes.py"

N9_EXPECTED = (
    "N9_REDUCE_ONLY_REJECT_RESENT_AFTER_CATCH_UP",
    "N9_NO_CATCH_UP_NO_BLIND_RESEND",
)

# Do not reproduce N9's fixture or stub its send logic: run the exact existing
# test's setup and assertions, stopping as soon as both N9 checks are observed.
WORKER = r"""
import importlib.util
import sys

source = sys.argv[1]
spec = importlib.util.spec_from_file_location("run3_n9_witness", source)
witness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(witness)

expected = (
    "N9_REDUCE_ONLY_REJECT_RESENT_AFTER_CATCH_UP",
    "N9_NO_CATCH_UP_NO_BLIND_RESEND",
)
seen = {}
original_check = witness.check

class N9Finished(Exception):
    pass

def capture(name, condition, detail=""):
    if name in expected:
        seen[name] = bool(condition)
        print("N9_RED::%s_%s%s" %
              (name, "PASS" if condition else "FAIL",
               "" if condition else (" | " + str(detail)[:600])), flush=True)
        if len(seen) == len(expected):
            raise N9Finished()
        return
    # Earlier fixture checks are allowed to run but cannot hide the N9 verdict.
    original_check(name, condition, detail)

witness.check = capture
try:
    witness.main()
except N9Finished:
    pass

missing = set(expected) - set(seen)
if missing:
    print("N9_RED::MISSING_CHECKS " + ",".join(sorted(missing)), flush=True)
    sys.exit(2)
failed = [name for name in expected if not seen[name]]
print("N9_RED_TOTAL=2 FAILED=%d" % len(failed), flush=True)
sys.exit(1 if failed else 0)
"""


def test_n9_reject_catchup_and_no_blind_resend():
    """N9 must retry only after owned-ledger net catch-up, never blindly.

    Case 1: reduce-only rejection + confirmed ledger catch-up allows the
    N9-owned close under the existing netting ruling, with second call no-RO.
    Case 2: no catch-up yields a single refused reduce-only attempt; never
    an unowned second physical order.
    """
    assert SOURCE.is_file(), "N9 fixture unavailable: %s" % SOURCE
    run = subprocess.run(
        [sys.executable, "-c", WORKER, str(SOURCE)],
        cwd=str(HERE),
        text=True,
        capture_output=True,
        timeout=120,
    )
    output = (run.stdout or "") + (run.stderr or "")
    print(output, end="" if output.endswith("\n") else "\n", flush=True)
    for name in N9_EXPECTED:
        assert "N9_RED::" + name + "_" in output, (
            "N9 witness not reached: %s; exit=%d\n%s" % (name, run.returncode, output)
        )
    assert run.returncode == 0, "N9 RED gate failed (exit %s)" % run.returncode
