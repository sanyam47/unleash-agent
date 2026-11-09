"""
Test Suite for Unleash-Agent Privacy-Preserving Web Documentation Search Tool.
Tests:
  1. Live documentation lookup (DuckDuckGo HTML).
  2. In-flight secret and file path scrubber (zero leakage).
  3. Confidential project air-gap isolation (.private blocks external queries).
  4. Tool dispatch and schema integrity.
"""

import sys
import shutil
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.agent_tools import (
    search_web_docs,
    dispatch_tool,
    AGENT_TOOLS_SCHEMA,
    get_project_dir,
    write_project_file
)
from backend.core.memory_manager import exclude_project_from_memory, PROJECTS_ROOT


def test_live_web_search():
    print("\n--- Test 1: Live Privacy Documentation Search ---")
    res = search_web_docs("Leaflet map quickstart CDN")
    assert res["status"] in ("success", "fallback_local", "offline")
    if res["status"] == "success":
        assert res.get("privacy_protected") is True
        assert len(res.get("results", [])) > 0
        print(f"Retrieved {len(res['results'])} documentation results.")
        print(f"Top snippet: {res['results'][0]['snippet'][:120]}...")
    else:
        print(f"Search completed with status: {res['status']}")


def test_secret_and_path_scrubbing():
    print("\n--- Test 2: In-Flight Secret & File Path Scrubber ---")
    leak_query = "Chart.js docs with sk-proj1234567890abcdef1234567890abcdef from C:\\Users\\secret\\code.js"
    res = search_web_docs(leak_query)
    
    # Assert secret was scrubbed in query response
    assert "sk-proj1234567890abcdef" not in res["query"], "CRITICAL FLAW: API key not scrubbed!"
    assert "C:\\Users\\secret\\code.js" not in res["query"], "CRITICAL FLAW: Local file path not scrubbed!"
    assert "[SECRET_REDACTED]" in res["query"]
    assert "[PATH_REDACTED]" in res["query"]
    print("Verified: API keys and local file paths are completely scrubbed in-flight!")


def test_confidential_project_air_gap():
    print("\n--- Test 3: Confidential Project Air-Gap Isolation ---")
    pname = "test_confidential_enterprise_bank"
    write_project_file(pname, "index.html", "<h1>Top Secret</h1>")
    
    # Mark project as private
    exclude_project_from_memory(pname)
    assert (PROJECTS_ROOT / pname / ".private").exists()

    # Attempt web search scoped to this project
    res = search_web_docs("Leaflet map CDN", project_name=pname)
    assert res["status"] == "privacy_blocked"
    assert res["offline"] is True
    assert "disabled for confidential project" in res["message"]
    print("Verified: Confidential projects are strictly blocked from external network requests!")

    # Cleanup
    shutil.rmtree(PROJECTS_ROOT / pname, ignore_errors=True)


def test_tool_dispatch_and_schema():
    print("\n--- Test 4: Tool Schema & Dispatch Integration ---")
    tool_names = [t["name"] for t in AGENT_TOOLS_SCHEMA]
    assert "search_web_docs" in tool_names

    # Test tool dispatch
    ctx = {"project_name": "test_public_tool_proj"}
    res = dispatch_tool("search_web_docs", {"query": "Vue 3 reactive CDN"}, ctx)
    assert res["status"] in ("success", "fallback_local", "offline")
    print("Verified: 'search_web_docs' dispatches cleanly via agent loop!")


def main():
    print("="*70)
    print("RUNNING PRIVACY-PRESERVING WEB SEARCH TOOL TEST SUITE")
    print("="*70)
    test_live_web_search()
    test_secret_and_path_scrubbing()
    test_confidential_project_air_gap()
    test_tool_dispatch_and_schema()
    print("\n" + "="*70)
    print("ALL WEB SEARCH TOOL TESTS PASSED (100% SUCCESS)!")
    print("="*70)


if __name__ == "__main__":
    main()
