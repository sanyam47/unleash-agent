#!/usr/bin/env python3
"""
Scout Contract Skeleton Generator
Extracts lean interface definitions (functions, classes, route declarations)
from code files to keep LLM context consumption under 400 tokens per file.
"""

import sys
import os
import re
import argparse
import json
from typing import Dict, Any, List

def extract_python_skeleton(content: str) -> str:
    lines = content.split("\n")
    skeleton = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("class ", "def ", "@", "import ", "from ")):
            if stripped.startswith("def ") and stripped.endswith(":"):
                # Replace body with ellipsis
                indent = len(line) - len(line.lstrip())
                skeleton.append(line)
                skeleton.append(" " * (indent + 4) + "...")
            else:
                skeleton.append(line)
    return "\n".join(skeleton)

def extract_js_ts_skeleton(content: str) -> str:
    lines = content.split("\n")
    skeleton = []
    pattern = re.compile(r"^\s*(export\s+)?(function|class|const|let|interface|type)\s+([A-Za-z0-9_]+)")
    for line in lines:
        if pattern.match(line) or line.strip().startswith(("import ", "export default")):
            skeleton.append(line)
    return "\n".join(skeleton)

def scout_file(filepath: str) -> Dict[str, Any]:
    if not os.path.exists(filepath):
        return {"error": f"File '{filepath}' not found."}

    ext = os.path.splitext(filepath)[1].lower()
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    orig_tokens = len(content.split())
    if ext == ".py":
        skel = extract_python_skeleton(content)
    elif ext in [".js", ".jsx", ".ts", ".tsx"]:
        skel = extract_js_ts_skeleton(content)
    else:
        skel = "\n".join(content.split("\n")[:20]) # First 20 lines

    skel_tokens = len(skel.split())
    return {
        "file": filepath,
        "original_tokens_approx": orig_tokens,
        "skeleton_tokens_approx": skel_tokens,
        "savings_percent": round((1 - (skel_tokens / max(1, orig_tokens))) * 100, 1),
        "skeleton_contract": skel
    }

def main():
    parser = argparse.ArgumentParser(description="Scout Contract Skeleton Generator")
    parser.add_argument("--file", required=True, help="File to scout")
    args = parser.parse_args()

    res = scout_file(args.file)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
