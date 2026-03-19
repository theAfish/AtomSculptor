from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

from agent_team.agents.planner import planner

logger = logging.getLogger(__name__)

# Notes directory relative to this file: ../../memories/notes
_NOTES_DIR = Path(__file__).parent.parent / "memories" / "notes"

# Maximum number of notes before auto-aggregation is triggered
MAX_NUM_NOTES = 10

# Module-level handle for the background aggregator task (one at a time)
_aggregator_task: asyncio.Task | None = None

_aggregator_status = {
    "running": False,
    "note_count": 0,
    "threshold": MAX_NUM_NOTES,
    "message": "Idle",
    "last_started_at": None,
    "last_completed_at": None,
    "last_error": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_aggregator_status(**updates) -> None:
    _aggregator_status.update(updates)


def get_aggregator_status() -> dict:
    return dict(_aggregator_status)


async def _run_aggregator_bg() -> None:
    """Run the aggregator agent autonomously in the background."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from agent_team.agents.aggregator import aggregator

    _set_aggregator_status(
        running=True,
        message="Aggregating notes into instructions...",
        last_started_at=_now_iso(),
        last_error=None,
    )
    logger.info("Auto-aggregation triggered: running aggregator in background.")
    try:
        session_service = InMemorySessionService()
        agg_runner = Runner(
            agent=aggregator,
            app_name="aggregator_bg",
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="aggregator_bg", user_id="system"
        )
        trigger_message = types.Content(
            role="user",
            parts=[types.Part(text=(
                "Please read all current notes, aggregate them into reusable "
                "task-specific instructions, and update the instruction files."
            ))],
        )
        async for _ in agg_runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=trigger_message,
        ):
            pass  # consume events; no human output needed
        _set_aggregator_status(
            running=False,
            message="Aggregation complete.",
            last_completed_at=_now_iso(),
            last_error=None,
        )
        logger.info("Auto-aggregation completed.")
    except Exception as exc:
        _set_aggregator_status(
            running=False,
            message="Aggregation failed.",
            last_completed_at=_now_iso(),
            last_error=str(exc),
        )
        logger.exception("Auto-aggregation failed.")


class Orchestrator(BaseAgent):

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Orchestrate between planner and modelling agents."""
        global _aggregator_task

        # Auto-aggregate notes in the background if the note count exceeds the limit.
        note_count = len(list(_NOTES_DIR.glob("*.md"))) if _NOTES_DIR.exists() else 0
        _set_aggregator_status(note_count=note_count, threshold=MAX_NUM_NOTES)
        if note_count >= MAX_NUM_NOTES and (
            _aggregator_task is None or _aggregator_task.done()
        ):
            _aggregator_task = asyncio.create_task(_run_aggregator_bg())

        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            current_stage = ctx.session.state.get('current_stage', 'planning')
            ctx.session.state['note_written'] = 'false'
            
            if current_stage == 'planning':
                # Remember the stage before calling planner
                stage_before = current_stage
                
                # Planner discusses with human, gets requirements, and sets goals
                async for event in planner.run_async(ctx):
                    yield event
                
                # Check what the planner decided
                stage_after = ctx.session.state.get('current_stage', 'planning')
                to_human = ctx.session.state.get('to_human', 'false')
                
                # If planner explicitly set to_human=true, return to human
                if to_human == 'true':
                    return
                
                # If planner didn't change stage, it means there's no work to do
                # Default behavior: return to human
                if stage_before == stage_after:
                    return
                
            elif current_stage == 'modelling':
                # Planner executes modelling work by calling its sub-agents as needed
                async for event in planner.run_async(ctx):
                    yield event
                
                # After planner's modelling work, check if done or need to continue
                to_human = ctx.session.state.get('to_human', 'false')
                if to_human == 'true':
                    note_written = ctx.session.state.get('note_written', 'false')
                    if note_written == 'false':
                        # If not already written tools, ask planner once whether it wants to write notes for future agents
                        system_event = Event(
                            author="system",
                            invocation_id=ctx.invocation_id,
                            content=types.Content(
                                parts=[types.Part(text="Do you want to write notes for future agents based on what you learned during this modelling phase?")],
                            )
                        )
                        yield system_event
                        async for event in planner.run_async(ctx):
                            yield event
                    return
                
                # Otherwise, start a new planning cycle
                ctx.session.state['current_stage'] = 'planning'
            
            iteration += 1
        
        # Fallback: max iterations reached, let planner provide status
        async for event in planner.run_async(ctx):
            yield event




atom_sculptor = Orchestrator(
    name="atom_sculptor",
    sub_agents=[planner],
)