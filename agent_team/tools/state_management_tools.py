# tools that the planner agent can use to manage state and coordinate sub-agents

from enum import Enum
from typing import Any, Union
from pydantic import BaseModel, field_validator, ValidationError, ValidationInfo

from google.adk.tools.tool_context import ToolContext


# Define allowed values for each state using Enums
class CurrentStage(str, Enum):
    """Allowed values for the 'current_stage' state."""
    PLANNING = "planning"
    MODELLING = "modelling"
    CHECKING = "checking"
    SEARCHING = "searching"
    BUILDING = "building"


class ToHuman(str, Enum):
    """Allowed values for the 'to_human' state."""
    TRUE = "true"
    FALSE = "false"

class NoteWritten(str, Enum):
    """Allowed values for the 'note_written' state."""
    TRUE = "true"
    FALSE = "false"


# State validation registry
STATE_VALIDATORS = {
    "current_stage": CurrentStage,
    "to_human": ToHuman,
    "note_written": NoteWritten,
}


class StateValidator(BaseModel):
    """Pydantic model for validating state changes."""
    state_name: str
    state_value: Any
    
    @field_validator('state_name')
    @classmethod
    def validate_state_name(cls, v: str) -> str:
        """Check if state name is registered."""
        if v not in STATE_VALIDATORS:
            allowed_states = ', '.join(STATE_VALIDATORS.keys())
            raise ValueError(
                f"Unknown state '{v}'. Allowed states: {allowed_states}"
            )
        return v
    
    @field_validator('state_value')
    @classmethod
    def validate_state_value(cls, v: Any, info: ValidationInfo) -> Any:
        """Check if state value is valid for the given state."""
        if 'state_name' not in info.data:
            return v
        
        state_name = info.data['state_name']
        allowed_enum = STATE_VALIDATORS.get(state_name)
        
        if allowed_enum:
            # Try to convert the value to the enum
            try:
                # Handle both string and enum values
                if isinstance(v, str):
                    allowed_enum(v)
                elif not isinstance(v, allowed_enum):
                    raise ValueError(f"Invalid type for state '{state_name}'")
            except ValueError:
                allowed_values = ', '.join([e.value for e in allowed_enum])
                raise ValueError(
                    f"Invalid value '{v}' for state '{state_name}'. "
                    f"Allowed values: {allowed_values}"
                )
        return v


def change_state(state_name: str, state_value: str, tool_context: ToolContext) -> dict:
    """
    Change the session state of the agent team.
    
    Args:
        state_name: Name of the state to change
        state_value: New value for the state
    
    Returns:
        Dictionary with success message or error
    """
    try:
        # Validate the state change
        StateValidator(state_name=state_name, state_value=state_value)
        
        # If validation passes, update the state
        tool_context.state[state_name] = state_value
        return {
            "message": f"State '{state_name}' changed to '{state_value}'."
        }
    
    except ValidationError as e:
        # Return validation errors in a readable format
        error_messages = []
        for error in e.errors():
            error_messages.append(error['msg'])
        return {
            "error": "State validation failed",
            "details": "; ".join(error_messages)
        }

