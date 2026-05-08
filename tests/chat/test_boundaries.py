import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
    return found


def test_scheduling_modules_do_not_import_chat() -> None:
    scheduling_roots = [
        ROOT / "app" / "api",
        ROOT / "app" / "services",
        ROOT / "app" / "models",
    ]
    violations: list[str] = []
    for root in scheduling_roots:
        for py in root.rglob("*.py"):
            for module in _imports(py):
                if module.startswith("app.chat"):
                    violations.append(f"{py.relative_to(ROOT)} -> {module}")
    assert violations == []
