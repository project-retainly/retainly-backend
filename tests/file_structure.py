import ast
from pathlib import Path
from typing import List

# Project root: /home/<user>/Documents/retainly_project/backend
PROJECT_ROOT = Path.home() / "Documents" / "retainly_project" / "backend"


def format_arg(arg: ast.arg) -> str:
    if arg.annotation:
        return f"{arg.arg}: {ast.unparse(arg.annotation)}"
    return arg.arg


def get_function_signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args: List[str] = []

    # positional + keyword args
    for arg in fn.args.args:
        args.append(format_arg(arg))

    # *args
    if fn.args.vararg:
        args.append(f"*{fn.args.vararg.arg}")

    # keyword-only args
    for arg in fn.args.kwonlyargs:
        args.append(format_arg(arg))

    # **kwargs
    if fn.args.kwarg:
        args.append(f"**{fn.args.kwarg.arg}")

    params = ", ".join(args)

    if fn.returns:
        return f"{fn.name}({params}) -> {ast.unparse(fn.returns)}"

    return f"{fn.name}({params})"


def generate_class_docs(relative_path: str) -> str:
    file_path = PROJECT_ROOT / relative_path

    with file_path.open("r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    lines: List[str] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            lines.append(f"class {node.name}:")

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    lines.append(f"  - {get_function_signature(item)}")

            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    print(
        generate_class_docs("tests/auth/tasks/cleanup_expired_refresh_tokens_test.py")
    )
