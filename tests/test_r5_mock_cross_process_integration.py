"""R5 two independent OS processes exercise SQLite transactional reservation model, not SenderGateway."""
import multiprocessing as mp
import sqlite3

SCHEMA = "CREATE TABLE reservations (intent TEXT PRIMARY KEY, notional INTEGER NOT NULL, state TEXT NOT NULL)"

def reserve_worker(db, intent, gate, output):
    gate.wait()
    conn = sqlite3.connect(db, timeout=5, isolation_level=None)
    try:
        conn.execute('BEGIN IMMEDIATE')
        held = conn.execute("SELECT COALESCE(SUM(notional),0) FROM reservations WHERE state='UNKNOWN'").fetchone()[0]
        if held + 6 > 10:
            conn.rollback()
            output.put(('BLOCKED', intent))
            return
        conn.execute("INSERT INTO reservations VALUES (?,6,'UNKNOWN')", (intent,))
        conn.commit()
        output.put(('WIRE_ALLOWED', intent))
    finally:
        conn.close()

def test_competing_processes_and_restart_persistence(tmp_path):
    db = str(tmp_path/'reservations.sqlite')
    conn = sqlite3.connect(db)
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()
    context = mp.get_context('spawn')
    gate = context.Event()
    output = context.Queue()
    processes = [context.Process(target=reserve_worker, args=(db, f'intent-{i}', gate, output)) for i in range(2)]
    for process in processes: process.start()
    gate.set()
    for process in processes:
        process.join(10)
        assert process.exitcode == 0
    outcomes = sorted(output.get(timeout=2)[0] for _ in processes)
    assert outcomes == ['BLOCKED','WIRE_ALLOWED']
    restarted = sqlite3.connect(db)
    assert restarted.execute("SELECT SUM(notional) FROM reservations WHERE state='UNKNOWN'").fetchone()[0] == 6
    restarted.close()
