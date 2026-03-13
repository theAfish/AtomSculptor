from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.agents.invocation_context import InvocationContext
from typing import AsyncGenerator
from google.genai import types

from agent_team.agents.planner import planner



class Orchestrator(BaseAgent):

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Orchestrate between planner and modelling agents."""
        
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            current_stage = ctx.session.state.get('current_stage', 'planning')
            
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