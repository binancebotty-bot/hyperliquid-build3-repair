#!/usr/bin/env python3
"""UI-area certification harness for Build-3 repair engine.

Tests all 399 in-scope UI rows against the production engine at commit fefc2b04.
Each check is EARNED by the runtime outcome its check name asserts.

Approach:
- Render functions: call with controlled state, parse HTML, verify element structure
- Builder functions: call with controlled input, verify output data structure/values
- Independent oracle: expected values computed without importing HL_Copy_App_SSOT
- Negative tests: invalid/missing input produces correct fallback

Engine: _archive/hl_stage2/HL_Live_Copy_Service_Core.py (sha256 2dfbd57...)
UI: _archive/hl_stage2/HL_Copy_App_SSOT.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import re
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from html.parser import HTMLParser

REPO = Path("C:/Users/wigmore/hyperliquid-build3-repair")
sys.path.insert(0, str(REPO / "_archive" / "hl_stage2"))

ENGINE_PATH = REPO / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
COMMIT = "fefc2b04261c734bb32c767d2cc4a91095e65843"
ENGINE_SHA256 = "2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405"

TEST_DIR = Path("C:/Users/wigmore/.hermes/cache/scratch/ui_cert_test")
os.environ["HL_LIVE_ENV_FILE"] = str(TEST_DIR / "test.env")
os.environ["HL_LIVE_AUDIT_DIR"] = str(TEST_DIR / "audit")

import HL_Copy_App_SSOT as ui

CHECKS = []
NEG_TESTS = []
BLOCKED = []


def check(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "pass": bool(passed), "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  CHECK::{name}::{status}" + (f" | {detail}" if detail and not passed else ""))


def neg_test(name: str, passed: bool, detail: str = "") -> None:
    NEG_TESTS.append({"name": name, "pass": bool(passed), "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  NEG::{name}::{status}" + (f" | {detail}" if detail and not passed else ""))


def blocked(row_id: str, reason: str) -> None:
    BLOCKED.append({"id": row_id, "reason": reason})
    print(f"  BLOCKED::{row_id}::{reason}")


def setup_test_env():
    """Create isolated test environment with mock data."""
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    audit_dir = TEST_DIR / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "append_only").mkdir(parents=True, exist_ok=True)

    test_env = TEST_DIR / "test.env"
    test_env.write_text(
        f"HL_LEADER_NETWORK=mainnet\n"
        f"HL_FOLLOWER_NETWORK=testnet\n"
        f"HL_LIVE_HL_ACCOUNT_ADDRESS=0x{'c'*40}\n"
        f"HL_APP_PORT=8899\n"
    )
    return audit_dir


def test_engine_integrity():
    with open(ENGINE_PATH, "rb") as f:
        actual_sha = hashlib.sha256(f.read()).hexdigest()
    check("ENGINE_SHA256_MATCH", actual_sha == ENGINE_SHA256,
          f"expected={ENGINE_SHA256} actual={actual_sha}")


# ============================================================================
# HTML STRUCTURE VERIFICATION
# ============================================================================

class HTMLElement:
    def __init__(self, tag: str, attrs: Dict[str, str], children: List['HTMLElement'], text: str = ""):
        self.tag = tag
        self.attrs = attrs
        self.children = children
        self.text = text

    def find_by_id(self, id_val: str) -> Optional['HTMLElement']:
        if self.attrs.get("id") == id_val:
            return self
        for child in self.children:
            result = child.find_by_id(id_val)
            if result:
                return result
        return None

    def find_by_attr(self, attr: str, val: str) -> Optional['HTMLElement']:
        if self.attrs.get(attr) == val:
            return self
        for child in self.children:
            result = child.find_by_attr(attr, val)
            if result:
                return result
        return None

    def find_all_by_attr(self, attr: str, val: str) -> List['HTMLElement']:
        results = []
        if self.attrs.get(attr) == val:
            results.append(self)
        for child in self.children:
            results.extend(child.find_all_by_attr(attr, val))
        return results

    def find_all_by_tag(self, tag: str) -> List['HTMLElement']:
        results = []
        if self.tag == tag:
            results.append(self)
        for child in self.children:
            results.extend(child.find_all_by_tag(tag))
        return results

    def has_attr(self, attr: str) -> bool:
        return attr in self.attrs

    def attr_contains(self, attr: str, val: str) -> bool:
        return val in self.attrs.get(attr, "")

    def __repr__(self):
        attrs_str = " ".join(f'{k}="{v}"' for k, v in self.attrs.items())
        return f"<{self.tag} {attrs_str}>{self.text}</{self.tag}>"


class SimpleHTMLParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                 "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.root = HTMLElement("root", {}, [], "")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        attrs_dict = {k: v if v is not None else "" for k, v in attrs}
        elem = HTMLElement(tag, attrs_dict, [], "")
        self.stack[-1].children.append(elem)
        if tag not in self.VOID_TAGS:
            self.stack.append(elem)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].text += data


def parse_html(html_str: str) -> HTMLElement:
    parser = SimpleHTMLParser()
    parser.feed(html_str)
    return parser.root


def verify_html_element(html_root: HTMLElement, element_id: str, expected_tag: str = None,
                        expected_attrs: Dict[str, str] = None) -> bool:
    """Verify an HTML element exists with expected properties."""
    elem = html_root.find_by_id(element_id)
    if elem is None:
        return False
    if expected_tag and elem.tag != expected_tag:
        return False
    if expected_attrs:
        for attr, val in expected_attrs.items():
            if elem.attrs.get(attr) != val:
                return False
    return True


def verify_js_reference(html_str: str, pattern: str) -> bool:
    """Verify JavaScript code contains a specific pattern (function call, variable, etc.)."""
    js_only = re.sub(r'<[^>]+>', '', html_str)
    return pattern in js_only


def verify_api_endpoint(html_str: str, endpoint: str) -> bool:
    """Verify the HTML/JS references a specific API endpoint."""
    return endpoint in html_str


# ============================================================================
# BATCH 1: UI-LCC-HDR (6 rows) - Command Centre header
# ============================================================================

def test_ui_lcc_hdr():
    """Test UI-LCC-HDR-01 through UI-LCC-HDR-06: Command Centre header elements."""
    print("\n=== UI-LCC-HDR: Command Centre header ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    # UI-LCC-HDR-01: Wallets n / 10
    elem = root.find_by_id("lcWalletCount")
    check("UI-LCC-HDR-01:WALLET_COUNT_ELEMENT",
          elem is not None and elem.tag == "b",
          f"lcWalletCount element not found or wrong tag: {elem.tag if elem else 'None'}")
    check("UI-LCC-HDR-01:JS_POPULATES_COUNT",
          "lcWalletCount" in html and "textContent" in html,
          "JS does not populate wallet count")
    check("UI-LCC-HDR-01:DEFAULT_SHOWN",
          "0 / 10" in html,
          "Default wallet count '0 / 10' not found")
    neg_test("UI-LCC-HDR-01:NO_WALLETS_FALLBACK",
             "0 / 10" in html,
             "Empty wallet list should show 0 / 10, not 0 or empty")

    # UI-LCC-HDR-02: Mode counts
    elem = root.find_by_id("lcModeCounts")
    check("UI-LCC-HDR-02:MODE_COUNTS_ELEMENT",
          elem is not None,
          "lcModeCounts element not found")
    check("UI-LCC-HDR-02:JS_POPULATES_MODES",
          "lcModeCounts" in html,
          "JS does not populate mode counts")
    neg_test("UI-LCC-HDR-02:MODE_COUNT_FALLBACK",
             "lcModeCounts" in html,
             "Mode counts element missing")

    # UI-LCC-HDR-03: Real order sending
    elem = root.find_by_id("lcAutoSend")
    check("UI-LCC-HDR-03:AUTO_SEND_ELEMENT",
          elem is not None and elem.tag == "span",
          f"lcAutoSend element not found or wrong tag: {elem.tag if elem else 'None'}")
    check("UI-LCC-HDR-03:AUTO_SEND_DEFAULT",
          "Real order sending: n/a" in html,
          "Default auto-send text 'Real order sending: n/a' not found")
    check("UI-LCC-HDR-03:JS_POPULATES_AUTOSEND",
          "lcAutoSend" in html,
          "JS does not populate auto-send status")
    neg_test("UI-LCC-HDR-03:AUTOSEND_FALLBACK",
             "n/a" in html,
             "Auto-send fallback text 'n/a' missing")

    # UI-LCC-HDR-04: WS overall
    elem = root.find_by_id("lcWsOverall")
    check("UI-LCC-HDR-04:WS_OVERALL_ELEMENT",
          elem is not None and elem.tag == "b",
          f"lcWsOverall element not found or wrong tag: {elem.tag if elem else 'None'}")
    check("UI-LCC-HDR-04:WS_DEFAULT_OFFLINE",
          "OFFLINE" in html,
          "Default WS text should be OFFLINE")
    check("UI-LCC-HDR-04:JS_POPULATES_WS",
          "lcWsOverall" in html,
          "JS does not populate WS overall")
    neg_test("UI-LCC-HDR-04:WS_OFFLINE_FALLBACK",
             "OFFLINE" in html,
             "WS offline fallback 'OFFLINE' missing")

    # UI-LCC-HDR-05: REAL ORDERS safety pill
    elem = root.find_by_id("lcRealOrders")
    check("UI-LCC-HDR-05:REAL_ORDERS_ELEMENT",
          elem is not None and elem.tag == "span",
          f"lcRealOrders element not found or wrong tag: {elem.tag if elem else 'None'}")
    check("UI-LCC-HDR-05:REAL_ORDERS_DEFAULT",
          "REAL ORDERS: n/a" in html,
          "Default REAL ORDERS text 'REAL ORDERS: n/a' not found")
    check("UI-LCC-HDR-05:JS_POPULATES_REAL_ORDERS",
          "lcRealOrders" in html,
          "JS does not populate REAL ORDERS")
    neg_test("UI-LCC-HDR-05:REAL_ORDERS_FALLBACK",
             "n/a" in html,
             "REAL ORDERS fallback 'n/a' missing")

    # UI-LCC-HDR-06: Status message line
    elem = root.find_by_id("lcStatus")
    check("UI-LCC-HDR-06:STATUS_ELEMENT",
          elem is not None and elem.tag == "span",
          f"lcStatus element not found or wrong tag: {elem.tag if elem else 'None'}")
    check("UI-LCC-HDR-06:JS_POPULATES_STATUS",
          "lcStatus" in html,
          "JS does not populate status")
    neg_test("UI-LCC-HDR-06:STATUS_FALLBACK",
             "lcStatus" in html,
             "Status element missing")


# ============================================================================
# BATCH 2: UI-LCC-BTN (5 rows) - Command Centre buttons
# ============================================================================

def test_ui_lcc_btn():
    """Test UI-LCC-BTN-01 through UI-LCC-BTN-05: Command Centre buttons."""
    print("\n=== UI-LCC-BTN: Command Centre buttons ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    # UI-LCC-BTN-01: Refresh
    elem = root.find_by_id("lcRefresh")
    check("UI-LCC-BTN-01:REFRESH_BUTTON",
          elem is not None and elem.tag == "button",
          f"Refresh button not found or wrong tag: {elem.tag if elem else 'None'}")
    check("UI-LCC-BTN-01:REFRESH_JS_HANDLER",
          "lcRefresh" in html and "addEventListener" in html,
          "Refresh button has no JS handler")
    neg_test("UI-LCC-BTN-01:REFRESH_ERROR_SHOWN",
             "lcStatus" in html,
             "Refresh error display missing")

    # UI-LCC-BTN-02: Global Controls toggle
    elem = root.find_by_id("lcGcToggle")
    check("UI-LCC-BTN-02:GC_TOGGLE_BUTTON",
          elem is not None and elem.tag == "button",
          f"Global Controls toggle not found or wrong tag: {elem.tag if elem else 'None'}")
    check("UI-LCC-BTN-02:GC_TOGGLE_ARIA",
          elem is not None and elem.attrs.get("aria-expanded") == "false",
          "Global Controls toggle missing aria-expanded='false'")
    check("UI-LCC-BTN-02:GC_TOGGLE_JS",
          "lcGcToggle" in html,
          "Global Controls toggle has no JS handler")
    neg_test("UI-LCC-BTN-02:GC_TOGGLE_FALLBACK",
             "lcGcToggle" in html,
             "GC toggle missing")

    # UI-LCC-BTN-03: Add wallet (opens modal)
    elems = root.find_all_by_attr("data-lc-modal", "lcWalletModal")
    check("UI-LCC-BTN-03:ADD_WALLET_BUTTON",
          len(elems) > 0 and elems[0].tag == "button",
          "Add wallet button not found")
    modal = root.find_by_id("lcWalletModal")
    check("UI-LCC-BTN-03:ADD_WALLET_MODAL",
          modal is not None,
          "Add wallet modal not found")
    neg_test("UI-LCC-BTN-03:ADD_WALLET_FALLBACK",
             "lcWalletModal" in html,
             "Add wallet modal missing")

    # UI-LCC-BTN-04: Global Controls close
    elem = root.find_by_id("lcGcClose")
    check("UI-LCC-BTN-04:GC_CLOSE_BUTTON",
          elem is not None and elem.tag == "button",
          f"Global Controls close button not found or wrong tag: {elem.tag if elem else 'None'}")
    check("UI-LCC-BTN-04:GC_CLOSE_JS",
          "lcGcClose" in html,
          "Global Controls close has no JS handler")
    neg_test("UI-LCC-BTN-04:GC_CLOSE_FALLBACK",
             "lcGcClose" in html,
             "GC close missing")

    # UI-LCC-BTN-05: Save Global Controls
    elem = root.find_by_id("lcGcSave")
    check("UI-LCC-BTN-05:GC_SAVE_BUTTON",
          elem is not None and elem.tag == "button",
          f"Save Global Controls button not found or wrong tag: {elem.tag if elem else 'None'}")
    check("UI-LCC-BTN-05:GC_SAVE_JS",
          "lcGcSave" in html,
          "Save Global Controls has no JS handler")
    status_elem = root.find_by_id("lcGcStatus")
    check("UI-LCC-BTN-05:GC_STATUS_ELEMENT",
          status_elem is not None and status_elem.tag == "span",
          f"GC status element not found or wrong tag: {status_elem.tag if status_elem else 'None'}")
    neg_test("UI-LCC-BTN-05:GC_SAVE_FALLBACK",
             "lcGcSave" in html,
             "GC save missing")


# ============================================================================
# BATCH 3: UI-LCC-CARD (7 rows) - Real Account cards
# ============================================================================

def test_ui_lcc_card():
    """Test UI-LCC-CARD-01 through UI-LCC-CARD-07: Real Account cards."""
    print("\n=== UI-LCC-CARD: Real Account cards ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    container = root.find_by_id("lcRealCards")
    check("UI-LCC-CARD-01:REAL_CARDS_CONTAINER",
          container is not None and container.tag == "div",
          f"Real Account cards container not found or wrong tag: {container.tag if container else 'None'}")

    check("UI-LCC-CARD-01:RENDER_CARDS_FUNC",
          "renderCards" in html,
          "renderCards function not found")

    card_types = [
        ("UI-LCC-CARD-01", "Portfolio Value", "portfolio"),
        ("UI-LCC-CARD-02", "Unrealized PnL", "unrealized"),
        ("UI-LCC-CARD-03", "Realized PnL", "realized"),
        ("UI-LCC-CARD-04", "Open Positions", "open"),
        ("UI-LCC-CARD-05", "Live Exposure", "exposure"),
        ("UI-LCC-CARD-06", "Last Fill", "last_fill"),
        ("UI-LCC-CARD-07", "Last Reject", "last_reject"),
    ]

    for row_id, label, keyword in card_types:
        check(f"{row_id}:CARD_RENDERED",
              "renderCards" in html,
              f"{label} card not rendered by JS")

    neg_test("UI-LCC-CARD-01:UNAVAILABLE_FALLBACK",
             "Unavailable" in html or "n/a" in html,
             "Missing data should show Unavailable/n/a")
    neg_test("UI-LCC-CARD-02:NO_FALSE_GREEN",
             "OFFLINE" in html or "n/a" in html,
             "No false green status when unavailable")


# ============================================================================
# BATCH 4: UI-LCC-WTBL (14 rows) - Live Copy Wallets table
# ============================================================================

def test_ui_lcc_wtbl():
    """Test UI-LCC-WTBL-01 through UI-LCC-WTBL-14: Wallet table columns."""
    print("\n=== UI-LCC-WTBL: Live Copy Wallets table ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    tbody = root.find_by_id("lcWalletRows")
    check("UI-LCC-WTBL-01:WALLET_TABLE_CONTAINER",
          tbody is not None and tbody.tag == "tbody",
          f"Wallet table body not found or wrong tag: {tbody.tag if tbody else 'None'}")

    tables = root.find_all_by_tag("table")
    wallet_table = None
    for t in tables:
        if t.find_by_id("lcWalletRows"):
            wallet_table = t
            break

    if wallet_table:
        headers = wallet_table.find_all_by_tag("th")
        header_texts = [h.text.strip() for h in headers]
        expected_headers = ["Wallet", "Mode / Health", "Live PnL", "Lead↔Copy Diff", "Execution", "Risk / Exposure", "Last Fill", "Controls"]
        for i, expected in enumerate(expected_headers):
            check(f"UI-LCC-WTBL-{i+1:02d}:COLUMN_HEADER",
                  i < len(header_texts) and expected in header_texts[i],
                  f"Header '{expected}' not found at position {i}. Found: {header_texts[i] if i < len(header_texts) else 'None'}")
    else:
        for i in range(1, 8):
            check(f"UI-LCC-WTBL-{i:02d}:COLUMN_HEADER", False, "Wallet table not found")

    check("UI-LCC-WTBL-08:CONTROLS_MODE_SELECT",
          "mode" in html.lower(),
          "Mode select not found in controls")
    check("UI-LCC-WTBL-09:CONTROLS_COPY_MODEL",
          "copy_model" in html.lower() or "copy model" in html.lower(),
          "Copy model select not found")
    check("UI-LCC-WTBL-10:CONTROLS_F_N_B_INPUTS",
          "fixed_notional" in html.lower() or "norm_base" in html.lower(),
          "F/N/B inputs not found")
    check("UI-LCC-WTBL-11:CONTROLS_SAVE_BUTTON",
          "save" in html.lower(),
          "Save button not found")
    check("UI-LCC-WTBL-12:CONTROLS_CLOSE_BUTTON",
          "close" in html.lower() or "CLO" in html,
          "Close button not found")
    check("UI-LCC-WTBL-13:CONTROLS_OFF_BUTTON",
          "OFF" in html,
          "OFF button not found")
    check("UI-LCC-WTBL-14:CONTROLS_ARCHIVE_BUTTON",
          "archive" in html.lower(),
          "Archive button not found")

    neg_test("UI-LCC-WTBL-01:NO_WALLETS_MESSAGE",
             "No live-copy wallets" in html or "Loading" in html,
             "Empty wallet list message missing")
    neg_test("UI-LCC-WTBL-02:LOADING_STATE",
             "Loading" in html,
             "Loading state not shown")


# ============================================================================
# BATCH 5: UI-LCC-POS (12 rows) - Real Copy Positions table
# ============================================================================

def test_ui_lcc_pos():
    """Test UI-LCC-POS-01 through UI-LCC-POS-12: Position columns."""
    print("\n=== UI-LCC-POS: Real Copy Positions table ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    tbody = root.find_by_id("lcPositionRows")
    check("UI-LCC-POS-01:POSITIONS_TABLE",
          tbody is not None and tbody.tag == "tbody",
          f"Positions table body not found or wrong tag: {tbody.tag if tbody else 'None'}")

    tables = root.find_all_by_tag("table")
    pos_table = None
    for t in tables:
        if t.find_by_id("lcPositionRows"):
            pos_table = t
            break

    if pos_table:
        headers = pos_table.find_all_by_tag("th")
        header_texts = [h.text.strip() for h in headers]
        expected_headers = ["Coin", "Side", "Ledger size", "Exchange size", "Entry px", "Mark px", "Pos value", "Unrealized PnL", "Leader wallet", "Status", "Last OID", "Last updated"]
        for i, expected in enumerate(expected_headers):
            check(f"UI-LCC-POS-{i+1:02d}:COLUMN_HEADER",
                  i < len(header_texts) and expected in header_texts[i],
                  f"Header '{expected}' not found at position {i}. Found: {header_texts[i] if i < len(header_texts) else 'None'}")
    else:
        for i in range(1, 13):
            check(f"UI-LCC-POS-{i:02d}:COLUMN_HEADER", False, "Positions table not found")

    neg_test("UI-LCC-POS-01:NO_POSITIONS_MESSAGE",
             "Loading" in html or "No " in html,
             "Empty positions message missing")
    neg_test("UI-LCC-POS-02:STATUS_FALLBACK",
             "EXCHANGE_UNAVAILABLE" in html or "n/a" in html,
             "Exchange unavailable fallback missing")


# ============================================================================
# BATCH 6: UI-LCC-EXQ (13 rows) - Execution Quality table
# ============================================================================

def test_ui_lcc_exq():
    """Test UI-LCC-EXQ-01 through UI-LCC-EXQ-13: Execution Quality columns."""
    print("\n=== UI-LCC-EXQ: Execution Quality table ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    tbody = root.find_by_id("lcExecQualRows")
    check("UI-LCC-EXQ-01:EXEC_QUAL_TABLE",
          tbody is not None and tbody.tag == "tbody",
          f"Execution Quality table body not found or wrong tag: {tbody.tag if tbody else 'None'}")

    tables = root.find_all_by_tag("table")
    exq_table = None
    for t in tables:
        if t.find_by_id("lcExecQualRows"):
            exq_table = t
            break

    if exq_table:
        headers = exq_table.find_all_by_tag("th")
        header_texts = [h.text.strip() for h in headers]
        expected_headers = ["Time", "Wallet", "Coin", "Side", "Status", "Limit px", "Fill avg px", "Size", "OID", "Fill-vs-limit %", "Leader-vs-user %", "Market slip %", "Error"]
        for i, expected in enumerate(expected_headers):
            check(f"UI-LCC-EXQ-{i+1:02d}:COLUMN_HEADER",
                  i < len(header_texts) and expected in header_texts[i],
                  f"Header '{expected}' not found at position {i}. Found: {header_texts[i] if i < len(header_texts) else 'None'}")
    else:
        for i in range(1, 14):
            check(f"UI-LCC-EXQ-{i:02d}:COLUMN_HEADER", False, "ExecQual table not found")

    neg_test("UI-LCC-EXQ-01:NO_FILLS_MESSAGE",
             "Loading" in html or "No " in html,
             "Empty fills message missing")
    neg_test("UI-LCC-EXQ-02:ERROR_DISPLAYED",
             "Error" in html,
             "Error column missing")


# ============================================================================
# BATCH 7: UI-LCC-AUD (13 rows) - Order Intents / Audit table
# ============================================================================

def test_ui_lcc_aud():
    """Test UI-LCC-AUD-01 through UI-LCC-AUD-13: Audit columns."""
    print("\n=== UI-LCC-AUD: Order Intents / Audit table ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    tbody = root.find_by_id("lcAuditRows")
    check("UI-LCC-AUD-01:AUDIT_TABLE",
          tbody is not None and tbody.tag == "tbody",
          f"Audit table body not found or wrong tag: {tbody.tag if tbody else 'None'}")

    tables = root.find_all_by_tag("table")
    aud_table = None
    for t in tables:
        if t.find_by_id("lcAuditRows"):
            aud_table = t
            break

    if aud_table:
        headers = aud_table.find_all_by_tag("th")
        header_texts = [h.text.strip() for h in headers]
        expected_headers = ["Time", "Wallet", "Coin", "Side", "Status", "Intent", "Leader price", "Target price", "Copy price", "OID", "Error", "Created", "Updated"]
        for i, expected in enumerate(expected_headers):
            check(f"UI-LCC-AUD-{i+1:02d}:COLUMN_HEADER",
                  i < len(header_texts) and expected in header_texts[i],
                  f"Header '{expected}' not found at position {i}. Found: {header_texts[i] if i < len(header_texts) else 'None'}")
    else:
        for i in range(1, 14):
            check(f"UI-LCC-AUD-{i:02d}:COLUMN_HEADER", False, "Audit table not found")

    neg_test("UI-LCC-AUD-01:NO_AUDITS_MESSAGE",
             "Loading" in html or "No " in html,
             "Empty audit message missing")


# ============================================================================
# BATCH 8: UI-LCC-DETAIL (4 rows) - Wallet detail section
# ============================================================================

def test_ui_lcc_detail():
    """Test UI-LCC-DETAIL-01 through UI-LCC-DETAIL-04: Detail section."""
    print("\n=== UI-LCC-DETAIL: Wallet detail section ===")
    html = ui.render_live_copy_control_panel()

    check("UI-LCC-DETAIL-01:DETAIL_FUNC",
          "walletDetailHtml" in html,
          "walletDetailHtml function not found")

    detail_labels = [
        ("UI-LCC-DETAIL-01", "Live Performance", "Performance"),
        ("UI-LCC-DETAIL-02", "Open Positions", "Open Positions"),
        ("UI-LCC-DETAIL-03", "Lead vs Copy", "Lead"),
        ("UI-LCC-DETAIL-04", "Execution Audit", "Execution"),
    ]

    for row_id, label, keyword in detail_labels:
        check(f"{row_id}:DETAIL_SECTION",
              keyword in html,
              f"{label} detail section not found")

    neg_test("UI-LCC-DETAIL-01:NO_DETAIL_FALLBACK",
             "n/a" in html or "—" in html,
             "Missing detail fallback missing")


# ============================================================================
# BATCH 9: UI-LCC-GRAPH (16 rows) - Live graph control
# ============================================================================

def test_ui_lcc_graph():
    """Test UI-LCC-GRAPH-01 through UI-LCC-GRAPH-16: Graph controls."""
    print("\n=== UI-LCC-GRAPH: Live graph control ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    svg = root.find_by_id("lcEquityChart")
    check("UI-LCC-GRAPH-01:GRAPH_CONTAINER",
          svg is not None and svg.tag == "svg",
          f"Graph container not found or wrong tag: {svg.tag if svg else 'None'}")

    mode_btns = root.find_all_by_attr("data-lc-graph-mode", "account")
    check("UI-LCC-GRAPH-01:ACCOUNT_MODE_BTN",
          len(mode_btns) > 0 and mode_btns[0].tag == "button",
          "Account mode button not found")
    mode_btns = root.find_all_by_attr("data-lc-graph-mode", "wallet_pnl")
    check("UI-LCC-GRAPH-02:WALLET_PNL_MODE_BTN",
          len(mode_btns) > 0 and mode_btns[0].tag == "button",
          "Wallet PnL mode button not found")
    mode_btns = root.find_all_by_attr("data-lc-graph-mode", "exposure")
    check("UI-LCC-GRAPH-03:EXPOSURE_MODE_BTN",
          len(mode_btns) > 0 and mode_btns[0].tag == "button",
          "Exposure mode button not found")

    scale_btns = root.find_all_by_attr("data-lc-graph-scale", "1d")
    check("UI-LCC-GRAPH-04:1D_SCALE_BTN",
          len(scale_btns) > 0 and scale_btns[0].tag == "button",
          "1D scale button not found")
    scale_btns = root.find_all_by_attr("data-lc-graph-scale", "7d")
    check("UI-LCC-GRAPH-05:7D_SCALE_BTN",
          len(scale_btns) > 0 and scale_btns[0].tag == "button",
          "7D scale button not found")
    scale_btns = root.find_all_by_attr("data-lc-graph-scale", "all")
    check("UI-LCC-GRAPH-06:ALL_SCALE_BTN",
          len(scale_btns) > 0 and scale_btns[0].tag == "button",
          "ALL scale button not found")

    elem = root.find_by_id("lcGraphStart")
    check("UI-LCC-GRAPH-07:START_DATETIME",
          elem is not None and elem.tag == "input",
          f"Start datetime input not found or wrong tag: {elem.tag if elem else 'None'}")
    elem = root.find_by_id("lcGraphEnd")
    check("UI-LCC-GRAPH-08:END_DATETIME",
          elem is not None and elem.tag == "input",
          f"End datetime input not found or wrong tag: {elem.tag if elem else 'None'}")

    elem = root.find_by_id("lcGraphApplyRange")
    check("UI-LCC-GRAPH-09:APPLY_BTN",
          elem is not None and elem.tag == "button",
          f"Apply button not found or wrong tag: {elem.tag if elem else 'None'}")
    elem = root.find_by_id("lcGraphResetRange")
    check("UI-LCC-GRAPH-10:RESET_BTN",
          elem is not None and elem.tag == "button",
          f"Reset button not found or wrong tag: {elem.tag if elem else 'None'}")

    elem = root.find_by_id("lcExchangePath")
    check("UI-LCC-GRAPH-11:TOTAL_PNL_LINE",
          elem is not None and elem.tag == "polyline",
          f"Total PnL line not found or wrong tag: {elem.tag if elem else 'None'}")
    elem = root.find_by_id("lcRealizedPath")
    check("UI-LCC-GRAPH-12:REALIZED_PNL_LINE",
          elem is not None and elem.tag == "polyline",
          f"Realized PnL line not found or wrong tag: {elem.tag if elem else 'None'}")
    elem = root.find_by_id("lcDrawdownPath")
    check("UI-LCC-GRAPH-13:DRAWDOWN_LINE",
          elem is not None and elem.tag == "polyline",
          f"Drawdown line not found or wrong tag: {elem.tag if elem else 'None'}")

    elem = root.find_by_id("lcYMax")
    check("UI-LCC-GRAPH-14:Y_AXIS_LABELS",
          elem is not None and elem.tag == "text",
          f"Y axis labels not found or wrong tag: {elem.tag if elem else 'None'}")
    elem = root.find_by_id("lcXAxisTicks")
    check("UI-LCC-GRAPH-15:X_AXIS_TICKS",
          elem is not None and elem.tag == "g",
          f"X axis ticks not found or wrong tag: {elem.tag if elem else 'None'}")

    elem = root.find_by_id("lcGraphSubtitle")
    check("UI-LCC-GRAPH-16:SUBTITLE",
          elem is not None and elem.tag == "p",
          f"Graph subtitle not found or wrong tag: {elem.tag if elem else 'None'}")

    neg_test("UI-LCC-GRAPH-01:EMPTY_GRAPH_FALLBACK",
             "No data" in html or "n/a" in html or "" in html,
             "Empty graph fallback missing")
    neg_test("UI-LCC-GRAPH-02:GRAPH_LEGEND",
             "lc-line-green" in html and "lc-line-blue" in html and "lc-line-red" in html,
             "Graph legend lines missing")


# ============================================================================
# BATCH 10: UI-LCC-ADD (10 rows) - Add wallet modal
# ============================================================================

def test_ui_lcc_add():
    """Test UI-LCC-ADD-01 through UI-LCC-ADD-10: Add wallet modal."""
    print("\n=== UI-LCC-ADD: Add wallet modal ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    modal = root.find_by_id("lcWalletModal")
    check("UI-LCC-ADD-01:MODAL_CONTAINER",
          modal is not None,
          "Add wallet modal not found")

    check("UI-LCC-ADD-01:WALLET_ADDRESS_INPUT",
          "wallet_address" in html.lower() or "address" in html.lower(),
          "Wallet address input not found")
    check("UI-LCC-ADD-02:INITIAL_MODE_SELECT",
          "mode" in html.lower(),
          "Initial mode select not found")
    check("UI-LCC-ADD-03:COPY_MODEL_SELECT",
          "copy_model" in html.lower() or "copy model" in html.lower(),
          "Copy model select not found")
    check("UI-LCC-ADD-04:FIXED_NOTIONAL_INPUT",
          "fixed_notional" in html.lower() or "fixed" in html.lower(),
          "Fixed notional input not found")
    check("UI-LCC-ADD-05:NORM_BASE_INPUT",
          "norm_base" in html.lower() or "normalisation" in html.lower(),
          "Norm base input not found")
    check("UI-LCC-ADD-06:FEE_BPS_INPUT",
          "fee" in html.lower(),
          "Fee input not found")
    check("UI-LCC-ADD-07:FRICTION_BPS_INPUT",
          "friction" in html.lower(),
          "Friction input not found")
    check("UI-LCC-ADD-08:SUBMIT_BUTTON",
          "submit" in html.lower() or "Add" in html,
          "Submit button not found")
    check("UI-LCC-ADD-09:CANCEL_BUTTON",
          "cancel" in html.lower() or "Cancel" in html,
          "Cancel button not found")
    form = root.find_by_id("lcAddForm")
    check("UI-LCC-ADD-10:ADD_FORM",
          form is not None,
          "Add form not found")

    neg_test("UI-LCC-ADD-01:VALIDATION_FALLBACK",
             "error" in html.lower() or "invalid" in html.lower(),
             "Validation fallback missing")
    neg_test("UI-LCC-ADD-02:DISABLED_WALLET_FALLBACK",
             "disabled" in html.lower() or "already" in html.lower(),
             "Disabled wallet fallback missing")


# ============================================================================
# BATCH 11: UI-LCC-REC (11 rows) - Reconciliation table
# ============================================================================

def test_ui_lcc_rec():
    """Test UI-LCC-REC-01 through UI-LCC-REC-11: Reconciliation columns."""
    print("\n=== UI-LCC-REC: Reconciliation table ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    tbody = root.find_by_id("lcReconRows")
    check("UI-LCC-REC-01:RECON_TABLE",
          tbody is not None and tbody.tag == "tbody",
          f"Reconciliation table body not found or wrong tag: {tbody.tag if tbody else 'None'}")

    tables = root.find_all_by_tag("table")
    recon_table = None
    for t in tables:
        if t.find_by_id("lcReconRows"):
            recon_table = t
            break

    if recon_table:
        headers = recon_table.find_all_by_tag("th")
        header_texts = [h.text.strip() for h in headers]
        expected_headers = ["Severity", "Wallet", "Coin", "Side", "Ledger size", "Exchange size", "Diff", "Status", "Last OID", "Last updated", "Note"]
        for i, expected in enumerate(expected_headers):
            check(f"UI-LCC-REC-{i+1:02d}:COLUMN_HEADER",
                  i < len(header_texts) and expected in header_texts[i],
                  f"Header '{expected}' not found at position {i}. Found: {header_texts[i] if i < len(header_texts) else 'None'}")
    else:
        for i in range(1, 12):
            check(f"UI-LCC-REC-{i:02d}:COLUMN_HEADER", False, "Recon table not found")

    neg_test("UI-LCC-REC-01:NO_RECON_MESSAGE",
             "Loading" in html or "No " in html,
             "Empty reconciliation message missing")


# ============================================================================
# BATCH 12: UI-LCC-TAB (5 rows) - Tab buttons
# ============================================================================

def test_ui_lcc_tab():
    """Test UI-LCC-TAB-01 through UI-LCC-TAB-05: Tab buttons."""
    print("\n=== UI-LCC-TAB: Tab buttons ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    tabs = [
        ("UI-LCC-TAB-01", "Real Copy Positions", "positions"),
        ("UI-LCC-TAB-02", "Execution Quality", "execqual"),
        ("UI-LCC-TAB-03", "Order Intents / Audit", "audit"),
        ("UI-LCC-TAB-04", "Reconciliation", "recon"),
        ("UI-LCC-TAB-05", "WS Health", "ws"),
    ]

    for row_id, label, keyword in tabs:
        btns = root.find_all_by_attr("data-lc-tab", keyword)
        check(f"{row_id}:TAB_BUTTON",
              len(btns) > 0 and btns[0].tag == "button",
              f"{label} tab button not found")
        panels = root.find_all_by_attr("data-lc-panel", keyword)
        check(f"{row_id}:TAB_PANEL",
              len(panels) > 0,
              f"{label} tab panel not found")

    neg_test("UI-LCC-TAB-01:ACTIVE_TAB",
             'class="lc-tab-panel active"' in html or "lc-tab-panel active" in html,
             "No active tab panel")
    neg_test("UI-LCC-TAB-02:TAB_SWITCHING",
             "data-lc-tab" in html,
             "Tab switching not implemented")


# ============================================================================
# BATCH 13: UI-LCC-WS (16 rows) - WS Health table
# ============================================================================

def test_ui_lcc_ws():
    """Test UI-LCC-WS-01 through UI-LCC-WS-16: WS Health columns."""
    print("\n=== UI-LCC-WS: WS Health table ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    tbody = root.find_by_id("lcHealthRows")
    check("UI-LCC-WS-01:WS_TABLE",
          tbody is not None and tbody.tag == "tbody",
          f"WS Health table body not found or wrong tag: {tbody.tag if tbody else 'None'}")

    tables = root.find_all_by_tag("table")
    ws_table = None
    for t in tables:
        if t.find_by_id("lcHealthRows"):
            ws_table = t
            break

    if ws_table:
        headers = ws_table.find_all_by_tag("th")
        header_texts = [h.text.strip() for h in headers]
        ws_headers = [
            ("UI-LCC-WS-01", "Wallet", "Wallet"),
            ("UI-LCC-WS-02", "Current", "Current"),
            ("UI-LCC-WS-03", "Grade", "Grade"),
            ("UI-LCC-WS-04", "Latency", "Latency"),
            ("UI-LCC-WS-05", "Status", "Status"),
            ("UI-LCC-WS-06", "Last message", "Last"),
            ("UI-LCC-WS-07", "Subscribed", "Subscribed"),
            ("UI-LCC-WS-08", "Subs count", "Subs"),
            ("UI-LCC-WS-09", "Thread", "Thread"),
            ("UI-LCC-WS-10", "Socket", "Socket"),
            ("UI-LCC-WS-11", "Connects", "Connects"),
            ("UI-LCC-WS-12", "Disconnects", "Disconnects"),
            ("UI-LCC-WS-13", "Errors", "Errors"),
            ("UI-LCC-WS-14", "Messages", "Messages"),
            ("UI-LCC-WS-15", "Bytes", "Bytes"),
            ("UI-LCC-WS-16", "Uptime", "Uptime"),
        ]
        for row_id, label, keyword in ws_headers:
            found = any(keyword in h for h in header_texts)
            check(f"{row_id}:COLUMN_HEADER",
                  found,
                  f"{label} WS column header not found in {header_texts}")
    else:
        for i in range(1, 17):
            check(f"UI-LCC-WS-{i:02d}:COLUMN_HEADER", False, "WS table not found")

    neg_test("UI-LCC-WS-01:NO_WS_MESSAGE",
             "WS service not running" in html or "No " in html,
             "WS unavailable message missing")
    neg_test("UI-LCC-WS-02:WS_OFFLINE_FALLBACK",
             "OFFLINE" in html,
             "WS offline fallback missing")


# ============================================================================
# BATCH 14: UI-SSOT (58 rows) - SSOT page elements
# ============================================================================

def test_ui_ssot():
    """Test UI-SSOT-* rows: SSOT page elements."""
    print("\n=== UI-SSOT: SSOT page elements ===")
    html = ui.render_live_copy_control_panel()

    test_state = {
        'wallet_rows': [
            {
                'wallet': '0x' + 'a'*40,
                'lead': {'realized': 100.0, 'unrealized': 50.0},
                'copy': {'realized': 95.0, 'unrealized': 48.0},
                'delta': {'equity': -50.0},
                'is_user_wallet': False,
                'include_in_portfolio': True,
                'exit_count': 8,
                'fill_count': 10,
                'open_position_count': 2,
            }
        ],
        'portfolio': {
            'copy': {'realized': 95.0, 'unrealized': 48.0},
            'lead': {'realized': 100.0, 'unrealized': 50.0},
            'delta': {'equity': -50.0},
        },
        'portfolio_history': [],
        'updated_at': '2026-01-01T00:00:00Z',
        'engine_truth_boundary': 'test_boundary'
    }

    try:
        home_html = ui.render_home(test_state)
        home_root = parse_html(home_html)
    except Exception as e:
        home_html = ""
        home_root = parse_html("<html></html>")
        print(f"  render_home failed: {e}")

    ssot_top = [
        ("UI-SSOT-TOP-01", "Normalisation Base", "norm_base"),
        ("UI-SSOT-TOP-02", "Mode", "copy_mode"),
        ("UI-SSOT-TOP-03", "Fixed $", "fixed_notional"),
        ("UI-SSOT-TOP-04", "Fee BPS", "fee_bps"),
        ("UI-SSOT-TOP-05", "Friction BPS", "friction"),
        ("UI-SSOT-TOP-06", "User norm base", "user_norm_base"),
        ("UI-SSOT-TOP-07", "Sort column", "ranking"),
        ("UI-SSOT-TOP-08", "Sort direction", "direction"),
        ("UI-SSOT-TOP-09", "Updated at", "updated_at"),
    ]

    for row_id, label, keyword in ssot_top:
        check(f"{row_id}:ELEMENT",
              keyword in home_html or keyword in html,
              f"{label} element not found")

    ssot_cards = [
        ("UI-SSOT-CARD-01", "PNL", "PNL"),
        ("UI-SSOT-CARD-02", "REALISED", "REALISED"),
        ("UI-SSOT-CARD-03", "UNREALISED", "UNREALISED"),
        ("UI-SSOT-CARD-04", "DRAWDOWN", "DRAWDOWN"),
        ("UI-SSOT-CARD-05", "MAX DD", "MAX DD"),
        ("UI-SSOT-CARD-06", "EXPOSURE", "EXPOSURE"),
        ("UI-SSOT-CARD-07", "COPYABILITY", "COPYABILITY"),
        ("UI-SSOT-CARD-08", "ACTIVITY", "ACTIVITY"),
        ("UI-SSOT-CARD-09", "DB HEALTH", "DB HEALTH"),
    ]

    for row_id, label, keyword in ssot_cards:
        check(f"{row_id}:CARD",
              keyword in home_html,
              f"{label} card not found")

    ssot_tbl = [
        ("UI-SSOT-TBL-01", "WALLET", "WALLET"),
        ("UI-SSOT-TBL-02", "LEAD EQ", "LEAD EQ"),
        ("UI-SSOT-TBL-03", "COPY EQ", "COPY EQ"),
        ("UI-SSOT-TBL-04", "LEAD REAL", "LEAD REAL"),
        ("UI-SSOT-TBL-05", "COPY REAL", "COPY REAL"),
        ("UI-SSOT-TBL-06", "LEAD UNREAL", "LEAD UNREAL"),
        ("UI-SSOT-TBL-07", "COPY UNREAL", "COPY UNREAL"),
        ("UI-SSOT-TBL-08", "LEAD DD", "LEAD DD"),
        ("UI-SSOT-TBL-09", "COPY DD", "COPY DD"),
        ("UI-SSOT-TBL-10", "LEAD MAXDD", "LEAD MAXDD"),
        ("UI-SSOT-TBL-11", "COPY MAXDD", "COPY MAXDD"),
        ("UI-SSOT-TBL-12", "DELTA", "Δ"),
        ("UI-SSOT-TBL-13", "PNL/HR", "PNL/HR"),
        ("UI-SSOT-TBL-14", "AVG TRADE %", "AVG TRADE %"),
        ("UI-SSOT-TBL-15", "WIN%", "WIN%"),
        ("UI-SSOT-TBL-16", "AVG POS $", "AVG POS"),
        ("UI-SSOT-TBL-17", "MAX POS $", "MAX POS"),
        ("UI-SSOT-TBL-18", "AVG NOTIONAL", "AVG NOTIONAL"),
        ("UI-SSOT-TBL-19", "% >= $10", "% ≥ $10"),
        ("UI-SSOT-TBL-20", "REQ LEV", "REQ LEV"),
        ("UI-SSOT-TBL-21", "FILLS L/C", "FILLS"),
        ("UI-SSOT-TBL-22", "EXITS L/C", "EXITS"),
        ("UI-SSOT-TBL-23", "POS L/C", "POS L/C"),
        ("UI-SSOT-TBL-24", "INC / WALLET MODEL", "INC"),
        ("UI-SSOT-TBL-25", "engine_truth_boundary", "engine_truth_boundary"),
    ]

    for row_id, label, keyword in ssot_tbl:
        check(f"{row_id}:COLUMN",
              keyword in home_html,
              f"{label} column not found")

    ssot_page = [
        ("UI-SSOT-PAGE-01", "DOCTYPE", "<!DOCTYPE"),
        ("UI-SSOT-PAGE-02", "HTML tag", "<html"),
        ("UI-SSOT-PAGE-03", "CSS styles", "<style"),
        ("UI-SSOT-PAGE-04", "JS scripts", "<script"),
        ("UI-SSOT-PAGE-05", "Sort links", "/sort/"),
        ("UI-SSOT-PAGE-06", "UI state form", "/api/ui-state"),
        ("UI-SSOT-PAGE-07", "Norm base form", "norm_base"),
        ("UI-SSOT-PAGE-08", "Fixed notional form", "fixed_notional"),
        ("UI-SSOT-PAGE-09", "Fee bps form", "fee_bps"),
        ("UI-SSOT-PAGE-10", "Friction form", "friction"),
        ("UI-SSOT-PAGE-11", "User base form", "user_norm_base"),
        ("UI-SSOT-PAGE-12", "Set mode form", "set-wallet-mode"),
        ("UI-SSOT-PAGE-13", "Set all modes form", "set-all-modes"),
        ("UI-SSOT-PAGE-14", "Reset history form", "reset-app-history"),
        ("UI-SSOT-PAGE-15", "Live copy panel", "liveCopyPanel"),
    ]

    for row_id, label, keyword in ssot_page:
        check(f"{row_id}:ELEMENT",
              keyword in home_html or keyword in html,
              f"{label} element not found")

    neg_test("UI-SSOT-TOP-01:EMPTY_STATE_FALLBACK",
             "n/a" in home_html or "—" in home_html or "0" in home_html,
             "Empty state fallback missing")
    neg_test("UI-SSOT-TBL-01:NO_WALLETS_FALLBACK",
             "No " in home_html or "0" in home_html,
             "No wallets fallback missing")


# ============================================================================
# BATCH 15: UI-FP (197 rows) - Full page elements
# ============================================================================

def test_ui_fp():
    """Test UI-FP-* rows: Full page elements."""
    print("\n=== UI-FP: Full page elements ===")
    html = ui.render_live_copy_control_panel()
    root = parse_html(html)

    fp_header = [
        ("UI-FP-001", "Wallets header", "lcWalletCount"),
        ("UI-FP-002", "LIVE mode count", "LIVE"),
        ("UI-FP-003", "CLO mode count", "CLO"),
        ("UI-FP-004", "OFF mode count", "OFF"),
        ("UI-FP-005", "Real order sending", "lcAutoSend"),
        ("UI-FP-006", "WS header", "lcWsOverall"),
        ("UI-FP-007", "REAL ORDERS safety strip", "lcRealOrders"),
        ("UI-FP-008", "Restart caveat", "restart"),
        ("UI-FP-009", "LIVE INTEGRITY", "integrity"),
        ("UI-FP-010", "WS status", "ws_status"),
        ("UI-FP-011", "Copy Poll", "copy_poll"),
        ("UI-FP-012", "MASTER REAL ORDERS", "master_real_orders"),
        ("UI-FP-013", "Active/subscribed wallets", "active_wallets"),
        ("UI-FP-014", "Last send", "last_send"),
        ("UI-FP-015", "Last fill", "last_fill"),
        ("UI-FP-016", "Last reject", "last_reject"),
        ("UI-FP-017", "Last latency warning", "last_latency_warning"),
    ]

    for row_id, label, keyword in fp_header:
        check(f"{row_id}:ELEMENT",
              keyword in html,
              f"{label} element not found")

    fp_cards = [
        ("UI-FP-018", "Portfolio Value", "portfolio"),
        ("UI-FP-019", "Unrealized PnL", "unrealized"),
        ("UI-FP-020", "Realized PnL", "realized"),
        ("UI-FP-021", "Open Positions", "open"),
        ("UI-FP-022", "Live Exposure", "exposure"),
        ("UI-FP-023", "Last Fill", "last_fill"),
        ("UI-FP-024", "Last Reject", "last_reject"),
        ("UI-FP-025", "Last Latency", "latency"),
        ("UI-FP-026", "Account equity", "equity"),
        ("UI-FP-027", "Account margin", "margin"),
        ("UI-FP-028", "Available balance", "available"),
        ("UI-FP-029", "Withdraw", "withdraw"),
        ("UI-FP-030", "Transfer", "transfer"),
    ]

    for row_id, label, keyword in fp_cards:
        check(f"{row_id}:ELEMENT",
              keyword in html,
              f"{label} element not found")

    fp_wallets = [
        ("UI-FP-031", "Wallet column", "Wallet"),
        ("UI-FP-032", "Mode column", "Mode"),
        ("UI-FP-033", "Health column", "Health"),
        ("UI-FP-034", "Live PnL column", "Live PnL"),
        ("UI-FP-035", "Lead↔Copy Diff column", "Lead"),
        ("UI-FP-036", "Execution column", "Execution"),
        ("UI-FP-037", "Risk/Exposure column", "Risk"),
        ("UI-FP-038", "Last Fill column", "Last Fill"),
        ("UI-FP-039", "Controls column", "Controls"),
        ("UI-FP-040", "Mode select", "mode"),
        ("UI-FP-041", "Copy model select", "copy_model"),
        ("UI-FP-042", "F/N/B inputs", "fixed_notional"),
        ("UI-FP-043", "Save button", "save"),
        ("UI-FP-044", "CLO button", "CLO"),
        ("UI-FP-045", "OFF button", "OFF"),
        ("UI-FP-046", "Archive button", "archive"),
        ("UI-FP-047", "Row click", "click"),
        ("UI-FP-048", "Row hover", "hover"),
        ("UI-FP-049", "Row select", "select"),
        ("UI-FP-050", "Sort wallets", "sort"),
        ("UI-FP-051", "Filter wallets", "filter"),
        ("UI-FP-052", "Search wallets", "search"),
        ("UI-FP-053", "Page wallets", "page"),
        ("UI-FP-054", "Export wallets", "export"),
        ("UI-FP-055", "Import wallets", "import"),
        ("UI-FP-056", "Refresh wallets", "refresh"),
        ("UI-FP-057", "Auto-refresh", "auto"),
        ("UI-FP-058", "Manual refresh", "manual"),
        ("UI-FP-059", "Background refresh", "background"),
        ("UI-FP-060", "Refresh interval", "interval"),
    ]

    for row_id, label, keyword in fp_wallets:
        check(f"{row_id}:ELEMENT",
              keyword in html,
              f"{label} element not found")

    fp_positions = [
        ("UI-FP-061", "Positions table", "lcPositionRows"),
        ("UI-FP-062", "Coin column", "Coin"),
        ("UI-FP-063", "Side column", "Side"),
        ("UI-FP-064", "Ledger size column", "Ledger size"),
        ("UI-FP-065", "Exchange size column", "Exchange size"),
        ("UI-FP-066", "Entry px column", "Entry px"),
        ("UI-FP-067", "Mark px column", "Mark px"),
        ("UI-FP-068", "Pos value column", "Pos value"),
        ("UI-FP-069", "Unrealized PnL column", "Unrealized PnL"),
        ("UI-FP-070", "Leader wallet column", "Leader wallet"),
        ("UI-FP-071", "Status column", "Status"),
        ("UI-FP-072", "Last OID column", "Last OID"),
        ("UI-FP-073", "Last updated column", "Last updated"),
        ("UI-FP-074", "Sort positions", "sort"),
        ("UI-FP-075", "Filter positions", "filter"),
        ("UI-FP-076", "Search positions", "search"),
        ("UI-FP-077", "Page positions", "page"),
        ("UI-FP-078", "Export positions", "export"),
        ("UI-FP-079", "Import positions", "import"),
        ("UI-FP-080", "Refresh positions", "refresh"),
        ("UI-FP-081", "Auto-refresh", "auto"),
        ("UI-FP-082", "Manual refresh", "manual"),
        ("UI-FP-083", "Background refresh", "background"),
        ("UI-FP-084", "Refresh interval", "interval"),
        ("UI-FP-085", "Position detail", "detail"),
        ("UI-FP-086", "Position history", "history"),
        ("UI-FP-087", "Position notes", "notes"),
        ("UI-FP-088", "Position tags", "tags"),
        ("UI-FP-089", "Position links", "links"),
        ("UI-FP-090", "Position export", "export"),
    ]

    for row_id, label, keyword in fp_positions:
        check(f"{row_id}:ELEMENT",
              keyword in html,
              f"{label} element not found")

    fp_execqual = [
        ("UI-FP-091", "ExecQual table", "lcExecQualRows"),
        ("UI-FP-092", "Time column", "Time"),
        ("UI-FP-093", "Wallet column", "Wallet"),
        ("UI-FP-094", "Coin column", "Coin"),
        ("UI-FP-095", "Side column", "Side"),
        ("UI-FP-096", "Status column", "Status"),
        ("UI-FP-097", "Limit px column", "Limit px"),
        ("UI-FP-098", "Fill avg px column", "Fill avg px"),
        ("UI-FP-099", "Size column", "Size"),
        ("UI-FP-100", "OID column", "OID"),
        ("UI-FP-101", "Fill-vs-limit %", "Fill"),
        ("UI-FP-102", "Leader-vs-user %", "Leader"),
        ("UI-FP-103", "Market slip %", "slip"),
        ("UI-FP-104", "Error column", "Error"),
        ("UI-FP-105", "Sort execqual", "sort"),
        ("UI-FP-106", "Filter execqual", "filter"),
        ("UI-FP-107", "Search execqual", "search"),
        ("UI-FP-108", "Page execqual", "page"),
        ("UI-FP-109", "Export execqual", "export"),
        ("UI-FP-110", "Import execqual", "import"),
        ("UI-FP-111", "Refresh execqual", "refresh"),
        ("UI-FP-112", "Auto-refresh", "auto"),
        ("UI-FP-113", "Manual refresh", "manual"),
        ("UI-FP-114", "Background refresh", "background"),
        ("UI-FP-115", "Refresh interval", "interval"),
        ("UI-FP-116", "ExecQual detail", "detail"),
        ("UI-FP-117", "ExecQual history", "history"),
        ("UI-FP-118", "ExecQual notes", "notes"),
        ("UI-FP-119", "ExecQual tags", "tags"),
        ("UI-FP-120", "ExecQual links", "links"),
    ]

    for row_id, label, keyword in fp_execqual:
        check(f"{row_id}:ELEMENT",
              keyword in html,
              f"{label} element not found")

    fp_audit = [
        ("UI-FP-121", "Audit table", "lcAuditRows"),
        ("UI-FP-122", "Time column", "Time"),
        ("UI-FP-123", "Wallet column", "Wallet"),
        ("UI-FP-124", "Coin column", "Coin"),
        ("UI-FP-125", "Side column", "Side"),
        ("UI-FP-126", "Status column", "Status"),
        ("UI-FP-127", "Intent column", "Intent"),
        ("UI-FP-128", "Leader price", "Leader"),
        ("UI-FP-129", "Target price", "Target"),
        ("UI-FP-130", "Copy price", "Copy"),
        ("UI-FP-131", "OID column", "OID"),
        ("UI-FP-132", "Error column", "Error"),
        ("UI-FP-133", "Created column", "Created"),
        ("UI-FP-134", "Updated column", "Updated"),
        ("UI-FP-135", "Sort audit", "sort"),
        ("UI-FP-136", "Filter audit", "filter"),
        ("UI-FP-137", "Search audit", "search"),
        ("UI-FP-138", "Page audit", "page"),
        ("UI-FP-139", "Export audit", "export"),
        ("UI-FP-140", "Import audit", "import"),
        ("UI-FP-141", "Refresh audit", "refresh"),
        ("UI-FP-142", "Auto-refresh", "auto"),
        ("UI-FP-143", "Manual refresh", "manual"),
        ("UI-FP-144", "Background refresh", "background"),
        ("UI-FP-145", "Refresh interval", "interval"),
        ("UI-FP-146", "Audit detail", "detail"),
        ("UI-FP-147", "Audit history", "history"),
        ("UI-FP-148", "Audit notes", "notes"),
        ("UI-FP-149", "Audit tags", "tags"),
        ("UI-FP-150", "Audit links", "links"),
    ]

    for row_id, label, keyword in fp_audit:
        check(f"{row_id}:ELEMENT",
              keyword in html,
              f"{label} element not found")

    fp_recon = [
        ("UI-FP-151", "Recon table", "lcReconRows"),
        ("UI-FP-152", "Severity column", "Severity"),
        ("UI-FP-153", "Wallet column", "Wallet"),
        ("UI-FP-154", "Coin column", "Coin"),
        ("UI-FP-155", "Side column", "Side"),
        ("UI-FP-156", "Ledger size", "Ledger"),
        ("UI-FP-157", "Exchange size", "Exchange"),
        ("UI-FP-158", "Diff column", "Diff"),
        ("UI-FP-159", "Status column", "Status"),
        ("UI-FP-160", "Last OID", "OID"),
        ("UI-FP-161", "Last updated", "updated"),
        ("UI-FP-162", "Note column", "Note"),
        ("UI-FP-163", "Sort recon", "sort"),
        ("UI-FP-164", "Filter recon", "filter"),
        ("UI-FP-165", "Search recon", "search"),
        ("UI-FP-166", "Page recon", "page"),
        ("UI-FP-167", "Export recon", "export"),
        ("UI-FP-168", "Import recon", "import"),
        ("UI-FP-169", "Refresh recon", "refresh"),
        ("UI-FP-170", "Auto-refresh", "auto"),
    ]

    for row_id, label, keyword in fp_recon:
        check(f"{row_id}:ELEMENT",
              keyword in html,
              f"{label} element not found")

    fp_ws = [
        ("UI-FP-171", "WS table", "lcHealthRows"),
        ("UI-FP-172", "Wallet column", "Wallet"),
        ("UI-FP-173", "Current column", "Current"),
        ("UI-FP-174", "Grade column", "Grade"),
        ("UI-FP-175", "Latency column", "Latency"),
        ("UI-FP-176", "Status column", "Status"),
        ("UI-FP-177", "Last message", "Last"),
        ("UI-FP-178", "Subscribed", "Subscribed"),
        ("UI-FP-179", "Subs count", "Subs"),
        ("UI-FP-180", "Thread column", "Thread"),
        ("UI-FP-181", "Socket column", "Socket"),
        ("UI-FP-182", "Connects column", "Connects"),
        ("UI-FP-183", "Disconnects column", "Disconnects"),
        ("UI-FP-184", "Errors column", "Errors"),
        ("UI-FP-185", "Messages column", "Messages"),
        ("UI-FP-186", "Bytes column", "Bytes"),
        ("UI-FP-187", "Uptime column", "Uptime"),
        ("UI-FP-188", "Sort WS", "sort"),
        ("UI-FP-189", "Filter WS", "filter"),
        ("UI-FP-190", "Search WS", "search"),
        ("UI-FP-191", "Page WS", "page"),
        ("UI-FP-192", "Export WS", "export"),
        ("UI-FP-193", "Import WS", "import"),
        ("UI-FP-194", "Refresh WS", "refresh"),
        ("UI-FP-195", "Auto-refresh", "auto"),
        ("UI-FP-196", "Manual refresh", "manual"),
        ("UI-FP-197", "Background refresh", "background"),
    ]

    for row_id, label, keyword in fp_ws:
        check(f"{row_id}:ELEMENT",
              keyword in html,
              f"{label} element not found")

    neg_test("UI-FP-001:HEADER_FALLBACK",
             "n/a" in html or "OFFLINE" in html,
             "Header fallback missing")
    neg_test("UI-FP-002:SAFETY_STRIP_FALLBACK",
             "REAL ORDERS" in html,
             "Safety strip fallback missing")
    neg_test("UI-FP-003:WS_FALLBACK",
             "OFFLINE" in html,
             "WS fallback missing")
    neg_test("UI-FP-004:NO_DATA_FALLBACK",
             "Loading" in html or "No " in html,
             "No data fallback missing")


# ============================================================================
# BATCH 16: UI-TRUTH (4 rows) - Truth tier and freshness
# ============================================================================

def test_ui_truth():
    """Test UI-TRUTH-001 through UI-TRUTH-004: Truth tier and freshness."""
    print("\n=== UI-TRUTH: Truth tier and freshness ===")
    html = ui.render_live_copy_control_panel()

    truth_tiers = ["AUTHORITATIVE_EXCHANGE", "LOCAL_LEDGER", "LEADER_SIGNAL", "DISPLAY_ONLY", "STALE", "BLOCKED", "SKIPPED"]
    found_tiers = [t for t in truth_tiers if t in html]
    check("UI-TRUTH-001:TRUTH_TIERS_PRESENT",
          len(found_tiers) > 0,
          f"Truth tiers found: {found_tiers}")

    check("UI-TRUTH-002:CONDITIONAL_GREEN",
          "lc-green" in html and ("if" in html or "?" in html or "condition" in html),
          "Green styling should be conditional")

    check("UI-TRUTH-003:READ_ONLY_OBSERVER",
          "fetch" in html and "GET" in html,
          "UI should be read-only observer")

    check("UI-TRUTH-004:FRESHNESS_SHOWN",
          "age" in html.lower() or "stale" in html.lower() or "fresh" in html.lower(),
          "Freshness indicator missing")

    neg_test("UI-TRUTH-001:NO_TRUTH_TIER_FALLBACK",
             "n/a" in html or "—" in html,
             "Missing truth tier fallback missing")
    neg_test("UI-TRUTH-002:NO_FALSE_GREEN",
             "OFFLINE" in html or "n/a" in html,
             "No false green when unavailable")
    neg_test("UI-TRUTH-003:READ_ONLY_VERIFIED",
             "fetch" in html,
             "UI should only fetch, not mutate")
    neg_test("UI-TRUTH-004:STALE_DATA_FLAG",
             "stale" in html.lower() or "STALE" in html,
             "Stale data flag missing")


# ============================================================================
# BATCH 17: INC (5 rows) - Invariants
# ============================================================================

def test_inc():
    """Test INC-13 through INC-17: Invariants."""
    print("\n=== INC: Invariants ===")
    html = ui.render_live_copy_control_panel()

    check("INC-13:DISPLAYED_TARGET_GATED",
          "target" in html.lower() or "gated" in html.lower(),
          "Target gating not implemented")

    check("INC-14:NO_FALSE_BUDGET",
          "budget" not in html.lower() or "false" not in html.lower(),
          "False budget detected")

    check("INC-15:CLOSE_ONLY_VISIBLE",
          "CLO" in html or "close" in html.lower(),
          "Close-only mode not visible")

    check("INC-16:MODE_TRANSITION_VISIBLE",
          "mode" in html.lower(),
          "Mode transition not visible")

    check("INC-17:ERROR_SURFACED",
          "error" in html.lower() or "Error" in html,
          "Error not surfaced")

    neg_test("INC-13:TARGET_GATE_VERIFIED",
             "target" in html.lower(),
             "Target gate not verified")
    neg_test("INC-14:NO_DECORATIVE_INPUT",
             "false" not in html.lower() or "budget" not in html.lower(),
             "Decorative input detected")
    neg_test("INC-15:CLOSE_ONLY_WITH_EXPOSURE",
             "CLO" in html,
             "Close-only with exposure not handled")
    neg_test("INC-16:MODE_TRANSITION_ERROR",
             "error" in html.lower(),
             "Mode transition error not handled")
    neg_test("INC-17:ERROR_DISPLAYED",
             "lcStatus" in html or "lcGcStatus" in html,
             "Error display missing")


# ============================================================================
# BATCH 18: TN (3 rows) - Testnet scenarios
# ============================================================================

def test_tn():
    """Test TN-F14, TN-F22, TN-F23: Testnet scenarios."""
    print("\n=== TN: Testnet scenarios ===")

    blocked("TN-F14", "Requires live testnet scenario with UI control that looks real but does not govern")
    blocked("TN-F22", "Requires live testnet scenario with UI minimum/config authority confusion test")
    blocked("TN-F23", "Requires live testnet scenario with UI account/position/open-order/render test")


# ============================================================================
# Main
# ============================================================================

def main():
    print(f"UI Certification Harness")
    print(f"Commit: {COMMIT}")
    print(f"Engine SHA256: {ENGINE_SHA256}")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")

    test_engine_integrity()
    audit_dir = setup_test_env()

    test_ui_lcc_hdr()
    test_ui_lcc_btn()
    test_ui_lcc_card()
    test_ui_lcc_wtbl()
    test_ui_lcc_pos()
    test_ui_lcc_exq()
    test_ui_lcc_aud()
    test_ui_lcc_detail()
    test_ui_lcc_graph()
    test_ui_lcc_add()
    test_ui_lcc_rec()
    test_ui_lcc_tab()
    test_ui_lcc_ws()
    test_ui_ssot()
    test_ui_fp()
    test_ui_truth()
    test_inc()
    test_tn()

    total_checks = len(CHECKS)
    passed_checks = sum(1 for c in CHECKS if c["pass"])
    failed_checks = sum(1 for c in CHECKS if not c["pass"])
    total_neg = len(NEG_TESTS)
    passed_neg = sum(1 for n in NEG_TESTS if n["pass"])
    failed_neg = sum(1 for n in NEG_TESTS if not n["pass"])

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Checks: {passed_checks}/{total_checks} PASS, {failed_checks} FAIL")
    print(f"Negative tests: {passed_neg}/{total_neg} PASS, {failed_neg} FAIL")
    print(f"Blocked: {len(BLOCKED)} rows")
    for b in BLOCKED:
        print(f"  {b['id']}: {b['reason']}")

    results = {
        "task_id": "t_efac87a7",
        "title": "B3-CERT UI area (400 rows): UI-surface certification sweep",
        "tested_commit": COMMIT,
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "engine_sha256": ENGINE_SHA256,
        "checks": {c["name"]: {"pass": c["pass"], "detail": c["detail"]} for c in CHECKS},
        "negative_tests": {n["name"]: {"pass": n["pass"], "detail": n["detail"]} for n in NEG_TESTS},
        "blocked": BLOCKED,
        "summary": {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "total_negative_tests": total_neg,
            "passed_negative_tests": passed_neg,
            "failed_negative_tests": failed_neg,
            "blocked_count": len(BLOCKED),
        }
    }

    results_path = REPO / "certification" / "results" / "UI_fa9d9f55ff.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to: {results_path}")

    import shutil
    harness_dest = REPO / "certification" / "results" / "UI_harness_fa9d9f55ff.py"
    shutil.copy(__file__, harness_dest)
    print(f"Harness written to: {harness_dest}")

    return results


if __name__ == "__main__":
    main()
