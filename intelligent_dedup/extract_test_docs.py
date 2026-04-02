import ast
import os
from pathlib import Path

def get_test_descriptions(tests_dir: Path) -> dict[str, str]:
    """Map 'ClassName.test_name' or 'test_name' to docstring or first comment."""
    descriptions = {}
    for py_file in tests_dir.glob("test_*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = node.name
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                            doc = ast.get_docstring(item)
                            key = f"{py_file.stem}.{class_name}.{item.name}"
                            if doc:
                                descriptions[key] = doc.strip()
                            # Alternate key for short classname
                            descriptions[f"{class_name}.{item.name}"] = doc.strip() if doc else ""
                elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    doc = ast.get_docstring(node)
                    if doc:
                        descriptions[f"{py_file.stem}.{node.name}"] = doc.strip()
                        descriptions[node.name] = doc.strip()
        except Exception:
            pass
    return descriptions
