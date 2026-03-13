# planning with the todo flow
from typing import List
from agent_team.state import todo_flow
from agent_team.planning.task import Task, TaskStatus
from agent_team.planning.plan import Plan


def _regularize_dependencies(dependencies: dict) -> dict:
    # Tool-call arguments arrive as JSON, so dependency keys may be strings.
    # Normalize them into integer task IDs for internal use.
    if not dependencies:
        return {}
    regularized = {}
    for key, value in dependencies.items():
        try:
            int_key = int(key)
            int_values = [int(v) for v in value]
            regularized[int_key] = int_values
        except (ValueError, TypeError):
            continue
    return regularized

def reset_plan():
    """
    Reset the current plan and clear all tasks.
    """
    todo_flow.reset()
    return {
        "status": "success",
    }

def create_plan(
    tasks: List[str], 
    dependencies: dict = None
):
    """
    Create a new plan for execution.
    
    Args:
        tasks: List of task descriptions. Task IDs will be assigned sequentially starting from 1.
        dependencies: JSON object mapping task IDs to dependency lists.
            Example: {"2": [1, 3]} means task 2 can only be executed after task 1 and 3.
            Default dependency is sequential, where task n depends on task n-1.
    """
    
    try:
        dependencies = _regularize_dependencies(dependencies)
    except Exception as e:
        return {
            "error": f"Invalid dependencies format: {e}. Use a JSON object like {{\"2\": [1, 3]}}."
        }

    # create Task lists
    task_objects = []
    for i, desc in enumerate(tasks):
        task_id = i + 1  # Task IDs start from 1
        if dependencies:
            deps = dependencies.get(task_id, [])
        else:
            # Default sequential dependency: task n depends on task n-1
            deps = [task_id - 1] if task_id > 1 else []
        task_objects.append(Task(description=desc, id=task_id, dependencies=deps))

    plan = Plan(task_objects)
    todo_flow.set_plan(plan)

    return {
        "status": "success",
        "plan": todo_flow.summary(verbose=True)
    }

def revise_plan(
    add_tasks: List[str], 
    add_dependencies: dict = None, 
    deprecate_tasks: List[int] = None, 
    remove_dependencies: dict = None
):
    """
    Revise the existing plan.
    
    Args:
        add_tasks: List of new task descriptions to add. Task IDs will be assigned sequentially after existing tasks.
        add_dependencies: Optional JSON object mapping task IDs to dependency IDs to add.
            Example: {"2": [4, 5]} means task 2 should now also depend on tasks 4 and 5.
        deprecate_tasks: Optional list of task IDs to mark as deprecated (wrong or not needed anymore). 
                The dependencies of the deprecated tasks will also be removed from other tasks.
        remove_dependencies: Optional JSON object mapping task IDs to dependency IDs to remove.
            Example: {"3": [1, 2]} means task 3 should no longer depend on tasks 1 and 2.
    """

    try:
        add_dependencies = _regularize_dependencies(add_dependencies)
        remove_dependencies = _regularize_dependencies(remove_dependencies)
    except Exception as e:
        return {
            "error": f"Invalid dependencies format: {e}. Use JSON objects like {{\"2\": [4, 5]}}."
        }

    if todo_flow.plan is None:
        raise ValueError("No existing plan to revise. Please create a plan first.")

    # Create new Task objects for the new descriptions
    starting_id = len(todo_flow.plan.tasks) + 1
    new_tasks = []
    for i, desc in enumerate(add_tasks):
        task_id = starting_id + i
        deps = add_dependencies.get(task_id, []) if add_dependencies else []
        new_tasks.append(Task(description=desc, id=task_id, dependencies=deps))

    todo_flow.revise_plan(
        new_tasks=new_tasks,
        add_dependencies=add_dependencies,
        deprecate_tasks=deprecate_tasks,
        remove_dependencies=remove_dependencies
    )

    return {
        "status": "success",
        "new plan": todo_flow.summary(verbose=True)
    }

def get_plan_summary(verbose=True):
    """
    Get a summary of the current plan, including task statuses and dependencies.
    
    Args:
        verbose: If True, include unmet dependencies in the summary.
    """
    if todo_flow.plan is None:
        return {
            "plan": None
        }
    
    summary = todo_flow.summary(verbose=verbose)
    return {
        "plan": summary
    }

def start_task(task_id: int):
    """
    Mark a task as in progress if it's ready to be started (i.e., all dependencies are met).
    
    Args:
        task_id: ID of the task to start.
    """
    try:
        todo_flow.start_task(task_id)
        return {
            "message": f"Task {task_id} started."
        }
    except Exception as e:
        return {
            "error": str(e)
        }
    
def complete_task(task_id: int, result=None):
    """
    Mark a task as completed if it's currently in progress.
    
    Args:
        task_id: ID of the task to complete.
        result: Optional result or output from completing the task.
    """
    try:
        todo_flow.complete_task(task_id, result)
        return {
            "message": f"Task {task_id} completed."
        }
    except Exception as e:
        return {
            "error": str(e)
        }
    
def is_plan_finished():
    """
    Check if all tasks in the current plan are completed.
    """
    if todo_flow.plan is None:
        return {
            "message": "No plan exists."
        }
    
    finished = todo_flow.is_finished()
    return {
        "finished": finished
    }


if __name__ == "__main__":
    # Example usage
    descriptions = [
        "Task 1: Gather requirements",
        "Task 2: Design system architecture",
        "Task 3: Implement core modules"
    ]
    dependencies = {
        2: [1],  # Task 2 depends on Task 1
        3: [1, 2]  # Task 3 depends on Task 1 and Task 2
    }
    result = create_plan(descriptions, dependencies)
    print(result)

    # revise
    new_descriptions = [
        "Task 4: Write documentation",
        "Task 5: Set up CI/CD pipeline"
    ]
    add_deps = {
        4: [2,3],  # Task 4 depends on Task 3
        5: [4]   # Task 5 depends on Task 3
    }
    deprecate = [1]  # Deprecate Task 1
    result = revise_plan(
        add_tasks=new_descriptions,
        add_dependencies=add_deps,
        deprecate_tasks=deprecate
    )
    print(result)