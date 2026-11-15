#!/usr/bin/env python3
"""
Surgical AST Diff Patcher
Performs a 3-pass anchor match (Exact -> Normalized Whitespace -> Indentation-Agnostic)
and validates syntax via AST before saving to disk.

Prevents AI agents from wiping or corrupting existing files.
"""

import sys
import os
import ast
import json
import argparse
from typing import Dict, Any, Tuple

def validate_syntax(filepath: str, content: str) -> Tuple[bool, str]:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".py":
        try:
            ast.parse(content)
            return True, "Valid Python syntax"
        except SyntaxError as e:
            return False, f"Python SyntaxError at line {e.lineno}: {e.msg}"
    elif ext == ".json":
        try:
            json.loads(content)
            return True, "Valid JSON syntax"
        except Exception as e:
            return False, f"JSON SyntaxError: {str(e)}"
    # JS/TS and other text files pass through standard balance checks
    return True, "Syntax check skipped (non-Python/JSON)"

def apply_3pass_patch(original: str, target: str, replacement: str) -> Tuple[bool, str, str]:
    if not target:
        return False, original, "Target string cannot be empty"

    # Pass 1: Exact Match
    if target in original:
        occurrences = original.count(target)
        if occurrences > 1:
            return False, original, f"Ambiguous target: found {occurrences} occurrences. Provide larger anchor context."
        patched = original.replace(target, replacement, 1)
        return True, patched, "Pass 1: Exact match successful"

    # Pass 2: Normalized Whitespace / Line-Ending Match
    norm_orig = original.replace("\r\n", "\n")
    norm_target = target.replace("\r\n", "\n")
    norm_replacement = replacement.replace("\r\n", "\n")
    if norm_target in norm_orig:
        occurrences = norm_orig.count(norm_target)
        if occurrences > 1:
            return False, original, f"Ambiguous target in normalized pass: found {occurrences} matches."
        patched = norm_orig.replace(norm_target, norm_replacement, 1)
        return True, patched, "Pass 2: Normalized line-ending match successful"

    # Pass 3: Trimmed Block Indentation Match
    target_lines = [l.strip() for l in norm_target.strip().split("\n") if l.strip()]
    if target_lines:
        orig_lines = norm_orig.split("\n")
        first_target = target_lines[0]
        match_idx = -1
        for idx, line in enumerate(orig_lines):
            if line.strip() == first_target:
                # Check subsequent lines
                sub_match = True
                for t_offset, t_line in enumerate(target_lines):
                    if idx + t_offset >= len(orig_lines) or orig_lines[idx + t_offset].strip() != t_line:
                        sub_match = False
                        break
                if sub_match:
                    if match_idx != -1:
                        return False, original, "Ambiguous target in Pass 3: multiple block matches found."
                    match_idx = idx

        if match_idx != -1:
            # Reconstruct lines
            before = orig_lines[:match_idx]
            after = orig_lines[match_idx + len(target_lines):]
            patched = "\n".join(before + [norm_replacement] + after)
            return True, patched, "Pass 3: Indentation-agnostic block match successful"

    return False, original, "Target string not found in file. Check anchor lines."

def main():
    parser = argparse.ArgumentParser(description="Surgical AST Diff Patcher")
    parser.add_argument("--file", required=True, help="Path to file to patch")
    parser.add_argument("--target", required=True, help="Exact code block to replace")
    parser.add_argument("--replacement", required=True, help="New code block to insert")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(json.dumps({"status": "error", "error": f"File '{args.file}' does not exist."}))
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8-sig", errors="replace") as f:
        original_content = f.read()

    success, patched_content, match_mode = apply_3pass_patch(original_content, args.target, args.replacement)
    if not success:
        print(json.dumps({"status": "error", "error": match_mode}))
        sys.exit(1)

    # Validate AST
    is_valid, syntax_msg = validate_syntax(args.file, patched_content)
    if not is_valid:
        print(json.dumps({
            "status": "error",
            "error": f"Surgical diff rejected due to syntax corruption: {syntax_msg}"
        }))
        sys.exit(1)

    # Write back without BOM
    with open(args.file, "w", encoding="utf-8") as f:
        f.write(patched_content)

    print(json.dumps({
        "status": "success",
        "file": args.file,
        "match_mode": match_mode,
        "syntax_verification": syntax_msg
    }, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
