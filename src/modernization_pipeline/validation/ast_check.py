"""Static validation of generated Python."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def check_ast(code: str) -> dict[str, Any]:
    try:
        ast.parse(code)
        return {"ok": True, "error": None}
    except SyntaxError as exc:
        return {
            "ok": False,
            "error": {
                "message": exc.msg,
                "lineno": exc.lineno,
                "offset": exc.offset,
            },
        }


def check_ruff(code: str) -> dict[str, Any]:
    """Run ruff check on a temporary file; soft-fail if ruff is unavailable."""
    if not code.strip():
        return {"ok": False, "issues": [{"code": "EMPTY", "message": "empty code"}], "available": True}

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "generated.py"
        path.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "--output-format", "json", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return {"ok": True, "issues": [], "available": False, "note": "ruff not installed"}

        issues: list[dict[str, Any]] = []
        if proc.stdout.strip():
            try:
                payload = json.loads(proc.stdout)
                for item in payload:
                    issues.append(
                        {
                            "code": item.get("code"),
                            "message": item.get("message"),
                            "lineno": (item.get("location") or {}).get("row"),
                        }
                    )
            except json.JSONDecodeError:
                if proc.returncode != 0:
                    issues.append({"code": "RUFF", "message": proc.stdout or proc.stderr})

        # Exit 0 => clean; exit 1 => findings; other => tool error
        if proc.returncode not in (0, 1) and not issues:
            return {
                "ok": True,
                "issues": [],
                "available": True,
                "note": (proc.stderr or "ruff returned unexpected status").strip(),
            }

        return {
            "ok": len(issues) == 0,
            "issues": issues,
            "available": True,
        }
