"""
Start TutorLoop — FastAPI app + LiveKit AI lecture agent in one command.

  python run.py
  python run.py --port 8080
  python run.py --production          # Docker / production
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "backend" / ".env")
    if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


def should_run_agent() -> bool:
    flag = os.getenv("RUN_LIVEKIT_AGENT", "true").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    has_livekit = bool(os.getenv("LIVEKIT_URL") and os.getenv("LIVEKIT_API_KEY") and os.getenv("LIVEKIT_API_SECRET"))
    has_llm = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    return has_livekit and has_llm


def terminate_processes(processes: list[subprocess.Popen]) -> None:
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
    for proc in processes:
        if proc.poll() is not None:
            continue
        try:
            proc.wait(timeout=12)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TutorLoop (web app + AI lecture agent)")
    parser.add_argument("--host", default=os.getenv("APP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")))
    parser.add_argument("--production", action="store_true", help="Production mode (agent start, no API reload)")
    parser.add_argument("--no-reload", action="store_true", help="Disable API auto-reload")
    parser.add_argument("--no-agent", action="store_true", help="Skip LiveKit agent even if configured")
    args = parser.parse_args()

    load_env()
    processes: list[subprocess.Popen] = []
    env = os.environ.copy()

    agent_mode = "start" if args.production else "dev"
    if not args.no_agent and should_run_agent():
        try:
            agent_proc = subprocess.Popen(
                [sys.executable, "-m", "backend.agent.tutor_agent", agent_mode],
                cwd=str(ROOT),
                env=env,
            )
            processes.append(agent_proc)
            print(f"[tutorloop] LiveKit AI agent started ({agent_mode}, pid {agent_proc.pid})", flush=True)
        except Exception as exc:
            print(f"[tutorloop] Could not start LiveKit agent: {exc}", flush=True)
    else:
        print("[tutorloop] LiveKit agent skipped — AI lectures use browser voice fallback.", flush=True)

    uvicorn_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if not args.production and not args.no_reload:
        uvicorn_cmd.append("--reload")

    api_proc = subprocess.Popen(uvicorn_cmd, cwd=str(ROOT), env=env)
    processes.append(api_proc)
    print(f"[tutorloop] Web app at http://{args.host}:{args.port}", flush=True)

    def shutdown_handler(*_args) -> None:
        print("\n[tutorloop] Shutting down…")
        terminate_processes(processes)
        sys.exit(0)

    if sys.platform != "win32":
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        while True:
            for proc in processes:
                code = proc.poll()
                if code is not None:
                    print(f"[tutorloop] Process exited with code {code}. Stopping all services.")
                    terminate_processes(processes)
                    return code or 1
            import time

            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown_handler()


if __name__ == "__main__":
    raise SystemExit(main())
