import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.goal_stepper import decompose_goals, verify_milestones, format_goal_checklist_for_prompt

def test_decomposition():
    prompt = (
        "Build a modern Cyberpunk Focus & Pomodoro Station with a dark theme (#0b0f17, neon cyan #00f2fe and violet #8a2be2 accents). "
        "Include a glowing circular timer display with 25-minute Work and 5-minute Break toggle buttons, Start / Pause / Reset controls, "
        "and a task list where I can add focus goals and check them off with sound feedback."
    )
    goals = decompose_goals(prompt)
    print(f"Decomposed {len(goals)} goals:")
    for idx, g in enumerate(goals, 1):
        print(f"  {idx}. {g['name']} ({g['id']})")
    
    assert len(goals) >= 2, "Expected at least 2 milestones"
    assert any(g["id"] == "milestone_layout" for g in goals), "Expected layout milestone"
    assert any(g["id"] == "milestone_timer" for g in goals), "Expected timer milestone"
    assert any(g["id"] == "milestone_audio" for g in goals), "Expected audio milestone"
    assert any(g["id"] == "milestone_tasks" for g in goals), "Expected tasks milestone"
    print("test_decomposition passed!")

def test_verification_incomplete():
    # Test on a dummy incomplete project folder
    test_dir = Path("c:/coding/ai-trainer/backend/data/projects/test_validator")
    prompt = "Build a pomodoro timer with audio feedback and task list"
    goals = decompose_goals(prompt)
    res = verify_milestones(test_dir, goals, current_step=1)
    print("Incomplete verification result:")
    print(f"  All completed: {res['all_completed']}")
    print(f"  Completed: {res['completed_count']} / {res['total_count']}")
    if res['next_uncompleted']:
        print(f"  Next uncompleted: {res['next_uncompleted']['name']}")
    print("Feedback prompt:\n", res['feedback_prompt'])
    assert not res['all_completed'], "Should not be all completed for incomplete project"
    print("test_verification_incomplete passed!")

def test_prompt_formatting():
    prompt = "Build an e-commerce store with search and cart"
    goals = decompose_goals(prompt)
    text = format_goal_checklist_for_prompt(goals)
    print("Formatted Checklist:\n", text)
    assert "=== AUTONOMOUS GOAL CHECKLIST" in text
    print("test_prompt_formatting passed!")

if __name__ == "__main__":
    test_decomposition()
    test_verification_incomplete()
    test_prompt_formatting()
    print("ALL TESTS PASSED!")
