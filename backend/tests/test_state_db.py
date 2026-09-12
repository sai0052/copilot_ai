from app.agent.state import AgentState
from app.api.events import clear_cancel, is_cancelled, request_cancel
from app.database.database import Base, SessionLocal, engine
from app.database.repository import ProjectRepository, TaskRepository


def setup_module(_module) -> None:
    Base.metadata.create_all(bind=engine)


def test_cancel_flag():
    request_cancel(99)
    assert is_cancelled(99)
    clear_cancel(99)
    assert not is_cancelled(99)


def test_agent_state_roundtrip():
    state = AgentState(task="Add health", files_modified=["app.py"], iteration=2)
    data = state.model_dump()
    restored = AgentState.model_validate(data)
    assert restored.iteration == 2
    assert restored.files_modified == ["app.py"]


def test_project_and_task_persistence():
    db = SessionLocal()
    try:
        project = ProjectRepository(db).create("demo", "C:/tmp/demo", "fastapi")
        task = TaskRepository(db).create(project.id, "Add health", "implement", 3)
        TaskRepository(db).add_event(task.id, "agent_started", "started", {"ok": True})
        events = TaskRepository(db).events(task.id)
        assert task.id
        assert events[0].event_type == "agent_started"
        found = ProjectRepository(db).get(project.id)
        assert found is not None
        assert found.name == "demo"
    finally:
        db.close()
