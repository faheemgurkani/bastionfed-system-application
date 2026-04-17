#!/usr/bin/env python3
"""
OpenAPI-driven smoke scan for unified + legacy implementation backends.

What it does:
- Loads each app (TestClient, so no port needed).
- Iterates `app.openapi()` paths/methods.
- Calls each endpoint with best-effort placeholder params.
- Records HTTP status + response detail `code` (when present).

Fail rule:
- Only HTTP 5xx or request/runtime exceptions are considered "bad".
  401/403/404/422 are expected due to auth/validation/missing demo data.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"


@dataclass(frozen=True)
class AppSpec:
    name: str
    parent_dir: Path  # contains the `app/` package


APP_SPECS = [
    AppSpec(name="unified", parent_dir=BACKEND_DIR),
    AppSpec(name="hunain", parent_dir=BACKEND_DIR / "hunain_implementation"),
    AppSpec(name="hammad", parent_dir=BACKEND_DIR / "hammad_implementation"),
    AppSpec(name="faheem", parent_dir=BACKEND_DIR / "faheem_implementation"),
]


def _placeholder_for_param(param_name: str) -> str:
    n = (param_name or "").lower()
    if "alert" in n:
        return "ALT-TEST"
    if "incident" in n:
        return "INC-001"
    if "sample" in n:
        return "MAL-TEST"
    if "rca" in n:
        return "RCA-TEST"
    if "client" in n:
        return "Client-1"
    if "device" in n:
        return "dev-01"
    if "conversation" in n:
        return "conv-does-not-exist"
    if "model_name" in n or "model" in n:
        return "v4.2.1-DNN"
    if "step" in n:
        return "s1"
    return "TEST"


def _detail_code_from_response(resp: Any) -> str | None:
    try:
        j = resp.json()
    except Exception:
        return None

    if not isinstance(j, dict):
        return None

    d = j.get("detail")
    if isinstance(d, dict):
        code = d.get("code")
        return str(code) if code is not None else None
    if isinstance(d, str):
        return d
    return None


def _import_app_from_parent(parent_dir: Path):
    # Ensure the correct `app/` package is importable.
    sys.path.insert(0, str(parent_dir))

    # Remove any previously imported `app.*` modules so each variant loads its own package.
    for m in list(sys.modules.keys()):
        if m == "app" or m.startswith("app."):
            del sys.modules[m]

    try:
        mod = importlib.import_module("app.main")
        app = getattr(mod, "app")
        return app
    finally:
        # Keep sys.path clean for next variant.
        try:
            sys.path.remove(str(parent_dir))
        except ValueError:
            pass


def _openapi_route_params(path_item: dict[str, Any], operation: dict[str, Any]) -> list[dict[str, Any]]:
    params: list[dict[str, Any]] = []
    for p in path_item.get("parameters", []) or []:
        if isinstance(p, dict):
            params.append(p)
    for p in operation.get("parameters", []) or []:
        if isinstance(p, dict):
            params.append(p)
    return params


def _scan_app(app_spec: AppSpec) -> dict[str, Any]:
    # Make unified app imports not fail due to strict data-plane.
    os.environ.setdefault("DEMO_MODE", "1")
    os.environ["BASTIONFED_STRICT_DATA_PLANE"] = os.environ.get("BASTIONFED_STRICT_DATA_PLANE", "0")

    app = _import_app_from_parent(app_spec.parent_dir)
    schema = app.openapi()
    paths = schema.get("paths", {}) or {}

    client = TestClient(app)

    try:
        out: dict[str, Any] = {
            "app": app_spec.name,
            "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "totalRoutes": 0,
            "badRoutes": [],
            "routes": [],
        }

        # SSE endpoints (text/event-stream) are infinite; we either skip them or they will time out.
        def _is_probably_streaming(op: dict[str, Any]) -> bool:
            responses = op.get("responses") or {}
            if not isinstance(responses, dict):
                return False
            for resp_obj in responses.values():
                if not isinstance(resp_obj, dict):
                    continue
                content = resp_obj.get("content") or {}
                if not isinstance(content, dict):
                    continue
                for media_type in content.keys():
                    if str(media_type).startswith("text/event-stream"):
                        return True
            return False

        for path_template, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            methods = path_item.keys()
            for method in methods:
                op = path_item.get(method)
                if not isinstance(op, dict):
                    continue
                if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                    continue

                op_params = _openapi_route_params(path_item, op)
                path_params: dict[str, str] = {}
                query_params: dict[str, str] = {}
                for p in op_params:
                    if p.get("in") == "path":
                        name = p.get("name")
                        if name:
                            path_params[name] = _placeholder_for_param(name)
                    elif p.get("in") == "query":
                        name = p.get("name")
                        if name and isinstance(p.get("schema"), dict):
                            default = p["schema"].get("default")
                            if default is not None:
                                query_params[name] = str(default)

                # Replace path params placeholders.
                url = path_template
                for k, v in path_params.items():
                    url = url.replace("{" + k + "}", v)

                # Auth bypass for read endpoints (unified uses `?dev=true` for demo mode reads).
                params: dict[str, Any] = dict(query_params)
                if method.lower() == "get":
                    params.setdefault("dev", "true")

                files = None
                data = None
                body = None

                skipped = False
                skip_reason = None
                rb = op.get("requestBody")
                if isinstance(rb, dict):
                    content = rb.get("content") or {}
                    if "application/json" in content:
                        body = {}
                    elif "multipart/form-data" in content:
                        data = {}
                        files = {}

                t0 = time.time()
                status_code = None
                detail_code = None
                exc_str: str | None = None

                try:
                    path_lower = str(path_template).lower()
                    if method.lower() == "get" and (
                        "/fl-events" in path_lower
                        or path_lower.endswith("/events")
                        or "/events" in path_lower
                        or "event-stream" in path_lower
                        or _is_probably_streaming(op)
                    ):
                        skipped = True
                        skip_reason = "SSE/streaming (events/text/event-stream) — skipped"
                        status_code = 0
                    else:
                        resp = client.request(
                            method.upper(),
                            url,
                            params=params,
                            json=body if body is not None else None,
                            data=data,
                            files=files,
                            timeout=8,
                        )
                        status_code = int(resp.status_code)
                        detail_code = _detail_code_from_response(resp)
                except Exception as exc:  # noqa: BLE001
                    exc_str = f"{type(exc).__name__}: {exc}"
                    status_code = 599
                finally:
                    duration_ms = int((time.time() - t0) * 1000)

                record = {
                    "method": method.upper(),
                    "pathTemplate": path_template,
                    "urlCalled": url,
                    "status": status_code,
                    "durationMs": duration_ms,
                    "detailCode": detail_code,
                    "exception": exc_str,
                    "skipped": skipped,
                    "skipReason": skip_reason,
                }

                out["totalRoutes"] += 1
                out["routes"].append(record)

                if (status_code >= 500 or exc_str) and not skipped:
                    out["badRoutes"].append(record)

        return out
    finally:
        client.close()


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = BACKEND_DIR / "test_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, Any] = {"generatedAt": ts, "apps": []}

    for spec in APP_SPECS:
        print(f"[scan] {spec.name} …")
        res = _scan_app(spec)
        out_path = out_dir / f"endpoint_statuses_{ts}_{spec.name}.json"
        out_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
        all_results["apps"].append({"name": spec.name, "out": str(out_path), "badRoutes": len(res["badRoutes"])})

        bad = res["badRoutes"]
        if bad:
            print(f"[scan] {spec.name}: BAD routes={len(bad)} (showing up to 5)")
            for r in bad[:5]:
                print(f"  - {r['method']} {r['pathTemplate']} -> {r['status']} ({r.get('detailCode')})")
        else:
            print(f"[scan] {spec.name}: OK (no 5xx/exception)")

    summary_path = out_dir / f"endpoint_statuses_{ts}_SUMMARY.json"
    summary_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"[scan] Summary: {summary_path}")


if __name__ == "__main__":
    main()

