#!/usr/bin/env python3
"""Record matrix run results into certification/run_results.json, then regenerate the status table.

Why this exists: gen_status.py builds the live table from run_results.json only. A verdict left in a
record's own `result` field is invisible to the table and drifts from it. Every verdict must therefore
enter through this tool, which refuses anything the table cannot show.

Usage:
  python record_result.py --run run19 --commit a1acc28 --follower-network testnet \
      --set ENG-INV-01=PASS --set NET-001=FAIL \
      --evidence "certification/results/ENG-INV-01.json" \
      --report RUN19_FINDINGS.md --summary "..."

  python record_result.py --list-runs
  python record_result.py --check          # verify every id exists and the table regenerates

A result line is ID=RESULT. RESULT must be PASS, FAIL or BLOCKED (NOT_TESTED means "do not record").
Unknown ids are refused: the matrix is the contract, not a suggestion.
"""
import argparse, csv, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MATRIX = HERE / "certification_matrix.json"
RUNS = HERE / "run_results.json"
ALLOWED = ("PASS", "FAIL", "BLOCKED")


def load():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8-sig"))
    runs = json.loads(RUNS.read_text(encoding="utf-8-sig"))
    return matrix, runs


def save(runs):
    RUNS.write_text(json.dumps(runs, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def regenerate():
    r = subprocess.run([sys.executable, str(HERE / "gen_status.py")], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("gen_status failed:\n" + r.stdout + r.stderr)
    return r.stdout.strip()


def parse_sets(items):
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit("bad --set %r, expected ID=RESULT" % item)
        rid, res = item.split("=", 1)
        rid, res = rid.strip(), res.strip().upper()
        if res not in ALLOWED:
            raise SystemExit("%s: result must be one of %s (got %r)" % (rid, ALLOWED, res))
        if rid in out:
            raise SystemExit("%s given twice" % rid)
        out[rid] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--commit")
    ap.add_argument("--follower-network", choices=("testnet", "mainnet"))
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--evidence", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--summary", default="")
    ap.add_argument("--list-runs", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    matrix, runs = load()
    ids = {r["id"] for r in matrix["records"]}

    if a.list_runs:
        for run in runs["runs"]:
            print("%-10s %-10s %-12s %s results" % (run["run"], run["commit"][:8], run["follower_network"], len(run["results"])))
        return
    if a.check:
        for run in runs["runs"]:
            for res in run["results"]:
                if res["id"] not in ids:
                    raise SystemExit("%s: unknown id %s" % (run["run"], res["id"]))
        print(regenerate())
        return

    if not (a.run and a.commit and a.follower_network and a.set):
        raise SystemExit("need --run, --commit, --follower-network and at least one --set ID=RESULT")

    wanted = parse_sets(a.set)
    unknown = sorted(set(wanted) - ids)
    if unknown:
        raise SystemExit("unknown matrix ids, refused: " + ", ".join(unknown))

    run = next((r for r in runs["runs"] if r["run"] == a.run), None)
    if run is None:
        run = {"run": a.run, "date": a.commit and "", "commit": a.commit, "network": "",
               "follower_network": a.follower_network, "report": a.report, "summary": a.summary,
               "results": []}
        runs["runs"].append(run)
    if run["commit"] != a.commit:
        raise SystemExit("run %s is pinned to commit %s, refusing to append results for %s"
                         % (a.run, run["commit"], a.commit))
    if run["follower_network"] != a.follower_network:
        raise SystemExit("run %s uses follower_network %s, got %s" % (a.run, run["follower_network"], a.follower_network))

    have = {r["id"]: r for r in run["results"]}
    # a later recording of the same id replaces the earlier one within the same run
    for rid, res in wanted.items():
        have[rid] = {"id": rid, "result": res, "evidence": a.evidence}
    order = [r["id"] for r in matrix["records"]]
    run["results"] = sorted(have.values(), key=lambda r: order.index(r["id"]))
    if a.summary:
        run["summary"] = a.summary
    save(runs)
    print("recorded %d results into %s @ %s" % (len(wanted), a.run, a.commit[:8]))
    print(regenerate())


if __name__ == "__main__":
    main()
