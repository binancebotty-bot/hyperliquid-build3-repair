"""Offline production-derivation checks for UI-WALLET-015..019."""
import asyncio
import copy
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "_archive" / "hl_stage2" / "HL_Copy_App_SSOT.py"
PROBE = Path(r"C:/Users/wigmore/.hermes/cache/scratch/wallet2d/probe")

TARGET = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"

# Paths isolated for the purge (SSOT 518+); RAW_FILLS_CSV is a legacy leftover from the
# pre-narrowing full purge and no assertion depends on it.
# DATA_DIR is redirected separately: it is the root of the backup location.
PURGE_PATH_NAMES = (
    "RAW_FILLS_CSV", "EXPECTED_COPY_FILLS_CSV", "COPY_TRADES_CSV",
    "LIVE_WALLET_METRICS_CSV",
    "UI_STATE_FILE", "WALLET_GATE_FILE", "LIVE_COPY_CONFIG_FILE",
    "EXCHANGE_BASELINES_JSON", "ENGINE_TRUTH_JSON", "LEGACY_LIVE_STATE_JSON",
    "PURGED_WALLETS_FILE", "MANUAL_WALLETS_FILE",
    "APP_MODEL_STATE_JSON", "PORTFOLIO_HISTORY_FILE", "EQUITY_HISTORY_FILE",
)


