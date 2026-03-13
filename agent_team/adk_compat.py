import ast
import json
import logging
import re
from typing import Any

import yaml


logger = logging.getLogger(__name__)

_PATCHED = False


def _quote_bare_object_keys(raw_args: str) -> str:
    pattern = re.compile(r'([\{,]\s*)([A-Za-z_][A-Za-z0-9_\-]*|\d+)(\s*:)')
    return pattern.sub(lambda match: f'{match.group(1)}"{match.group(2)}"{match.group(3)}', raw_args)


def _parse_tool_arguments(raw_args: str | None) -> Any:
    if not raw_args:
        return {}

    candidates = [raw_args]
    quoted_keys = _quote_bare_object_keys(raw_args)
    if quoted_keys != raw_args:
        candidates.append(quoted_keys)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    for candidate in candidates:
        try:
            parsed = yaml.safe_load(candidate)
        except yaml.YAMLError:
            continue
        if parsed is not None:
            return parsed

    python_literal_candidate = raw_args.replace("null", "None")
    python_literal_candidate = re.sub(r"\btrue\b", "True", python_literal_candidate)
    python_literal_candidate = re.sub(r"\bfalse\b", "False", python_literal_candidate)
    python_literal_candidate = _quote_bare_object_keys(python_literal_candidate)
    try:
        return ast.literal_eval(python_literal_candidate)
    except (SyntaxError, ValueError) as exc:
        raise json.JSONDecodeError(str(exc), raw_args, 0) from exc


def patch_litellm_tool_argument_parsing() -> None:
    global _PATCHED
    if _PATCHED:
        return

    from google.adk.models import lite_llm

    def _patched_message_to_generate_content_response(
        message,
        is_partial: bool = False,
        model_version: str | None = None,
        thought_parts=None,
    ):
        lite_llm._ensure_litellm_imported()

        parts = []
        if not thought_parts:
            thought_parts = lite_llm._convert_reasoning_value_to_parts(
                lite_llm._extract_reasoning_value(message)
            )
        if thought_parts:
            parts.extend(thought_parts)

        message_content, tool_calls = lite_llm._split_message_content_and_tool_calls(
            message
        )
        if isinstance(message_content, str) and message_content:
            parts.append(lite_llm.types.Part.from_text(text=message_content))

        if tool_calls:
            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    tool_type = tool_call.get("type")
                    tool_function = tool_call.get("function") or {}
                    tool_id = tool_call.get("id")
                    tool_name = tool_function.get("name")
                    raw_args = tool_function.get("arguments") or "{}"
                else:
                    tool_type = tool_call.type
                    tool_function = tool_call.function
                    tool_id = tool_call.id
                    tool_name = tool_function.name
                    raw_args = tool_function.arguments or "{}"

                if tool_type != "function":
                    continue

                try:
                    parsed_args = _parse_tool_arguments(raw_args)
                except json.JSONDecodeError:
                    logger.exception(
                        "Failed to parse tool arguments for %s: %r",
                        tool_name,
                        raw_args,
                    )
                    raise

                part = lite_llm.types.Part.from_function_call(
                    name=tool_name,
                    args=parsed_args,
                )
                part.function_call.id = tool_id
                parts.append(part)

        return lite_llm.LlmResponse(
            content=lite_llm.types.Content(role="model", parts=parts),
            partial=is_partial,
            model_version=model_version,
        )

    lite_llm._message_to_generate_content_response = _patched_message_to_generate_content_response
    _PATCHED = True
