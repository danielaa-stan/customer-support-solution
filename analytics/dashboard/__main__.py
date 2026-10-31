"""Launcher: python -m analytics.dashboard [--sample] [--port N]"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(prog="analytics.dashboard")
    parser.add_argument("--sample", action="store_true", help="show synthetic in-memory data")
    parser.add_argument("--port", type=int, default=8502)
    args = parser.parse_args()
    env = dict(os.environ)
    if args.sample:
        env["DASHBOARD_SAMPLE"] = "1"
    app = Path(__file__).with_name("app.py")
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(app), "--server.port", str(args.port),
        "--theme.base", "dark", "--theme.primaryColor", "#1DB954",
    ]
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