def load(path=APP, name="wallet2_app"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def check(name, fn):
    try:
        fn()
        print(f"RESULT::{name}_PASS")
        return True
    except Exception as exc:
        print(f"RESULT::{name}_FAIL::{type(exc).__name__}:{exc}")
        return False


def isolate_purge_paths(mod, root):
    """Redirect every purge target AND the backup location into root.

    Returns the original attribute values so the caller can restore them;
    backup_purge_files derives its destination from DATA_DIR, and all
    relative_to() bookkeeping derives from BASE_DIR, so both are moved too.
    """
    data = root / "hl_copy_output"
    data.mkdir(parents=True, exist_ok=True)
    saved = {"BASE_DIR": mod.BASE_DIR, "DATA_DIR": mod.DATA_DIR}
    mod.BASE_DIR = root
    mod.DATA_DIR = data
    paths = {}
    for name in PURGE_PATH_NAMES:
        saved[name] = getattr(mod, name)
        path = data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        setattr(mod, name, path)
        paths[name] = path
    return saved, paths


def restore_attrs(mod, saved):
    for name, value in saved.items():
        setattr(mod, name, value)


# Row checks take the module under test: the SAME check drives the live verdict
# and the throwaway rename probe, so probe logic can never diverge from the row.
def row_015(mod):
    # Real app-config purge, fully contained: all targets + backup location live in a
    # TemporaryDirectory. Assert the derived result, not the mutation itself.
    # 42ac357 narrowed PURGE to app config/caches/live state; engine history and positions
    # are deliberately kept, so the row's "purge everywhere" prose no longer describes the product.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        saved, paths = isolate_purge_paths(mod, root)
        try:
            ui_path = paths["UI_STATE_FILE"]
            pre = {
                "wallet_config": {TARGET: {"mode": "LIVE"}},
                "wallet_include": {TARGET: True, OTHER: False},
                "keep_me": "present",
            }
            ui_path.write_text(json.dumps(pre), encoding="utf-8")
            paths["MANUAL_WALLETS_FILE"].write_text(
                f"{TARGET}\n{OTHER}\n", encoding="utf-8"
            )
            paths["PURGED_WALLETS_FILE"].write_text("", encoding="utf-8")

            result = mod.purge_wallet_app_config(TARGET)

            assert result["ok"] is True, result
            post = json.loads(ui_path.read_text(encoding="utf-8"))
            assert TARGET not in post["wallet_config"], post
            assert TARGET not in post["wallet_include"], post
            assert OTHER in post["wallet_include"], post  # sibling survives
            assert post["keep_me"] == "present", post
            backup = Path(result["backup_dir"])
            assert backup.is_dir(), backup
            backed = backup / ui_path.relative_to(root)
            assert backed.is_file(), sorted(str(p) for p in backup.rglob("*"))
            assert json.loads(backed.read_text(encoding="utf-8")) == pre
        finally:
            restore_attrs(mod, saved)


def row_016(mod):
    assert mod.wallet_included("0xabc", {"wallet_include": {"0xabc": False}}) is False
    assert mod.wallet_included("0xdef", {"wallet_include": {}}) is True


def row_017(mod):
    # "watch" is a member of WALLET_META_TAGS (SSOT 866, 881-883); it must survive sanitisation.
    got = mod.set_wallet_meta({}, "0xABC", "watch", "note", "blue")
    assert got["0xabc"] == {"tag": "watch", "note": "note", "color": "blue"}


class _BodyRequest:
    """Minimal stand-in for the ASGI Request: only json() is used by the handler."""

    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def call_add_wallet(mod, body):
    return asyncio.run(mod.add_live_config_wallet(_BodyRequest(body)))


def response_parts(resp):
    return resp.status_code, json.loads(resp.body)


def row_018(mod):
    # Real async handler; only its load/save persistence boundaries are stubbed.
    # UI-WALLET-018: "Adding an existing or archived wallet restores the existing record rather than creating a second."
    # Test the archived re-add path: wallet exists in archived_wallets, not in wallets.
    captured = {}

    # Fixture: wallet is archived with specific meta (tag, copy_mode, etc.)
    archived_wallet = {
        "mode": "OFF",
        "enabled": False,
        "copy_mode": "proportional",
        "norm_base": 5000.0,
        "tag": "ArchivedLeader",
        "archived_at": "2026-01-01T00:00:00Z",
    }

    def fake_load():
        # Return a fresh copy each call so mutations don't leak
        return {"wallets": {}, "archived_wallets": {TARGET: copy.deepcopy(archived_wallet)}}

    def fake_save(config):
        captured["config"] = copy.deepcopy(config)
        captured["saves"] = captured.get("saves", 0) + 1

    saved = (mod._load_live_copy_config, mod._save_live_copy_config)
    mod._load_live_copy_config = fake_load
    mod._save_live_copy_config = fake_save
    try:
        # Re-add the archived wallet: should restore from archived_wallets, not create duplicate
        status, payload = response_parts(
            call_add_wallet(mod, {"wallet": TARGET, "mode": "LIVE", "copy_mode": "fixed"})
        )
        assert status == 200, (status, payload)
        assert payload.get("ok") is True, payload
        assert captured.get("saves") == 1, captured
        saved_cfg = captured["config"]
        assert TARGET in saved_cfg["wallets"], saved_cfg
        assert TARGET not in saved_cfg["archived_wallets"], "archived wallet should be removed on re-add"
        # The restored wallet should have the new mode (LIVE) but preserve archived meta where not overridden
        assert saved_cfg["wallets"][TARGET]["mode"] == "LIVE", saved_cfg
        assert saved_cfg["wallets"][TARGET]["copy_mode"] == "fixed", "new copy_mode from request should apply"
        assert saved_cfg["wallets"][TARGET]["norm_base"] == 5000.0, "archived norm_base should be preserved"
        assert saved_cfg["wallets"][TARGET]["tag"] == "ArchivedLeader", "archived tag should be preserved"
        assert payload["config"]["wallets"][TARGET]["mode"] == "LIVE", payload

        # Documented rejection: a malformed wallet is refused and never saved.
        before = captured.get("saves", 0)
        bad_status, bad_payload = response_parts(
            call_add_wallet(mod, {"wallet": "not-a-wallet"})
        )
        assert bad_status == 400, (bad_status, bad_payload)
        assert bad_payload.get("ok") is False, bad_payload
        assert bad_payload.get("error") == "BAD_WALLET", bad_payload
        assert captured.get("saves") == before, "bad wallet must not reach save"
    finally:
        mod._load_live_copy_config, mod._save_live_copy_config = saved


def row_019(mod):
    # ws_subscription is derived at SSOT 3467 from health-file presence, shared
    # websocket status and mode. No health file + no shared WS + LIVE => NOT_SUBSCRIBED.
    rows = mod._build_live_wallet_rows(
        {"wallets": {"0xabc": {"mode": "LIVE", "enabled": True}}},
        [], [], {}, {}, {}, live_leader_performance={}, live_fills=[]
    )
    assert rows[0]["ws_subscription"] == "NOT_SUBSCRIBED"


def main():
    app = load()
    verdicts = {}

    verdicts["UI-WALLET-015"] = "PASS" if check("UI-WALLET-015", lambda: row_015(app)) else "FAIL"
    verdicts["UI-WALLET-016"] = "PASS" if check("UI-WALLET-016", lambda: row_016(app)) else "FAIL"
    verdicts["UI-WALLET-017"] = "PASS" if check("UI-WALLET-017", lambda: row_017(app)) else "FAIL"
    verdicts["UI-WALLET-018"] = "PASS" if check("UI-WALLET-018", lambda: row_018(app)) else "FAIL"
    verdicts["UI-WALLET-019"] = "PASS" if check("UI-WALLET-019", lambda: row_019(app)) else "FAIL"

    # One throwaway source mutation per executable row; verify only its row flips.
    # (target, needle, replacement, row check, unaffected other check)
    probes = [
        ("UI-WALLET-015", 'for key in ("wallet_config', 'for key_RENAMED in ("wallet_config', row_015, row_016),
        ("UI-WALLET-016", 'ui.get("wallet_include")', 'ui.get("wallet_include_RENAMED")', row_016, row_017),
        ("UI-WALLET-017", "WALLET_META_TAGS = {", "WALLET_META_TAGS_RENAMED = {", row_017, row_016),
        ("UI-WALLET-018",
         'config["wallets"][wallet] = _normalise_live_wallet_payload(body, existing)',
         'config["wallets"][wallet] = _normalise_live_wallet_payload_RENAMED(body, existing)',
         row_018, row_016),
        ("UI-WALLET-019", '"ws_subscription"', '"ws_subscription_RENAMED"', row_019, row_016),
    ]
    source = APP.read_text(encoding="utf-8")
    PROBE.mkdir(parents=True, exist_ok=True)
    for target, needle, replacement, row_fn, other_fn in probes:
        if target == "UI-WALLET-015":
            count = source.count(needle)
            assert count == 1, f"probe needle count for purge loop: {count} (expected 1): {needle}"
        else:
            assert needle in source, f"probe needle missing: {needle}"
        mutated = PROBE / f"{target}.py"
        mutated.write_text(source.replace(needle, replacement, 1), encoding="utf-8")
        mod_name = f"probe_{target.replace('-', '_')}"
        try:
            mod = load(mutated, mod_name)
            try:
                row_fn(mod)
                row_failed = False
            except Exception:
                row_failed = True
            try:
                other_fn(mod)
                other_pass = True
            except Exception:
                other_pass = False
            assert row_failed and other_pass, f"{target}: row_failed={row_failed} other_pass={other_pass}"
            print(f"PROBE::{target}::RENAMED={needle}::TARGET_FAIL::OTHER_PASS")
        finally:
            mutated.unlink(missing_ok=True)
            sys.modules.pop(mod_name, None)
    shutil.rmtree(PROBE, ignore_errors=True)

    passed = sum(v == "PASS" for v in verdicts.values())
    skipped = sum(v == "SKIP" for v in verdicts.values())
    failed = sum(v == "FAIL" for v in verdicts.values())
    print(f"RESULT::COUNT::{passed}_PASS::{skipped}_SKIP::{failed}_FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
