#!/usr/bin/env python3
"""Hidden, stdlib-only supervisor for trading_stack. Run with pythonw.exe.

This program never controls the copy engine or runner, edits live_config.json,
or sends orders.
"""
import csv
import datetime
import json
import logging
import logging.handlers
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(r"C:\Users\wigmore\trading_stack")
TOOLS = ROOT / "_tools"
CONFIG_PATH = TOOLS / "supervisor.json"
STOP_PATH = TOOLS / "supervisor_stop.txt"
STATE_PATH = TOOLS / "pump_state.json"
LOG_PATH = TOOLS / "supervisor.log"
QUEUE_PATH = TOOLS / "queue.jsonl"
BOARD = "hl-build3-fresh"
HERMES = Path(r"C:\Users\wigmore\.hermes\bin\hermes.exe")
AUDIT_DIR = ROOT / "hl-build3-testnet-cert" / "_archive" / "hl_stage2" / "hl_live_copy_audit_testnet"
SEND_ATTEMPTS = AUDIT_DIR / "append_only" / "send_attempts.csv"
LIVE_CONFIG = AUDIT_DIR / "live_config.json"
CLEAN_STATE = AUDIT_DIR / "clean_core_runtime_state.json"
DASHBOARD = ROOT / "_dashboard" / "dashboard.py"
ACK_ALL = ROOT / "_dashboard" / "ack_all.py"
ORDER_STATS = TOOLS / "order_stats.py"
BACKLOG_PLAIN = ROOT / "_oc_jobs" / "backlog_plain.py"
WALLET_RANK = ROOT / "_oc_jobs" / "wallet_rank.py"

CREATE_NO_WINDOW = 0x08000000
DEFAULT_CONFIG = {"pump_max": 12, "hours": 6}
POLL_SECONDS = 25
WATCHDOG_SECONDS = 60
DAILY_SECONDS = 30 * 60
LOGGER = logging.getLogger("trading_stack.supervisor")
STOP_EVENT = threading.Event()
PUMP_LOCK = threading.Lock()
DISPATCH_PROCESS = None
LAST_DISPATCH_AT = 0.0
LAST_DASHBOARD_RESTART = 0.0
TICK = 0


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_directories():
    TOOLS.mkdir(parents=True, exist_ok=True)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def configure_logging():
    ensure_directories()
    handler = logging.handlers.RotatingFileHandler(
        str(LOG_PATH), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s"))
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers[:] = [handler]
    LOGGER.propagate = False


def read_config():
    ensure_directories()
    if not CONFIG_PATH.exists():
        try:
            atomic_json(CONFIG_PATH, DEFAULT_CONFIG)
        except OSError:
            LOGGER.exception("Could not create default supervisor.json")
        return dict(DEFAULT_CONFIG)
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as stream:
            raw = json.load(stream)
        return {
            "pump_max": max(0, int(raw.get("pump_max", DEFAULT_CONFIG["pump_max"]))),
            "hours": max(0.0, float(raw.get("hours", DEFAULT_CONFIG["hours"]))),
        }
    except Exception:
        LOGGER.exception("Could not read supervisor.json; using defaults")
        return dict(DEFAULT_CONFIG)


def python_executable():
    current = Path(sys.executable)
    if current.name.lower() == "pythonw.exe":
        sibling = current.with_name("python.exe")
        if sibling.exists():
            return str(sibling)
    return str(current)


def pythonw_executable():
    current = Path(sys.executable)
    if current.name.lower() == "pythonw.exe":
        return str(current)
    if current.name.lower() == "python.exe":
        sibling = current.with_name("pythonw.exe")
        if sibling.exists():
            return str(sibling)
    return "pythonw.exe"


def command_log_path(label):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(label))[:100]
    return TOOLS / ("supervisor_" + safe + ".out")


