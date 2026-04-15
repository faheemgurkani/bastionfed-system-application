from __future__ import annotations

"""
Local FastAPI server.

`reload=True` uses a parent WatchFiles process; Ctrl+C sometimes does not kill it
cleanly (especially in IDE terminals). By default we run a **single process** so
SIGINT exits immediately. Use `--reload` when you want auto-restart on file changes.
"""

import argparse
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parent


def main() -> None:
    p = argparse.ArgumentParser(description="Run BastionFed API with uvicorn.")
    p.add_argument(
        "-r",
        "--reload",
        action="store_true",
        help="Restart when app/ or tests/ change (extra process; Ctrl+C may need an extra tap).",
    )
    args = p.parse_args()

    kwargs: dict = {
        "host": "0.0.0.0",
        "port": 8000,
        "reload": args.reload,
    }
    if args.reload:
        kwargs["reload_dirs"] = [
            str(ROOT / "app"),
            str(ROOT / "tests"),
        ]
        kwargs["reload_excludes"] = [
            "*.sqlite3",
            "*.db",
            "*.pyc",
            "__pycache__/*",
            ".pytest_cache/*",
            ".venv/*",
            "data/*",
            "faheem_implementation/*",
            "hunain_implementation/*",
            "hammad_implementation/*",
        ]

    uvicorn.run("app.main:app", **kwargs)


if __name__ == "__main__":
    main()
