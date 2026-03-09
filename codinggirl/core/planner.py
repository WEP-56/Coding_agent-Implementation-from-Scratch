from __future__ import annotations

from codinggirl.core.contracts import Plan, PlanStep, Task


def build_plan(task: Task) -> Plan:
    steps = [
        PlanStep(
            step_id="s1",
            title="Locate target context",
            description="Find target file and current text for modification.",
            expected_tools=["fs_read_file", "search_rg"],
            exit_criteria=["target located"],
        ),
        PlanStep(
            step_id="s2",
            title="Generate patch",
            description="Create minimal unified diff patch.",
            expected_tools=["patch_apply_unified_diff"],
            exit_criteria=["patch generated"],
        ),
        PlanStep(
            step_id="s3",
            title="Apply and verify",
            description="Apply patch then verify expected string change.",
            expected_tools=["patch_apply_unified_diff", "fs_read_file"],
            exit_criteria=["verification passed"],
        ),
    ]

    return Plan(
        task_id=task.task_id,
        assumptions=[
            "MVP planner expects a text-replacement style goal.",
            "Goal format: replace <old> with <new> in <file>.",
        ],
        steps=steps,
        exit_criteria=["target text replaced", "file readable", "no patch conflict"],
    )