def run_to_file(args, label, cwd=ROOT, timeout=180):
    """Run a hidden subprocess with both output streams redirected to a file."""
    path = command_log_path(label)
    try:
        with path.open("wb") as output:
            result = subprocess.run(
                [str(item) for item in args],
                cwd=str(cwd),
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
        return result.returncode, path
    except subprocess.TimeoutExpired:
        LOGGER.warning("Command timed out: %s", args[0] if args else "empty command")
        return 124, path
    except Exception:
        LOGGER.exception("Could not run command: %s", args[0] if args else "empty command")
        return 125, path


def run_capture(args, timeout=1800, cwd=ROOT):
    """Run a hidden report subprocess with captured output."""
    try:
        result = subprocess.run(
            [str(item) for item in args],
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
        return result.returncode, result.stdout or ""
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", "replace")
        return 124, output + "\n[supervisor: command timed out]\n"
    except Exception as exc:
        LOGGER.exception("Could not run report command: %s", args[0] if args else "empty command")
        return 125, "[supervisor: %s]\n" % exc


def read_text(path, limit=4 * 1024 * 1024):
    try:
        with Path(path).open("r", encoding="utf-8", errors="replace") as stream:
            return stream.read(limit)
    except OSError:
        return ""


def load_state():
    if not STATE_PATH.exists():
        return {"version": 1, "jobs": {}}
    try:
        with STATE_PATH.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
        if not isinstance(value, dict) or not isinstance(value.get("jobs"), dict):
            raise ValueError("invalid state shape")
        value.setdefault("version", 1)
        return value
    except Exception:
        LOGGER.exception("Could not read pump_state.json; starting fresh")
        return {"version": 1, "jobs": {}}


def save_state(state):
    try:
        atomic_json(STATE_PATH, state)
    except Exception:
        LOGGER.exception("Could not persist pump_state.json")


def load_queue():
    items = []
    try:
        with QUEUE_PATH.open("r", encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict) and item.get("id") is not None:
                        items.append(item)
                    else:
                        LOGGER.warning("Ignoring queue line %d without an id", line_no)
                except Exception:
                    LOGGER.exception("Ignoring invalid queue line %d", line_no)
    except FileNotFoundError:
        return items
    except OSError:
        LOGGER.exception("Could not read queue.jsonl")
    return items


def resolved_path(value):
    path = Path(str(value))
    return path if path.is_absolute() else ROOT / path


def normalized_models(raw):
    result = []
    if isinstance(raw, list):
        for pair in raw:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                provider, model = str(pair[0]).strip(), str(pair[1]).strip()
                if provider and model:
                    result.append({"provider": provider, "model": model})
    return result


def queue_spec(item):
    try:
        max_runtime = max(1, int(float(item.get("max_runtime", 1800))))
    except (TypeError, ValueError):
        max_runtime = 1800
    return {
        "id": str(item["id"]),
        "title": str(item.get("title", item["id"])),
        "prompt_file": str(resolved_path(item.get("prompt_file", ""))),
        "expect": str(resolved_path(item.get("expect", ""))),
        "max_runtime": max_runtime,
        "models": normalized_models(item.get("models")),
    }


def sync_queue(state, items):
    jobs = state.setdefault("jobs", {})
    for item in items:
        try:
            spec = queue_spec(item)
        except Exception:
            LOGGER.exception("Ignoring malformed queue item")
            continue
        job = jobs.setdefault(spec["id"], {
            "status": "pending", "attempts": [], "score_written": False, "ack_done": False
        })
        job["spec"] = spec
        job.setdefault("attempts", [])
        job.setdefault("status", "pending")
        job.setdefault("score_written", False)
        job.setdefault("ack_done", False)
    return jobs


def latest_attempt(job):
    attempts = job.get("attempts") or []
    return attempts[-1] if attempts else None


def active_attempts(jobs):
    active = []
    for job in jobs.values():
        attempt = latest_attempt(job)
        if attempt and attempt.get("status") in ("creating", "waiting", "archive_pending"):
            active.append((job, attempt))
    return active


def parse_kanban_list(text):
    clean = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text or "")
    cards = []
    for line in clean.splitlines():
        match = re.search(r"\b(t_[A-Za-z0-9_-]+)\s+([A-Za-z_-]+)\s+\S+\s+(.*)$", line.strip())
        if match:
            cards.append({
                "id": match.group(1),
                "status": match.group(2).lower().replace("-", "_"),
                "title": match.group(3).strip(),
            })
    return cards


def poll_board():
    rc, path = run_to_file(
        [HERMES, "kanban", "--board", BOARD, "list"], "kanban_list", timeout=90
    )
    if rc != 0:
        LOGGER.warning("Kanban list returned %s", rc)
        return None
    return parse_kanban_list(read_text(path))


def find_card(attempt, cards):
    card_id = attempt.get("card_id")
    if card_id:
        for card in cards:
            if card["id"] == card_id:
                return card
    target = attempt.get("title", "")
    for card in cards:
        if card["title"] == target or card["title"].startswith(target + " ") or (
            target and target.startswith(card["title"])
        ):
            return card
    return None


def run_archive(card_id):
    if not card_id:
        return False
    rc, _ = run_to_file(
        [HERMES, "kanban", "--board", BOARD, "archive", str(card_id)],
        "kanban_archive_" + str(card_id),
        timeout=120,
    )
    return rc == 0


def start_attempt(job, provider_model, state):
    spec = job["spec"]
    attempts = job.setdefault("attempts", [])
    attempt_no = len(attempts) + 1
    attempt = {
        "job_id": spec["id"],
        "attempt_no": attempt_no,
        "provider": provider_model["provider"],
        "model": provider_model["model"],
        "title": "PUMP-%s %s" % (spec["id"], spec["title"]),
        "card_id": None,
        "created_at": time.time(),
        "max_runtime": spec["max_runtime"],
        "expect": spec["expect"],
        "status": "creating",
        "create_tries": 0,
    }
    attempts.append(attempt)
    job["status"] = "active"
    save_state(state)
    return attempt


def create_attempt(job, attempt, state):
    spec = job["spec"]
    prompt = Path(spec["prompt_file"])
    if not prompt.is_file():
        LOGGER.warning("Prompt file is missing for queue id %s: %s", spec["id"], prompt)
        return False

    attempt["create_tries"] = int(attempt.get("create_tries", 0)) + 1
    save_state(state)
    key = "supervisor-%s-%s" % (spec["id"], attempt["attempt_no"])
    args = [
        HERMES, "kanban", "--board", BOARD, "create",
        attempt["title"],
        "--body-file", str(prompt),
        "--assignee", "default",
        "--provider", attempt["provider"],
        "--model", attempt["model"],
        "--workspace", "dir:" + str(ROOT),
        "--max-runtime", str(attempt["max_runtime"]),
        "--max-retries", "1",
        "--idempotency-key", key,
    ]
    rc, output_path = run_to_file(
        args, "kanban_create_%s_%s" % (spec["id"], attempt["attempt_no"]), timeout=180
    )
    output = read_text(output_path)
    id_match = re.search(r"\b(t_[A-Za-z0-9_-]+)\b", output)
    if id_match:
        attempt["card_id"] = id_match.group(1)
    if rc == 0:
        attempt["status"] = "waiting"
        attempt["create_error"] = None
        LOGGER.info(
            "Created card for %s on %s/%s (%s)",
            spec["id"], attempt["provider"], attempt["model"], attempt.get("card_id")
        )
        save_state(state)
        return True
    attempt["status"] = "creating"
    attempt["create_error"] = "exit %s" % rc
    LOGGER.warning("Card create failed for %s, try %d (rc=%s)", spec["id"], attempt["create_tries"], rc)
    save_state(state)
    return False


def append_score(job, attempt):
    score_path = TOOLS / "model_scores.csv"
    job_id = str(job["spec"]["id"])
    model_name = "%s/%s" % (attempt["provider"], attempt["model"])
    if score_path.exists():
        try:
            with score_path.open("r", newline="", encoding="utf-8", errors="replace") as stream:
                for row in csv.reader(stream):
                    if len(row) >= 3 and row[0] == job_id and row[1] == model_name and row[2] == "1":
                        return
        except OSError:
            LOGGER.exception("Could not inspect model_scores.csv")
    seconds = max(0, int(time.time() - float(attempt.get("created_at", time.time()))))
    try:
        with score_path.open("a", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerow([job_id, model_name, 1, seconds, ""])
        LOGGER.info("Recorded passing model score for %s", job_id)
    except OSError:
        LOGGER.exception("Could not append model score for %s", job_id)


def ack_card(job, attempt):
    if job.get("ack_done") or not attempt.get("card_id"):
        return
    rc, _ = run_to_file(
        [python_executable(), "-I", ROOT / "_dashboard" / "ack_all.py", str(attempt["card_id"])],
        "ack_all_" + str(attempt["card_id"]),
        timeout=300,
    )
    if rc == 0:
        job["ack_done"] = True
        LOGGER.info("Acknowledged card %s", attempt["card_id"])
    else:
        LOGGER.warning("ack_all.py returned %s for card %s", rc, attempt["card_id"])


def finalize_success(job, attempt):
    job["status"] = "done"
    attempt["status"] = "done"
    attempt["ended_at"] = time.time()
    append_score(job, attempt)
    job["score_written"] = True
    ack_card(job, attempt)


def complete_archive(job, attempt, reason):
    attempt["status"] = "archived"
    attempt["ended_at"] = time.time()
    attempt["failure_reason"] = reason
    if len(job.get("attempts") or []) < 2:
        job["status"] = "pending"
        LOGGER.warning("Retrying %s once after %s", job.get("spec", {}).get("id"), reason)
    else:
        job["status"] = "give_up"
        LOGGER.error("Giving up on %s after retry failure: %s", job.get("spec", {}).get("id"), reason)


def fail_attempt(job, attempt, reason):
    attempt["failure_reason"] = reason
    if not attempt.get("card_id"):
        LOGGER.warning("Cannot archive %s yet; card id is unknown", job.get("spec", {}).get("id"))
        return
    if run_archive(attempt["card_id"]):
        complete_archive(job, attempt, reason)
    else:
        attempt["status"] = "archive_pending"
        LOGGER.warning("Archive failed for card %s; will retry", attempt["card_id"])


def resolve_card_ids(jobs, cards):
    for job in jobs.values():
        attempt = latest_attempt(job)
        if not attempt or attempt.get("status") not in ("creating", "waiting", "archive_pending"):
            continue
        found = find_card(attempt, cards)
        if found:
            if not attempt.get("card_id"):
                attempt["card_id"] = found["id"]
            attempt["board_status"] = found["status"]
            if attempt.get("status") == "creating":
                attempt["status"] = "waiting"


def reconcile(jobs, cards):
    now = time.time()
    if cards is None:
        return
    resolve_card_ids(jobs, cards)
    for job in list(jobs.values()):
        attempt = latest_attempt(job)
        if not attempt:
            continue
        status = attempt.get("status")
        if status == "archive_pending":
            reason = attempt.get("failure_reason", "previous failure")
            if run_archive(attempt.get("card_id")):
                complete_archive(job, attempt, reason)
            continue
        if status != "waiting":
            continue
        found = find_card(attempt, cards)
        board_status = found["status"] if found else attempt.get("board_status", "")
        if found:
            attempt["board_status"] = board_status
        if board_status == "done":
            if Path(attempt.get("expect", "")).is_file():
                finalize_success(job, attempt)
            else:
                fail_attempt(job, attempt, "card done but expect file is missing")
            continue
        if board_status in ("blocked", "failed"):
            fail_attempt(job, attempt, "card status " + board_status)
            continue
        started = float(attempt.get("created_at", now))
        max_runtime = max(1, int(attempt.get("max_runtime", 1800)))
        if now - started > max_runtime + 600:
            fail_attempt(job, attempt, "card exceeded max_runtime + 600 seconds")


def model_key(provider, model):
    return (str(provider).strip().lower(), str(model).strip().lower())


def model_capacity(jobs):
    model_counts = {}
    provider_counts = {}
    for _job, attempt in active_attempts(jobs):
        key = model_key(attempt.get("provider", ""), attempt.get("model", ""))
        model_counts[key] = model_counts.get(key, 0) + 1
        provider_counts[key[0]] = provider_counts.get(key[0], 0) + 1
    return model_counts, provider_counts


def select_model(job, jobs):
    models = (job.get("spec") or {}).get("models", [])
    used = {model_key(a.get("provider", ""), a.get("model", "")) for a in (job.get("attempts") or [])}
    model_counts, provider_counts = model_capacity(jobs)
    has_unused = False
    for option in models:
        provider, model = option["provider"], option["model"]
        key = model_key(provider, model)
        if key in used:
            continue
        has_unused = True
        provider_limit = 4 if key[0] == "nous" else (10 if key[0] == "openrouter" else None)
        if model_counts.get(key, 0) >= 2:
            continue
        if provider_limit is not None and provider_counts.get(key[0], 0) >= provider_limit:
            continue
        return option, True
    return None, has_unused


def append_concurrency(inflight, total):
    global TICK
    TICK += 1
    try:
        with (TOOLS / "concurrency_log.csv").open("a", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerow([utc_now(), inflight, total, TICK, "pump_tick"])
    except OSError:
        LOGGER.exception("Could not append concurrency_log.csv")


def dispatch_if_ready(cards):
    global DISPATCH_PROCESS, LAST_DISPATCH_AT
    now = time.time()
    if DISPATCH_PROCESS is not None and DISPATCH_PROCESS.poll() is not None:
        DISPATCH_PROCESS = None
    if DISPATCH_PROCESS is not None or now - LAST_DISPATCH_AT < 45:
        return
    if not any(card["status"] in ("ready", "queued", "pending") for card in (cards or [])):
        return
    path = command_log_path("kanban_dispatch")
    output = None
    try:
        output = path.open("ab")
        DISPATCH_PROCESS = subprocess.Popen(
            [str(HERMES), "kanban", "--board", BOARD, "dispatch"],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
            close_fds=True,
        )
        output.close()
        LAST_DISPATCH_AT = now
        LOGGER.info("Started background kanban dispatch")
    except Exception:
        if output is not None:
            output.close()
        LOGGER.exception("Could not start kanban dispatch")


def pump_cycle(state):
    with PUMP_LOCK:
        queue = load_queue()
        jobs = sync_queue(state, queue)
        cards = poll_board()
        reconcile(jobs, cards)

        for job in jobs.values():
            if job.get("status") == "done" and not job.get("ack_done"):
                attempt = latest_attempt(job)
                if attempt:
                    ack_card(job, attempt)

        for job, attempt in list(active_attempts(jobs)):
            if attempt.get("status") == "creating":
                create_attempt(job, attempt, state)

        config = read_config()
        active = active_attempts(jobs)
        while len(active) < config["pump_max"]:
            candidate_job = None
            candidate_model = None
            for item in queue:
                job = jobs.get(str(item.get("id")))
                if not job or job.get("status") != "pending":
                    continue
                selected, has_unused = select_model(job, jobs)
                if selected:
                    candidate_job, candidate_model = job, selected
                    break
                if not has_unused:
                    job["status"] = "give_up"
                    LOGGER.error("No eligible model remains for %s; giving up", item.get("id"))
            if candidate_job is None:
                break
            attempt = start_attempt(candidate_job, candidate_model, state)
            active.append((candidate_job, attempt))
            create_attempt(candidate_job, attempt, state)

        append_concurrency(len(active_attempts(jobs)), len(queue))
        if cards is not None:
            dispatch_if_ready(cards)
        save_state(state)


def pump_thread():
    state = load_state()
    next_tick = time.monotonic()
    while not STOP_EVENT.is_set():
        try:
            pump_cycle(state)
        except Exception:
            LOGGER.exception("Job pump cycle failed")
        next_tick += POLL_SECONDS
        delay = max(0.0, next_tick - time.monotonic())
        if delay == 0:
            next_tick = time.monotonic() + POLL_SECONDS
        STOP_EVENT.wait(delay)


def port_is_up(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2.0):
            return True
    except OSError:
        return False


def restart_dashboard():
    path = command_log_path("dashboard")
    output = None
    try:
        output = path.open("ab")
        process = subprocess.Popen(
            [pythonw_executable(), str(DASHBOARD), "--serve"],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
            close_fds=True,
        )
        output.close()
        LOGGER.warning("Restarted dashboard process pid=%s", process.pid)
        return True
    except Exception:
        if output is not None:
            output.close()
        LOGGER.exception("Could not restart dashboard")
        return False


def watchdog_state():
    global LAST_DASHBOARD_RESTART
    alerts = []
    now = time.time()
    if not port_is_up(8040) and now - LAST_DASHBOARD_RESTART >= 300:
        if restart_dashboard():
            LAST_DASHBOARD_RESTART = now
    if not port_is_up(8031):
        alerts.append("127.0.0.1:8031 is down")

    try:
        if now - SEND_ATTEMPTS.stat().st_mtime >= 15 * 60:
            alerts.append("send_attempts.csv has not been modified for 15 minutes")
    except OSError:
        alerts.append("send_attempts.csv is missing or unavailable")

    try:
        with LIVE_CONFIG.open("r", encoding="utf-8") as stream:
            config = json.load(stream)
        if config.get("auto_send_enabled") is False:
            alerts.append("live_config.json auto_send_enabled is false")
    except Exception:
        alerts.append("live_config.json is missing or unreadable")

    try:
        if SEND_ATTEMPTS.stat().st_size > 400 * 1024 * 1024:
            alerts.append("send_attempts.csv is larger than 400 MB")
    except OSError:
        pass
    try:
        if CLEAN_STATE.stat().st_size > 60 * 1024 * 1024:
            alerts.append("clean_core_runtime_state.json is larger than 60 MB")
    except OSError:
        pass

    try:
        atomic_json(TOOLS / "alerts.json", {"ts": utc_now(), "alerts": alerts})
    except Exception:
        LOGGER.exception("Could not write alerts.json")
    if alerts:
        LOGGER.warning("Watchdog alerts: %s", "; ".join(alerts))


def watchdog_thread():
    next_tick = time.monotonic()
    while not STOP_EVENT.is_set():
        try:
            watchdog_state()
        except Exception:
            LOGGER.exception("Watchdog cycle failed")
        next_tick += WATCHDOG_SECONDS
        delay = max(0.0, next_tick - time.monotonic())
        if delay == 0:
            next_tick = time.monotonic() + WATCHDOG_SECONDS
        STOP_EVENT.wait(delay)


def run_report_command(args, timeout=1800):
    return run_capture([python_executable(), "-I"] + [str(item) for item in args], timeout=timeout)


def write_scoreboard():
    order_rc, order_output = run_report_command([ORDER_STATS], timeout=1800)
    backlog_rc, backlog_output = run_report_command([BACKLOG_PLAIN, "B", "C"], timeout=3600)
    report = [
        "# Trading stack scoreboard", "",
        "Generated: " + utc_now(), "",
        "## order_stats.py (exit %d)" % order_rc, "",
        order_output.rstrip(), "",
        "## backlog_plain.py B C (exit %d)" % backlog_rc, "",
        backlog_output.rstrip(), "",
    ]
    target = TOOLS / ("scoreboard_" + datetime.datetime.now().strftime("%Y%m%d") + ".md")
    temp = target.with_suffix(target.suffix + ".tmp")
    try:
        temp.write_text("\n".join(report), encoding="utf-8")
        os.replace(temp, target)
        LOGGER.info("Wrote %s (order rc=%s, backlog rc=%s)", target.name, order_rc, backlog_rc)
    except Exception:
        LOGGER.exception("Could not write scoreboard")
        try:
            temp.unlink()
        except OSError:
            pass


def refresh_weekly():
    rc, output = run_report_command([WALLET_RANK], timeout=7200)
    target = TOOLS / "rerank_week.txt"
    temp = target.with_suffix(".txt.tmp")
    if rc != 0:
        output += "\n[supervisor: wallet_rank.py exited %d]\n" % rc
    try:
        temp.write_text(output, encoding="utf-8")
        os.replace(temp, target)
        LOGGER.info("Refreshed rerank_week.txt (rc=%s)", rc)
    except Exception:
        LOGGER.exception("Could not write rerank_week.txt")
        try:
            temp.unlink()
        except OSError:
            pass


def daily_cycle():
    today = datetime.datetime.now().strftime("%Y%m%d")
    scoreboard = TOOLS / ("scoreboard_" + today + ".md")
    try:
        refresh_scoreboard = time.time() - scoreboard.stat().st_mtime >= 6 * 60 * 60
    except OSError:
        refresh_scoreboard = True
    if refresh_scoreboard:
        write_scoreboard()

    weekly = TOOLS / "rerank_week.txt"
    try:
        refresh_rank = time.time() - weekly.stat().st_mtime >= 7 * 24 * 60 * 60
    except OSError:
        refresh_rank = True
    if refresh_rank:
        refresh_weekly()


def daily_thread():
    next_tick = time.monotonic()
    while not STOP_EVENT.is_set():
        try:
            daily_cycle()
        except Exception:
            LOGGER.exception("Daily report cycle failed")
        next_tick += DAILY_SECONDS
        delay = max(0.0, next_tick - time.monotonic())
        if delay == 0:
            next_tick = time.monotonic() + DAILY_SECONDS
        STOP_EVENT.wait(delay)


def main():
    configure_logging()
    config = read_config()
    started = time.time()
    LOGGER.info("Supervisor started; pump_max=%s hours=%s", config["pump_max"], config["hours"])
    workers = [
        threading.Thread(target=pump_thread, name="job-pump", daemon=True),
        threading.Thread(target=watchdog_thread, name="watchdog", daemon=True),
        threading.Thread(target=daily_thread, name="daily", daemon=True),
    ]
    for worker in workers:
        worker.start()

    last_config_check = 0.0
    hours = config["hours"]
    try:
        while not STOP_EVENT.is_set():
            if STOP_PATH.exists():
                LOGGER.info("Stop file found")
                break
            now = time.time()
            if now - last_config_check >= 5:
                config = read_config()
                hours = config["hours"]
                last_config_check = now
            if now - started >= hours * 60 * 60:
                LOGGER.info("Configured runtime elapsed")
                break
            STOP_EVENT.wait(1.0)
    except KeyboardInterrupt:
        LOGGER.info("Keyboard interrupt")
    finally:
        STOP_EVENT.set()
        LOGGER.info("Supervisor stopping")


if __name__ == "__main__":
    main()
