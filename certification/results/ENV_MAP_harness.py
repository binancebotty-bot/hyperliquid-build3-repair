#!/usr/bin/env python3
"""ENV-MAP evidence harness for task t_ce3bb91a (B3-ENV-MAP).

Wiring + fail-closed proof only. PLACES NO ORDER.
- Reads (never copies) C:/Users/wigmore/trading_stack/hl-prod-base/.env.testnet, NAMES only.
- Proves the bounded NAME-MAP (HL_TESTNET_* -> HL_LIVE_HL_*), identity, follower network,
  and a NON-VACUOUS negative set (wrong network REJECTED; non-distinct identity REJECTED).
- Proves the py3.11 SDK predicate that makes Core _send_real() stop returning SDK_UNAVAILABLE.
NO secret value is printed or stored; only public addresses are reported.
"""
import os, sys, json, subprocess, tempfile, importlib.util
from pathlib import Path

REPO = Path(r"C:/Users/wigmore/hyperliquid-build3-repair")
STAGE2 = REPO / "_archive" / "hl_stage2"
PROD_ENV = Path(r"C:/Users/wigmore/trading_stack/hl-prod-base/.env.testnet")
PY311 = r"C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe"
import glob as _glob
_cands = sorted(_glob.glob(r"C:/Users/wigmore/.hermes/tools/python-3.14*/python.exe"))
PY314 = _cands[0] if _cands else sys.executable
RESULTS = REPO / "certification" / "results"

checks = []
def ck(name, ok, detail):
    checks.append({"name": name, "pass": bool(ok), "detail": detail})
    return bool(ok)

# ---------------------------------------------------------------- A. name map
sys.path.insert(0, str(STAGE2))
import exchange_truth as X  # noqa: E402

src_names = []
for raw in PROD_ENV.read_text(encoding="utf-8-sig").splitlines():
    raw = raw.strip()
    if raw and not raw.startswith("#") and "=" in raw:
        src_names.append(raw.partition("=")[0].strip())
ck("prod_env_read_not_copied", PROD_ENV.exists() and not (REPO / PROD_ENV.name).exists(),
   {"path": str(PROD_ENV), "source_names": sorted(src_names)})

merged = X.env_with_file(PROD_ENV)
ck("name_map_publishes_canonical_names",
   all(k in merged and merged[k] for k in ("HL_LIVE_HL_ACCOUNT_ADDRESS", "HL_LIVE_HL_PRIVATE_KEY")),
   {"aliases": X.ENV_NAME_ALIASES,
    "canonical_present": {k: bool(merged.get(k)) for k in ("HL_LIVE_HL_ACCOUNT_ADDRESS", "HL_LIVE_HL_PRIVATE_KEY")}})

# os.environ must win over the alias
os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "SENTINEL_NOT_A_REAL_KEY"
m2 = X.env_with_file(PROD_ENV)
ck("os_environ_wins_over_alias", m2.get("HL_LIVE_HL_PRIVATE_KEY") == "SENTINEL_NOT_A_REAL_KEY",
   {"canonical_from_osenv": m2.get("HL_LIVE_HL_PRIVATE_KEY") == "SENTINEL_NOT_A_REAL_KEY"})
del os.environ["HL_LIVE_HL_PRIVATE_KEY"]

# ------------------------------------------------------- B. identity (positive)
ident = X.runtime_master_identity(merged)
master = ident.get("master", "")
signer = ident.get("signer", "")
ck("identity_ok_distinct",
   ident.get("ok") and ident.get("status") == "OK" and master and signer and master.lower() != signer.lower()
   and X.valid_address(master) and X.valid_address(signer),
   {"status": ident.get("status"), "master": master, "signer": signer})

# --------------------------------------- B2. identity NEGATIVE (non-distinct)
bad = dict(merged)
bad["HL_LIVE_HL_SIGNER_ADDRESS"] = master  # signer == master -> must be rejected
neg_ident = X.runtime_master_identity(bad)
neg_ident_rejected = (not neg_ident.get("ok")) and neg_ident.get("status") == X.IDENTITY_INVALID
ck("NEG_non_distinct_identity_rejected", neg_ident_rejected,
   {"status": neg_ident.get("status"), "detail": neg_ident.get("detail")})

# -------------------------------------------------------- C. networks positive
nets = X.resolve_networks(merged)
fol = nets["follower"]; lead = nets["leader"]
ck("follower_is_testnet", fol["network"] == "testnet", {"follower": fol["network"], "leader": lead["network"]})
ck("endpoint_netlocs_match",
   fol["exchange"].endswith("hyperliquid-testnet.xyz/exchange") and fol["info"].endswith("hyperliquid-testnet.xyz/info"),
   {"follower_info": fol["info"], "follower_exchange": fol["exchange"]})
ck("no_mainnet_on_follower", "api.hyperliquid.xyz" not in fol["base"], {"follower_base": fol["base"]})

# ------------------------------------- C2. network NEGATIVE (endpoint mismatch)
badnet = dict(merged)
badnet["HL_FOLLOWER_NETWORK"] = "testnet"
badnet["HL_LIVE_ORDER_ENDPOINT"] = "https://api.hyperliquid.xyz/exchange"  # mainnet vs testnet follower
net_rejected = False; net_err = ""
try:
    X.resolve_networks(badnet)
