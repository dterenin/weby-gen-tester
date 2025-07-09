import os
import aiohttp
import json
from opentelemetry import trace # For trace.get_current_span() and trace.Status
from src.tracing import (
    get_opentelemetry_tracer,
    set_llm_input_output,
    OTEL_SPAN_TYPE_LLM,
    OPENINFERENCE_SPAN_KIND,
    LLM_MODEL_NAME, # Not explicitly used in this file directly, but part of semantic conventions
    LLM_INPUT_VALUE, # Not explicitly used in this file directly, but part of semantic conventions
    LLM_OUTPUT_VALUE, # Not explicitly used in this file directly, but part of semantic conventions
    LLM_INVOCATION_PARAMETERS
)
import logging # Import logging

# Configure logger for this module
# When this file is run as a script, __name__ is "__main__".
# When imported, __name__ is the module name (e.g., "weby_client" if file is weby_client.py).
logger = logging.getLogger(__name__)

# Option to enable full debug logging of chunks
# Can be set via environment variable
ENABLE_FULL_CHUNK_LOGGING = os.getenv("ENABLE_FULL_CHUNK_LOGGING", "false").lower() == "true"

# If full logging is enabled, set logging level to DEBUG for this module's logger
if ENABLE_FULL_CHUNK_LOGGING:
    logger.setLevel(logging.ERROR)  # Это должно быть DEBUG!
    logger.info("Full chunk logging enabled - DEBUG level set for this logger.")
else:
    # Set a default level for this logger if not already set (e.g., by parent or environment)
    # and not already set to DEBUG by the above condition.
    if not logger.level or logger.level == logging.NOTSET or logger.level > logging.INFO:
        logger.setLevel(logging.INFO)


tracer = get_opentelemetry_tracer(__name__)

# Use specific URLs from .env, with fallbacks if not defined
WEBY_API_URL = os.getenv("WEBY_API_URL", "http://localhost:8000/v1/weby")
WEBY_ENHANCE_API_URL = os.getenv("WEBY_ENHANCE_API_URL", "http://localhost:8000/prompt-enhance")

# Get timeout from environment variable if set
DEFAULT_TIMEOUT = 420  # Default value (7 minutes) - original comment said "10 minutes"
try:
    # Ensure default value for getenv is a string for int conversion
    CLIENT_TIMEOUT = int(os.getenv("WEBY_CLIENT_TIMEOUT", str(DEFAULT_TIMEOUT)))
except ValueError:
    logger.warning(f"Invalid WEBY_CLIENT_TIMEOUT value, using default: {DEFAULT_TIMEOUT} seconds")
    CLIENT_TIMEOUT = DEFAULT_TIMEOUT

logger.info(f"Weby client using timeout: {CLIENT_TIMEOUT} seconds")

