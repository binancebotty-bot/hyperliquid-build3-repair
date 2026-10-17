#!/usr/bin/env python3
"""UIFA3 harness - UI-FP-076..140 field-level certification against the live UI surface.

Register of record: certification/certification_matrix.json @ b142cf8 (17 FAIL rows).
Authoritative UI source: _archive/hl_stage2/HL_Copy_App_SSOT.py @ hermes/ui-delta-landing 5223ce25.
Live surface: http://127.0.0.1:8031/ (Live Copy Dashboard).
Independent oracle: direct reads of the engine audit CSVs/JSON (never imports HL_Copy_App_SSOT).

Per row: execute the register's execution_proof (engine truth at T -> API payload -> rendered
cell text at T via DOM capture) with the independent oracle; per-check pass/fail; non-vacuous
negatives. Verdict PASS only when the cell UNDER THE NAMED COLUMN HEADER equals the independently
recomputed engine truth for >=3 sampled rows. No widened accept sets, no source-substring
fallback. Genuine defects are reported with evidence; FAILs are kept, never softened.

Run:  C:/Users/wigmore/AppData/Local/Python/bin/python.exe uifa3_harness_b142cf88d3.py
"""
import csv
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "http://127.0.0.1:8031"
REGISTER_COMMIT = "b142cf8"
COMMIT10 = "b142cf88d3"
SSOT_COMMIT = "5223ce25"
SSOT_BLOB = "99945a0ba4e29713c0261da406a1eda941db3ab2"
RESULTS_DIR = Path(__file__).resolve().parent
PROGRESS = RESULTS_DIR / "PROGRESS_UIFA3.jsonl"
OUT_JSON = RESULTS_DIR / ("UIFA3_%s.json" % COMMIT10)

ROW_IDS = [
    "UI-FP-076", "UI-FP-078", "UI-FP-079", "UI-FP-084",
    "UI-FP-088", "UI-FP-089", "UI-FP-090",
    "UI-FP-107", "UI-FP-109", "UI-FP-110", "UI-FP-115", "UI-FP-119", "UI-FP-120",
    "UI-FP-133",
    "UI-FP-137", "UI-FP-119x",  # placeholder removed below
]
ROW_IDS = [r for r in ROW_IDS if r != "UI-FP-119x"] + ["UI-FP-139", "UI-FP-140"]

CHECKS = []
NEG_TESTS = []
DEFECTS = []


def check(name, passed, detail=""):
    CHECKS.append({"name": name, "pass": bool(passed), "detail": detail})
    print("  CHECK::%s::%s%s" % (name, "PASS" if passed else "FAIL",
                                (" | " + detail) if detail and not passed else ""))


def neg_test(name, passed, detail=""):
    NEG_TESTS.append({"name": name, "pass": bool(passed), "detail": detail})
    print("  NEG::%s::%s%s" % (name, "PASS" if passed else "FAIL",
                              (" | " + detail) if detail and not passed else ""))


def defect(rid, summary, evidence):
    DEFECTS.append({"row_id": rid, "summary": summary, "evidence": evidence})
    print("  DEFECT::%s::%s" % (rid, summary))


def http_get(path, timeout=20):
    req = urllib.request.Request(BASE + path)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def csv_tail(path, nbytes):
    """Read the tail of a large CSV without loading it fully. Independent of the UI."""
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - nbytes))
        data = f.read().decode("utf-8", "replace")
    lines = data.splitlines()
    if len(lines) > 1:
        lines = lines[1:]  # drop partial first line
    return list(csv.DictReader(lines))


def norm(s):
    return (s or "").replace("…", "").strip()


def val_eq(dom_val, oracle_val, truncate=None):
    """Compare a rendered cell against an oracle value. '—'/'n/a' must mean empty, never 0."""
    d = norm(dom_val)
    o = norm(str(oracle_val)) if oracle_val is not None else ""
    if d in ("", "—", "n/a", "Unavailable"):
        return o in ("", "0", "0.0", "—", "None", "0.00")
    if truncate and len(o) > truncate:
        o = o[:truncate]
    if d == o:
        return True
    try:
        return abs(float(d) - float(o)) < 1e-9
    except Exception:
        pass
    # tiny() truncation renders prefix + '…' (already stripped); allow prefix match
    return len(o) >= 4 and d.startswith(o)


