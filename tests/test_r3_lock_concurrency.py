"""R3: process-level lease exclusion and atomic journal replacement regression."""
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import importlib.util
import pytest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/cert/replay_confirmed_attempts.py"
spec=importlib.util.spec_from_file_location("r3_locked", SCRIPT)
r3=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r3)
CLOID="0x"+"a"*32
FIELDS=["attempt_id","cloid","status","copy_size","leader_fill_id","exchange_order_id",
        "terminal_state","operator_action","notes"]
LEDGER=["exchange_order_id","leader_fill_id","copy_fill_id","fill_size"]

@pytest.fixture
def files(tmp_path,monkeypatch):
    lock=tmp_path/"engine-global.lock"
    monkeypatch.setenv("HL_LIVE_GLOBAL_LOCK_FILE",str(lock))
    monkeypatch.setenv("HL_LIVE_REPLAY_OFFLINE","1")
    monkeypatch.setenv("HL_LIVE_REPLAY_NETWORK","testnet")
    monkeypatch.setenv("HL_LIVE_REPLAY_ACCOUNT","acct-A")
    monkeypatch.setenv("HL_LIVE_REPLAY_DEX","dex-A")
    sends=tmp_path/"send_attempts.csv"
    with sends.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,lineterminator="\r\n")
        w.writeheader()
        w.writerow({"attempt_id":"a1","cloid":CLOID,"status":"pending_send",
                    "copy_size":"2","leader_fill_id":"L"})
    confirmation=tmp_path/"exchange.jsonl"
    confirmation.write_text(json.dumps({"cloid":CLOID,"oid":"123","status":"FILLED","filled_size":"2",
                                        "network":"testnet","account":"acct-A","dex":"dex-A"})+"\n")
    ledger=tmp_path/"live_fills.csv"
    with ledger.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=LEDGER)
        w.writeheader()
        w.writerow({"exchange_order_id":"123","leader_fill_id":"L","copy_fill_id":"copy1","fill_size":"2"})
    return sends,confirmation,ledger,lock

def command(files):
    s,c,l,_=files
    return ["--sends",str(s),"--confirmations",str(c),"--ledger",str(l),"--apply"]

def test_normal_atomic_commit_then_idempotent(files):
    s,c,l,_=files
    assert r3.apply_locked(s,c,l)==1
    assert r3.apply_locked(s,c,l)==0
    rows=r3.read_csv(s)
    assert rows[-1]["status"]=="ORDER_FILLED" and len(rows)==2
    assert b"\r\n" in s.read_bytes()

def test_non_strict_never_reads_or_writes(files):
    s,*_=files
    before=s.read_bytes()
    with pytest.raises(RuntimeError,match="R3_STRICT_REQUIRED"):
        r3.main(command(files)+["--non-strict"])
    assert s.read_bytes()==before

def test_other_process_engine_lease_blocks_replay(files):
    s,c,l,lock=files
    script=("import os,sys,time\n"
            "p=sys.argv[1];f=open(p,'a+b')\n"
            "if os.name=='nt':\n"
            " import msvcrt\n"
            " if not os.stat(p).st_size:f.write(b'0');f.flush()\n"
            " f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)\n"
            "else:\n"
            " import fcntl\n"
            " fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
            "print('LOCKED',flush=True);time.sleep(5)\n")
    p=subprocess.Popen([sys.executable,"-c",script,str(lock)],stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE,text=True)
    try:
        assert p.stdout.readline().strip()=="LOCKED"
        before=s.read_bytes()
        with pytest.raises(RuntimeError,match="R3_ENGINE_LEASE_HELD"):
            r3.apply_locked(s,c,l)
        assert s.read_bytes()==before
    finally:
        p.terminate()
        p.wait(timeout=5)

def test_concurrent_uncooperative_append_detected(files,monkeypatch):
    s,c,l,_=files
    orig=s.read_bytes()
    chmod=os.chmod
    def race(path,mode):
        with s.open("ab") as f:
            f.write(b"other,0x"+b"b"*32+b",pending_send,1,L,,,,\r\n")
            f.flush()
            os.fsync(f.fileno())
        return chmod(path,mode)
    monkeypatch.setattr(os,"chmod",race)
    with pytest.raises(RuntimeError,match="R3_JOURNAL_CHANGED_DURING_REPLAY"):
        r3.apply_locked(s,c,l)
    assert s.read_bytes().startswith(orig)
    assert len(r3.read_csv(s))==2
    assert not list(s.parent.glob(".r3-*.csv"))

def test_rename_failure_keeps_original(files,monkeypatch):
    s,c,l,_=files
    before=s.read_bytes()
    def fail(*a):raise OSError("injected rename failure")
    monkeypatch.setattr(os,"replace",fail)
    with pytest.raises(OSError,match="injected rename failure"):
        r3.apply_locked(s,c,l)
    assert s.read_bytes()==before
    assert not list(s.parent.glob(".r3-*.csv"))

def test_real_apply_locked_refuses_mainnet_before_file_reads(files,monkeypatch):
    sends, confirmation, ledger, _ = files
    before = sends.read_bytes()
    monkeypatch.setenv("HL_LIVE_REPLAY_NETWORK","mainnet")
    with pytest.raises(RuntimeError,match="R3_TESTNET_ONLY"):
        r3.apply_locked(sends,confirmation,ledger)
    assert sends.read_bytes() == before

def test_real_apply_locked_refuses_wrong_account_scope(files):
    sends, confirmation, ledger, _ = files
    before = sends.read_bytes()
    lines = [json.loads(x) for x in confirmation.read_text().splitlines()]
    lines[0]["account"] = "foreign"
    confirmation.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    with pytest.raises(RuntimeError,match="R3_CONFIRMATION_SCOPE_UNVERIFIED"):
        r3.apply_locked(sends,confirmation,ledger)
    assert sends.read_bytes() == before