@tracer.start_as_current_span("call_weby_v1_generate")
async def call_weby_v1_generate(question: str, framework: str = "Nextjs", temperature: float = 0.6, top_p: float = 0.95, files: list = None, model: str = None):
    """
    Calls the /v1/weby endpoint to generate code.
    Handles streaming response and concatenates chunks.
    """
    # Set default values if None
    if files is None:
        files = []

    url = WEBY_API_URL
    payload = {
        "messages": [
            {
                "role": "user",
                "content": question
            }
        ],
        "project_files": files,
        "temperature": temperature,
        "top_p": top_p,
        "framework": framework,
        # "nextjs_system_prompt": NEXTJS_SYSTEM_PROMPT
    }
    
    # Only include model in payload if it's explicitly provided
    if model is not None:
        payload["model"] = model

    span = trace.get_current_span()
    span.set_attribute(OPENINFERENCE_SPAN_KIND, OTEL_SPAN_TYPE_LLM)

    # HTTP-specific attributes
    span.set_attribute("http.method", "POST")
    span.set_attribute("http.url", url)

    # LLM-specific attributes using the helper
    # "weby/v1/generate" is a logical name for the operation using the LLM
    set_llm_input_output(
        span,
        input_text=question,
        model_name="weby/v1/generate", # Logical operation name
        temperature=temperature,
        top_p=top_p
    )
    # Store actual model and other invocation parameters
    invocation_params = {"model": model, "framework": framework, "has_files": bool(files)}
    span.set_attribute(LLM_INVOCATION_PARAMETERS, json.dumps(invocation_params))


    final_generated_code_parts = []

    # Define a timeout object using the CLIENT_TIMEOUT constant
    connect_timeout_ratio = 0.1 # 10% for connection
    sock_read_timeout_ratio = 0.9 # 90% for socket read

    connect_timeout = int(CLIENT_TIMEOUT * connect_timeout_ratio)
    sock_read_timeout = int(CLIENT_TIMEOUT * sock_read_timeout_ratio)

    # Ensure timeouts are at least 1 second if CLIENT_TIMEOUT is very small, or if ratios result in <1s
    connect_timeout = max(1, connect_timeout)
    sock_read_timeout = max(1, sock_read_timeout)
    # Ensure total timeout is not less than the sum of potentially adjusted connect/sock_read timeouts
    # or the original CLIENT_TIMEOUT, whichever is greater.
    actual_total_timeout = max(CLIENT_TIMEOUT, connect_timeout + sock_read_timeout)

    timeout = aiohttp.ClientTimeout(
        total=actual_total_timeout,
        connect=connect_timeout,
        sock_read=sock_read_timeout
    )
    logger.debug(f"Using timeout for generation: total={actual_total_timeout}s, connect={connect_timeout}s, sock_read={sock_read_timeout}s")

    async with aiohttp.ClientSession(timeout=timeout) as session:
        response_status = None
        raw_body_on_error = ""
        processed_chunks_count = 0
        stream_finish_reason = None
        full_code = "" # Initialize full_code here

        try:
            async with session.post(url, json=payload) as response:
                response_status = response.status
                span.set_attribute("http.status_code", response_status)

                if response_status >= 400:
                    raw_body_on_error = await response.text()
                    span.set_attribute("http.response.body", raw_body_on_error)
                    response.raise_for_status() # Raise HTTPError for 4xx/5xx

                # Stream processing block
                try:
                    async for line in response.content:
                        if line:
                            decoded_line = ""
                            data_part = ""
                            try:
                                decoded_line = line.decode('utf-8').strip()
                                if not decoded_line:
                                    continue

                                if decoded_line.startswith('data:'):
                                    data_part = decoded_line[5:].strip()

                                    if data_part == "[DONE]": # Common SSE stream termination signal
                                        logger.info("SSE stream indicated [DONE].")
                                        if not stream_finish_reason: # If not already set by a chunk
                                            stream_finish_reason = "done_marker"
                                        break # Exit the loop

                                    if data_part:
                                        logger.debug(f"Processing chunk: {data_part[:100]}...")
                                        if ENABLE_FULL_CHUNK_LOGGING:
                                            logger.debug(f"FULL CHUNK: {data_part}")

                                        parsed_chunk = json.loads(data_part)
                                        content_found_in_chunk = False

                                        # New structure: data.choices[0].delta.content or data.choices[0].message.content
                                        if ('data' in parsed_chunk and
                                            'choices' in parsed_chunk['data'] and
                                            parsed_chunk['data']['choices'] is not None and
                                            isinstance(parsed_chunk['data']['choices'], list) and
                                            len(parsed_chunk['data']['choices']) > 0):

                                            choice = parsed_chunk['data']['choices'][0]
                                            # Check delta.content
                                            if 'delta' in choice and isinstance(choice['delta'], dict) and \
                                               'content' in choice['delta'] and choice['delta']['content'] is not None:
                                                delta_content = choice['delta']['content']
                                                final_generated_code_parts.append(str(delta_content)) # Ensure string
                                                logger.debug(f"Found content in data.choices[0].delta.content: '{str(delta_content)[:20]}...'")
                                                content_found_in_chunk = True
                                            # Check message.content (often for full message in a chunk)
                                            elif 'message' in choice and isinstance(choice['message'], dict) and \
                                                 'content' in choice['message'] and choice['message']['content'] is not None:
                                                message_content = choice['message']['content']
                                                final_generated_code_parts.append(str(message_content)) # Ensure string
                                                logger.debug(f"Found content in data.choices[0].message.content: '{str(message_content)[:20]}...'")
                                                content_found_in_chunk = True
                                            # Check direct content in choice
                                            elif 'content' in choice and choice['content'] is not None:
                                                direct_content = choice['content']
                                                final_generated_code_parts.append(str(direct_content))
                                                logger.debug(f"Found content directly in choice.content: '{str(direct_content)[:20]}...'")
                                                content_found_in_chunk = True


                                            if 'finish_reason' in choice and choice['finish_reason']:
                                                stream_finish_reason = choice['finish_reason']
                                                logger.info(f"SSE stream indicates finish reason in choice: {stream_finish_reason}")

                                        # Top-level 'text' field
                                        elif 'text' in parsed_chunk and parsed_chunk['text'] is not None:
                                            text_content = parsed_chunk['text']
                                            final_generated_code_parts.append(str(text_content)) # Ensure string
                                            logger.debug(f"Found content in top-level 'text' field: '{str(text_content)[:20]}...'")
                                            content_found_in_chunk = True

                                        # Old structure: top-level delta.content
                                        elif 'delta' in parsed_chunk and isinstance(parsed_chunk['delta'], dict) and \
                                             'content' in parsed_chunk['delta'] and parsed_chunk['delta']['content'] is not None:
                                            delta_content = parsed_chunk['delta']['content']
                                            final_generated_code_parts.append(str(delta_content)) # Ensure string
                                            logger.debug(f"Found content in old delta structure (top-level delta.content): '{str(delta_content)[:20]}...'")
                                            content_found_in_chunk = True
                                            # Check for finish reason in old structure (top-level)
                                            if 'finish_reason' in parsed_chunk and parsed_chunk['finish_reason'] and not stream_finish_reason:
                                                stream_finish_reason = parsed_chunk['finish_reason']
                                                logger.info(f"SSE stream indicates finish_reason (old top-level): {stream_finish_reason}")

                                        # Top-level 'finish_reason' if not already found
                                        if 'finish_reason' in parsed_chunk and parsed_chunk['finish_reason'] and not stream_finish_reason:
                                            stream_finish_reason = parsed_chunk['finish_reason']
                                            logger.info(f"SSE stream indicates finish reason (top-level): {stream_finish_reason}")

                                        if not content_found_in_chunk and not stream_finish_reason:
                                            logger.debug(f"No known content field or finish_reason in chunk: {json.dumps(parsed_chunk)[:300]}")

                                        processed_chunks_count += 1
                            except json.JSONDecodeError as jde:
                                logger.warning(f"Error decoding JSON from chunk: {jde}. Chunk data: '{data_part[:200]}'")
                                continue # Skip this malformed chunk
                            except UnicodeDecodeError as ude:
                                logger.warning(f"Unicode decode error in SSE stream line. Error: {ude}. Line (raw): {line[:200]}")
                                continue
                            except Exception as chunk_proc_e: # Catch other errors during individual chunk processing
                                logger.error(f"Error processing individual chunk data: {chunk_proc_e}", exc_info=True)
                                logger.debug(f"Problematic chunk content (data_part if available): {data_part[:200] if data_part else decoded_line[:200]}")
                                continue
                # End of async for loop for response.content

                except aiohttp.ClientPayloadError as stream_cpe:
                    # This error means the stream was terminated prematurely or had other payload issues.
                    logger.warning(f"Stream interrupted by ClientPayloadError: {stream_cpe}. Processing partial data if any.")
                    # Partial data collected so far in final_generated_code_parts will be processed below.
                    # This exception will be effectively re-raised or lead to returning partial data via the outer handler.
                    pass # Allow flow to process accumulated parts. The outer ClientPayloadError handler will manage the final return.
                except Exception as stream_e:
                    # Generic error during the stream iteration process.
                    logger.error(f"Error during SSE stream processing loop: {stream_e}", exc_info=True)
                    # Similar to ClientPayloadError, process what we have accumulated.
                    pass # Allow flow to process accumulated parts. The outer generic Exception handler will manage.


                # After the loop (or if loop was interrupted by a handled stream error)
                full_code = ''.join(final_generated_code_parts)
                logger.info(f"Final code length after processing {processed_chunks_count} chunks: {len(full_code)} characters.")

                if len(full_code) > 0:
                    start_content_preview = full_code[:200]
                    end_content_preview = full_code[-200:] if len(full_code) > 400 else "" # Show end only if substantially long
                    logger.info(f"Code preview - START: {start_content_preview}{'...' if len(full_code) > 200 else ''}")
                    if end_content_preview:
                         logger.info(f"Code preview - END: ...{end_content_preview}")
                elif processed_chunks_count > 0:
                    logger.warning("Chunks were processed, but no actual code content was extracted.")
                else: # No chunks processed at all or no content in processed chunks
                    logger.warning("No code was generated (no chunks processed or no content found).")

                # Update span with the final output
                set_llm_input_output(
                    span,
                    input_text=question, # Input text is already set, but can be repeated for clarity or if helper expects it
                    output_text=full_code or "No code generated", # Use a placeholder if empty
                    model_name="weby/v1/generate" # Re-affirm logical model name
                )

                # Decide on success or failure based on content/chunks
                if full_code or (processed_chunks_count > 0 and stream_finish_reason): # Success if we got code, or if chunks were processed and stream finished
                    logger.info(f"Successfully processed {processed_chunks_count} chunks from {url}. Finish reason: {stream_finish_reason if stream_finish_reason else 'N/A'}.")
                    span.set_status(trace.StatusCode.OK)
                    return {
                        "code": full_code,
                        "output": full_code,  # For consistency
                        "status_code": response_status,
                        "chunks_count": processed_chunks_count,
                        "finish_reason": stream_finish_reason,
                        "raw_response": f"Stream processed. Chunks: {processed_chunks_count}. Finish: {stream_finish_reason}"
                    }
                else: # Stream might have ended cleanly (HTTP 200) but no meaningful data extracted
                    error_message = "No valid content extracted from SSE stream, though stream may have completed."
                    if processed_chunks_count == 0 and not stream_finish_reason:
                        error_message = "No chunks processed from SSE stream."

                    logger.error(f"{error_message} for question: '{question[:30]}...'")
                    span.set_status(trace.StatusCode.ERROR, error_message)
                    return {
                        "error": error_message,
                        "partial_code": full_code if full_code else None, # full_code would be empty here
                        "output": "",
                        "status_code": response_status, # Likely 200 if no HTTP error occurred
                        "raw_response": "Stream ended but no valid content chunks received or processed."
                    }
        # Outer exception handlers for the HTTP request itself or unhandled stream issues
        except aiohttp.ClientResponseError as e: # Handles 4xx/5xx HTTP status codes
            error_message = f"HTTP Error {e.status}: {e.message}"
            logger.error(f"HTTP ClientResponseError calling {url}: {error_message}. Response body: {raw_body_on_error}", exc_info=True)
            full_code = ''.join(final_generated_code_parts) # Attempt to get any partial data from interrupted stream

            set_llm_input_output(
                span,
                input_text=question,
                output_text=full_code or f"HTTP Error {e.status}: {e.message}",
                model_name="weby/v1/generate"
            )
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, error_message)
            return {
                "error": error_message,
                "partial_code": full_code if full_code else None,
                "output": full_code, # Return partial code if any
                "status_code": e.status,
                "raw_response": raw_body_on_error
            }

        except aiohttp.ClientPayloadError as e: # Handles incomplete response body, e.g. connection dropped mid-stream
            error_message = f"AIOHTTP ClientPayloadError (incomplete response): {str(e)}"
            logger.error(f"AIOHTTP ClientPayloadError calling {url}: {error_message}", exc_info=True)
            full_code = ''.join(final_generated_code_parts) # Attempt to get any partial data

            set_llm_input_output(
                span,
                input_text=question,
                output_text=full_code or f"Incomplete response: {str(e)}",
                model_name="weby/v1/generate"
            )
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, error_message)

            if full_code:
                logger.info(f"Returning partial code ({len(full_code)} chars) due to ClientPayloadError from {processed_chunks_count} chunks.")
                return {
                    "error": error_message + " (partial data returned)",
                    "partial_code": full_code,
                    "output": full_code,
                    "status_code": response_status, # This might be None if error occurred very early
                    "raw_response": str(e),
                    "chunks_count": processed_chunks_count
                }
            else:
                return {
                    "error": error_message,
                    "partial_code": None,
                    "output": "",
                    "status_code": response_status,
                    "raw_response": str(e)
                }

        except Exception as e: # Generic catch-all for other errors (timeouts, connection errors not caught by ClientError, etc.)
            error_message = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error calling {url}: {error_message}", exc_info=True)
            full_code = ''.join(final_generated_code_parts) # Attempt to get any partial data

            set_llm_input_output(
                span,
                input_text=question,
                output_text=full_code or f"Unexpected error: {str(e)}",
                model_name="weby/v1/generate"
            )
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, error_message)
            return {
                "error": error_message,
                "partial_code": full_code if full_code else None,
                "output": full_code, # Return partial code if any
                "status_code": response_status, # This might be None
                "raw_response": str(e)
            }

