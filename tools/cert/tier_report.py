"""Report Tier 1 and Tier 2 separately, using the SAME proof standard as the completion gate.

Controller ruling 6271119307: do not change the gate. Add `tier: 1|2` to the register and write this report instead. It
reads the same records and the same triple-match logic (`completion_gate.is_independent_verification`) and reports both
numbers every time:

    Tier 1 proven / total        (the blocking set)
    Full register proven / total (what the gate reports)

    python tools/cert/tier_report.py
    python tools/cert/tier_report.py --json
    python tools/cert/tier_report.py --rows        # one line per Tier-1 row

Exit 0 always: this is a report, not a gate. It never blocks anything.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

WS = Path(r"C:/Users/wigmore/hyperliquid-build3-repair")
MATRIX = WS / "certification" / "certification_matrix.json"
GATE_SCRIPTS = Path(r"C:/Users/wigmore/.hermes/skills/project-launch/scripts")


def load_gate():
    """Import the gate's own verifier so this report cannot drift from it."""
    if str(GATE_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(GATE_SCRIPTS))
    try:
        import completion_gate as cg
        return cg
    except Exception:
        return None


def proof_state(rec, cg) -> tuple[bool, str]:
    """Proven only when the gate's independent-verification test passes."""
    if cg is not None:
        try:
            if cg.is_independent_verification(rec, workspace=str(WS)):
                return True, "attested"
        except Exception:
            pass
    if str(rec.get("verified")) is True and rec.get("verifier") and rec.get("review_ref"):
        return False, "self-declared, no matching record"
    return False, "not attested"


def main() -> int:
    doc = json.loads(MATRIX.read_text(encoding="utf-8-sig"))
    recs = doc.get("records") or []
    cg = load_gate()

    tiers = {1: [], 2: []}
    for r in recs:
        tiers[1 if int(r.get("tier") or 2) == 1 else 2].append(r)

    out = {"tier1": {}, "tier2": {}, "all": {}, "gate_imported": cg is not None}
    for t in (1, 2):
        rows = tiers[t]
        proven = [r for r in rows if proof_state(r, cg)[0]]
        out["tier%d" % t] = {
            "total": len(rows),
            "proven": len(proven),
            "verdicts": dict(Counter(str(r.get("result")) for r in rows)),
            "not_pass": sum(1 for r in rows if str(r.get("result")) != "PASS"),
        }
    proven_all = [r for r in recs if proof_state(r, cg)[0]]
    out["all"] = {"total": len(recs), "proven": len(proven_all),
                  "verdicts": dict(Counter(str(r.get("result")) for r in recs))}

    if "--json" in sys.argv:
        print(json.dumps(out, indent=1))
        return 0

    if "--rows" in sys.argv:
        for r in sorted(tiers[1], key=lambda x: str(x.get("id"))):
            ok, why = proof_state(r, cg)
            print("  %-14s %-6s %-11s %-8s %s" % (
                str(r.get("id"))[:14], str(r.get("area"))[:6], str(r.get("result")),
                "PROVEN" if ok else "-", why))
        return 0

    t1, t2, al = out["tier1"], out["tier2"], out["all"]
    print("TIER 1 (blocking)      %3d proven of %3d   | verdicts %s" % (t1["proven"], t1["total"], t1["verdicts"]))
    print("                       %3d row(s) still not PASS" % t1["not_pass"])
    print("TIER 2 (tracked)       %3d proven of %3d   | verdicts %s" % (t2["proven"], t2["total"], t2["verdicts"]))
    print("FULL REGISTER          %3d proven of %3d   | verdicts %s" % (al["proven"], al["total"], al["verdicts"]))
    print("")
    print("Gate imported: %s  (proof standard = completion_gate.is_independent_verification)" % out["gate_imported"])
    print("The gate itself still reports all %d as one set; this report is the tiered view." % al["total"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
