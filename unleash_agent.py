#!/usr/bin/env python3
"""
Unleash-Agent Autonomous CLI Governor
Terminal interface for AI-assisted code editing, test verification, and automated rollback.

Usage:
  python unleash_agent.py "Add error handling to backend/core/config.py"
  python unleash_agent.py --triage
  python unleash_agent.py --fix-permissions
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.unleash_orchestrator import UnleashOrchestrator
from tools.sys_doctor import diagnose_app, fix_permissions, check_zombies

def print_banner():
    banner = r"""
  _   _       _                  _          _                    _   
 | | | |_ __ | | ___  __ _ ___| |__       / \   __ _  ___ _ __ | |_ 
 | | | | '_ \| |/ _ \/ _` / __| '_ \     / _ \ / _` |/ _ \ '_ \| __|
 | |_| | | | | |  __/ (_| \__ \ | | |   / ___ \ (_| |  __/ | | | |_ 
  \___/|_| |_|_|\___|\__,_|___/_| |_|  /_/   \_\__, |\___|_| |_|\__|
                                              |___/     CLI Governor
"""
    print(banner)

def main():
    parser = argparse.ArgumentParser(description="Unleash-Agent CLI Autonomous Governor")
    parser.add_argument("prompt", nargs="?", default="", help="Natural language instruction for the coding agent")
    parser.add_argument("--model", default="llama-3.3-70b-versatile", help="Model to target (Ollama or Cloud)")
    parser.add_argument("--triage", action="store_true", help="Run sys_doctor diagnostic check on host environment")
    parser.add_argument("--fix-permissions", action="store_true", help="Fix Windows workspace ACL and permission locks")
    parser.add_argument("--check-zombies", action="store_true", help="Inspect abandoned zombie server processes")

    args = parser.parse_args()
    print_banner()

    if args.triage:
        print("[CLI Governor]: Running System Doctor Triage...")
        results = diagnose_app(str(PROJECT_ROOT))
        if results and isinstance(results, dict):
            for k, v in results.items():
                print(f" * {k}: {v}")
        else:
            print("[✓] Clean bill of health. No active fault codes.")
        return

    if args.fix_permissions:
        print("[CLI Governor]: Repairing workspace ACL permissions...")
        fix_permissions(str(PROJECT_ROOT))
        return

    if args.check_zombies:
        print("[CLI Governor]: Checking zombie server processes...")
        zombies = check_zombies()
        print(f"Found Zombies: {len(zombies)}")
        for z in zombies:
            print(f" - PID {z.get('Id')}: {z.get('ProcessName')}")
        return

    if not args.prompt.strip():
        print("Error: No prompt provided. Example usage:")
        print('  python unleash_agent.py "Refactor backend/core/config.py to load .env reliably"')
        sys.exit(1)

    print(f"[CLI Governor]: Target Model -> {args.model}")
    print(f"[CLI Governor]: Task -> \"{args.prompt}\"")
    print("-" * 65)

    orchestrator = UnleashOrchestrator(workspace_path=str(PROJECT_ROOT))
    result = orchestrator.execute_task(args.prompt, model=args.model)

    print("-" * 65)
    print(f"Status: {result.get('status', 'complete').upper()}")
    if result.get("files_modified"):
        print(f"Files Modified: {', '.join(result['files_modified'])}")
    print(f"Summary: {result.get('summary', 'Task execution finished.')}")

if __name__ == "__main__":
    main()
