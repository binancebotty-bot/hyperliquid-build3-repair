#!/usr/bin/env python3
"""Machine-readable function list of a Python file (stdlib ast, deterministic).
    python tools/function_inventory.py <file.py> [out.json]
Writes {file, sha256, functions:[{name, qualname, line, end_line, args, doc1}]}. Diff two inventories to compare builds."""
import ast, hashlib, json, sys


def main(argv):
    src = open(argv[1], 'rb').read()
    tree = ast.parse(src.decode('utf-8-sig', errors='replace'))
    out = []

    def walk(node, prefix=""):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = prefix + ch.name
                out.append({"name": ch.name, "qualname": q, "line": ch.lineno, "end_line": getattr(ch, "end_lineno", ch.lineno),
                            "args": [a.arg for a in ch.args.args], "doc1": (ast.get_docstring(ch) or "").split("\n")[0][:120]})
                walk(ch, q + ".")
            elif isinstance(ch, ast.ClassDef):
                walk(ch, prefix + ch.name + ".")
    walk(tree)
    res = {"file": argv[1], "sha256": hashlib.sha256(src).hexdigest(), "count": len(out), "functions": out}
    open(argv[2] if len(argv) > 2 else argv[1] + ".functions.json", "w").write(json.dumps(res, indent=1))
    print(len(out), "functions")


if __name__ == "__main__":
    main(sys.argv)
