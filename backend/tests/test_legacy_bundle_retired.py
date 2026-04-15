from __future__ import annotations

from pathlib import Path


def _backend_app_root() -> Path:
    return Path(__file__).resolve().parent.parent / "app"


def test_unified_runtime_does_not_import_legacy_bundle_module() -> None:
    main_py = (_backend_app_root() / "main.py").read_text()
    assert "app.db.persistence" not in main_py
    assert "bf_bundle" not in main_py


def test_legacy_bundle_module_is_marked_legacy_only() -> None:
    persistence_py = (_backend_app_root() / "db" / "persistence.py").read_text()
    assert "legacy" in persistence_py.lower()
    assert "Do not wire new code to `bf_bundle`" in persistence_py
