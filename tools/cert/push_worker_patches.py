"""Push every worker patch folder to origin.

Workers cannot push (headless, no credential prompt) but they DO write bundles + patches + HEAD.txt per the skill rule.
The coordinator pushes from the bundle - the token stays in the environment via a credential helper, never in argv.
"""
import os
import subprocess

PATCH_ROOT = r"C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/worker_patches"
REPO = r"C:/Users/wigmore/hyperliquid-build3-repair"
ENV_FILE = r"C:/Users/wigmore/.hermes/.env"

token = None
with open(ENV_FILE, encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        for key in ("GITHUB_TOKEN", "GITHUB_API_TOKEN", "GH_TOKEN"):
            if line.startswith(key + "="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
        if token:
            break

if not token:
    raise SystemExit("no token")

env = dict(os.environ, GIT_TOKEN=token)
helper = '!f() { echo username=x-access-token; echo password=$GIT_TOKEN; }; f'
base = ["git", "-C", REPO]
authed = base + ["-c", f"credential.helper={helper}"]

results = []
for card in sorted(os.listdir(PATCH_ROOT)):
    folder = os.path.join(PATCH_ROOT, card)
    if not os.path.isdir(folder):
        continue
    bundles = [f for f in os.listdir(folder) if f.endswith(".bundle")]
    if not bundles:
        results.append((card, "NO BUNDLE", ""))
        continue

    # Prefer the bundle whose HEAD matches HEAD.txt. Alphabetical order picked a STALE bundle on t_4cd40044 and
    # pushed a superseded commit over the corrected one - the worker had written two bundles across two runs.
    want = ""
    hp = os.path.join(folder, "HEAD.txt")
    if os.path.exists(hp):
        txt = open(hp, encoding="utf-8", errors="ignore").read()
        for token in txt.replace("=", " ").split():
            if len(token) >= 7 and all(ch in "0123456789abcdef" for ch in token.lower()):
                want = token
                break
    chosen = None
    for f in bundles:
        heads = subprocess.run(base + ["bundle", "list-heads", os.path.join(folder, f)],
                               capture_output=True, text=True, timeout=60).stdout
        if want and want[:8] in heads:
            chosen = f
            break
    bundle = os.path.join(folder, chosen or bundles[0])

    heads = subprocess.run(base + ["bundle", "list-heads", bundle],
                           capture_output=True, text=True, timeout=60).stdout.split()
    pairs = [(heads[i], heads[i + 1]) for i in range(0, len(heads) - 1, 2)]
    named = [ref for _, ref in pairs if ref.startswith("refs/heads/")]
    if named:
        src = named[0]
        target = src if src not in ("refs/heads/main", "refs/heads/master") else f"refs/heads/hermes/{card}"
    elif pairs:
        # git bundle create <file> HEAD stores the ref as plain "HEAD" - push it to a branch named after the card
        src = "HEAD"
        target = f"refs/heads/hermes/{card}"
    else:
        results.append((card, "EMPTY BUNDLE", ""))
        continue

    f = subprocess.run(base + ["fetch", "--no-tags", bundle, f"{src}:refs/patchpush/{card}"],
                       capture_output=True, text=True, timeout=180)
    if f.returncode != 0:
        results.append((card, "FETCH FAILED", (f.stderr or "").strip().splitlines()[-1][:110]))
        continue

    sha = subprocess.run(base + ["rev-parse", f"refs/patchpush/{card}"],
                         capture_output=True, text=True).stdout.strip()[:12]
    p = subprocess.run(authed + ["push", "origin", f"refs/patchpush/{card}:{target}"],
                       capture_output=True, text=True, env=env, timeout=240)
    if p.returncode == 0:
        results.append((card, "PUSHED", f"{sha} -> {target}"))
    else:
        err = (p.stderr or "").strip().splitlines()
        results.append((card, "PUSH FAILED", err[-1][:110] if err else ""))

print("  %-14s %-13s %s" % ("CARD", "RESULT", "DETAIL"))
for card, status, detail in results:
    print("  %-14s %-13s %s" % (card, status, detail))

print()
v = subprocess.run(base + ["ls-remote", "--heads", "origin"], capture_output=True, text=True, timeout=180)
wanted = {c for c, s, _ in results if s == "PUSHED"}
for line in (v.stdout or "").splitlines():
    for c in wanted:
        if c in line:
            print("   verified:", line)