@tracer.start_as_current_span("call_weby_prompt_enhance")
async def call_weby_prompt_enhance(question: str, temperature: float = 0.6, top_p: float = 0.95):
    """
    Calls the weby/prompt-enhance endpoint to get an enhanced prompt.
    Returns a dictionary: {"enhanced_prompt": ..., "raw_response": ...} or {"error": ..., "raw_response": ..., "status_code": ...}
    """
    url = WEBY_ENHANCE_API_URL
    payload = {
        "message": {
            "role": "user",
            "content": question
        },
        "temperature": temperature,
        "top_p": top_p
    }

    span = trace.get_current_span()
    span.set_attribute(OPENINFERENCE_SPAN_KIND, OTEL_SPAN_TYPE_LLM)

    # HTTP-specific attributes
    span.set_attribute("http.method", "POST")
    span.set_attribute("http.url", url)

    # LLM-specific attributes
    set_llm_input_output(
        span,
        input_text=question,
        model_name="weby/prompt-enhance", # Logical operation name
        temperature=temperature,
        top_p=top_p
    )
    # Optionally, add specific invocation parameters if known for prompt-enhance
    # span.set_attribute(LLM_INVOCATION_PARAMETERS, json.dumps({"some_param": "value"}))


    connect_timeout = int(CLIENT_TIMEOUT * 0.1) # 10% for connection
    connect_timeout = max(1, connect_timeout) # Ensure at least 1s
    # For non-streaming, total timeout is mainly driven by connect + server processing time.
    # aiohttp.ClientTimeout's `total` applies to the entire operation including all redirects, reads etc.
    # `sock_read` is time per read operation. `sock_connect` is for connection establishment part of `connect`.
    client_timeout_obj = aiohttp.ClientTimeout(total=CLIENT_TIMEOUT, connect=connect_timeout)
    logger.debug(f"Using timeout for prompt enhancement: total={CLIENT_TIMEOUT}s, connect={connect_timeout}s")

    async with aiohttp.ClientSession(timeout=client_timeout_obj) as session:
        response_status = None
        raw_body_on_error = "" # Will store response.text() on error
        response_text_content = "" # To store successful response text

        try:
            async with session.post(url, json=payload) as response:
                response_status = response.status
                span.set_attribute("http.status_code", response_status)
                response_text_content = await response.text() # Read the full response text

                if response_status >= 400:
                    raw_body_on_error = response_text_content
                    span.set_attribute("http.response.body", raw_body_on_error)

                    # Set LLM output to error message before raising
                    set_llm_input_output(
                        span,
                        input_text=question, # Can be omitted if already set and helper is idempotent
                        output_text=f"HTTP Error {response_status}",
                        model_name="weby/prompt-enhance"
                    )
                    response.raise_for_status() # Raises ClientResponseError for 4xx/5xx

                # If 2xx status, parse JSON from the response_text_content
                enhanced_prompt_data = json.loads(response_text_content)
                
                enhanced_prompt = "" # Initialize
                if "enhanced_message" in enhanced_prompt_data and isinstance(enhanced_prompt_data["enhanced_message"], dict):
                    enhanced_prompt = enhanced_prompt_data["enhanced_message"].get("content", "")
                elif "content" in enhanced_prompt_data: # Check if content is directly in the root
                    enhanced_prompt = enhanced_prompt_data.get("content", "")
                elif "enhanced_prompt" in enhanced_prompt_data: # Another possible key
                     enhanced_prompt = enhanced_prompt_data.get("enhanced_prompt", "")
                # Ensure enhanced_prompt is a string
                enhanced_prompt = str(enhanced_prompt) if enhanced_prompt is not None else ""

                # Add successful result to span
                set_llm_input_output(
                    span,
                    input_text=question, # Can be omitted if helper is idempotent
                    output_text=enhanced_prompt or "No enhancement provided",
                    model_name="weby/prompt-enhance"
                )
                span.set_status(trace.StatusCode.OK)
                logger.info(f"Successfully received enhanced prompt from {url} for: '{question[:30]}...' Extracted length: {len(enhanced_prompt)}.")
                return {
                    "enhanced_prompt": enhanced_prompt,
                    "output": enhanced_prompt,  # Adding output field for consistency
                    "raw_response": response_text_content, # Full JSON string
                    "status_code": response_status
                }
        except aiohttp.ClientResponseError as e: # Handles 4xx/5xx from response.raise_for_status()
            error_message = f"HTTP Error {e.status}: {e.message}"
            # raw_body_on_error should be set from the try block if status >= 400
            logger.error(f"HTTP ClientResponseError calling {url}: {error_message}. Response body: {raw_body_on_error}", exc_info=True)

            # LLM output already set to error in the try block for HTTP >= 400
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, description=error_message)
            return {
                "error": error_message,
                "output": "",  # Adding empty output field for consistency
                "raw_response": raw_body_on_error,
                "status_code": e.status
            }
        except json.JSONDecodeError as e: # Handles errors parsing successful (2xx) responses
            error_message = f"JSONDecodeError: Failed to parse response from {url}. Error: {str(e)}"
            # response_text_content contains the non-JSON body from the 2xx response
            logger.error(f"{error_message}. Response body: {response_text_content[:500]}", exc_info=True)

            set_llm_input_output(
                span,
                input_text=question, # Can be omitted
                output_text="Failed to parse JSON response",
                model_name="weby/prompt-enhance"
            )
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, description=error_message)
            return {
                "error": error_message,
                "output": "",
                "raw_response": response_text_content, # The problematic body
                "status_code": response_status # Should be 2xx if this error occurs
            }
        except aiohttp.ClientError as e: # Catches other client errors (connection, non-HTTP timeouts, etc.)
            error_message = f"AIOHTTP ClientError: {str(e)}"
            logger.error(f"AIOHTTP ClientError calling {url}: {error_message}", exc_info=True)

            set_llm_input_output(
                span,
                input_text=question, # Can be omitted
                output_text=f"Client error: {str(e)}",
                model_name="weby/prompt-enhance"
            )
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, description=error_message)
            return {
                "error": error_message,
                "output": "",
                "raw_response": str(e), # Error string, as body might not have been received
                "status_code": response_status # May be None if error happened before response
            }
        except Exception as e: # Generic catch-all
            error_message = f"Generic error: {str(e)}"
            logger.error(f"Generic error calling {url}: {error_message}", exc_info=True)

            set_llm_input_output(
                span,
                input_text=question, # Can be omitted
                output_text=f"Generic error: {str(e)}",
                model_name="weby/prompt-enhance"
            )
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, description=error_message)
            return {
                "error": error_message,
                "output": "",
                "raw_response": str(e),
                "status_code": response_status # May be None
            }