except X.NetworkConfigError as exc:
    net_rejected = True; net_err = str(exc)
ck("NEG_wrong_network_endpoint_rejected", net_rejected, {"error": net_err})

# ---------------------------------------------------- D. network stamp fail-closed
stamp_dir = Path(tempfile.mkdtemp(prefix="envmap_stamp_"))
X.claim_network_stamp(stamp_dir, nets)
stamp_rejected = False; stamp_err = ""
try:
    X.claim_network_stamp(stamp_dir, {"leader": X.network_endpoints("mainnet"),
                                      "follower": X.network_endpoints("mainnet")})
except X.NetworkConfigError as exc:
    stamp_rejected = True; stamp_err = str(exc)
ck("NEG_state_dir_network_stamp_mismatch_rejected", stamp_rejected, {"error": stamp_err})

# -------------------------------- E. Core import under py3.11: _send_real SDK gate
os.environ["HL_LIVE_ENV_FILE"] = str(PROD_ENV)
os.environ["HL_FOLLOWER_NETWORK"] = "testnet"
os.environ["HL_LIVE_AUDIT_DIR"] = tempfile.mkdtemp(prefix="envmap_audit_")
MOD = "hl_core_envmap"
spec = importlib.util.spec_from_file_location(MOD, str(STAGE2 / "HL_Live_Copy_Service_Core.py"))
core = importlib.util.module_from_spec(spec)
sys.modules[MOD] = core
spec.loader.exec_module(core)

sdk_predicate_false = not (core.HLAccount is None or core.HLExchange is None)
ck("py311_sdk_available_sendreal_gate_false", sdk_predicate_false,
   {"HLAccount_is_None": core.HLAccount is None, "HLExchange_is_None": core.HLExchange is None,
    "guard": "_send_real L3380 returns SDK_UNAVAILABLE iff HLAccount/HLExchange is None"})
ck("core_loaded_name_map_into_environ",
   X.valid_address(os.environ.get("HL_LIVE_HL_ACCOUNT_ADDRESS"))
   and bool(os.environ.get("HL_LIVE_HL_PRIVATE_KEY")),
   {"account_present": bool(os.environ.get("HL_LIVE_HL_ACCOUNT_ADDRESS")),
    "private_key_present": bool(os.environ.get("HL_LIVE_HL_PRIVATE_KEY"))})
ck("core_follower_network_testnet", core.FOLLOWER_NETWORK == "testnet",
   {"follower": core.FOLLOWER_NETWORK, "leader": core.LEADER_NETWORK,
    "exchange_url": core.HL_EXCHANGE_URL})

# ------------------------------------------ F. differential: py3.14 lacks the SDK
probe = "import hyperliquid"
r314 = subprocess.run([PY314, "-c", probe], capture_output=True, text=True)
r311 = subprocess.run([PY311, "-c", probe], capture_output=True, text=True)
ck("differential_py311_has_sdk_py314_does_not",
   r311.returncode == 0 and r314.returncode != 0,
   {"py311_ok": r311.returncode == 0, "py314_ok": r314.returncode == 0,
    "py314_err": (r314.stderr.strip().splitlines() or [""])[-1]})

tested_commit = subprocess.run(["git", "-C", str(REPO).replace("\\", "/"), "rev-parse", "HEAD"],
                               capture_output=True, text=True).stdout.strip()
import hashlib
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

result = {
    "task": "t_ce3bb91a",
    "title": "B3-ENV-MAP repoint HL_LIVE_ENV_FILE; bounded NAME-MAP; fail-closed identity/network",
    "tested_commit": tested_commit,
    "env_file_path": str(PROD_ENV),
    "env_file_sha256": sha(PROD_ENV),
    "env_file_source_names": sorted(src_names),
    "engine_sha256": {
        "_archive/hl_stage2/exchange_truth.py": sha(STAGE2 / "exchange_truth.py"),
        "_archive/hl_stage2/HL_Live_Copy_Service_Core.py": sha(STAGE2 / "HL_Live_Copy_Service_Core.py"),
    },
    "python": {"evidence_runner": sys.version.split()[0], "sdk_py": "3.11", "hermes_py": "3.14 (no SDK)"},
    "identity": {"status": ident.get("status"), "master": master, "signer": signer},
    "follower_network": fol["network"],
    "endpoint_netlocs": {"follower_info": fol["info"], "follower_exchange": fol["exchange"]},
    "negative_tests": {
        "non_distinct_identity": {"rejected": neg_ident_rejected, "status": neg_ident.get("status")},
        "wrong_network_endpoint": {"rejected": net_rejected, "error": net_err},
        "state_dir_network_stamp_mismatch": {"rejected": stamp_rejected, "error": stamp_err},
    },
    "checks": checks,
    "passed": all(c["pass"] for c in checks),
    "orders_placed": False,
}
RESULTS.mkdir(parents=True, exist_ok=True)
out = RESULTS / f"ENV_MAP_{tested_commit[:12]}.json"
out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps({"written": str(out), "passed": result["passed"],
                  "failed": [c["name"] for c in checks if not c["pass"]]}, indent=2))
