"""P1 — architectural guardrail: the core imports no vendor SDK.

Pure AST scan of src/domain and src/application so the rule holds with no extra
tooling. (.importlinter mirrors this for CI.) This is the rule ARCHITECTURE.md
says Code "can't violate."
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE_DIRS = [ROOT / "src" / "domain", ROOT / "src" / "application"]

FORBIDDEN_TOP_LEVEL = {
    "fastapi", "starlette", "uvicorn", "pydantic",  # delivery/framework
    "psycopg", "sqlalchemy", "supabase",            # persistence
    "anthropic", "stripe", "httpx", "requests",     # vendor SDKs / HTTP
}


def _imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def test_core_imports_no_vendor_sdk():
    violations: list[str] = []
    for core in CORE_DIRS:
        for py in core.rglob("*.py"):
            bad = _imported_modules(py) & FORBIDDEN_TOP_LEVEL
            if bad:
                violations.append(f"{py.relative_to(ROOT)} imports {sorted(bad)}")
    assert not violations, "core layer imports forbidden modules:\n" + "\n".join(violations)
