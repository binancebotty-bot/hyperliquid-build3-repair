"""R8 v2: actual state writer + UI server consumers, in isolated source-bound environment."""
import ast
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

ROOT = Path(__file__).parent
CORE = ROOT / "HL_Live_Copy_Service_Core.py"
UI = ROOT / "HL_Copy_App_SSOT.py"


def method(path, cls, name, env):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    owners = [x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == cls]
    assert len(owners) == 1
    selected = [x for x in owners[0].body
                if isinstance(x, ast.FunctionDef) and x.name == name]
    assert len(selected) == 1
    unit = ast.fix_missing_locations(ast.Module(body=[
        ast.ClassDef(name="Extracted", bases=[], keywords=[],
                     body=selected, decorator_list=[])], type_ignores=[]))
    exec(compile(unit, str(path), "exec"), env)
    return env["Extracted"]


def function(path, name, env):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    funcs = [x for x in tree.body
             if isinstance(x, ast.FunctionDef) and x.name == name]
    assert len(funcs) == 1
    unit = ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[]))
    exec(compile(unit, str(path), "exec"), env)
    return env[name]


def test_engine_writer_to_ui_forced_states(tmp_path):
    """No mocked status implementation: execute production writer method."""
    now = int(time.time() * 1000)
    storage = {}
    def write(path, value):
        storage[str(path)] = json.loads(json.dumps(value))
    def read(path, default=None):
        return storage.get(str(path), default)
    common = dict(__builtins__=__builtins__, Any=Any, Dict=Dict,
                  Optional=Optional, os=__import__("os"), time=time,
                  utc_now_ms=lambda: now, utc_now_iso=lambda: "now",
                  fnum=lambda x, default=0: float(x if x is not None else default))
    c = dict(common, LIVE_WS_HEALTH_FILE="raw", PROCESS_STARTED_AT_MS=now-1000,
             load_json=read)
    Writer = method(CORE, "ServiceStateWriter", "ws_summary_from_file", c)
    writer = Writer()
    u = dict(common, load_json=read, LIVE_COPY_WS_HEALTH_FILE="raw",
             LIVE_COPY_SERVICE_STATE_FILE="service")
    load_ui = function(UI, "_load_live_ws_health", u)
    enabled_ui = function(UI, "_engine_ws_enabled", u)
    for status, expected, enabled in [
        ("WS_OK", "WS_OK", True),
        ("WS_DEGRADED", "WS_DEGRADED", True),
        ("WS_DISCONNECTED", "WS_DISCONNECTED", True),
        ("WS_DISABLED", "WS_DISABLED", False),
    ]:
        storage["raw"] = {"created_at_ms": now,
            "ws_summary": {"ws_status": status, "socket_open": True}}
        emitted = writer.ws_summary_from_file()
        storage["service"] = {
            "ws_status": emitted["ws_status"],
            "ws_feature_enabled": enabled,
            "last_state_write_ms": now, "started_at_ms": now-1000}
        ui = load_ui()
        assert ui["overall"] == emitted["ws_status"] == expected
        assert ui["ws_summary"]["ws_status"] == expected
        assert enabled_ui(ui, storage["service"]) is enabled
        assert ui["status_source"] == "live_service_state.json"


def test_old_ok_heartbeat_and_unknown_fail_closed():
    now = int(time.time() * 1000)
    storage = {
        "raw": {"ws_summary": {"ws_status": "WS_OK"}},
        "service": {"ws_status": "WS_OK", "ws_feature_enabled": True,
                    "last_state_write_ms": now-600000,
                    "started_at_ms": now-900000}}
    env = dict(__builtins__=__builtins__, Any=Any, Dict=Dict,
               time=time, os=__import__("os"),
               fnum=lambda v, default=0: float(v if v is not None else default),
               load_json=lambda p, default=None: storage.get(str(p), default),
               LIVE_COPY_WS_HEALTH_FILE="raw",
               LIVE_COPY_SERVICE_STATE_FILE="service")
    load_ui = function(UI, "_load_live_ws_health", env)
    enabled = function(UI, "_engine_ws_enabled", env)
    assert load_ui()["overall"] == "WS_STALE"
    storage["service"]["last_state_write_ms"] = now
    storage["service"]["ws_status"] = "SURPRISE_OK"
    assert load_ui()["overall"] == "WS_UNKNOWN"
    assert enabled(load_ui(), storage["service"]) is False


def test_ui_top_consumer_reads_canonical_field():
    tree = ast.parse(UI.read_text(encoding="utf-8-sig"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "_build_live_top_status")
    # The rendered top-status consumer takes canonical 'overall', not
    # uncontrolled per-wallet/raw ws_summary status.
    values = [v for n in ast.walk(fn) if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name) and t.id == "ws_status"
              for v in [n.value]]
    assert len(values) == 1
    assert "overall" in ast.unparse(values[0])
    assert "ws_summary.get" not in ast.unparse(values[0])