if __name__ == '__main__':
    import asyncio
    # nest_asyncio allows asyncio.run() to be called from an already running event loop (e.g., in Jupyter)
    import nest_asyncio
    nest_asyncio.apply()

    # --- Basic logging setup for script execution ---
    # The module's logger (`logger` which is logging.getLogger(__name__)) has its level set
    # based on ENABLE_FULL_CHUNK_LOGGING.
    # This basicConfig call sets up handlers for the root logger, allowing module logs to be seen.
    # It only configures if no handlers are already present on the root logger.
    if not logging.getLogger().hasHandlers():
        script_log_level = logging.DEBUG if ENABLE_FULL_CHUNK_LOGGING else logging.INFO
        logging.basicConfig(
            level=script_log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        # Ensure the module's logger also respects this level if it was higher (e.g. WARNING)
        if logger.level > script_log_level:
            logger.setLevel(script_log_level)
        logger.info(f"Basic logging configured for script execution at level: {logging.getLevelName(script_log_level)}")
    # --- End of logging setup ---

    async def main():
        try:
            from src.tracing import init_tracer
            # Initialize tracer for this test service (if main is run)
            init_tracer("weby_client_test_service")
            logger.info("Tracer initialized.")
        except ImportError:
            logger.warning("src.tracing.init_tracer could not be imported. Tracing will not be initialized for this test run.")
            # Mock tracer if actual module is not available
            def init_tracer_mock(service_name):
                logger.info(f"Mock tracer initialized for {service_name}")
            init_tracer_mock("weby_client_test_service_mocked")


        test_question = "Create a simple snake game web app using HTML, CSS, and JavaScript."

        logger.info(f"--- Testing /v1/weby endpoint with question: '{test_question}' ---")
        generated_code_result = await call_weby_v1_generate(test_question, framework="HTML/CSS/JS")

        if "error" in generated_code_result:
            logger.error(f"Error generating code: {generated_code_result['error']}")
            if "raw_response" in generated_code_result and generated_code_result["raw_response"]:
                 logger.error(f"Raw response for error (first 500 chars): {str(generated_code_result['raw_response'])[:500]}...")
            if "partial_code" in generated_code_result and generated_code_result['partial_code']:
                 logger.info(f"Partial code received (first 200 chars): {generated_code_result['partial_code'][:200]}...")
        else:
            logger.info(f"Generated code (first 200 chars):\n{generated_code_result.get('code', '')[:200]}...")
            logger.info(f"Full generation result details: "
                        f"Status Code: {generated_code_result.get('status_code')}, "
                        f"Chunks: {generated_code_result.get('chunks_count')}, "
                        f"Finish Reason: {generated_code_result.get('finish_reason')}")


        logger.info(f"\n--- Testing /weby/prompt-enhance endpoint with question: '{test_question}' ---")
        enhanced_question_result = await call_weby_prompt_enhance(test_question)

        if "error" in enhanced_question_result:
            logger.error(f"Error enhancing question: {enhanced_question_result['error']}")
            if "raw_response" in enhanced_question_result and enhanced_question_result["raw_response"]:
                logger.error(f"Raw response for error (first 500 chars): {str(enhanced_question_result['raw_response'])[:500]}...")
        else:
            logger.info(f"Enhanced question:\n{enhanced_question_result.get('enhanced_prompt', '')}")
            logger.info(f"Full enhancement result details: "
                        f"Status Code: {enhanced_question_result.get('status_code')}")

    asyncio.run(main())