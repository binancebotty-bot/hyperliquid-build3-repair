"""AST census of exchange.order call sites across the five-file engine surface, at a given ref.

ENG-INV-02/06 require exactly ONE reachable production call site. Grep is not a census: it counts docstrings and
comments (the Core file mentions exchange.order() in prose twice). This walks the AST.
"""
import ast
import subprocess
import sys

REPO = r"C:/Users/wigmore/hyperliquid-build3-repair"
FILES = [
    "_archive/hl_stage2/convergence_shadow.py",
    "_archive/hl_stage2/exchange_truth.py",
    "_archive/hl_stage2/HL_Copy_App_SSOT.py",
    "_archive/hl_stage2/HL_Live_Copy_Service.py",
    "_archive/hl_stage2/HL_Live_Copy_Service_Core.py",
]


def blob(ref, path):
    r = subprocess.run(["git", "-C", REPO, "show", f"{ref}:{path}"], capture_output=True, timeout=120)
    return r.stdout if r.returncode == 0 else None


def census(ref):
    total = []
    print(f"  === {ref} ===")
    for path in FILES:
        data = blob(ref, path)
        if data is None:
            print(f"    {path.split('/')[-1]:<32} MISSING at this ref")
            continue
        try:
            tree = ast.parse(data.decode("utf-8-sig", errors="ignore"))
        except SyntaxError as exc:
            print(f"    {path.split('/')[-1]:<32} PARSE ERROR {exc}")
            continue
        calls = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "order" and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "exchange"):
                calls.append(node.lineno)
        flag = " <-- CALL SITE" if calls else ""
        print(f"    {path.split('/')[-1]:<32} {len(calls):>2} call(s) {calls}{flag}")
        total += [(path, ln) for ln in calls]
    print(f"    {'TOTAL production call sites':<32} {len(total)}")
    return total


if __name__ == "__main__":
    refs = sys.argv[1:] or ["origin/main"]
    for ref in refs:
        sites = census(ref)
        print()
        print(f"  single_order_call_site = {str(len(sites) == 1).lower()}")
        if len(sites) == 1:
            p, ln = sites[0]
            print(f"  the one site: {p.split('/')[-1]}:{ln}")
        print()
