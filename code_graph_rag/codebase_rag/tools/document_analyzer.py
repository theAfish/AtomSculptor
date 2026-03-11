import mimetypes
import os
import shutil
import uuid
from pathlib import Path

from loguru import logger
from pydantic_ai import Agent, Tool
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from ..config import settings


class DocumentAnalyzer:
    """
    A tool to perform document analysis. Uses Gemini for multimodal inputs
    and DeepSeek/local for text-only analysis.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.mode = settings.LLM_PROVIDER
        self.client = None
        self.text_agent: Agent | None = None
        self.max_chars = 20000

        if self.mode == "gemini":
            from google import genai
            from google.genai import types as genai_types

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY is not set in the environment.")
            self.client = genai.Client(api_key=api_key)
            self._genai_types = genai_types
        elif self.mode == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY is not set in the environment.")
            model = OpenAIModel(
                settings.DEEPSEEK_MODEL_ID,
                provider=OpenAIProvider(
                    api_key=api_key,
                    base_url="https://api.deepseek.com/v1",
                ),
            )
            self.text_agent = Agent(model=model, system_prompt="You analyze documents.")
        else:  # local
            model = OpenAIModel(
                settings.LOCAL_ORCHESTRATOR_MODEL_ID,
                provider=OpenAIProvider(
                    api_key=settings.LOCAL_MODEL_API_KEY,
                    base_url=str(settings.LOCAL_MODEL_ENDPOINT),
                ),
            )
            self.text_agent = Agent(model=model, system_prompt="You analyze documents.")

        logger.info(f"DocumentAnalyzer initialized with root: {self.project_root}")

    def analyze(self, file_path: str, question: str) -> str:
        """
        Reads a document (e.g., PDF), sends it to the Gemini multimodal endpoint
        with a specific question, and returns the model's analysis.
        """
        logger.info(
            f"[DocumentAnalyzer] Analyzing '{file_path}' with question: '{question}'"
        )
        try:
            # Handle absolute paths by copying to .tmp folder
            if Path(file_path).is_absolute():
                source_path = Path(file_path)
                if not source_path.is_file():
                    return f"Error: File not found at '{file_path}'."

                # Create .tmp folder if it doesn't exist
                tmp_dir = self.project_root / ".tmp"
                tmp_dir.mkdir(exist_ok=True)

                # Copy file to .tmp with a unique filename to avoid collisions
                tmp_file = tmp_dir / f"{uuid.uuid4()}-{source_path.name}"
                shutil.copy2(source_path, tmp_file)
                full_path = tmp_file
                logger.info(f"Copied external file to: {full_path}")
            else:
                # Handle relative paths as before
                full_path = (self.project_root / file_path).resolve()
                full_path.relative_to(self.project_root)  # Security check

            if not full_path.is_file():
                return f"Error: File not found at '{file_path}'."

            # Determine mime type dynamically
            mime_type, _ = mimetypes.guess_type(full_path)
            if not mime_type:
                mime_type = (
                    "application/octet-stream"  # Default if type can't be guessed
                )

            # Prepare the multimodal prompt
            file_bytes = full_path.read_bytes()

            if self.mode == "gemini":
                # Use the simpler format that the library expects
                prompt_parts = [
                    self._genai_types.Part.from_bytes(
                        data=file_bytes, mime_type=mime_type
                    ),
                    (
                        "Based on the document provided, please answer the following "
                        f"question: {question}"
                    ),
                ]

                # Call the model and get the response
                response = self.client.models.generate_content(
                    model=settings.GEMINI_MODEL_ID, contents=prompt_parts
                )

                logger.success(f"Successfully received analysis for '{file_path}'.")

                # Check if response has text content
                if hasattr(response, "text") and response.text:
                    return str(response.text)
                elif hasattr(response, "candidates") and response.candidates:
                    # Try to get text from candidates
                    for candidate in response.candidates:
                        if hasattr(candidate, "content") and candidate.content:
                            parts = candidate.content.parts
                            if parts and hasattr(parts[0], "text"):
                                return str(parts[0].text)
                    return "No valid text found in response candidates."
                else:
                    logger.warning(f"No text found in response: {response}")
                    return "No text content received from the API."

            # DeepSeek/local: text-only analysis
            text_like = mime_type.startswith("text/") or full_path.suffix.lower() in {
                ".txt",
                ".md",
                ".rst",
                ".py",
                ".json",
                ".toml",
                ".yaml",
                ".yml",
                ".ini",
                ".cfg",
                ".csv",
            }
            if not text_like:
                return (
                    "Error: This document type requires Gemini multimodal support. "
                    "Please use a text file or switch to LLM_PROVIDER=gemini."
                )

            content = full_path.read_text(encoding="utf-8", errors="ignore")
            if len(content) > self.max_chars:
                content = content[: self.max_chars]
            prompt = (
                "You are given a document and a question. "
                "Answer the question using the document content.\n\n"
                f"Question: {question}\n\n"
                f"Document ({full_path.name}):\n{content}"
            )
            if not self.text_agent:
                return "Error: Text analysis agent is not initialized."
            result = self.text_agent.run_sync(prompt)
            logger.success(f"Successfully received analysis for '{file_path}'.")
            return str(result.output)

        except ValueError as e:
            # Check if this is a security-related ValueError (from relative_to)
            if "does not start with" in str(e):
                err_msg = f"Security risk: Attempted to access file outside of project root: {file_path}"
                logger.error(err_msg)
                return f"Error: {err_msg}"
            else:
                # API-related ValueError
                logger.error(f"[DocumentAnalyzer] API validation error: {e}")
                return f"Error: API validation failed: {e}"
        except Exception as e:
            logger.error(
                f"Failed to analyze document '{file_path}': {e}", exc_info=True
            )
            return f"An error occurred during analysis: {e}"


def create_document_analyzer_tool(analyzer: DocumentAnalyzer) -> Tool:
    """Factory function to create the document analyzer tool."""

    def analyze_document(file_path: str, question: str) -> str:
        """
        Analyzes a document (like a PDF) to answer a specific question about its content.
        Use this tool when a user asks a question that requires understanding the content of a non-source-code file.

        Args:
            file_path: The path to the document file (e.g., 'path/to/book.pdf').
            question: The specific question to ask about the document's content.
        """
        try:
            result = analyzer.analyze(file_path, question)
            logger.debug(
                f"[analyze_document] Result type: {type(result)}, content: {result[:100] if result else 'None'}..."
            )
            return result
        except Exception as e:
            logger.error(
                f"[analyze_document] Exception during analysis: {e}", exc_info=True
            )
            return f"Error during document analysis: {e}"

    return Tool(
        function=analyze_document,
        name="analyze_document",
        description="Analyzes documents (PDFs, images) to answer questions about their content.",
    )
