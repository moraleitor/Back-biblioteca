"""Levanta todos los microservicios en local (cada uno en su propio proceso y puerto).

    python run_all.py          # gateway en http://127.0.0.1:8000
"""
import os
import signal
import subprocess
import sys
import time

SERVICES = {"auth": 8001, "library": 8002, "notes": 8003, "ocr": 8004, "ai": 8005, "backup": 8006, "gateway": int(os.environ.get("PORT", 8000))}


def main() -> None:
    procs = []
    env = {**os.environ, "PYTHONPATH": os.getcwd()}
    for name, port in SERVICES.items():
        cmd = [sys.executable, "-m", "uvicorn", f"services.{name}.main:app", "--host", "0.0.0.0", "--port", str(port)]
        procs.append(subprocess.Popen(cmd, env=env))
        print(f"→ {name:8s} http://127.0.0.1:{port}")

    def stop(*_):
        for p in procs:
            p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
