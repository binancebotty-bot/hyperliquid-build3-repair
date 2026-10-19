"""Which register rows cite a source_sha256 that does not match the file at their OWN tested_commit?

The UI rows are the suspect set: source_sha256 declares fad19d22 (a file outside git, served by :8023), while
tested_commit points at a repo commit. If the file at that commit hashes to something else, the row asserts two
incompatible things at once and cannot be verified against either.
"""
import json
import subprocess
import sys

MATRIX = "origin/cert/local-main-b142cf8:certification/certification_matrix.json"
CANDIDATE_PATHS = [
    "_archive/hl_stage2/HL_Copy_App_SSOT.py",
    "HL_Copy_App_SSOT_20260513.py",
    "certification/../_archive/hl_stage2/HL_Copy_App_SSOT.py",
]


def blob_hash(commit, path):
    try:
        out = subprocess.run(["git", "show", f"{commit}:{path}"], capture_output=True, timeout=60)
        if out.returncode != 0 or not out.stdout:
            return None
        import hashlib
        return hashlib.sha256(out.stdout).hexdigest()
    except Exception:
        return None


def main():
    raw = subprocess.run(["git", "show", MATRIX], capture_output=True, timeout=120).stdout
    data = json.loads(raw)
    records = data["records"]
    declared = data.get("source_sha256") or {}
    print(f"  rows: {len(records)}")
    print(f"  source_sha256 keys: {len(declared)}")
    for k, v in list(declared.items())[:6]:
        print(f"    {k} -> {v[:16]}")

    ui_rows = [r for r in records if str(r.get("source_sha256") or "") .startswith("fad19d22")]
    print(f"\n  rows declaring source_sha256 = fad19d22: {len(ui_rows)}")

    cache = {}
    mismatch = match = nocommit = nofile = 0
    examples = []
    for r in ui_rows:
        tc = r.get("tested_commit")
        rid = r.get("id")
        if not tc:
            nocommit += 1
            continue
        h = None
        for p in CANDIDATE_PATHS:
            key = (tc, p)
            if key not in cache:
                cache[key] = blob_hash(tc, p)
            if cache[key]:
                h = cache[key]
                break
        if not h:
            nofile += 1
            continue
        if h.startswith("fad19d22"):
            match += 1
        else:
            mismatch += 1
            if len(examples) < 8:
                examples.append((rid, tc, h[:16]))

    print(f"  file at tested_commit MATCHES declared hash : {match}")
    print(f"  file at tested_commit DIFFERS              : {mismatch}")
    print(f"  no tested_commit                           : {nocommit}")
    print(f"  file not found at that commit              : {nofile}")
    if examples:
        print("\n  examples (row, tested_commit, actual file hash):")
        for rid, tc, h in examples:
            print(f"    {rid:<22} {tc:<10} {h}")


if __name__ == "__main__":
    main()
