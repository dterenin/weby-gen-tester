import sys
import os
import phoenix as px # For Phoenix client
from opentelemetry import trace # For trace.get_current_span()
import json

# Add the parent directory to sys.path to allow importing evaluation_prompts
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
# sys.path.append(parent_dir) # No longer needed for evaluation_prompts

# Constants previously in evaluation_prompts.py
TARGET_PROMPT_NAME = "weby-llm-judge-evaluator"
TARGET_PROMPT_VERSION_ID = "UHJvbXB0VmVyc2lvbjo3"

from src.tracing import get_opentelemetry_tracer, init_tracer_provider # Assuming init_tracer_provider is needed here too

tracer = get_opentelemetry_tracer(__name__)

# Helper function to fetch specific prompt version by its ID
@tracer.start_as_current_span("fetch_specific_prompt_version_by_id_span")
def _fetch_specific_prompt_version(version_id_to_fetch: str):
    span = trace.get_current_span()
    span.set_attribute("phoenix.prompt.version_id_to_fetch", version_id_to_fetch)

    try:
        if not os.getenv("PHOENIX_INITIALIZED"): 
            # Use a more specific service name for clarity in traces
            if not init_tracer_provider(service_name=f"prompt-fetcher-src-prompts-{version_id_to_fetch}"):
                print(f"Warning: Failed to initialize tracer provider for {version_id_to_fetch}.")
            os.environ["PHOENIX_INITIALIZED"] = "true"

        if not os.getenv("PHOENIX_COLLECTOR_ENDPOINT"):
            raise EnvironmentError("PHOENIX_COLLECTOR_ENDPOINT is not set. Cannot initialize Phoenix client.")
        
        client = px.Client()
        # print(f"Attempting to fetch prompt version directly by ID: '{version_id_to_fetch}'") # Less verbose logging
        
        prompt_version_data = client.prompts.get(prompt_version_id=version_id_to_fetch)

        if not prompt_version_data:
            error_msg = f"Prompt version with ID '{version_id_to_fetch}' not found by client.prompts.get()."
            span.set_status(trace.StatusCode.ERROR, error_msg)
            raise ValueError(error_msg)
        
        retrieved_id = getattr(prompt_version_data, 'id', None)
        if retrieved_id != version_id_to_fetch:
            error_msg = f"Fetched prompt object by ID '{version_id_to_fetch}', but its ID is '{retrieved_id}'."
            if retrieved_id is None:
                error_msg = f"Fetched prompt object by ID '{version_id_to_fetch}' has no 'id' attribute."
            
            span.set_attribute("phoenix.prompt.id_mismatch", True)
            span.set_attribute("phoenix.prompt.retrieved_id", str(retrieved_id))
            span.set_status(trace.StatusCode.ERROR, error_msg)
            raise ValueError(error_msg)

        span.set_attribute("phoenix.prompt.fetched_version_id", prompt_version_data.id)
        span.set_status(trace.StatusCode.OK)
        return prompt_version_data

    except Exception as e:
        error_msg = f"Error in _fetch_specific_prompt_version for ID '{version_id_to_fetch}': {type(e).__name__} - {e}"
        current_span = trace.get_current_span()
        if current_span.is_recording():
            current_span.record_exception(e)
            current_span.set_status(trace.StatusCode.ERROR, error_msg)
        if isinstance(e, (ValueError, EnvironmentError)):
            raise 
        raise RuntimeError(error_msg) from e

