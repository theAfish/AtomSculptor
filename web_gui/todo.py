"""Todo-flow DAG serialisation."""

from agent_team.state import todo_flow


def serialize_todo_flow() -> dict:
    if todo_flow.plan is None:
        return {"tasks": [], "finished": True}
    tasks = []
    for t in todo_flow.plan.tasks:
        tasks.append({
            "id": t.id,
            "uuid": t.uuid,
            "description": t.description,
            "status": t.status.value,
            "dependencies": t.dependencies,
            "result": t.result,
        })
    return {"tasks": tasks, "finished": todo_flow.is_finished()}
