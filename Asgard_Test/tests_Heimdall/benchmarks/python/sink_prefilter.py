"""Benchmark fixture — python.injection-sink-candidate (not imported; scanned as text)."""
import os


def queries(cur, uid, name, base_cmd, flags):
    cur.execute("SELECT * FROM users WHERE id = " + uid)  # ruleid: python.injection-sink-candidate
    cur.execute(f"SELECT * FROM users WHERE name = {name}")  # ruleid: python.injection-sink-candidate
    os.system(base_cmd + flags)  # ruleid: python.injection-sink-candidate
    cur.execute("SELECT * FROM users WHERE id = %s", (uid,))  # ok: python.injection-sink-candidate
    cur.execute("DELETE FROM sessions")
    os.system("ls -la")