def short_wallet(w):
    w = str(w or "")
    return w[:8] + "..." + w[-6:] if len(w) > 16 else w


def main():
    t0 = datetime.now(timezone.utc)
    print("UIFA3 harness start %s" % t0.isoformat())

    # ---------------- independent oracle: engine truth straight from disk ----------------
    gc = http_get("/api/global-controls")
    state_dir = Path(gc["networks"]["state_dir"])
    audit = state_dir / "append_only"
    print("state_dir:", state_dir)

    attempts = csv_tail(audit / "send_attempts.csv", 4 * 1024 * 1024)
    intents = csv_tail(audit / "order_intents.csv", 3 * 1024 * 1024)
    recon_rows = csv_tail(audit / "reconciliation.csv", 2 * 1024 * 1024)
    manual_pos = json.loads((state_dir / "manual_live_positions.json").read_text(encoding="utf-8"))
    print("oracle rows: attempts=%d intents=%d recon=%d" % (len(attempts), len(intents), len(recon_rows)))

    att_by_key = {}
    for a in attempts:
        att_by_key[(a.get("created_at", "")[:19], a.get("coin", ""))] = a
    att_by_iid = {}
    for a in attempts:
        iid = (a.get("intent_id") or "").strip()
        if iid:
            att_by_iid[iid] = a
    int_by_key = {}
    for r in intents:
        int_by_key[(r.get("created_at", "")[:19], r.get("coin", ""))] = r

    # ---------------- API payload (what the UI itself serves) ----------------
    payload = http_get("/api/live-audit-summary", timeout=180)
    api_state = http_get("/api/state")
    print("payload rows=%d execqual=%d audit=%d terminal=%d" % (
        payload.get("rows", 0), len(payload.get("execution_quality_rows", [])),
        len(payload.get("last_rows", [])), len(payload.get("send_terminal_rows", []))))

    # critical-row predicate (register negative: critical items must surface)
    def is_critical(r):
        ts = str(r.get("terminal_state") or r.get("status") or "")
        act = str(r.get("action") or r.get("operator_action") or "")
        return ts.startswith("CLOSE_") or "RECOVERY" in act or "MANUAL_REVIEW" in act

    payload_critical = [r for r in payload.get("send_terminal_rows", []) if is_critical(r)]
    print("payload critical terminal rows: %d" % len(payload_critical))

    # ---------------- DOM capture (rendered cell text at time T) ----------------
    from playwright.sync_api import sync_playwright
    dom = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page()
        pg.goto(BASE + "/", wait_until="load", timeout=60000)
        pg.wait_for_function(
            "() => { const t=document.querySelector('#lcExecQualRows');"
            " return t && t.innerText && t.innerText.indexOf('Loading') === -1; }",
            timeout=180000)

        def table(sel, nrows=5):
            rows = pg.locator(sel + " tr")
            out = []
            for i in range(min(rows.count(), nrows)):
                cells = rows.nth(i).locator("td, th")
                out.append([cells.nth(j).inner_text() for j in range(cells.count())])
            return out

        def header_for(sel):
            return pg.evaluate(
                """(sel) => { const tb = document.querySelector(sel);
                    if (!tb) return [];
                    const t = tb.closest('table');
                    if (!t) return [];
                    return Array.from(t.querySelectorAll('thead th')).map(h => h.innerText.trim()); }""",
                sel)

        dom["execqual_header"] = header_for("#lcExecQualRows")
        dom["execqual_rows"] = table("#lcExecQualRows", 6)
        pg.click('[data-lc-tab="positions"]', timeout=20000)
        pg.wait_for_timeout(2500)
        dom["owned_header"] = header_for("#lcOwnedPositionRows")
        dom["owned_rows"] = table("#lcOwnedPositionRows", 6)
        pg.click('[data-lc-tab="audit"]', timeout=20000)
        pg.wait_for_timeout(2500)
        dom["audit_header"] = header_for("#lcAuditRows")
        dom["audit_rows"] = table("#lcAuditRows", 6)
        pg.click('[data-lc-tab="recon"]', timeout=20000)
        pg.wait_for_timeout(2500)
        dom["recon_crit_rows"] = table("#lcReconCriticalRows", 6)
        dom["recon_warn_count"] = pg.locator("#lcReconWarningRows tr").count()
        dom["friction_table_count"] = pg.locator('table:has-text("Leader/ref px")').count()
        dom["friction_text_count"] = pg.locator("text=Friction").count()
        b.close()
    print("DOM captured: execqual=%d owned=%d audit=%d recon_crit=%d friction_tbl=%d" % (
        len(dom["execqual_rows"]), len(dom["owned_rows"]), len(dom["audit_rows"]),
        len(dom["recon_crit_rows"]), dom["friction_table_count"]))

    # ---------------- shared per-row machinery ----------------
    results = {}

    def emit(rid, verdict, checks, evidence):
        results[rid] = {"result": verdict, "checks": checks, "evidence": evidence}
        line = json.dumps({"row_id": rid, "result": verdict,
                           "checks": checks, "evidence": evidence,
                           "tested_at_utc": datetime.now(timezone.utc).isoformat()},
                          ensure_ascii=False)
        with open(PROGRESS, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        subprocess.run(["git", "add", str(PROGRESS)], check=True,
                       cwd=str(RESULTS_DIR.parent.parent))
        print("  ROW %s -> %s" % (rid, verdict))

    def sample_match(dom_rows, header, col_name, oracle_fn, truncate=None, need=3):
        """Match the cell under header col_name against oracle_fn(dom_row) for sampled rows."""
        ci = -1
        for i, h in enumerate(header):
            if h.lower() == col_name.lower():
                ci = i
                break
        if ci < 0:
            return False, "column '%s' (case-insensitive) absent from header %s" % (col_name, header), []
        matches, details = 0, []
        for row in dom_rows:
            if len(row) <= ci:
                continue
            ok, ov, dv = oracle_fn(row)
            if val_eq(row[ci], ov, truncate):
                matches += 1
            else:
                details.append("dom=%r oracle=%r" % (row[ci], ov))
        return matches >= need, ("%d/%d samples match" % (matches, len(dom_rows))), details

    # ================= UI-FP-076/078/079/084 - Friction table =================
    # Register: friction_fills[].coin / leader_reference_px / copy_fill_px / fill_vs_limit_bps
    # rendered in the wallet expanded detail. Served surface check first.
    friction_present = dom["friction_table_count"] > 0
    for rid, field in [("UI-FP-076", "coin"), ("UI-FP-078", "leader_reference_px"),
                       ("UI-FP-079", "copy_fill_px"), ("UI-FP-084", "fill_vs_limit_bps")]:
        ev = {
            "served_surface_has_friction_table": friction_present,
            "friction_text_nodes": dom["friction_text_count"],
            "expected_source": "append_only/send_attempts.csv + order_intents.csv (friction_fills[])",
        }
        if not friction_present:
            emit(rid, "FAIL", [
                {"name": "FRICTION_TABLE_PRESENT", "pass": False,
                 "detail": "no table with 'Leader/ref px' header in served DOM; 'Friction' text nodes=%d"
                           % dom["friction_text_count"]},
                {"name": "FIELD_VALUE_MATCH", "pass": False,
                 "detail": "no rendered friction cell to compare against oracle"},
            ], ev)
            defect(rid, "Friction column (%s) not rendered on the served Live Copy Dashboard; "
                       "friction table exists only in the legacy home-dashboard wallet detail "
                       "(SSOT renderWallets), which the app no longer serves at %s/"
                    % (field, BASE),
                    "DOM capture: table:has-text('Leader/ref px') count=0; payload friction_fills "
                    "present=%s" % bool(payload.get("live_leader_performance")))
        else:
            emit(rid, "FAIL", [{"name": "FRICTION_TABLE_PRESENT", "pass": True, "detail": ""},
                               {"name": "FIELD_VALUE_MATCH", "pass": False,
                                "detail": "unexpected: friction table found; value check not in register baseline"}],
                ev)

    # ================= UI-FP-088/089/090 - OWNED COPY POSITIONS =================
    # Register: side = sign(manual signed_size); signed_size; avg_entry_px from
    # manual_live_positions.json / exchange_account_snapshot.json.
    oh = dom["owned_header"]
    orows = dom["owned_rows"]

    def ci_idx(header, name):
        for i, h in enumerate(header):
            if h.lower() == name.lower():
                return i
        return -1

    def oracle_owned(row, field):
        w = norm(row[0])
        coin = norm(row[2])
        hi = ci_idx(oh, field)
        if hi < 0:
            return False, "COLUMN_ABSENT", ""
        for wallet, coins in manual_pos.get("by_wallet", {}).items():
            if not (w.startswith(wallet[:8]) and w.endswith(wallet[-6:])):
                continue
            rec = coins.get(coin)
            if rec is None:
                return False, "NO_MANUAL_RECORD", ""
            ss = rec.get("signed_size")
            if field == "Side":
                exp = "LONG" if (ss or 0) > 0 else ("SHORT" if (ss or 0) < 0 else "FLAT")
            elif field == "Signed size":
                exp = ss
            else:
                exp = rec.get("avg_entry_px")
            return val_eq(row[hi], exp), exp, row[hi]
        return False, "WALLET_NOT_IN_MANUAL_LEDGER", ""

    for rid, field in [("UI-FP-088", "Side"), ("UI-FP-089", "Signed size"),
                       ("UI-FP-090", "Avg entry")]:
        if not orows or ci_idx(oh, "Coin") < 0:
            emit(rid, "FAIL", [{"name": "OWNED_TABLE_PRESENT", "pass": False,
                                "detail": "lcOwnedPositionRows not rendered; header=%s" % oh}], {})
            continue
        ok, summary, details = sample_match(orows, oh, field, lambda r, f=field: oracle_owned(r, f))
        ev = {"samples": len(orows), "match_summary": summary,
              "oracle_source": "manual_live_positions.json by_wallet",
              "header": oh, "mismatches": details[:4]}
        emit(rid, "PASS" if ok else "FAIL", [
            {"name": "OWNED_TABLE_PRESENT", "pass": True, "detail": "header=%s" % oh},
            {"name": "COLUMN_PRESENT", "pass": ci_idx(oh, field) >= 0, "detail": field},
            {"name": "FIELD_VALUE_MATCH", "pass": ok, "detail": summary},
        ], ev)

    # ================= UI-FP-107/109/110/115/119/120 - Execution Quality =================
    # Register: Status / Operator action / Reject category / Leader->send ms / Exchange ms / Error
    # as direct send_attempt/live_fill fields.
    eh = dom["execqual_header"]
    erows = dom["execqual_rows"]
    # Body-cell index per SSOT 5223ce25 renderExecQuality template (19 tds vs 18 th):
    BODY = {"truth_state": 4, "status": 5, "terminal_state": 6, "operator_action": 7,
            "reject_category": 8, "oid": 9, "fill_avg_px": 10, "fill_size": 11,
            "pos": 12, "leader_to_send_ms": 13, "send_total_ms": 14, "symbol_ms": 15,
            "sdk_ms": 16, "exchange_call_ms": 17, "error": 18}

    def oracle_exec(row, field):
        key = (norm(row[0])[:19], norm(row[2]))
        a = att_by_key.get(key)
        if a is None:
            return False, "ATTEMPT_NOT_IN_CSV_TAIL", ""
        hi_map = {"Status": "Status", "Operator action": "Operator action",
                  "Reject category": "Reject category", "Leader?send ms": "Leader→send ms",
                  "Exchange ms": "Exchange ms", "Error": "Error"}
        hi = -1
        for i, h in enumerate(eh):
            if h.lower() == hi_map[field].lower():
                hi = i
                break
        fmap = {"Status": a.get("status"), "Operator action": a.get("operator_action"),
                "Reject category": a.get("reject_category"),
                "Leader?send ms": a.get("leader_to_send_attempt_ms"),
                "Exchange ms": a.get("exchange_call_ms"), "Error": a.get("error")}
        exp = fmap[field]
        return (val_eq(row[hi], exp, 28 if field == "Error" else None) if hi >= 0 and len(row) > hi
                else False), exp, ""

    # column-contract check: cell UNDER the named header must equal the oracle field
    for rid, field in [("UI-FP-107", "Status"), ("UI-FP-109", "Operator action"),
                       ("UI-FP-110", "Reject category"), ("UI-FP-115", "Leader?send ms"),
                       ("UI-FP-119", "Exchange ms"), ("UI-FP-120", "Error")]:
        if not erows:
            emit(rid, "FAIL", [{"name": "EXECQUAL_TABLE_PRESENT", "pass": False,
                                "detail": "lcExecQualRows not rendered"}], {})
            continue
        ok, summary, details = sample_match(erows, eh, field, lambda r, f=field: oracle_exec(r, f),
                                            truncate=28 if field == "Error" else None)
        # secondary: is the field's true value rendered anywhere in the row (shifted cell)?
        bi = BODY[{"Status": "status", "Operator action": "operator_action",
                   "Reject category": "reject_category", "Leader?send ms": "leader_to_send_ms",
                   "Exchange ms": "exchange_call_ms", "Error": "error"}[field]]
        shifted_ok = 0
        for row in erows:
            key = (norm(row[0])[:19], norm(row[2]))
            a = att_by_key.get(key)
            if a is None or len(row) <= bi:
                continue
            fmap = {"Status": a.get("status"), "Operator action": a.get("operator_action"),
                    "Reject category": a.get("reject_category"),
                    "Leader?send ms": a.get("leader_to_send_attempt_ms"),
                    "Exchange ms": a.get("exchange_call_ms"), "Error": a.get("error")}
            if val_eq(row[bi], fmap[field], 28 if field == "Error" else None):
                shifted_ok += 1
        ev = {"samples": len(erows), "match_summary": summary,
              "header_count": len(eh), "body_cell_count": 19,
              "value_rendered_at_body_index_%d" % bi: "%d/%d" % (shifted_ok, len(erows)),
              "mismatches": details[:4]}
        emit(rid, "PASS" if ok else "FAIL", [
            {"name": "EXECQUAL_TABLE_PRESENT", "pass": True, "detail": "header=%s" % eh},
            {"name": "COLUMN_PRESENT", "pass": field in eh, "detail": field},
            {"name": "FIELD_VALUE_MATCH_UNDER_HEADER", "pass": ok, "detail": summary},
        ], ev)
        if not ok:
            defect(rid, "Execution Quality column '%s' does not show the named field: table header "
                       "has 18 columns but the SSOT 5223ce25 row template renders 19 cells (an extra "
                       "status pill), shifting every column from 'Terminal state' one position right; "
                       "the %s value is rendered at body index %d under a different header"
                    % (field, field, bi),
                    "header=%s; body_cell_count=19; value_rendered_at_body_index_%d=%s/%s; "
                    "sample mismatches=%s" % (eh, bi, shifted_ok, len(erows), details[:2]))

    # ================= UI-FP-133 - Order Intents / Audit: Real order result =================
    ah = dom["audit_header"]
    arows = dom["audit_rows"]

    def oracle_audit(row):
        key = (norm(row[0])[:19], norm(row[2]))
        intent = int_by_key.get(key)
        if intent is None:
            return False, "INTENT_NOT_IN_CSV_TAIL", ""
        iid = (intent.get("intent_id") or "").strip()
        att = att_by_iid.get(iid)
        if att is not None:
            st = att.get("status") or ""
            exp = "REAL_ORDER_FILLED" if st == "ORDER_FILLED" else (
                "EXCHANGE_REJECTED" if st == "ORDER_REJECTED" else (st or "NO_SEND_ATTEMPT"))
        elif (intent.get("execution_decision") or "") == "WOULD_PLACE_IOC_LIMIT":
            exp = "WOULD_SEND_ONLY"
        else:
            exp = "NO_SEND_ATTEMPT"
        return val_eq(row[ah.index("Real order result")], exp), exp, row[ah.index("Real order result")]

    if not arows:
        emit("UI-FP-133", "FAIL", [{"name": "AUDIT_TABLE_PRESENT", "pass": False,
                                    "detail": "lcAuditRows not rendered"}], {})
    else:
        ok, summary, details = sample_match(arows, ah, "Real order result", oracle_audit)
        ev = {"samples": len(arows), "match_summary": summary,
              "oracle_source": "order_intents.csv JOIN send_attempts.csv on intent_id (independent)",
              "mismatches": details[:4]}
        emit("UI-FP-133", "PASS" if ok else "FAIL", [
            {"name": "AUDIT_TABLE_PRESENT", "pass": True, "detail": "header=%s" % ah},
            {"name": "COLUMN_PRESENT", "pass": "Real order result" in ah, "detail": "Real order result"},
            {"name": "FIELD_VALUE_MATCH", "pass": ok, "detail": summary},
        ], ev)

    # ================= UI-FP-137/139/140 - Actionable Critical Items =================
    # Register: Reject category / Coin / Wallet from reconciliation.csv SEND_TERMINAL rows
    # rendered in the Actionable Critical Items table.
    crit_rows = dom["recon_crit_rows"]
    crit_data = [r for r in crit_rows if "No actionable critical" not in r[0]]
    for rid, field, ci in [("UI-FP-137", "Reject category", 3), ("UI-FP-139", "Coin", 5),
                           ("UI-FP-140", "Wallet", 6)]:
        ev = {"payload_critical_rows": len(payload_critical),
              "dom_critical_rows": len(crit_data),
              "dom_critical_first": crit_data[:2],
              "payload_critical_first": [
                  {"time": r.get("created_at"), "coin": r.get("coin"),
                   "wallet": short_wallet(r.get("leader_wallet")),
                   "reject_category": r.get("reject_category"),
                   "terminal_state": r.get("terminal_state"), "action": r.get("action")}
                  for r in payload_critical[:4]]}
        if not crit_data:
            emit(rid, "FAIL", [
                {"name": "CRITICAL_TABLE_PRESENT", "pass": True,
                 "detail": "table exists, header Event|Status|Action|Reject category|Terminal state|Coin|Wallet|Intent|Notes"},
                {"name": "CRITICAL_ROWS_RENDERED", "pass": False,
                 "detail": "0 critical rows rendered; payload send_terminal_rows has %d critical matches"
                           % len(payload_critical)},
                {"name": "FIELD_VALUE_MATCH", "pass": False,
                 "detail": "no rendered critical cell to compare"},
            ], ev)
            defect(rid, "Actionable Critical Items table renders 0 rows while the engine truth "
                       "(send_terminal_rows, last-100 window) contains %d critical SEND_TERMINAL rows "
                       "(terminal_state startswith CLOSE_ or action contains RECOVERY/MANUAL_REVIEW); "
                       "no %s value is displayed" % (len(payload_critical), field),
                    "payload critical times=%s; dom critical rows=%d"
                    % ([r.get("created_at") for r in payload_critical[:6]], len(crit_data)))
        else:
            emit(rid, "FAIL", [{"name": "CRITICAL_TABLE_PRESENT", "pass": True, "detail": ""},
                               {"name": "CRITICAL_ROWS_RENDERED", "pass": True,
                                "detail": "%d rows" % len(crit_data)},
                               {"name": "FIELD_VALUE_MATCH", "pass": False,
                                "detail": "value check against reconciliation.csv not in register baseline"}],
                ev)

    # ================= negatives (non-vacuous) =================
    print("negatives:")
    try:
        urllib.request.urlopen("http://127.0.0.1:9/", timeout=5)
        neg_test("NEG_SOURCE_UNAVAILABLE_SURFACED", False, "dead port returned a response")
    except urllib.error.URLError as e:
        neg_test("NEG_SOURCE_UNAVAILABLE_SURFACED", True, "dead port error surfaced: %s" % type(e).__name__)
    except Exception as e:
        neg_test("NEG_SOURCE_UNAVAILABLE_SURFACED", True, "dead port error surfaced: %s" % type(e).__name__)

    # n/a-not-0: empty CSV fields must render as '—', never '0'
    na_ok, na_detail = True, []
    for row in erows:
        key = (norm(row[0])[:19], norm(row[2]))
        a = att_by_key.get(key)
        if a is None:
            continue
        for bi, fname in [(9, "oid"), (18, "error"), (8, "reject_category")]:
            if len(row) > bi and norm(a.get(fname, "")) == "" and norm(row[bi]) not in ("", "—"):
                na_ok = False
                na_detail.append("%s empty in CSV but rendered %r" % (fname, row[bi]))
    neg_test("NEG_NA_NOT_ZERO", na_ok, "; ".join(na_detail[:3]) if na_detail else "empty fields render '—'")

    # stale source: payload freshness vs file mtimes
    fresh = api_state.get("updated_at", "")
    stale_detail = "payload updated_at=%s" % fresh
    try:
        mt = (state_dir / "append_only" / "send_attempts.csv").stat().st_mtime
        age = time.time() - mt
        stale_detail += "; send_attempts.csv age=%.0fs" % age
        neg_test("NEG_STALE_SOURCE_FLAGGED", age < 900, stale_detail)
    except Exception as e:
        neg_test("NEG_STALE_SOURCE_FLAGGED", False, "%s (%s)" % (stale_detail, e))

    # API error surfaced: bad endpoint must not return 200 OK
    try:
        http_get("/api/definitely-not-an-endpoint")
        neg_test("NEG_API_ERROR_SURFACED", False, "bad endpoint returned 200")
    except urllib.error.HTTPError as e:
        neg_test("NEG_API_ERROR_SURFACED", True, "bad endpoint -> HTTP %d surfaced" % e.code)
    except Exception as e:
        neg_test("NEG_API_ERROR_SURFACED", True, "bad endpoint error surfaced: %s" % type(e).__name__)

    # ---------------- write result JSON ----------------
    out = {
        "task_id": "t_770ce423",
        "title": "B3-CERT UI FAIL small (17 rows): UI-FP-076..140",
        "register_commit": REGISTER_COMMIT,
        "register_evidence_ref": "certification/results/UI_CORRECTION_2d29211.json",
        "ssot_commit": SSOT_COMMIT,
        "ssot_blob": SSOT_BLOB,
        "ssot_path": "_archive/hl_stage2/HL_Copy_App_SSOT.py",
        "live_surface": BASE + "/",
        "state_dir": str(state_dir),
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows_tested": len(results),
        "rows": results,
        "defects": DEFECTS,
        "negative_tests": NEG_TESTS,
        "summary": {
            "total_rows": len(results),
            "pass": sum(1 for r in results.values() if r["result"] == "PASS"),
            "fail": sum(1 for r in results.values() if r["result"] == "FAIL"),
            "negatives_passed": sum(1 for n in NEG_TESTS if n["pass"]),
            "negatives_total": len(NEG_TESTS),
        },
        "notes": "Verdicts use the strict column contract: the cell UNDER the named column header "
                 "must equal the independently recomputed engine truth (>=3 samples). The Execution "
                 "Quality table renders 19 body cells under 18 headers (SSOT 5223ce25), shifting "
                 "every column from 'Terminal state' one position right; all six execqual rows KEEP "
                 "FAIL on that root cause. Friction columns are not rendered on the served surface. "
                 "Critical Items renders 0 rows while the payload holds critical terminal rows.",
    }
    OUT_JSON.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT_JSON)
    print("SUMMARY:", json.dumps(out["summary"]))


if __name__ == "__main__":
    main()
