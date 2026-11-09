import sys
from pathlib import Path
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.browser_gate import audit_workspace_runtime

def test_working_app():
    # Test on existing project
    proj_dir = Path("c:/coding/ai-trainer/backend/data/projects/proj_chat_17941159652")
    res = audit_workspace_runtime(proj_dir)
    print("Working App Audit Result:")
    print("  Valid:", res["valid"])
    print("  Interactions tested:", len(res["interactions"]))
    print("  Summary:\n", res["summary"])
    assert res["is_rendered"], "Expected page to be rendered"
    print("test_working_app passed!")

def test_broken_runtime_app():
    # Create temporary directory with a broken JS file that throws runtime error on click
    tmp = Path(tempfile.mkdtemp(prefix="test_browser_gate_"))
    try:
        (tmp / "index.html").write_text("""<!DOCTYPE html>
<html>
<head><title>Broken App</title></head>
<body>
  <h1>Broken App Test</h1>
  <button id="crashBtn">Click to Crash</button>
  <script src="app.js"></script>
</body>
</html>""", encoding="utf-8")

        # Deliberate runtime crash on click
        (tmp / "app.js").write_text("""
document.getElementById('crashBtn').addEventListener('click', function() {
    let obj = null;
    obj.someNonExistentFunction(); // Throws TypeError: Cannot read properties of null
});
""", encoding="utf-8")

        res = audit_workspace_runtime(tmp)
        print("Broken App Audit Result:")
        print("  Valid:", res["valid"])
        print("  Errors caught:", len(res["critical_errors"]))
        print("  Summary:\n", res["summary"])
        assert not res["valid"], "Expected broken app to fail runtime audit"
        assert any("BUTTON CRASH" in err or "TypeError" in err for err in res["critical_errors"])
        print("test_broken_runtime_app successfully caught runtime crash!")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    test_working_app()
    test_broken_runtime_app()
    print("ALL BROWSER GATE TESTS PASSED!")
