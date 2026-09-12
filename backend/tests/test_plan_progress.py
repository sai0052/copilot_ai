from __future__ import annotations

from app.agent.plan_progress import COMPLETED, FAILED, PENDING, RUNNING, SKIPPED, CANCELLED, PlanTracker
from app.agent.state import AgentState
from app.schemas.agent import PlanStep


def _tracker() -> PlanTracker:
    tracker = PlanTracker()
    tracker.load(
        [
            PlanStep(index=1, title="Inspect repository", detail="Identify relevant files"),
            PlanStep(index=2, title="Fix implementation", detail="Correct apply_discount"),
            PlanStep(index=3, title="Add/update tests", detail="Cover 0/10/50/100"),
            PlanStep(index=4, title="Run test suite", detail="pytest"),
            PlanStep(index=5, title="Commit changes", detail="Commit modified files"),
        ]
    )
    return tracker


def test_plan_starts_pending():
    tracker = _tracker()
    assert [step.status for step in tracker.steps] == [PENDING] * 5


def test_step_changes_to_running_and_completed():
    tracker = _tracker()
    state = AgentState(task="fix", files_modified=["app/cart.py"])
    ready = tracker.on_plan_ready(scan_already_done=True, mode="implement")
    assert any(change.status == COMPLETED and change.step_id == 1 for change in ready)
    assert any(change.status == RUNNING and change.step_id == 2 for change in ready)
    assert tracker.steps[0].status == COMPLETED
    assert tracker.steps[1].status == RUNNING
    tracker.apply("file_modified", state, {"path": "app/cart.py"})
    tracker.apply("test_started", state)
    assert tracker.steps[1].status == COMPLETED
    assert tracker.steps[2].status == COMPLETED
    assert tracker.steps[3].status == RUNNING


def test_test_success_completes_test_step():
    tracker = _tracker()
    state = AgentState(task="fix", files_modified=["app/cart.py"])
    tracker.on_plan_ready(scan_already_done=True, mode="implement")
    tracker.apply("test_started", state)
    tracker.apply("test_completed", state, {"exit_code": 0, "passed": 4, "failed": 0})
    assert tracker.steps[3].status == COMPLETED
    assert FAILED not in {step.status for step in tracker.steps}


def test_failed_step_and_preserves_failure():
    tracker = _tracker()
    state = AgentState(task="fix", files_modified=["app/cart.py"])
    tracker.on_plan_ready(scan_already_done=True, mode="implement")
    tracker.apply("test_started", state)
    tracker.apply("test_completed", state, {"exit_code": 1, "failed": 1})
    tracker.finalize("FAILED", state)
    assert FAILED in {step.status for step in tracker.steps}
    assert tracker.steps[3].status == FAILED


def test_skipped_commit_on_success():
    tracker = _tracker()
    state = AgentState(
        task="fix",
        files_modified=["app/cart.py"],
        test_results=[{"exit_code": 0, "passed": 4, "failed": 0}],
        status="success",
    )
    tracker.on_plan_ready(scan_already_done=True, mode="implement")
    tracker.apply("file_modified", state, {"path": "app/cart.py"})
    tracker.apply("test_started", state)
    tracker.apply("test_completed", state, {"exit_code": 0})
    tracker.finalize("SUCCESS", state)
    statuses = {step.title: step.status for step in tracker.steps}
    assert statuses["Inspect repository"] == COMPLETED
    assert statuses["Fix implementation"] == COMPLETED
    assert statuses["Add/update tests"] == COMPLETED
    assert statuses["Run test suite"] == COMPLETED
    assert statuses["Commit changes"] == SKIPPED
    assert tracker.steps[4].detail == "SKIPPED — Optional commit not requested"
    assert PENDING not in statuses.values()


def test_cancelled_does_not_complete_unfinished():
    tracker = _tracker()
    state = AgentState(task="fix")
    tracker.on_plan_ready(scan_already_done=True, mode="implement")
    tracker.finalize("CANCELLED", state)
    assert tracker.steps[1].status == CANCELLED
    assert tracker.steps[4].status == SKIPPED
    assert COMPLETED not in {tracker.steps[2].status, tracker.steps[3].status, tracker.steps[4].status}


def test_timeout_does_not_complete_unfinished():
    tracker = _tracker()
    state = AgentState(task="fix")
    tracker.on_plan_ready(scan_already_done=True, mode="implement")
    tracker.finalize("TIMEOUT", state)
    assert tracker.steps[1].status == FAILED
    assert tracker.steps[3].status == PENDING
    assert tracker.steps[4].status == PENDING


def test_limit_reached_does_not_complete_unfinished():
    tracker = _tracker()
    state = AgentState(task="fix", stop_reason="tool_round_limit")
    tracker.on_plan_ready(scan_already_done=True, mode="implement")
    tracker.finalize("LIMIT_REACHED", state)
    assert tracker.steps[1].status == FAILED
    assert PENDING in {step.status for step in tracker.steps}
    assert tracker.steps[4].status != COMPLETED