@tracer.start_as_current_span("get_evaluation_prompts_from_phoenix")
def get_evaluation_prompts():
    """
    Fetches the configured system and user prompt templates for evaluation from Phoenix.
    This function is traced.
    """
    span = trace.get_current_span()
    try:
        print(f"Fetching evaluation prompts for: {TARGET_PROMPT_NAME} (Version ID: {TARGET_PROMPT_VERSION_ID}) from Phoenix.")
        prompt_version_data = _fetch_specific_prompt_version(TARGET_PROMPT_VERSION_ID)

        # print(f"DEBUG: prompt_version_data type: {type(prompt_version_data)}") # Removed
        raw_messages = None
        if hasattr(prompt_version_data, '_template') and \
           isinstance(getattr(prompt_version_data, '_template'), dict) and \
           'messages' in prompt_version_data._template:
            raw_messages = prompt_version_data._template['messages']
            # print(f"DEBUG: Successfully accessed prompt_version_data._template['messages']. Type: {type(raw_messages)}") # Removed
            # if isinstance(raw_messages, list):
            #     print(f"DEBUG: raw_messages is a list with {len(raw_messages)} items.") # Removed
            # else:
            #     print(f"DEBUG: prompt_version_data._template['messages'] is NOT a list.") # Removed
        else:
            debug_missing_reasons = []
            if not hasattr(prompt_version_data, '_template'): 
                debug_missing_reasons.append("pv_data lacks '_template' attribute")
            else:
                template_attr = getattr(prompt_version_data, '_template')
                if not isinstance(template_attr, dict):
                    debug_missing_reasons.append(f"'_template' attribute is not a dict (type: {type(template_attr).__name__})")
                elif 'messages' not in template_attr:
                    debug_missing_reasons.append("'_template' dict lacks 'messages' key")
            error_msg = f"Could not access _template['messages'] from PromptVersion. Reasons: {'; '.join(debug_missing_reasons) if debug_missing_reasons else 'Unknown structure issue'}."
            span.set_status(trace.StatusCode.ERROR, error_msg)
            raise AttributeError(error_msg)

        if not isinstance(raw_messages, list):
            error_msg = f"Accessed _template['messages'] (ID: {TARGET_PROMPT_VERSION_ID}) but it is not a list. Type: {type(raw_messages)}"
            span.set_status(trace.StatusCode.ERROR, error_msg)
            raise ValueError(error_msg)

        system_prompt_content = None
        user_prompt_template_content = None

        for i, msg_data in enumerate(raw_messages):
            if not isinstance(msg_data, dict):
                print(f"WARNING: Message item {i} is not a dict: {msg_data}")
                continue
            
            role = msg_data.get('role')
            content_list = msg_data.get('content') # This should be a list e.g. [{'type': 'text', 'text': '...'}]

            current_content_text = None
            if isinstance(content_list, list) and len(content_list) > 0:
                first_content_item = content_list[0]
                if isinstance(first_content_item, dict) and 'text' in first_content_item:
                    current_content_text = first_content_item['text']
                else:
                    print(f"WARNING: Message {i} (role '{role}') first content item is not in expected dict format or lacks 'text' key: {first_content_item}")
            elif isinstance(content_list, str): # Fallback for plain string content (less likely based on Phoenix structure)
                current_content_text = content_list 
                print(f"INFO: Message {i} (role '{role}') content was a plain string (unexpected for Phoenix _template structure).")
            else:
                print(f"WARNING: Message {i} (role '{role}') content_list is not a list or is empty, or has unexpected type: {type(content_list)}")

            if current_content_text is not None:
                if role == 'system':
                    system_prompt_content = current_content_text
                elif role == 'user':
                    user_prompt_template_content = current_content_text
        
        if not system_prompt_content or not user_prompt_template_content:
            error_msg = "Could not extract system or user prompt text from raw messages list."
            span.set_attribute("phoenix.prompt.parsing_error", error_msg)
            # Log the raw_messages list for debugging if parsing fails
            try:
                span.set_attribute("phoenix.prompt.raw_messages_for_parsing_debug", json.dumps(raw_messages))
            except TypeError:
                span.set_attribute("phoenix.prompt.raw_messages_for_parsing_debug", "Raw messages list not JSON serializable")
            span.set_status(trace.StatusCode.ERROR, error_msg)
            raise ValueError(error_msg)

        span.set_attribute("system_prompt_length", len(system_prompt_content))
        span.set_attribute("user_prompt_template_length", len(user_prompt_template_content))
        span.set_attribute("system_prompt_start", system_prompt_content[:50] + "...")
        span.set_attribute("user_prompt_template_start", user_prompt_template_content[:50] + "...")
        span.set_attribute("phoenix.prompt.name_used_for_context", TARGET_PROMPT_NAME)
        span.set_attribute("phoenix.prompt.version_id_used", TARGET_PROMPT_VERSION_ID)
        
        print("Evaluation prompts successfully fetched and parsed from Phoenix (using _template).")
        span.set_status(trace.StatusCode.OK)
        return system_prompt_content, user_prompt_template_content

    except Exception as e:
        error_msg_final = f"Failed to get evaluation prompts (version {TARGET_PROMPT_VERSION_ID}) from Phoenix: {type(e).__name__} - {e}"
        current_span = trace.get_current_span()
        if current_span.is_recording():
            current_span.set_status(trace.StatusCode.ERROR, error_msg_final)
            if not (hasattr(e, '__cause__') and e.__cause__ is not None) and not isinstance(e, (ValueError, EnvironmentError, AttributeError)):
                 current_span.record_exception(e)
        print(f"ERROR: {error_msg_final}")
        if isinstance(e, (ValueError, EnvironmentError, RuntimeError, AttributeError)):
            raise
        raise RuntimeError(error_msg_final) from e


if __name__ == '__main__':
    # Example usage:
    # Ensure tracer is initialized for standalone run. 
    if not os.getenv("PHOENIX_INITIALIZED"): 
        from src.tracing import init_tracer 
        from dotenv import load_dotenv
        env_path = os.path.join(parent_dir, '.env') 
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)
            print(f"Loaded .env from {env_path}")
        else:
            print(f".env not found at {env_path}, ensure PHOENIX_COLLECTOR_ENDPOINT is set.")
        
        # Use a more specific service name for clarity in traces for the main block
        if not init_tracer(f"prompt-test-main-src-prompts-{TARGET_PROMPT_VERSION_ID}"): 
             print(f"Warning: Main __main__ failed to initialize tracer for {TARGET_PROMPT_VERSION_ID}.")
        os.environ["PHOENIX_INITIALIZED"] = "true"

    try:
        system_prompt, user_template = get_evaluation_prompts()
        print("\\nFetched System Prompt from Phoenix (via _template):")
        print(system_prompt)
        print("\\nFetched User Prompt Template from Phoenix (via _template):")
        print(user_template) 
    except Exception as e:
        print(f"Error in example usage: {e}") 