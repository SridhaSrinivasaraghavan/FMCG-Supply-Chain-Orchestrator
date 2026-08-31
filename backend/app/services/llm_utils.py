"""
LLM Utilities — Retry with Exponential Backoff

Provides a robust wrapper around LLM invocations with:
- Automatic retry on transient failures (rate limits, timeouts, parse errors)
- Exponential backoff to avoid hammering APIs
- JSON extraction and cleanup from LLM responses
- Graceful fallback to None on final failure
"""
import json
import time
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Common markdown wrappers LLMs add around JSON
JSON_CLEANUP_PATTERNS = [
    ("```json", ""),
    ("```JSON", ""),
    ("```", ""),
    ("\\n", "\n"),
]


def clean_llm_json(raw_text: str) -> str:
    """
    Cleans common LLM artifacts from JSON responses:
    - Strips markdown code fences
    - Removes leading/trailing whitespace
    - Handles escaped newlines
    """
    text = raw_text.strip()
    for pattern, replacement in JSON_CLEANUP_PATTERNS:
        text = text.replace(pattern, replacement)
    text = text.strip()
    
    # Sometimes LLMs prefix with explanatory text before the JSON
    # Try to find the first { or [ and last } or ]
    json_start_obj = text.find("{")
    json_start_arr = text.find("[")
    
    if json_start_obj == -1 and json_start_arr == -1:
        return text  # No JSON found, return as-is
    
    if json_start_obj == -1:
        json_start = json_start_arr
    elif json_start_arr == -1:
        json_start = json_start_obj
    else:
        json_start = min(json_start_obj, json_start_arr)
    
    json_end_obj = text.rfind("}")
    json_end_arr = text.rfind("]")
    json_end = max(json_end_obj, json_end_arr)
    
    if json_end > json_start:
        text = text[json_start:json_end + 1]
    
    return text


def parse_llm_json(raw_text: str) -> Any:
    """
    Attempts to parse JSON from an LLM response, with cleanup.
    Raises ValueError if parsing fails after cleanup.
    """
    cleaned = clean_llm_json(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM JSON after cleanup: {e}\nCleaned text: {cleaned[:200]}...")


def invoke_llm_with_retry(
    llm,
    prompt_text: str,
    max_retries: int = 2,
    initial_backoff: float = 1.0,
    pipeline_run_id: str = "unknown",
    agent_name: str = "unknown",
) -> Optional[str]:
    """
    Invokes an LLM with retry logic and exponential backoff.
    
    Returns the raw content string on success, or None on final failure.
    Handles:
    - Rate limit errors (429)
    - Timeout errors
    - Connection errors
    - Generic exceptions
    
    Args:
        llm: The LangChain LLM instance
        prompt_text: The formatted prompt string
        max_retries: Maximum number of retry attempts (default 2, so 3 total attempts)
        initial_backoff: Initial backoff time in seconds
        pipeline_run_id: For logging correlation
        agent_name: For logging identification
    
    Returns:
        Raw content string from LLM, or None on failure
    """
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke(prompt_text)
            content = response.content if hasattr(response, 'content') else str(response)
            
            if not content or not content.strip():
                raise ValueError("LLM returned empty response")
            
            logger.info(
                f"[{agent_name}] LLM invocation successful on attempt {attempt + 1} "
                f"(pipeline: {pipeline_run_id})"
            )
            return content
            
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            
            # Check if it's a retryable error
            is_rate_limit = "429" in error_str or "rate" in error_str or "quota" in error_str
            is_timeout = "timeout" in error_str or "timed out" in error_str
            is_connection = "connection" in error_str or "connect" in error_str
            
            if attempt < max_retries and (is_rate_limit or is_timeout or is_connection):
                backoff = initial_backoff * (2 ** attempt)
                logger.warning(
                    f"[{agent_name}] LLM attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {backoff}s... (pipeline: {pipeline_run_id})"
                )
                time.sleep(backoff)
                continue
            elif attempt < max_retries:
                # Non-retryable error on non-final attempt — still try once more
                backoff = initial_backoff * (2 ** attempt)
                logger.warning(
                    f"[{agent_name}] LLM attempt {attempt + 1} failed with non-retryable error: {e}. "
                    f"Trying once more in {backoff}s... (pipeline: {pipeline_run_id})"
                )
                time.sleep(backoff)
                continue
            else:
                logger.error(
                    f"[{agent_name}] LLM invocation failed after {max_retries + 1} attempts. "
                    f"Last error: {e} (pipeline: {pipeline_run_id})"
                )
    
    return None
