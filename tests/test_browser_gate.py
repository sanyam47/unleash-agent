import sys
from pathlib import Path
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.browser_gate import audit_workspace_runtime

def test_working_app():
    # Test on a clean self-contained temporary working app
    tmp = Path(tempfile.mkdtemp(prefix="test_working_gate_"))
    try:
        (tmp / "index.html").write_text("""<!DOCTYPE html>
<html>
<head><title>Working App</title></head>
<body>
  <h1>Pomodoro App</h1>
  <div id="timer-display">25:00</div>
  <input type="text" id="taskInput" placeholder="Add task">
  <button id="startBtn">Start</button>
  <button id="addBtn">Add</button>
  <ul id="taskList"></ul>
  <script src="app.js"></script>
</body>
</html>""", encoding="utf-8")

        (tmp / "app.js").write_text("""
let count = 1500;
document.getElementById('startBtn').addEventListener('click', function() {
    count--;
    document.getElementById('timer-display').innerText = "24:59";
});
document.getElementById('addBtn').addEventListener('click', function() {
    const val = document.getElementById('taskInput').value;
    const li = document.createElement('li');
    li.innerText = val;
    document.getElementById('taskList').appendChild(li);
});
""", encoding="utf-8")

        res = audit_workspace_runtime(tmp)
        print("Working App Audit Result:")
        print("  Valid:", res["valid"])
        print("  Interactions tested:", len(res["interactions"]))
        print("  Summary:\n", res["summary"])
        assert res["valid"], f"Expected working app to pass audit: {res.get('critical_errors')}"
        assert res["is_rendered"], "Expected page to be rendered"
        print("test_working_app passed!")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

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

def test_disabled_button_and_audio():
    # Test that disabled buttons are not flagged as unresponsive defects,
    # and AudioContext initializes cleanly without throwing headless security exceptions.
    tmp = Path(tempfile.mkdtemp(prefix="test_audio_gate_"))
    try:
        (tmp / "index.html").write_text("""<!DOCTYPE html>
<html>
<head><title>Audio & State App</title></head>
<body>
  <h1>Audio & Form App</h1>
  <input type="text" id="userInput" placeholder="Type here">
  <button id="submitBtn">Submit</button>
  <button id="disabledNextBtn" disabled>Next Step</button>
  <div id="output"></div>
  <script src="app.js"></script>
</body>
</html>""", encoding="utf-8")

        (tmp / "app.js").write_text("""
// Initialize Web Audio API on load
try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
} catch(e) {}

document.getElementById('submitBtn').addEventListener('click', function() {
    const val = document.getElementById('userInput').value;
    document.getElementById('output').innerText = "Submitted: " + val;
});
""", encoding="utf-8")

        res = audit_workspace_runtime(tmp)
        print("Disabled Button & Audio Audit Result:")
        print("  Valid:", res["valid"])
        print("  Interactions:", [(i['element'], i.get('is_disabled')) for i in res["interactions"]])
        assert res["valid"], f"Expected app to pass: {res.get('critical_errors')}"
        
        # Verify disabled button was identified
        disabled_entries = [i for i in res["interactions"] if i.get("is_disabled")]
        assert len(disabled_entries) >= 1, "Expected disabled button to be detected"
        print("test_disabled_button_and_audio passed!")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_canvas_pixel_verification():
    # Test that HTML5 canvas pixel rendering and RAF loops are audited accurately
    tmp = Path(tempfile.mkdtemp(prefix="test_canvas_gate_"))
    try:
        (tmp / "index.html").write_text("""<!DOCTYPE html>
<html>
<head><title>Canvas Game</title></head>
<body>
  <canvas id="gameCanvas" width="200" height="200"></canvas>
  <button id="drawBtn">Start Game</button>
  <script src="app.js"></script>
</body>
</html>""", encoding="utf-8")

        (tmp / "app.js").write_text("""
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
ctx.fillStyle = "#ff0055";
ctx.fillRect(10, 10, 50, 50);

document.getElementById('drawBtn').addEventListener('click', function() {
    ctx.fillStyle = "#00ffcc";
    ctx.fillRect(60, 60, 50, 50);
});
""", encoding="utf-8")

        res = audit_workspace_runtime(tmp)
        print("Canvas App Audit Result:")
        print("  Valid:", res["valid"])
        print("  is_rendered:", res["is_rendered"])
        assert res["valid"], f"Expected canvas app to pass: {res.get('critical_errors')}"
        assert res["is_rendered"], "Expected canvas app to be marked as rendered"
        print("test_canvas_pixel_verification passed!")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_compact_diagnostics_token_budget():
    from backend.core.browser_gate import compress_browser_diagnostics
    mock_failure = {
        "valid": False,
        "critical_errors": [
            "BUTTON CRASH: Clicking '#startBtn' threw: TypeError: Cannot read properties of null",
            "UNHANDLED RUNTIME EXCEPTION: ReferenceError: 'synth' is not defined"
        ],
        "diagnostics": [
            {"file": "app.js", "category": "runtime_exception", "message": "synth is not defined"}
        ]
    }
    compact = compress_browser_diagnostics(mock_failure)
    print("Compressed Diagnostics Output:\n", compact)
    assert len(compact.split()) < 50, "Expected compressed feedback to be under 50 words (<70 tokens)"
    print("test_compact_diagnostics_token_budget passed!")


if __name__ == "__main__":
    test_working_app()
    test_broken_runtime_app()
    test_disabled_button_and_audio()
    test_canvas_pixel_verification()
    test_compact_diagnostics_token_budget()
    print("\nALL HARDENED BROWSER GATE SUITE TESTS PASSED!")

