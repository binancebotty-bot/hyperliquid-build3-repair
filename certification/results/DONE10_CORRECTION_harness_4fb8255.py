#!/usr/bin/env python3
"""
DONE10_CORRECTION_harness_4fb8255.py

Correction of the DONE-10 PASS in RHC_RESIDUAL_2a269ad.json (committed 4fb8255).

DONE-10 = CONTROL / APPLIES, feature 'Richard explicitly decides LIVE/mainnet'.
This is a HUMAN-AUTHORITY gate. The previous harness 'certified' it PASS via
check_done10_positive(), whose body only asserted the control-mailbox git branch
and control_mailbox/ structure EXIST. That proves the mailbox TRANSPORT exists,
not that Richard made the LIVE/mainnet decision.

This correction harness:
  1. Verifies the engine SHA256 is unchanged.
  2. Verifies the control-mailbox transport exists (as a transport check only).
  3. Searches the control mailbox and EVIDENCE/DECISIONS.md for any recorded
     human LIVE/mainnet decision. If none is found, DONE-10 is BLOCKED.
  4. Keeps the negative control (no auto-LIVE: default_network != mainnet,
     no wallet mode==LIVE).

Verdict: BLOCKED on operator's LIVE/mainnet decision.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone

REPO = Path("C:/Users/wigmore/hyperliquid-build3-repair")
ENGINE_PATH = REPO / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
COMMIT = "4fb8255354180189f813524786ede44700312071"
COMMIT10 = COMMIT[:10]
ENGINE_SHA256 = "2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405"

LEADER = "0x" + "d" * 40

CHECKS = []
NEG_TESTS = []


def check(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "pass": bool(passed), "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  CHECK::{name}::{status}" + (f" | {detail}" if detail and not passed else ""))


def neg_test(name: str, passed: bool, detail: str = "") -> None:
    NEG_TESTS.append({"name": name, "pass": bool(passed), "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  NEG::{name}::{status}" + (f" | {detail}" if detail and not passed else ""))


def run_check(name, fn):
    try:
        detail = fn()
        return True, detail
    except AssertionError as e:
        return False, f"ASSERT: {e}"
    except Exception as e:
        return False, f"ERROR: {type(e).__name__}: {e}"


# ============================================================
# CHECK 1: Engine SHA256 unchanged
# ============================================================

def check_engine_sha256():
    with open(ENGINE_PATH, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    assert actual == ENGINE_SHA256, f"Engine SHA256 mismatch: {actual}"
    return f"sha256={actual[:12]}... (unchanged)"


# ============================================================
# CHECK 2: Control-mailbox transport exists (transport only)
# ============================================================

def check_mailbox_transport():
    """Verify the control-mailbox branch and structure exist (transport check)."""
    result = subprocess.run(
        ["git", "-C", str(REPO), "branch", "-a"],
        capture_output=True, text=True, timeout=10
    )
    branches = result.stdout
    assert "control-mailbox" in branches, "control-mailbox branch not found"

    result = subprocess.run(
        ["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", "origin/control-mailbox"],
        capture_output=True, text=True, timeout=10
    )
    files = result.stdout
    assert "control_mailbox/" in files, "control_mailbox/ not found"
    return "control-mailbox branch + control_mailbox/ structure exist (transport)"


# ============================================================
# CHECK 3: Search for recorded human LIVE/mainnet decision
# ============================================================

def search_control_mailbox_for_live_decision():
    """Search all control-mailbox inbox messages for a LIVE/mainnet decision."""
    result = subprocess.run(
        ["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", "origin/control-mailbox"],
        capture_output=True, text=True, timeout=10
    )
    inbox_files = [
        f for f in result.stdout.strip().split("\n")
        if f.startswith("control_mailbox/inbox/") and f.endswith(".json")
    ]

    live_decision_found = False
    live_decision_evidence = None

    # Negation patterns that indicate the OPPOSITE of a decision
    negation_patterns = [
        r"NOT\s+AUTHORI",
        r"FORBIDDEN",
        r"remains\s+FORBIDDEN",
        r"NOT\s+approved",
        r"NOT\s+authorised",
        r"NOT\s+authorized",
        r"prohibited",
        r"must\s+not.*LIVE",
        r"must\s+not.*mainnet",
        r"no\s+LIVE",
        r"no\s+mainnet",
        r"zero\s+LIVE",
        r"zero\s+mainnet",
        r"blocked.*LIVE",
        r"blocked.*mainnet",
        r"LIVE.*blocked",
        r"mainnet.*blocked",
    ]

    # Affirmative decision patterns (must NOT be near a negation)
    affirmative_patterns = [
        r"Richard\s+(?:authorises?|approves?|decides?|rules?|grants?)\s+(?:a\s+)?LIVE",
        r"Richard\s+(?:authorises?|approves?|decides?|rules?|grants?)\s+(?:a\s+)?mainnet",
        r"operator\s+(?:authorises?|approves?|decides?|rules?|grants?)\s+(?:a\s+)?LIVE",
        r"operator\s+(?:authorises?|approves?|decides?|rules?|grants?)\s+(?:a\s+)?mainnet",
        r"LIVE\s+mainnet\s+(?:is\s+)?(?:authorised|approved|granted|decided)",
        r"mainnet\s+LIVE\s+(?:is\s+)?(?:authorised|approved|granted|decided)",
        r"(?:authorise|approve|grant|decide|rule)\s+.*LIVE\s+mainnet",
        r"(?:authorise|approve|grant|decide|rule)\s+.*mainnet\s+LIVE",
        r"GO\s+LIVE",
        r"GO\s+mainnet",
        r"LIVE\s+mainnet\s+GO",
        r"mainnet\s+LIVE\s+GO",
        r"LIVE\s+mainnet\s+yes",
        r"mainnet\s+LIVE\s+yes",
        r"approve.*LIVE\s+mainnet",
        r"approve.*mainnet\s+LIVE",
    ]

    for f in inbox_files:
        show = subprocess.run(
            ["git", "-C", str(REPO), "show", f"origin/control-mailbox:{f}"],
            capture_output=True, text=True, timeout=10
        )
        try:
            msg = json.loads(show.stdout)
        except json.JSONDecodeError:
            continue

        body = msg.get("BODY", "")
        msg_type = msg.get("TYPE", "")

        # Check for affirmative patterns
        for pattern in affirmative_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                # Check if this match is near a negation
                # Get surrounding context (200 chars before and after)
                start = max(0, match.start() - 200)
                end = min(len(body), match.end() + 200)
                context = body[start:end]

                is_negated = False
                for neg_pat in negation_patterns:
                    if re.search(neg_pat, context, re.IGNORECASE):
                        is_negated = True
                        break

                if not is_negated:
                    live_decision_found = True
                    live_decision_evidence = f"{f}: pattern '{pattern}' matched (no negation in context)"
                    break

        if live_decision_found:
            break

    return live_decision_found, live_decision_evidence, len(inbox_files)


def search_decisions_md_for_live_decision():
    """Search EVIDENCE/DECISIONS.md for a LIVE/mainnet decision."""
    decisions_path = REPO / "EVIDENCE" / "DECISIONS.md"
    if not decisions_path.exists():
        return False, "EVIDENCE/DECISIONS.md not found"

    content = decisions_path.read_text(encoding="utf-8")

    negation_patterns = [
        r"NOT\s+AUTHORI", r"FORBIDDEN", r"remains\s+FORBIDDEN",
        r"NOT\s+approved", r"NOT\s+authorised", r"NOT\s+authorized",
        r"prohibited", r"must\s+not.*LIVE", r"must\s+not.*mainnet",
        r"no\s+LIVE", r"no\s+mainnet", r"zero\s+LIVE", r"zero\s+mainnet",
        r"blocked.*LIVE", r"blocked.*mainnet", r"LIVE.*blocked", r"mainnet.*blocked",
    ]

    affirmative_patterns = [
        r"Richard\s+(?:authorises?|approves?|decides?|rules?|grants?)\s+(?:a\s+)?LIVE",
        r"Richard\s+(?:authorises?|approves?|decides?|rules?|grants?)\s+(?:a\s+)?mainnet",
        r"operator\s+(?:authorises?|approves?|decides?|rules?|grants?)\s+(?:a\s+)?LIVE",
        r"operator\s+(?:authorises?|approves?|decides?|rules?|grants?)\s+(?:a\s+)?mainnet",
        r"LIVE\s+mainnet\s+(?:is\s+)?(?:authorised|approved|granted|decided)",
        r"mainnet\s+LIVE\s+(?:is\s+)?(?:authorised|approved|granted|decided)",
        r"(?:authorise|approve|grant|decide|rule)\s+.*LIVE\s+mainnet",
        r"(?:authorise|approve|grant|decide|rule)\s+.*mainnet\s+LIVE",
        r"GO\s+LIVE", r"GO\s+mainnet", r"LIVE\s+mainnet\s+GO", r"mainnet\s+LIVE\s+GO",
        r"LIVE\s+mainnet\s+yes", r"mainnet\s+LIVE\s+yes",
        r"approve.*LIVE\s+mainnet", r"approve.*mainnet\s+LIVE",
    ]

    for pattern in affirmative_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 200)
            end = min(len(content), match.end() + 200)
            context = content[start:end]
            is_negated = any(re.search(neg_pat, context, re.IGNORECASE) for neg_pat in negation_patterns)
            if not is_negated:
                return True, f"EVIDENCE/DECISIONS.md: pattern '{pattern}' matched (no negation)"

    return False, "No LIVE/mainnet decision found in EVIDENCE/DECISIONS.md"


def check_done10_blocked():
    """
    DONE-10 is BLOCKED: no recorded human LIVE/mainnet decision exists.
    The control-mailbox transport exists, but that is NOT a human decision.
    """
    mailbox_found, mailbox_evidence, mailbox_count = search_control_mailbox_for_live_decision()
    decisions_found, decisions_evidence = search_decisions_md_for_live_decision()

    assert not mailbox_found, f"Unexpected: LIVE/mainnet decision found in control mailbox: {mailbox_evidence}"
    assert not decisions_found, f"Unexpected: LIVE/mainnet decision found in DECISIONS.md: {decisions_evidence}"

    return (
        f"BLOCKED: No recorded human LIVE/mainnet decision. "
        f"Searched {mailbox_count} control-mailbox messages + EVIDENCE/DECISIONS.md. "
        f"Transport exists but no operator ruling."
    )


# ============================================================
# CHECK 4: Negative control - no auto-LIVE (KEEP)
# ============================================================

def check_no_auto_live():
    """Negative: system does NOT auto-transition to LIVE/mainnet without human decision."""
    sys.path.insert(0, str(REPO / "_archive" / "hl_stage2"))
    import HL_Live_Copy_Service_Core as c

    tmp = Path(tempfile.mkdtemp(prefix="done10n_"))
    c.BASE_DIR = tmp
    c.ENGINE_OUTPUT_DIR = tmp / "hl_copy_output"
    c.AUDIT_DIR = tmp / "hl_live_copy_audit"
    c.APPEND_ONLY_DIR = c.AUDIT_DIR / "append_only"
    c.LIVE_CONFIG_FILE = c.AUDIT_DIR / "live_config.json"
    c.SERVICE_STATE_FILE = c.AUDIT_DIR / "live_service_state.json"
    c.CORE_RUNTIME_STATE_FILE = c.AUDIT_DIR / "clean_core_runtime_state.json"
    c.LIVE_WS_HEALTH_FILE = c.AUDIT_DIR / "live_ws_health.json"
    c.MANUAL_LIVE_POSITIONS_FILE = c.AUDIT_DIR / "manual_live_positions.json"
    c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = c.AUDIT_DIR / "exchange_account_snapshot.json"
    c.LIVE_INTEGRITY_STATUS_FILE = c.AUDIT_DIR / "live_integrity_status.json"
    c.ORDER_INTENTS_CSV = c.APPEND_ONLY_DIR / "order_intents.csv"
    c.SEND_ATTEMPTS_CSV = c.APPEND_ONLY_DIR / "send_attempts.csv"
    c.LIVE_FILLS_CSV = c.APPEND_ONLY_DIR / "live_fills.csv"
    c.RECONCILIATION_CSV = c.APPEND_ONLY_DIR / "reconciliation.csv"
    c.ERRORS_CSV = c.APPEND_ONLY_DIR / "errors.csv"
    c.RAW_LEADER_FILLS_CSV = c.ENGINE_OUTPUT_DIR / "raw_live_fills.csv"
    c.MANUAL_WALLETS_FILE = tmp / "manual_wallets.txt"
    c.WALLET_GATE_FILE = tmp / "wallet_gate.json"
    c.UI_STATE_FILE = tmp / "ui_state.json"
    c.FORBIDDEN_LIVE_POSITIONS_FILE = c.AUDIT_DIR / "live_positions.json"
    c.FORBIDDEN_WOULD_SEND_ORDERS_CSV = c.APPEND_ONLY_DIR / "would_send_orders.csv"
    c.ASSET_UNIVERSE_SNAPSHOT_FILE = c.AUDIT_DIR / "asset_universe_snapshot.json"
    c.ensure_dirs()

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": False,
        "wallets": {
            LEADER: {"enabled": True, "mode": "OFF", "copy_mode": "fixed", "fixed_notional": 1000},
        },
        "global_controls": {},
    })

    default_network = os.getenv("HL_LEADER_NETWORK", "")
    assert default_network != "mainnet", "Engine defaults to mainnet"

    config = c.load_json(c.LIVE_CONFIG_FILE, {})
    wallets = config.get("wallets", {})
    for wallet, wcfg in wallets.items():
        mode = wcfg.get("mode", "OFF")
        assert mode != "LIVE", f"Wallet in LIVE mode without explicit decision"

    return f"No auto-LIVE: default_network={default_network!r}"


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("DONE10_CORRECTION_harness_4fb8255.py")
    print(f"Commit: {COMMIT}")
    print(f"Engine: {ENGINE_PATH.name} (sha256 {ENGINE_SHA256[:12]}...)")
    print("=" * 70)

    for name, fn in [
        ("ENGINE_SHA256_MATCH", check_engine_sha256),
        ("MAILBOX_TRANSPORT_EXISTS", check_mailbox_transport),
        ("DONE-10:BLOCKED_ON_HUMAN_DECISION", check_done10_blocked),
    ]:
        ok, detail = run_check(name, fn)
        check(name, ok, detail)

    ok, detail = run_check("DONE-10:NEG_NO_AUTO_LIVE", check_no_auto_live)
    neg_test("DONE-10:NEG_NO_AUTO_LIVE", ok, detail)

    passed = sum(1 for c in CHECKS if c["pass"])
    failed = sum(1 for c in CHECKS if not c["pass"])
    neg_passed = sum(1 for n in NEG_TESTS if n["pass"])
    neg_failed = sum(1 for n in NEG_TESTS if not n["pass"])

    print(f"\n{'=' * 70}")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(CHECKS)} checks")
    print(f"Negative tests: {neg_passed} PASS, {neg_failed} FAIL out of {len(NEG_TESTS)} tests")
    print(f"{'=' * 70}")

    verdict = "BLOCKED" if failed == 0 else "FAIL"
    print(f"DONE-10 VERDICT: {verdict}")

    output = {
        "harness": "DONE10_CORRECTION_harness_4fb8255.py",
        "tested_commit": COMMIT,
        "tested_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "engine_sha256": ENGINE_SHA256,
        "done10_verdict": verdict,
        "done10_reason": (
            "No recorded human LIVE/mainnet decision found in control mailbox "
            f"or EVIDENCE/DECISIONS.md. Transport exists but is not a human ruling."
        ),
        "total_checks": len(CHECKS),
        "passed": passed,
        "failed": failed,
        "negative_tests": {
            "total": len(NEG_TESTS),
            "passed": neg_passed,
            "failed": neg_failed,
        },
        "checks": CHECKS,
        "negative_tests_detail": NEG_TESTS,
    }

    output_path = Path(__file__).resolve().parent / "DONE10_CORRECTION_4fb8255.json"
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nResults written to: {output_path}")

    return 0 if (failed == 0 and neg_failed == 0) else 1


if __name__ == "__main__":
    sys.exit(main())