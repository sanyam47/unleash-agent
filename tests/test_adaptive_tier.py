import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.adaptive_tier import probe_local_gpu_hardware, probe_active_compute_tier, ExecutionTier
from backend.core.goal_stepper import decompose_goals, verify_milestones
from backend.core.browser_gate import audit_workspace_runtime
from backend.core.workspace_validator import validate_workspace

def test_local_hardware_probe():
    hw = probe_local_gpu_hardware()
    print("Local Hardware Probe:")
    print("  GPU:", hw.get("gpu_name"))
    print("  VRAM:", hw.get("vram_gb"), "GB")
    print("  Source:", hw.get("source"))
    assert hw.get("vram_gb") > 0, "Expected non-zero VRAM"
    print("test_local_hardware_probe passed!")

def test_tier_resolution():
    # 1. Local default (RTX 3050 + 8b model)
    tier_lite = probe_active_compute_tier(model_name="dolphin3:latest")
    print("\nLite Tier Resolution:")
    print("  Tier:", tier_lite["tier"])
    print("  Max Milestones:", tier_lite["max_milestones"])
    print("  Max Steps:", tier_lite["max_steps"])
    assert tier_lite["tier"] == ExecutionTier.LITE_EDGE
    assert tier_lite["max_milestones"] == 4
    assert tier_lite["max_steps"] == 14
    assert tier_lite["context_window"] == 8192
    assert len(tier_lite["viewports"]) == 1

    # 2. 32B Cloud model resolution
    tier_cloud = probe_active_compute_tier(model_name="qwen2.5-coder:32b")
    print("\nCloud Balanced Tier Resolution:")
    print("  Tier:", tier_cloud["tier"])
    print("  Max Milestones:", tier_cloud["max_milestones"])
    print("  Max Steps:", tier_cloud["max_steps"])
    assert tier_cloud["tier"] == ExecutionTier.CLOUD_BALANCED
    assert tier_cloud["max_milestones"] == 6
    assert tier_cloud["max_steps"] == 24
    assert tier_cloud["context_window"] == 32768
    assert len(tier_cloud["viewports"]) == 2

    # 3. Vision / Frontier model resolution
    tier_ultra = probe_active_compute_tier(model_name="llava:13b")
    print("\nFrontier Ultra Tier Resolution:")
    print("  Tier:", tier_ultra["tier"])
    print("  Max Milestones:", tier_ultra["max_milestones"])
    print("  Visual Mode:", tier_ultra["visual_mode"])
    assert tier_ultra["tier"] == ExecutionTier.FRONTIER_ULTRA
    assert tier_ultra["max_milestones"] == 8
    assert tier_ultra["max_steps"] == 36
    assert tier_ultra["context_window"] == 65536
    assert len(tier_ultra["viewports"]) == 3

    print("test_tier_resolution passed!")

def test_adaptive_goal_stepper_scaling():
    prompt = "Build a pomodoro timer with sound effects, task queue, search filtering, and shopping store"
    
    # Lite Tier (cap at 4)
    goals_lite = decompose_goals(prompt, max_milestones=4)
    print(f"\nDecomposed Goals (Lite Tier - Max 4): {len(goals_lite)} milestones")
    for g in goals_lite:
        print(f"  - {g['name']}")
    assert len(goals_lite) == 4

    # Balanced Tier (cap at 6)
    goals_balanced = decompose_goals(prompt, max_milestones=6)
    print(f"\nDecomposed Goals (Balanced Tier - Max 6): {len(goals_balanced)} milestones")
    for g in goals_balanced:
        print(f"  - {g['name']}")
    assert len(goals_balanced) >= 5

    # Ultra Tier (scales up to 8)
    goals_ultra = decompose_goals(prompt, max_milestones=8)
    print(f"\nDecomposed Goals (Ultra Tier - Max 8): {len(goals_ultra)} milestones")
    for g in goals_ultra:
        print(f"  - {g['name']}")
    assert len(goals_ultra) >= 6
    print("test_adaptive_goal_stepper_scaling passed!")

def test_browser_gate_viewports():
    # Test browser runtime audit with responsive viewports
    dummy_dir = Path("backend/data/projects")
    res = audit_workspace_runtime(
        proj_dir=dummy_dir / "non_existent_test_proj",
        viewports=[
            {"name": "desktop", "width": 1280, "height": 800},
            {"name": "mobile", "width": 390, "height": 844}
        ]
    )
    assert "viewports_tested" in res
    print("\ntest_browser_gate_viewports passed!")

if __name__ == "__main__":
    test_local_hardware_probe()
    test_tier_resolution()
    test_adaptive_goal_stepper_scaling()
    test_browser_gate_viewports()
    print("\nALL ADAPTIVE TIER & RESPONSIVE VERIFICATION TESTS PASSED SUCCESSFULLY!")
