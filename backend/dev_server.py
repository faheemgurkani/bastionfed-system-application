from __future__ import annotations

from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parent


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[
            str(ROOT / "app"),
            str(ROOT / "tests"),
        ],
        reload_excludes=[
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
        ],
    )


if __name__ == "__main__":
    main()
