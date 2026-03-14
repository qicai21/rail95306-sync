import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT_DIR / "runtime"
PID_FILE = RUNTIME_DIR / "95306_keepalive.pid"
STDOUT_LOG = RUNTIME_DIR / "95306_keepalive_runner.log"
HEARTBEAT_LOG = RUNTIME_DIR / "95306_keepalive.log"
RUNNER = ROOT_DIR / "tools" / "run_95306_keepalive.py"


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def ensure_runtime_dir() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR


def read_pid_record() -> dict[str, Any] | None:
    if not PID_FILE.exists():
        return None
    return json.loads(PID_FILE.read_text(encoding="utf-8"))


def write_pid_record(record: dict[str, Any]) -> None:
    ensure_runtime_dir()
    PID_FILE.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_pid_record() -> None:
    if PID_FILE.exists():
        PID_FILE.unlink()


def process_exists(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout.strip()
    return bool(output and "No tasks are running" not in output and str(pid) in output)


def last_heartbeat_event() -> dict[str, Any] | None:
    if not HEARTBEAT_LOG.exists():
        return None
    lines = [line.strip() for line in HEARTBEAT_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])


def start_process(headed: bool = False) -> int:
    ensure_runtime_dir()
    existing = read_pid_record()
    if existing and process_exists(int(existing["pid"])):
        return int(existing["pid"])

    stdout_handle = STDOUT_LOG.open("a", encoding="utf-8")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    command = [sys.executable, str(RUNNER)]
    if headed:
        command.append("--headed")

    proc = subprocess.Popen(
        command,
        cwd=str(ROOT_DIR),
        stdout=stdout_handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=False if os.name == "nt" else True,
    )
    write_pid_record(
        {
            "pid": proc.pid,
            "started_at": iso_now(),
            "command": command,
            "cwd": str(ROOT_DIR),
            "headed": headed,
        }
    )
    stdout_handle.close()
    return proc.pid


def stop_process() -> bool:
    record = read_pid_record()
    if not record:
        return False
    pid = int(record["pid"])
    if not process_exists(pid):
        remove_pid_record()
        return False
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True, text=True)
    for _ in range(10):
        if not process_exists(pid):
            remove_pid_record()
            return True
        time.sleep(0.5)
    return False


def status() -> dict[str, Any]:
    record = read_pid_record()
    pid = int(record["pid"]) if record else None
    running = bool(pid and process_exists(pid))
    if record and not running:
        remove_pid_record()
    return {
        "running": running,
        "pid": pid,
        "pid_record": record,
        "heartbeat_log": str(HEARTBEAT_LOG.resolve()),
        "runner_log": str(STDOUT_LOG.resolve()),
        "last_event": last_heartbeat_event(),
    }


def git_pull() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT_DIR), "pull", "--ff-only"],
        capture_output=True,
        text=True,
        check=False,
    )


def update_restart(headed: bool = False) -> dict[str, Any]:
    stopped = stop_process()
    pulled = git_pull()
    if pulled.returncode != 0:
        return {
            "stopped": stopped,
            "pull_ok": False,
            "pull_stdout": pulled.stdout,
            "pull_stderr": pulled.stderr,
            "started": False,
            "pid": None,
        }
    pid = start_process(headed=headed)
    return {
        "stopped": stopped,
        "pull_ok": True,
        "pull_stdout": pulled.stdout,
        "pull_stderr": pulled.stderr,
        "started": True,
        "pid": pid,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the 95306 keepalive worker.")
    parser.add_argument("action", choices=["start", "status", "stop", "update-restart"])
    parser.add_argument("--headed", action="store_true", help="Start the keepalive worker in headed mode.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.action == "start":
        pid = start_process(headed=args.headed)
        print(json.dumps({"action": "start", "pid": pid}, ensure_ascii=False))
        return 0
    if args.action == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0
    if args.action == "stop":
        print(json.dumps({"action": "stop", "stopped": stop_process()}, ensure_ascii=False))
        return 0
    if args.action == "update-restart":
        result = update_restart(headed=args.headed)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["pull_ok"] and result["started"] else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
