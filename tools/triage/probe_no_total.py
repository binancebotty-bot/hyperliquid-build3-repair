"""Probe every test_*.py in _archive/hl_stage2; record parseability of output.

Rows: file, exit code, TOTAL= present, RESULT:: present, first stderr line.
Read-only w.r.t. the tests. Writes docs/BASE_RED_TRIAGE_B_raw.md.
"""
import glob
import os
import subprocess

PY = r"C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
D = os.path.join(ROOT, "_archive", "hl_stage2")
TIMEOUT = int(os.environ.get("PROBE_TIMEOUT", "120"))
OUT = os.environ.get("PROBE_OUT", os.path.join(ROOT, "docs", "BASE_RED_TRIAGE_B_raw.md"))


def first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:200]
    return ""


def dec(x):
    if isinstance(x, bytes):
        return x.decode("utf-8", "replace")
    return x or ""


def run(path):
    name = os.path.basename(path)
    try:
        p = subprocess.run([PY, name], cwd=D, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=TIMEOUT)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = "TIMEOUT", dec(e.stdout), dec(e.stderr)
    return {"name": name, "rc": rc, "total": "TOTAL=" in out,
            "result": "RESULT::" in out,
            "err1": "" if rc == 0 else first_line(err),
            "tail": first_line(out)}


def main():
    rows = [run(f) for f in sorted(glob.glob(os.path.join(D, "test_*.py")))]
    L = ["# BASE_RED_TRIAGE_B raw probe", "",
         f"commit a1acc28 | dir _archive/hl_stage2 | files {len(rows)} | timeout {TIMEOUT}s",
         f"interpreter {PY}", "",
         "| file | exit | TOTAL= | RESULT:: | first stderr line |",
         "|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['name']} | {r['rc']} | {'Y' if r['total'] else 'N'} | "
                 f"{'Y' if r['result'] else 'N'} | {r['err1'].replace('|', chr(92)+'|')} |")
    nt = [r for r in rows if not r["total"]]
    L += ["", f"files={len(rows)} with_TOTAL={len(rows)-len(nt)} no_TOTAL={len(nt)}",
          f"exit_nonzero={sum(1 for r in rows if r['rc'] != 0)} "
          f"timeouts={sum(1 for r in rows if r['rc'] == 'TIMEOUT')}", "", "## no-TOTAL files", ""]
    for r in nt:
        L.append(f"- {r['name']} exit={r['rc']} RESULT={'Y' if r['result'] else 'N'} tail={r['tail'][:120]}")
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote {OUT}: {len(rows)} files, {len(nt)} no-TOTAL, "
          f"{sum(1 for r in rows if r['rc'] == 'TIMEOUT')} timeouts")


if __name__ == "__main__":
    main()
