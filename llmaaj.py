import asyncio
import os
import logging
import pandas as pd
import time
import uuid # Added for fallback experiment_id
from dotenv import load_dotenv
import json # For serializing row data for OTel events, and parsing metrics
import math # <<< Added import
import phoenix as px # Import phoenix
from opentelemetry import trace # Import trace for get_current_span()
from phoenix.experiments.evaluators import create_evaluator # Import create_evaluator
import pickle # Added for caching
import argparse
import requests
import csv
import io

# Initialize OpenTelemetry Tracer Provider ONCE at the very top.
from src.tracing import (
    init_tracer_provider, 
    get_opentelemetry_tracer,
    set_llm_input_output,
    OTEL_SPAN_TYPE_LLM,
    OPENINFERENCE_SPAN_KIND
)

# Call init_tracer_provider immediately. It handles the global setup.
# It will print errors/warnings if PHOENIX_ENDPOINT is not set.
tracer_provider = init_tracer_provider(service_name="weby-evaluation-pipeline")

# Get a tracer for the main module itself
tracer = get_opentelemetry_tracer(__name__, "1.0.0") 

from src.prompts import get_evaluation_prompts
from src.data_loader import download_and_process_dataset
from src.weby_client import call_weby_prompt_enhance, call_weby_v1_generate
from src.evaluation import evaluate_response_with_llm_judge

# For running asyncio in environments like Jupyter/IPython if needed, not strictly for scripts
import nest_asyncio
nest_asyncio.apply()

load_dotenv() # Load .env variables

# Configure Phoenix Client for SaaS (before px.Client() is ever called)
# These environment variables are expected by px.Client() according to documentation
# Standardize to use PHOENIX_COLLECTOR_ENDPOINT directly
phoenix_collector_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
phoenix_api_key_for_client = os.getenv("PHOENIX_API_KEY") # This is the same key used for OTel export

if phoenix_collector_endpoint and phoenix_api_key_for_client:
    # Ensure PHOENIX_COLLECTOR_ENDPOINT is in os.environ for px.Client() if it checks there
    if os.environ.get("PHOENIX_COLLECTOR_ENDPOINT") != phoenix_collector_endpoint:
        os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = phoenix_collector_endpoint
    
    # The documentation consistently shows f"api_key={...}" for PHOENIX_CLIENT_HEADERS
    # Let's use this format. If it needs "Authorization: Bearer ...", we can change it.
    # Ensure PHOENIX_CLIENT_HEADERS is also set in os.environ
    client_headers = f"api_key={phoenix_api_key_for_client}"
    if os.environ.get("PHOENIX_CLIENT_HEADERS") != client_headers:
        os.environ["PHOENIX_CLIENT_HEADERS"] = client_headers
        
    print(f"Phoenix Client Config: PHOENIX_COLLECTOR_ENDPOINT is: {phoenix_collector_endpoint}")
    print(f"Phoenix Client Config: PHOENIX_CLIENT_HEADERS set using 'api_key=...'")
elif not phoenix_collector_endpoint:
    print("Warning: PHOENIX_COLLECTOR_ENDPOINT not found in .env. px.Client() might default to localhost or fail.")
elif not phoenix_api_key_for_client:
    print("Warning: PHOENIX_API_KEY not found in .env for client headers. px.Client() calls might be unauthorized.")

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Pipeline modes
PIPELINE_MODE_GENERATE = "generate"
PIPELINE_MODE_EVALUATE = "evaluate"
PIPELINE_MODE_FULL = "full"  # Both generate and evaluate

# Default configuration settings - used only if parameters are not explicitly specified
DEFAULT_CONFIG = {
    "dataset_name": "smirki/UIGEN-T1.1-TAILWIND",
    "dataset_seed": 42, 
    "dataset_limit": 64, 
    "max_concurrent_tasks": 5,
    "pipeline_mode": PIPELINE_MODE_GENERATE,
    "framework": "Nextjs",
    "skip_prompt_enhancement": True,
    "max_retries": 1,
    "timeout_seconds": 600,
    # New optional parameters for weby_client payload
    "files": [],
    "temperature": 0.6,
    "top_p": 0.95,
    "model": None  # Will use default from weby_client if not specified
}

# --- Phoenix Evaluator Functions ---
@create_evaluator(name="LLM Score Overall", kind="CODE") # Was get_llm_rating, now targets score_overall
def get_llm_score_overall(output: dict) -> float: # Scores can be int or float, changed to float
    metrics_json = output.get("evaluation_metrics")
    if metrics_json and isinstance(metrics_json, str):
        try:
            metrics = json.loads(metrics_json)
            score = metrics.get("score_overall")
            return float(score) if score is not None else math.nan
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse evaluation_metrics JSON for score_overall: {metrics_json[:100]}")
            return math.nan
    elif isinstance(metrics_json, dict):
        score = metrics_json.get("score_overall")
        return float(score) if score is not None else math.nan
    return math.nan

@create_evaluator(name="LLM Score Functionality", kind="CODE") # New evaluator
def get_llm_score_functionality(output: dict) -> float: # Changed to float
    metrics_json = output.get("evaluation_metrics")
    if metrics_json and isinstance(metrics_json, str):
        try:
            metrics = json.loads(metrics_json)
            score = metrics.get("score_functionality")
            return float(score) if score is not None else math.nan
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse evaluation_metrics JSON for score_functionality: {metrics_json[:100]}")
            return math.nan
    elif isinstance(metrics_json, dict):
        score = metrics_json.get("score_functionality")
        return float(score) if score is not None else math.nan
    return math.nan

@create_evaluator(name="LLM Score Completeness", kind="CODE") # New evaluator
def get_llm_score_completeness(output: dict) -> float: # Changed to float
    metrics_json = output.get("evaluation_metrics")
    if metrics_json and isinstance(metrics_json, str):
        try:
            metrics = json.loads(metrics_json)
            score = metrics.get("score_completeness")
            return float(score) if score is not None else math.nan
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse evaluation_metrics JSON for score_completeness: {metrics_json[:100]}")
            return math.nan
    elif isinstance(metrics_json, dict):
        score = metrics_json.get("score_completeness")
        return float(score) if score is not None else math.nan
    return math.nan

@create_evaluator(name="LLM Score Code Quality", kind="CODE") # New evaluator
def get_llm_score_code_quality(output: dict) -> float: # Changed to float
    metrics_json = output.get("evaluation_metrics")
    if metrics_json and isinstance(metrics_json, str):
        try:
            metrics = json.loads(metrics_json)
            score = metrics.get("score_code_quality")
            return float(score) if score is not None else math.nan
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse evaluation_metrics JSON for score_code_quality: {metrics_json[:100]}")
            return math.nan
    elif isinstance(metrics_json, dict):
        score = metrics_json.get("score_code_quality")
        return float(score) if score is not None else math.nan
    return math.nan

@create_evaluator(name="LLM Score Responsiveness", kind="CODE") # New evaluator
def get_llm_score_responsiveness(output: dict) -> float: # Changed to float
    metrics_json = output.get("evaluation_metrics")
    if metrics_json and isinstance(metrics_json, str):
        try:
            metrics = json.loads(metrics_json)
            score = metrics.get("score_responsiveness")
            return float(score) if score is not None else math.nan
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse evaluation_metrics JSON for score_responsiveness: {metrics_json[:100]}")
            return math.nan
    elif isinstance(metrics_json, dict):
        score = metrics_json.get("score_responsiveness")
        return float(score) if score is not None else math.nan
    return math.nan

@create_evaluator(name="LLM Score UX/UI", kind="CODE") # New evaluator for "score_ux_ui"
def get_llm_score_ux_ui(output: dict) -> float: # Changed to float
    metrics_json = output.get("evaluation_metrics")
    if metrics_json and isinstance(metrics_json, str):
        try:
            metrics = json.loads(metrics_json)
            score = metrics.get("score_ux_ui") # Key from your JSON
            return float(score) if score is not None else math.nan
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse evaluation_metrics JSON for score_ux_ui: {metrics_json[:100]}")
            return math.nan
    elif isinstance(metrics_json, dict):
        score = metrics_json.get("score_ux_ui")
        return float(score) if score is not None else math.nan
    return math.nan

@create_evaluator(name="LLM Summary Provided", kind="CODE") # Was get_llm_feedback_provided, now targets summary_overall
def get_llm_summary_overall_provided(output: dict) -> bool:
    metrics_json = output.get("evaluation_metrics")
    summary_present = False
    if metrics_json and isinstance(metrics_json, str):
        try:
            metrics = json.loads(metrics_json)
            summary = metrics.get("summary_overall")
            summary_present = bool(summary and str(summary).strip())
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse evaluation_metrics JSON for summary_overall: {metrics_json[:100]}")
            # summary_present remains False
    elif isinstance(metrics_json, dict):
        summary = metrics_json.get("summary_overall")
        summary_present = bool(summary and str(summary).strip())
    return summary_present

@create_evaluator(name="LLM Evaluation Error", kind="CODE") # No changes needed for this one
def get_llm_evaluation_error_present(output: dict) -> bool:
    error_reason = output.get("evaluation_error_reason")
    return bool(error_reason and str(error_reason).strip())

# List of evaluators to pass to run_experiment
# Updated to reflect the new and modified evaluators
phoenix_evaluators = [
    get_llm_score_overall,
    get_llm_score_functionality,
    get_llm_score_completeness,
    get_llm_score_code_quality,
    get_llm_score_responsiveness,
    get_llm_score_ux_ui,
    get_llm_summary_overall_provided,
    get_llm_evaluation_error_present
]
# --- End Phoenix Evaluator Functions ---

# Setup caching for results
cache_dir = "cache"
os.makedirs(cache_dir, exist_ok=True)

def get_cached_result(key):
    """Retrieve cached result if available"""
    cache_file = os.path.join(cache_dir, f"{key}.pkl")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cached result for {key}: {e}")
    return None

def save_to_cache(key, data):
    """Save result to cache"""
    cache_file = os.path.join(cache_dir, f"{key}.pkl")
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(data, f)
        logger.debug(f"Saved result to cache: {key}")
    except Exception as e:
        logger.warning(f"Failed to cache result for {key}: {e}")

async def download_dataset_csv(dataset_id: str, phoenix_endpoint: str, api_key: str):
    """Download dataset as CSV from Phoenix using the /v1/datasets/{id}/csv endpoint"""
    if not dataset_id or not phoenix_endpoint or not api_key:
        logger.warning("Missing required parameters for dataset download")
        return None
    
    try:
        # Construct the CSV download URL
        csv_url = f"{phoenix_endpoint.rstrip('/')}/v1/datasets/{dataset_id}/csv"
        
        # Set up headers with API key
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "text/csv"
        }
        
        logger.info(f"Downloading dataset CSV from: {csv_url}")
        
        # Make the request
        response = requests.get(csv_url, headers=headers, timeout=60)
        response.raise_for_status()
        
        # Save to file
        filename = f"{dataset_id}.csv"
        filepath = os.path.join("datasets", filename)
        os.makedirs("datasets", exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        logger.info(f"Dataset CSV downloaded successfully: {filepath}")
        logger.info(f"File size: {len(response.text)} characters")
        
        # Parse CSV to get row count
        try:
            csv_reader = csv.reader(io.StringIO(response.text))
            row_count = sum(1 for row in csv_reader) - 1  # Subtract header row
            logger.info(f"Dataset contains {row_count} rows")
        except Exception as e:
            logger.warning(f"Could not parse CSV for row count: {e}")
        
        return {
            "filepath": filepath,
            "filename": filename,
            "size_chars": len(response.text),
            "download_url": csv_url
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP error downloading dataset CSV: {e}")
        return None
    except Exception as e:
        logger.error(f"Error downloading dataset CSV: {e}")
        return None

async def process_single_generation(question: str, framework: str, item_id: str, skip_prompt_enhancement: bool = False, max_retries: int = 1, files: list = None, temperature: float = 0.6, top_p: float = 0.95, model: str = None):
    """Processes a single question: enhance (optional), generate code."""
    # Check cache first
    cache_key = f"gen_{item_id}_{skip_prompt_enhancement}"
    cached_result = get_cached_result(cache_key)
    if cached_result:
        logger.info(f"[{item_id}] Using cached generation result")
        return cached_result

    # Set default values if None
    if files is None:
        files = []

    # experiment_id (now item_id) is used for tagging data and as a unique ID for the processed item.
    with tracer.start_as_current_span("process_single_generation", attributes={
        OPENINFERENCE_SPAN_KIND: OTEL_SPAN_TYPE_LLM,
        "tag.item_id": item_id,
        "config.skip_prompt_enhancement": skip_prompt_enhancement
    }) as current_span:
        
        # Set input data for initial LLM call
        set_llm_input_output(
            current_span,
            input_text=question
        )
        
        # --- 1. Prompt Enhancement (Optional) ---
        enhanced_question_text = question  # Default to original question
        question_for_generation = question
        enhancement_duration_s = 0.0
        enhancement_status_code = None
        enhancement_raw_response = None
        enhancement_error = None
        prompt_was_enhanced = False  # Flag to track successful enhancement

        if not skip_prompt_enhancement:
            logger.info(f"[{item_id}] Enhancing prompt for: '{question[:50]}...'")
            enhancement_start_time = time.time()
            try:
                enhancement_result = await call_weby_prompt_enhance(question)
                enhancement_duration_s = time.time() - enhancement_start_time
                
                # Get enhanced question from output field (if available) or from enhanced_prompt
                enhanced_question_text = enhancement_result.get("output") or enhancement_result.get("enhanced_prompt", question)
                question_for_generation = enhanced_question_text # Use enhanced if available
                enhancement_status_code = enhancement_result.get("status_code")
                enhancement_raw_response = enhancement_result.get("raw_response", "")
                enhancement_error = enhancement_result.get("error")
                
                # Check if prompt was actually enhanced (differs from original)
                prompt_was_enhanced = enhanced_question_text != question

                current_span.set_attribute("enhancement.duration_s", round(enhancement_duration_s, 2))
                
                if enhancement_status_code:
                    current_span.set_attribute("enhancement.status_code", enhancement_status_code)
                if enhancement_error:
                    current_span.set_attribute("enhancement.error", enhancement_error)
                    logger.warning(f"[{item_id}] Prompt enhancement failed: {enhancement_error}. Proceeding with original question.")
                else:
                    logger.info(f"[{item_id}] Prompt enhanced successfully in {enhancement_duration_s:.2f}s.")
            except Exception as e_enhance:
                enhancement_duration_s = time.time() - enhancement_start_time
                enhancement_error = f"Exception during prompt enhancement: {str(e_enhance)}"
                logger.error(f"[{item_id}] Exception during prompt enhancement: {e_enhance}", exc_info=True)
                current_span.set_attribute("enhancement.duration_s", round(enhancement_duration_s, 2))
                current_span.set_attribute("enhancement.error", enhancement_error)
                # Fallback to original question is already handled by default assignment
        else:
            logger.info(f"[{item_id}] Skipping prompt enhancement for question: '{question[:50]}...' by config.")
            current_span.set_attribute("enhancement.skipped", True)
            # question_for_generation remains the original question

        # --- 2. Code Generation для оригинального вопроса ---
        logger.info(f"[{item_id}] Generating code for original question: '{question[:50]}...'")
        generation_start_time = time.time()
        original_generation_result = None
        
        for retry in range(max_retries + 1):
            try:
                original_generation_result = await call_weby_v1_generate(
                    question=question, 
                    framework=framework,
                    temperature=temperature,
                    top_p=top_p,
                    files=files,
                    model=model
                )
                break
            except Exception as e:
                if retry < max_retries:
                    logger.warning(f"[{item_id}] Retry {retry+1}/{max_retries} for original code generation due to: {e}")
                    await asyncio.sleep(1)  # Short delay before retry
                else:
                    logger.error(f"[{item_id}] All retries failed for original code generation: {e}")
                    original_generation_result = {
                        "error": f"All {max_retries} retries failed: {str(e)}",
                        "status_code": 500,
                        "finish_reason": "error",
                        "output": ""  # Add empty output field for consistency
                    }
            
        generation_duration_s = time.time() - generation_start_time

        # Get generated code from output field (if available) or from code (for backward compatibility)
        original_generated_code = original_generation_result.get("output") or original_generation_result.get("code")
        original_partial_code_on_error = original_generation_result.get("partial_code")
        generation_status_code = original_generation_result.get("status_code")
        generation_raw_response = original_generation_result.get("raw_response", "")
        generation_error = original_generation_result.get("error")
        generation_finish_reason = original_generation_result.get("finish_reason")
        
        current_span.set_attribute("generation.duration_s", round(generation_duration_s, 2))
        if generation_status_code:
            current_span.set_attribute("generation.status_code", generation_status_code)
        if generation_error:
            current_span.set_attribute("generation.error", generation_error)
            logger.error(f"[{item_id}] Original code generation failed: {generation_error}")
        if generation_finish_reason:
            current_span.set_attribute("generation.finish_reason", generation_finish_reason)
        
        original_generated_content = original_generated_code if original_generated_code is not None else original_partial_code_on_error
        if original_generated_content is not None:
            current_span.set_attribute("generation.output_code_length", len(original_generated_content if original_generated_content else ""))
        else:
            current_span.set_attribute("generation.output_code_length", 0)

        # --- Prepare response data for original question ---
        original_response_for_phoenix = ""
        if original_generated_content is not None:
            original_response_for_phoenix = original_generated_content
            logger.info(f"[{item_id}] Original response length: {len(original_response_for_phoenix)} characters")
            if len(original_response_for_phoenix) == 0:
                logger.warning(f"[{item_id}] Original response is empty string!")
        elif generation_error:
            original_response_for_phoenix = f"Generation Error: {generation_error}"
            logger.warning(f"[{item_id}] Original response contains an error: {generation_error}")
        elif generation_finish_reason:
            original_response_for_phoenix = f"Generation Finish Reason: {generation_finish_reason} (No code found)"
            logger.warning(f"[{item_id}] Original response finished with reason: {generation_finish_reason} but no code found")
        else:
            original_response_for_phoenix = "Generation failed or produced no output."
            logger.warning(f"[{item_id}] Original response generation failed without specific error or reason")
        
        # Установка минимального текста для пустых ответов, чтобы трейсинг не был пустым
        if not original_response_for_phoenix or len(original_response_for_phoenix.strip()) == 0:
            original_response_for_phoenix = "Empty response generated"
            logger.warning(f"[{item_id}] Setting empty original response to placeholder text for tracing")
        
        # Устанавливаем выходные данные для LLM генерации
        set_llm_input_output(
            current_span,
            output_text=original_response_for_phoenix
        )
        
        # --- 3. Генерация кода для улучшенного вопроса (если он отличается от оригинала) ---
        enhanced_response_for_phoenix = ""
        enhanced_generation_duration_s = 0.0
        enhanced_generation_status_code = None
        enhanced_generation_error = None
        enhanced_generation_finish_reason = None
        
        if prompt_was_enhanced and not skip_prompt_enhancement:
            # Добавляем новый span для генерации улучшенного кода
            with tracer.start_as_current_span("process_enhanced_generation", attributes={
                OPENINFERENCE_SPAN_KIND: OTEL_SPAN_TYPE_LLM,
                "tag.item_id": f"{item_id}_enhanced"
            }) as enhanced_span:
                # Set input data for enhanced LLM call
                set_llm_input_output(
                    enhanced_span,
                    input_text=enhanced_question_text
                )
                
                logger.info(f"[{item_id}] Generating code for enhanced question: '{enhanced_question_text[:50]}...'")
                enhanced_generation_start_time = time.time()
                enhanced_generation_result = None
                
                for retry in range(max_retries + 1):
                    try:
                        enhanced_generation_result = await call_weby_v1_generate(
                            question=enhanced_question_text, 
                            framework=framework,
                            temperature=temperature,
                            top_p=top_p,
                            files=files,
                            model=model
                        )
                        break
                    except Exception as e:
                        if retry < max_retries:
                            logger.warning(f"[{item_id}] Retry {retry+1}/{max_retries} for enhanced code generation due to: {e}")
                            await asyncio.sleep(1)  # Short delay before retry
                        else:
                            logger.error(f"[{item_id}] All retries failed for enhanced code generation: {e}")
                            enhanced_generation_result = {
                                "error": f"All {max_retries} retries failed: {str(e)}",
                                "status_code": 500,
                                "finish_reason": "error",
                                "output": ""  # Add empty output field for consistency
                            }
                
                enhanced_generation_duration_s = time.time() - enhanced_generation_start_time
                
                # Get generated code from output field (if available) or from code (for backward compatibility)
                enhanced_generated_code = enhanced_generation_result.get("output") or enhanced_generation_result.get("code")
                enhanced_partial_code_on_error = enhanced_generation_result.get("partial_code")
                enhanced_generation_status_code = enhanced_generation_result.get("status_code")
                enhanced_generation_raw_response = enhanced_generation_result.get("raw_response", "")
                enhanced_generation_error = enhanced_generation_result.get("error")
                enhanced_generation_finish_reason = enhanced_generation_result.get("finish_reason")
                
                enhanced_span.set_attribute("enhanced_generation.duration_s", round(enhanced_generation_duration_s, 2))
                if enhanced_generation_status_code:
                    enhanced_span.set_attribute("enhanced_generation.status_code", enhanced_generation_status_code)
                if enhanced_generation_error:
                    enhanced_span.set_attribute("enhanced_generation.error", enhanced_generation_error)
                    logger.error(f"[{item_id}] Enhanced code generation failed: {enhanced_generation_error}")
                if enhanced_generation_finish_reason:
                    enhanced_span.set_attribute("enhanced_generation.finish_reason", enhanced_generation_finish_reason)
                
                enhanced_generated_content = enhanced_generated_code if enhanced_generated_code is not None else enhanced_partial_code_on_error
                if enhanced_generated_content is not None:
                    enhanced_span.set_attribute("enhanced_generation.output_code_length", len(enhanced_generated_content if enhanced_generated_content else ""))
                    
                    # Подготовка ответа для улучшенного вопроса
                    enhanced_response_for_phoenix = enhanced_generated_content
                elif enhanced_generation_error:
                    enhanced_response_for_phoenix = f"Generation Error: {enhanced_generation_error}"
                elif enhanced_generation_finish_reason:
                    enhanced_response_for_phoenix = f"Generation Finish Reason: {enhanced_generation_finish_reason} (No code found)"
                else:
                    enhanced_response_for_phoenix = "Enhanced generation failed or produced no output."
                
                # Устанавливаем выходные данные для улучшенного LLM-вызова
                set_llm_input_output(
                    enhanced_span,
                    output_text=enhanced_response_for_phoenix
                )
                    
                logger.info(f"[{item_id}] Enhanced code generation completed in {enhanced_generation_duration_s:.2f}s.")
        elif not prompt_was_enhanced:
            # If prompt was not enhanced, set enhanced_r to 'N/A' instead of empty string
            enhanced_response_for_phoenix = "N/A (no enhancement was made)"
        else:
            # If enhancement was skipped, explicitly indicate this
            enhanced_response_for_phoenix = "N/A (enhancement skipped by config)"

        # --- 4. Prepare Result Data for Phoenix ---
        result_data = {
            # IDs and Core Inputs/Outputs for Phoenix
            "question_id": item_id, # Used as unique row ID by Phoenix if schema matches
            "question": question,   # Original question (Phoenix 'input')
            "enhanced_q": enhanced_question_text if prompt_was_enhanced else "N/A (enhancement skipped/failed)", # (Phoenix 'input')
            "response": original_response_for_phoenix, # Original generated code or error message (Phoenix 'output')
            "enhanced_r": enhanced_response_for_phoenix, # Enhanced generated code or error message (Phoenix 'output')

            # Framework and Enhancement Details (Metadata)
            "framework": framework,
            "skip_enhancement_flag": skip_prompt_enhancement,
            "enhancement_duration_s": round(enhancement_duration_s, 2),
            "enhancement_status_code": enhancement_status_code,
            "enhancement_raw_response_preview": enhancement_raw_response[:200] if enhancement_raw_response else "N/A",
            "enhancement_error": enhancement_error,
            "prompt_was_enhanced": prompt_was_enhanced,
            
            # Generation Details (Metadata) - for original question
            "generation_duration_s": round(generation_duration_s, 2),
            "generation_status_code": generation_status_code,
            "generation_raw_response_preview": generation_raw_response[:200] if isinstance(generation_raw_response, str) else "N/A (not string)",
            "generation_error": generation_error,
            "generation_finish_reason": generation_finish_reason,
            "generation_had_partial_code": True if original_partial_code_on_error is not None and generation_error else False,
            
            # Generation Details (Metadata) - for enhanced question
            "enhanced_generation_duration_s": round(enhanced_generation_duration_s, 2) if prompt_was_enhanced else 0,
            "enhanced_generation_status_code": enhanced_generation_status_code,
            "enhanced_generation_error": enhanced_generation_error,
            "enhanced_generation_finish_reason": enhanced_generation_finish_reason,
        }
        
        # Cache the result
        save_to_cache(cache_key, result_data)
        
        current_span.set_status(trace.StatusCode.OK, "Generation for item completed.")
        return result_data

def handle_json_float_values(data):
    """
    Handles special float values (NaN, Infinity, -Infinity),
    replacing them with values that can be serialized to JSON.
    Also handles very large or small float values that may cause problems.
    """
    if isinstance(data, dict):
        return {k: handle_json_float_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [handle_json_float_values(item) for item in data]
    elif isinstance(data, float):
        try:
            # Check for NaN and Infinity
            if math.isnan(data):
                return 0.0  # Replace NaN with 0.0
            elif math.isinf(data) and data > 0:
                return 1.0e308  # Replace +Infinity with largest valid float
            elif math.isinf(data) and data < 0:
                return -1.0e308  # Replace -Infinity with smallest valid float
                
            # Check if value can be serialized to JSON
            json.dumps(data)
            return data
        except (OverflowError, ValueError):
            # If value causes error during serialization, replace it
            if data > 0:
                return 1.0e308  # For too large positive values
            else:
                return -1.0e308  # For too large negative values
    elif data is None:
        return None
    return data

async def process_single_evaluation(question: str, response_content: str, item_id: str, max_retries: int = 1):
    """Processes evaluation of a single response: call LLM judge."""
    # Check cache first
    cache_key = f"eval_{item_id}"
    cached_result = get_cached_result(cache_key)
    if cached_result:
        logger.info(f"[{item_id}] Using cached evaluation result")
        return cached_result

    with tracer.start_as_current_span("process_single_evaluation", attributes={
        OPENINFERENCE_SPAN_KIND: OTEL_SPAN_TYPE_LLM,
        "tag.item_id": item_id
    }) as current_span:
        
        # Set input data for LLM evaluation
        set_llm_input_output(
            current_span,
            input_text=f"Question: {question}\nResponse: {response_content}"
        )
        
        evaluation_metrics = {}
        evaluation_error_str = None

        # Handle empty response content differently - evaluate it rather than skip
        if not response_content or response_content.strip() == "":
            logger.warning(f"[{item_id}] Response content is empty, evaluating as empty response")
            current_span.set_attribute("evaluation.has_empty_response", True)
            # Continue with evaluation of empty response
        
        logger.info(f"[{item_id}] Evaluating response for: '{question[:50]}...'")
        current_span.set_attribute("evaluation.skipped", False)
        
        for retry in range(max_retries + 1):
            try:
                # Assuming evaluate_response takes the question the LLM saw and the generated code
                evaluation_result = await evaluate_response_with_llm_judge(
                    question=question,
                    response_content=response_content or "", # Ensure we pass empty string rather than None
                    experiment_id=item_id
                )
                evaluation_metrics = evaluation_result.get("metrics", {})
                evaluation_error_str = evaluation_result.get("error") # Error from the evaluation process itself
                
                # Process the metrics to handle JSON serialization issues
                processed_metrics = handle_json_float_values(evaluation_metrics)
                
                # Добавляем результат оценки в span
                if processed_metrics:
                    try:
                        # First, make sure we can serialize it to JSON
                        metrics_json = json.dumps(processed_metrics)
                        set_llm_input_output(
                            current_span,
                            output_text=metrics_json
                        )
                    except Exception as json_error:
                        logger.error(f"[{item_id}] Failed to serialize metrics to JSON: {json_error}")
                        # If serialization fails, create a sanitized version with default values
                        sanitized_metrics = {
                            "score_overall": 0.0,
                            "score_functionality": 0.0,
                            "score_completeness": 0.0,
                            "score_code_quality": 0.0,
                            "score_responsiveness": 0.0,
                            "score_ux_ui": 0.0,
                            "summary_overall": f"Evaluation failed to generate valid metrics: {str(json_error)}"
                        }
                        
                        # Try again with additional check
                        try:
                            metrics_json = json.dumps(sanitized_metrics)
                            set_llm_input_output(
                                current_span,
                                output_text=metrics_json
                            )
                        except Exception as second_json_error:
                            logger.error(f"[{item_id}] Even sanitized metrics failed to serialize: {second_json_error}")
                            # Last attempt - just a string
                            set_llm_input_output(
                                current_span,
                                output_text=json.dumps({"error": "Failed to serialize evaluation metrics"})
                            )
                        
                        # Update processed_metrics for the result_data
                        processed_metrics = sanitized_metrics
                        # Add error information
                        evaluation_error_str = f"JSON serialization error: {str(json_error)}. Using default metrics."
                
                if evaluation_error_str:
                    current_span.set_attribute("evaluation.error", evaluation_error_str)
                    logger.warning(f"[{item_id}] Evaluation process encountered an error: {evaluation_error_str}")
                logger.info(f"[{item_id}] Evaluation completed.")
                break
            except Exception as e_eval:
                if retry < max_retries:
                    logger.warning(f"[{item_id}] Retry {retry+1}/{max_retries} for evaluation due to: {e_eval}")
                    await asyncio.sleep(1)  # Short delay before retry
                else:
                    evaluation_error_str = f"Exception during evaluation: {str(e_eval)}"
                    logger.error(f"[{item_id}] Exception during evaluation: {e_eval}", exc_info=True)
                    current_span.set_attribute("evaluation.error", evaluation_error_str)
                    # Create default metrics for error case
                    processed_metrics = {
                        "score_overall": 0.0,
                        "score_functionality": 0.0,
                        "score_completeness": 0.0,
                        "score_code_quality": 0.0,
                        "score_responsiveness": 0.0,
                        "score_ux_ui": 0.0,
                        "summary_overall": f"Evaluation failed: {str(e_eval)}"
                    }

        # Ensure metrics can be serialized to JSON
        try:
            metrics_json = json.dumps(processed_metrics)
        except Exception as ser_error:
            logger.error(f"[{item_id}] Final metrics serialization failed: {ser_error}")
            processed_metrics = {
                "score_overall": 0.0,
                "score_functionality": 0.0,
                "score_completeness": 0.0,
                "score_code_quality": 0.0,
                "score_responsiveness": 0.0,
                "score_ux_ui": 0.0,
                "summary_overall": "Metrics could not be serialized properly"
            }
            metrics_json = json.dumps(processed_metrics)

        # Prepare result data
        result_data = {
            "question_id": item_id,
            "evaluation_metrics": metrics_json,
            "evaluation_error_reason": evaluation_error_str
        }
        
        # Cache the result
        save_to_cache(cache_key, result_data)
        
        current_span.set_status(trace.StatusCode.OK, "Evaluation for item completed.")
        return result_data

# Function to extract evaluator scores from results data
def extract_evaluator_scores(results_df):
    """Extract evaluator scores from the results dataframe for reporting"""
    metrics_df = pd.DataFrame()
    
    metrics_df["question_id"] = results_df["question_id"]
    
    # Parse evaluation_metrics for each row to extract scores
    def extract_score(row, score_key):
        metrics_json = row.get("evaluation_metrics")
        if metrics_json and isinstance(metrics_json, str):
            try:
                metrics = json.loads(metrics_json)
                score = metrics.get(score_key)
                return float(score) if score is not None else math.nan
            except:
                return math.nan
        return math.nan
    
    # Extract each score we're interested in
    metrics_df["LLM_Score_Overall"] = results_df.apply(
        lambda row: extract_score(row, "score_overall"), axis=1)
    
    metrics_df["LLM_Score_Functionality"] = results_df.apply(
        lambda row: extract_score(row, "score_functionality"), axis=1)
    
    metrics_df["LLM_Score_Completeness"] = results_df.apply(
        lambda row: extract_score(row, "score_completeness"), axis=1)
    
    metrics_df["LLM_Score_Code_Quality"] = results_df.apply(
        lambda row: extract_score(row, "score_code_quality"), axis=1)
    
    metrics_df["LLM_Score_Responsiveness"] = results_df.apply(
        lambda row: extract_score(row, "score_responsiveness"), axis=1)
    
    metrics_df["LLM_Score_UX_UI"] = results_df.apply(
        lambda row: extract_score(row, "score_ux_ui"), axis=1)
    
    # Extract summary presence
    def has_summary(row):
        metrics_json = row.get("evaluation_metrics")
        if metrics_json and isinstance(metrics_json, str):
            try:
                metrics = json.loads(metrics_json)
                summary = metrics.get("summary_overall")
                return bool(summary and str(summary).strip())
            except:
                return False
        return False
    
    metrics_df["LLM_Summary_Provided"] = results_df.apply(has_summary, axis=1)
    
    # Extract error presence
    metrics_df["LLM_Evaluation_Error"] = results_df["evaluation_error_reason"].apply(
        lambda x: bool(x and str(x).strip()))
    
    return metrics_df

@tracer.start_as_current_span("upload_results_to_phoenix_dataset_span")
def upload_results_to_phoenix_dataset(dataframe: pd.DataFrame, dataset_name: str, config: dict):
    """
    Uploads the results DataFrame to Arize Phoenix as a dataset.
    """
    current_span = trace.get_current_span()
    if not current_span.is_recording():
        logger.warning("Upload to Phoenix: No recording span, Phoenix upload attributes might be lost.")
        # Potentially start a new span here if absolutely necessary and no parent exists,
        # but ideally, this function is called within an active trace.

    current_span.set_attribute("phoenix.dataset.name_target", dataset_name)
    current_span.set_attribute("phoenix.dataset.num_rows", len(dataframe))
    current_span.set_attribute("phoenix.dataset.columns", json.dumps(dataframe.columns.tolist()))

    try:
        # Initialize Phoenix client
        logger.info(f"Initializing px.Client() for dataset upload to '{dataset_name}'.")
        phoenix_client = px.Client() 
        
        # Define input, output, and metadata for Phoenix
        input_keys = ["question", "enhanced_q"] 
        output_keys = ["response", "enhanced_r"]   
        
        all_columns = dataframe.columns.tolist()
        # Metadata keys are all other columns
        metadata_keys = [col for col in all_columns if col not in input_keys and col not in output_keys]
        
        actual_input_keys = [k for k in input_keys if k in all_columns]
        actual_output_keys = [k for k in output_keys if k in all_columns]

        # Critical check for core keys
        if "question" not in actual_input_keys:
            logger.error(f"Critical: 'question' column not found in DataFrame. Columns: {all_columns}. Aborting upload.")
            current_span.set_attribute("phoenix.dataset.upload_error", "Missing 'question' input_key")
            current_span.set_attribute("phoenix.dataset.upload_successful", False)
            return
        if "response" not in actual_output_keys and "response" in all_columns:
            logger.error(f"Critical: 'response' column found but not included in output_keys. Columns: {all_columns}. Aborting upload.")
            current_span.set_attribute("phoenix.dataset.upload_error", "Missing 'response' in output_keys")
            current_span.set_attribute("phoenix.dataset.upload_successful", False)
            return

        current_span.set_attribute("phoenix.dataset.input_keys_defined", json.dumps(input_keys))
        current_span.set_attribute("phoenix.dataset.output_keys_defined", json.dumps(output_keys))
        current_span.set_attribute("phoenix.dataset.input_keys_actual", json.dumps(actual_input_keys))
        current_span.set_attribute("phoenix.dataset.output_keys_actual", json.dumps(actual_output_keys))
        current_span.set_attribute("phoenix.dataset.metadata_keys_count", len(metadata_keys))

        logger.info(f"Attempting to upload DataFrame to Phoenix dataset: '{dataset_name}'")
        logger.info(f"Using Input keys: {actual_input_keys}")
        logger.info(f"Using Output keys: {actual_output_keys}")
        logger.info(f"Using Metadata keys ({len(metadata_keys)}): {metadata_keys[:10]}..." )

        # Handle potential mixed types for upload compatibility
        df_for_upload = dataframe.copy()
        
        # Process all string columns
        for col in df_for_upload.columns:
            if df_for_upload[col].dtype == 'object' or pd.api.types.is_bool_dtype(df_for_upload[col]):
                if df_for_upload[col].isna().any():
                    df_for_upload[col] = df_for_upload[col].astype(str).replace({'<NA>': None, 'nan': None, 'None': None})
        
        # Process all numeric columns - replace NaN and Infinity
        for col in df_for_upload.select_dtypes(include=['float', 'int']).columns:
            if df_for_upload[col].isna().any() or (df_for_upload[col].isin([float('inf'), float('-inf')])).any():
                df_for_upload[col] = df_for_upload[col].apply(lambda x: 
                    0.0 if pd.isna(x) else
                    1.0e308 if x == float('inf') else 
                    -1.0e308 if x == float('-inf') else x)
        
        # Process JSON columns for safety
        for col in df_for_upload.columns:
            if col.startswith("evaluation_") and "_metrics" in col:
                logger.info(f"Ensuring JSON safety of column: {col}")
                
                def ensure_json_safe(value):
                    if isinstance(value, str):
                        try:
                            # Try to parse JSON
                            parsed = json.loads(value)
                            # Apply float value processing
                            safe_parsed = handle_json_float_values(parsed)
                            # Serialize back
                            return json.dumps(safe_parsed)
                        except (json.JSONDecodeError, ValueError):
                            # If parsing failed, return empty JSON object
                            return '{}'
                    else:
                        # If value is not a string, return empty JSON object
                        return '{}'
                
                df_for_upload[col] = df_for_upload[col].apply(ensure_json_safe)

        dataset_response = phoenix_client.upload_dataset(
            dataframe=df_for_upload,
            dataset_name=dataset_name,
            input_keys=actual_input_keys,
            output_keys=actual_output_keys,
            metadata_keys=metadata_keys
        )
        
        logger.info(f"Successfully uploaded dataset to Phoenix: '{dataset_name}'. Phoenix Response/ID: {dataset_response.id if hasattr(dataset_response, 'id') else dataset_response}")
        current_span.set_attribute("phoenix.dataset.upload_successful", True)
        if hasattr(dataset_response, 'id'):
             current_span.set_attribute("phoenix.dataset.id", str(dataset_response.id))
             # Construct public URL if possible
             phoenix_ui_url = os.getenv("PHOENIX_UI_URL")
             if phoenix_ui_url:
                 logger.info(f"View dataset in Phoenix: {phoenix_ui_url}/datasets/{dataset_response.id}")
                 current_span.set_attribute("phoenix.dataset.ui_link", f"{phoenix_ui_url}/datasets/{dataset_response.id}")

        return dataset_response

    except Exception as e:
        error_msg = f"Error uploading dataset '{dataset_name}' to Phoenix: {e}"
        logger.error(error_msg, exc_info=True)
        current_span.set_attribute("phoenix.dataset.upload_error_type", type(e).__name__)
        current_span.record_exception(e)
        current_span.set_status(trace.StatusCode.ERROR, error_msg)
        current_span.set_attribute("phoenix.dataset.upload_successful", False)
        raise

async def generate_pipeline(config, pipeline_run_id: str):
    """Pipeline for generating code responses to questions."""
    start_time = time.time()
    logger.info(f"Starting Weby Generation Pipeline. Run ID: {pipeline_run_id}")
    logger.info(f"Pipeline Config: {config}")

    # Pass timeout to Weby client settings
    timeout_seconds = config.get("timeout_seconds", 600)
    os.environ["WEBY_CLIENT_TIMEOUT"] = str(timeout_seconds)
    logger.info(f"Setting client timeout to {timeout_seconds} seconds")

    pipeline_span = trace.get_current_span()
    pipeline_span.set_attribute("pipeline.run_id", pipeline_run_id)
    pipeline_span.set_attribute("pipeline.config", json.dumps(config))
    pipeline_span.set_attribute("pipeline.mode", PIPELINE_MODE_GENERATE)

    experiment_tag = config.get("phoenix_experiment_name", f"weby_gen_run_{pipeline_run_id[:8]}")
    logger.info(f"Using experiment tag for this run: {experiment_tag}")
    pipeline_span.set_attribute("phoenix.experiment.name_tag", experiment_tag)

    # Download dataset
    logger.info("Downloading and processing dataset from Hugging Face...")
    try:
        questions_df = download_and_process_dataset(
            dataset_name=config["dataset_name"],
            seed=config.get("dataset_seed"),
            limit=config.get("dataset_limit")
        )
        logger.info(f"Successfully loaded and processed dataset. Number of questions: {len(questions_df)}")
        pipeline_span.set_attribute("dataset.num_questions", len(questions_df))
        pipeline_span.set_attribute("dataset.loaded_successfully", True)
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}", exc_info=True)
        pipeline_span.record_exception(e)
        pipeline_span.set_status(trace.Status(trace.StatusCode.ERROR, f"Dataset loading failed: {e}"))
        pipeline_span.set_attribute("dataset.loaded_successfully", False)
        return

    if questions_df.empty:
        logger.warning("No questions loaded from the dataset. Skipping further processing.")
        pipeline_span.set_attribute("pipeline.status", "aborted_no_data")
        return

    # Store results from processing each question
    all_results = []
    max_retries = config.get("max_retries", 1)
    skip_enhancement_globally = config.get("skip_prompt_enhancement", False)
    max_concurrent = config.get("max_concurrent_tasks", 1)
    
    # Create a semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(question_text, framework, item_id, skip_prompt_enhancement):
        """Wrapper to process a question with semaphore for concurrency control"""
        async with semaphore:
            try:
                logger.info(f"Starting generation for item: {item_id}")
                result = await process_single_generation(
                    question=question_text,
                    framework=framework,
                    item_id=item_id,
                    skip_prompt_enhancement=skip_prompt_enhancement,
                    max_retries=max_retries,
                    files=config.get("files", []),
                    temperature=config.get("temperature", 0.6),
                    top_p=config.get("top_p", 0.95),
                    model=config.get("model")
                )
                logger.info(f"Completed generation for item: {item_id}")
                return result
            except Exception as e:
                logger.error(f"Error generating for item {item_id}: {str(e)}", exc_info=True)
                # Return a result with error information
                return {
                    "question_id": item_id,
                    "question": question_text,
                    "framework": framework,
                    "generation_error": str(e)
                }
    
    # Create tasks for all questions
    tasks = []
    for i, question_row in questions_df.iterrows():
        question_text = question_row.get("question", question_row.get("text", question_row.get("prompt")))
        if not question_text or not isinstance(question_text, str):
            logger.warning(f"Row {i} from source dataset lacks a valid question string. Skipping.")
            continue
        
        framework = config.get("framework", config.get("default_framework", "Nextjs"))
        item_id = f"{experiment_tag}_{pipeline_run_id[:4]}_{i}"
        
        task = process_with_semaphore(
            question_text=question_text,
            framework=framework,
            item_id=item_id,
            skip_prompt_enhancement=skip_enhancement_globally
        )
        tasks.append(task)
    
    # Run all tasks and collect results
    logger.info(f"Executing {len(tasks)} question generation tasks with max_concurrent={max_concurrent}")
    completed_results = await asyncio.gather(*tasks)
    all_results.extend([r for r in completed_results if r is not None])
    
    # Create a dataframe from the results
    if not all_results:
        logger.error("No valid generation results collected. Aborting.")
        pipeline_span.set_status(trace.StatusCode.ERROR, "No valid generation results collected")
        return
        
    results_df = pd.DataFrame(all_results)
    logger.info(f"Created generation results DataFrame with {len(results_df)} rows")
    
    # Upload results to Phoenix
    phoenix_dataset_name = f"{experiment_tag}_generated_{pipeline_run_id[:8]}"
    try:
        results_dataset = upload_results_to_phoenix_dataset(
            dataframe=results_df,
            dataset_name=phoenix_dataset_name,
            config=config
        )
        logger.info(f"Generation results uploaded to Phoenix dataset: {phoenix_dataset_name}")
        pipeline_span.set_attribute("phoenix.generation_dataset.name", phoenix_dataset_name)
        if hasattr(results_dataset, 'id'):
            pipeline_span.set_attribute("phoenix.generation_dataset.id", str(results_dataset.id))
            # Return dataset ID for evaluate_pipeline
            dataset_id = results_dataset.id
        else:
            dataset_id = phoenix_dataset_name  # Fallback to name if ID not available
    except Exception as e:
        logger.error(f"Failed to upload generation results to Phoenix: {e}", exc_info=True)
        pipeline_span.record_exception(e)
        pipeline_span.set_attribute("phoenix.generation_dataset.error", str(e))
        dataset_id = None
    
    end_time = time.time()
    duration = end_time - start_time
    pipeline_span.set_attribute("pipeline.duration_seconds", duration)
    logger.info(f"Generation pipeline finished in {duration:.2f} seconds. Run ID: {pipeline_run_id}")
    pipeline_span.set_status(trace.StatusCode.OK, "Generation pipeline completed successfully")
    
    return {
        "num_generated": len(results_df),
        "dataset_id": dataset_id,
        "dataset_name": phoenix_dataset_name,
        "duration_seconds": duration
    }

async def evaluate_pipeline(config, pipeline_run_id: str, generation_results=None, args=None):
    """Pipeline for evaluating previously generated code responses."""
    start_time = time.time()
    logger.info(f"Starting Weby Evaluation Pipeline. Run ID: {pipeline_run_id}")
    logger.info(f"Pipeline Config: {config}")

    pipeline_span = trace.get_current_span()
    pipeline_span.set_attribute("pipeline.run_id", pipeline_run_id)
    pipeline_span.set_attribute("pipeline.config", json.dumps(config))
    pipeline_span.set_attribute("pipeline.mode", PIPELINE_MODE_EVALUATE)

    experiment_tag = config.get("phoenix_experiment_name", f"weby_eval_run_{pipeline_run_id[:8]}")
    logger.info(f"Using experiment tag for this run: {experiment_tag}")
    pipeline_span.set_attribute("phoenix.experiment.name_tag", experiment_tag)

    # Get parameters from configuration
    dataset_id = config.get("evaluation_dataset_id")
    dataset_name = config.get("evaluation_dataset_name")
    # Additionally check how this name is passed from args
    if 'evaluation_dataset_name' not in config and dataset_name is None:
        # Maybe the name is passed in the main dataset_name parameter
        dataset_name = config.get("dataset_name")
        logger.info(f"Using alternate dataset_name from config: {dataset_name}")

    input_column = config.get("input_column", "question")
    output_column = config.get("output_column", "response")
    
    # Log received parameters and data types
    logger.info(f"Config keys: {list(config.keys())}")
    if dataset_id:
        logger.info(f"Using dataset ID from config: {dataset_id} (type: {type(dataset_id)})")
    if dataset_name:
        logger.info(f"Using dataset name from config: {dataset_name} (type: {type(dataset_name)})")
    logger.info(f"Using input column: {input_column}")
    logger.info(f"Using output column: {output_column}")

    try:
        # Initialize Phoenix client
        logger.info("Initializing Phoenix client...")
        phoenix_client = px.Client()
        logger.info("Phoenix client initialized for evaluation.")
        
        # Get dataset exactly according to format from user example
        logger.info(f"Getting dataset using name/version approach...")
        logger.info(f"Dataset name present: {bool(dataset_name)}, Dataset ID present: {bool(dataset_id)}")
        
        # Check parameter name in command line
        if args and hasattr(args, 'dataset_name') and args.dataset_name:
            logger.info(f"Args dataset_name value: {args.dataset_name}")
            # Override dataset_name from command line arguments
            dataset_name = args.dataset_name
            logger.info(f"Using dataset_name directly from args: {dataset_name}")
        
        try:
            # Direct use of example from your code
            if dataset_name and dataset_id and dataset_id.startswith("RGF0YXNldFZlcnNpb24"):
                logger.info(f"Getting dataset with name and version_id: name={dataset_name}, version_id={dataset_id}")
                dataset_to_evaluate = phoenix_client.get_dataset(name=dataset_name, version_id=dataset_id)
                logger.info(f"Successfully retrieved dataset version")
            elif dataset_name:
                # Get dataset by name only
                logger.info(f"Getting dataset by name: {dataset_name}")
                dataset_to_evaluate = phoenix_client.get_dataset(name=dataset_name)
                logger.info(f"Successfully retrieved dataset by name")
            elif dataset_id:
                # Get dataset by ID
                if dataset_id.startswith("RGF0YXNldFZlcnNpb24"):
                    raise ValueError("When using a dataset version ID, you must also specify the dataset name")
                else:
                    logger.info(f"Getting dataset by ID: {dataset_id}")
                    dataset_to_evaluate = phoenix_client.get_dataset(id=dataset_id)
                    logger.info(f"Successfully retrieved dataset by ID")
            else:
                raise ValueError("No dataset ID or name specified")
        except Exception as e:
            logger.error(f"Error retrieving dataset: {str(e)}")
            raise ValueError(f"Could not retrieve dataset: {str(e)}")
        
        if not dataset_to_evaluate:
            raise ValueError("Could not get a valid dataset for evaluation")
        
        logger.info(f"Successfully retrieved dataset: {dataset_to_evaluate.name if hasattr(dataset_to_evaluate, 'name') else 'unnamed dataset'}")
        
        # Определяем функцию оценки для Phoenix experiment
        async def evaluation_task(example):
            """Task function for Phoenix experiment"""
            try:
                # Получаем вопрос и ответ используя указанные колонки
                question = None
                response = None
                
                # Debug: Print the structure of the example object for troubleshooting
                try:
                    logger.info(f"Example object structure: {dir(example)}")
                    if hasattr(example, "input"):
                        logger.info(f"Example input type: {type(example.input)}")
                        if isinstance(example.input, dict):
                            logger.info(f"Example input keys: {example.input.keys()}")
                    if hasattr(example, "output"):
                        logger.info(f"Example output type: {type(example.output)}")
                        if isinstance(example.output, dict):
                            logger.info(f"Example output keys: {example.output.keys()}")
                except Exception as debug_e:
                    logger.warning(f"Error during debug logging: {debug_e}")
                
                # Try to get question from input data
                try:
                    if hasattr(example, "input") and example.input:
                        if isinstance(example.input, dict) and input_column in example.input:
                            question = example.input[input_column]
                            logger.info(f"Found question in example.input['{input_column}']")
                        else:
                            # Try more flexible column matching for input
                            input_attrs = [attr for attr in dir(example.input) if not attr.startswith('_')]
                            for attr in input_attrs:
                                attr_value = getattr(example.input, attr)
                                if isinstance(attr_value, str) and attr_value.strip():
                                    logger.info(f"Using '{attr}' as question with value: {attr_value[:50]}...")
                                    question = attr_value
                                    break
                            
                            if not question:  
                                available_columns = list(example.input.keys()) if isinstance(example.input, dict) else "not a dictionary"
                                logger.error(f"Input column '{input_column}' not found in example.input. Available columns: {available_columns}")
                except Exception as e:
                    logger.error(f"Error extracting question: {e}")
                
                # Try to get response from output data
                try:
                    if hasattr(example, "output") and example.output:
                        if isinstance(example.output, dict) and output_column in example.output:
                            response = example.output[output_column]
                            logger.info(f"Found response in example.output['{output_column}']")
                        else:
                            # Try more flexible column matching for output
                            output_attrs = [attr for attr in dir(example.output) if not attr.startswith('_')]
                            for attr in output_attrs:
                                attr_value = getattr(example.output, attr)
                                if isinstance(attr_value, str):
                                    logger.info(f"Using '{attr}' as response with value length: {len(attr_value) if attr_value else 0}")
                                    response = attr_value
                                    break
                            
                            if response is None:  # Use None check since empty string is valid
                                available_columns = list(example.output.keys()) if isinstance(example.output, dict) else "not a dictionary"
                                logger.error(f"Output column '{output_column}' not found in example.output. Available columns: {available_columns}")
                except Exception as e:
                    logger.error(f"Error extracting response: {e}")
                
                # Check if response is one of standard 'N/A' values, if yes, replace with empty string
                if response and isinstance(response, str) and response.startswith("N/A"):
                    logger.warning(f"Found N/A response value: '{response}'. Converting to empty string for evaluation.")
                    response = ""
                
                # For empty response, use empty string but continue evaluation
                if response is None:
                    response = ""
                    logger.warning(f"Using empty string for response")
                
                # Check if there is data for evaluation
                if not question:
                    error_msg = f"Could not extract question from dataset using column: {input_column}"
                    logger.error(f"Missing question in dataset example. {error_msg}")
                    return {
                        "evaluation_error_reason": error_msg
                    }
                
                # Log final data for debugging
                logger.info(f"Evaluating question (len={len(question)}) and response (len={len(response)})")
                if len(response) == 0:
                    logger.warning("Response is empty! Will evaluate an empty response.")
                
                # Generate unique ID for this evaluation
                item_id = f"{experiment_tag}_eval_{uuid.uuid4().hex[:8]}"
                
                # Call evaluation
                logger.info(f"Evaluating example with question: {question[:50]}...")
                evaluation_result = await process_single_evaluation(
                    question=question,
                    response_content=response,
                    item_id=item_id,
                    max_retries=config.get("max_retries", 1)
                )
                
                return evaluation_result
            
            except Exception as e:
                logger.error(f"Error processing example: {str(e)}")
                return {
                    "evaluation_error_reason": f"Error processing example: {str(e)}"
                }
        
        # Run Phoenix experiment with our evaluation function
        logger.info(f"Running Phoenix experiment for evaluation with tag: {experiment_tag}")
        experiment_object = px.experiments.run_experiment(
            dataset=dataset_to_evaluate,
            task=evaluation_task,
            evaluators=phoenix_evaluators,
            experiment_name=experiment_tag,
            concurrency=config.get("max_concurrent_tasks", 1)
        )
        
        logger.info(f"Phoenix experiment '{experiment_tag}' (ID: {experiment_object.id}) completed.")
        pipeline_span.set_attribute("phoenix.experiment.id", str(experiment_object.id))
        
    except Exception as e:
        logger.error(f"Error during Phoenix experiment for evaluation: {str(e)}")
        pipeline_span.record_exception(e)
        pipeline_span.set_status(trace.StatusCode.ERROR, f"Phoenix experiment error: {str(e)}")
        return None

    end_time = time.time()
    duration = end_time - start_time
    pipeline_span.set_attribute("pipeline.duration_seconds", duration)
    logger.info(f"Evaluation pipeline finished in {duration:.2f} seconds. Run ID: {pipeline_run_id}")
    pipeline_span.set_status(trace.StatusCode.OK, "Evaluation pipeline completed successfully")
    
    return {
        "duration_seconds": duration,
        "experiment_tag": experiment_tag,
        "experiment_id": experiment_object.id if 'experiment_object' in locals() else None
    }

async def main_pipeline(config, pipeline_run_id: str, args=None):
    """Main pipeline that coordinates the generation and evaluation phases."""
    start_time = time.time()
    logger.info(f"Starting Weby Full Pipeline. Run ID: {pipeline_run_id}")
    logger.info(f"Pipeline Config: {config}")

    pipeline_span = trace.get_current_span()
    pipeline_span.set_attribute("pipeline.run_id", pipeline_run_id)
    pipeline_span.set_attribute("pipeline.config", json.dumps(config))

    # Determine which pipeline modes to run
    pipeline_mode = config.get("pipeline_mode", PIPELINE_MODE_FULL)
    pipeline_span.set_attribute("pipeline.mode", pipeline_mode)
    
    run_generate = pipeline_mode in [PIPELINE_MODE_GENERATE, PIPELINE_MODE_FULL]
    run_evaluate = pipeline_mode in [PIPELINE_MODE_EVALUATE, PIPELINE_MODE_FULL]
    
    # Results to track across phases
    generation_results = None
    evaluation_results = None
    evaluation_enhanced_results = None
    dataset_download_result = None
    
    # 1. Run Generation Pipeline if needed
    if run_generate:
        logger.info("Starting Generation Phase...")
        generation_results = await generate_pipeline(config, pipeline_run_id)
        if not generation_results or not generation_results.get("dataset_id"):
            if run_evaluate and pipeline_mode == PIPELINE_MODE_FULL:
                logger.error("Generation phase failed to produce a dataset. Aborting evaluation phase.")
                run_evaluate = False
        logger.info(f"Generation Phase Completed: {generation_results}")
        
        # Download the generated dataset CSV if generation was successful
        if generation_results and generation_results.get("dataset_id"):
            logger.info("Starting dataset download...")
            phoenix_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
            api_key = os.getenv("PHOENIX_API_KEY")
            
            if phoenix_endpoint and api_key:
                dataset_download_result = await download_dataset_csv(
                    dataset_id=generation_results["dataset_id"],
                    phoenix_endpoint=phoenix_endpoint,
                    api_key=api_key
                )
                
                if dataset_download_result:
                    logger.info(f"Dataset download completed: {dataset_download_result['filename']}")
                    pipeline_span.set_attribute("dataset.download.successful", True)
                    pipeline_span.set_attribute("dataset.download.filepath", dataset_download_result["filepath"])
                else:
                    logger.warning("Dataset download failed")
                    pipeline_span.set_attribute("dataset.download.successful", False)
            else:
                logger.warning("PHOENIX_COLLECTOR_ENDPOINT or PHOENIX_API_KEY not found in environment. Skipping dataset download.")
                pipeline_span.set_attribute("dataset.download.skipped", True)
        
    # 2. Run Evaluation Pipeline if needed
    if run_evaluate:
        logger.info("Starting Evaluation Phase...")
        
        # If we are in full mode and have generation results, use their dataset for evaluation
        if pipeline_mode == PIPELINE_MODE_FULL and generation_results and generation_results.get("dataset_id"):
            # Create config copy for evaluation_pipeline with correct dataset data
            eval_config = config.copy()
            eval_config["evaluation_dataset_id"] = generation_results.get("dataset_id")
            eval_config["evaluation_dataset_name"] = generation_results.get("dataset_name")
            # Prevent using original dataset for evaluation
            if "dataset_name" in eval_config:
                del eval_config["dataset_name"]
            
            # 2.1 Evaluation for original questions and responses
            logger.info(f"Using generated dataset for evaluation of ORIGINAL responses: ID={generation_results.get('dataset_id')}, Name={generation_results.get('dataset_name')}")
            # Use standard columns question and response
            eval_config["input_column"] = "question"
            eval_config["output_column"] = "response"
            eval_config["phoenix_experiment_name"] = f"{eval_config.get('phoenix_experiment_name', 'weby_eval')}_original"
            
            evaluation_results = await evaluate_pipeline(eval_config, pipeline_run_id, generation_results, args)
            logger.info(f"Evaluation of ORIGINAL responses completed: {evaluation_results}")
            
            # 2.2 Evaluation for enhanced questions and responses
            logger.info(f"Using generated dataset for evaluation of ENHANCED responses: ID={generation_results.get('dataset_id')}, Name={generation_results.get('dataset_name')}")
            # Create new config for enhanced data evaluation
            eval_enhanced_config = eval_config.copy()
            eval_enhanced_config["input_column"] = "question"
            eval_enhanced_config["output_column"] = "enhanced_r"
            eval_enhanced_config["phoenix_experiment_name"] = f"{config.get('phoenix_experiment_name', 'weby_eval')}_enhanced"
            
            # Run second evaluation for enhanced prompts and responses
            evaluation_enhanced_results = await evaluate_pipeline(eval_enhanced_config, f"{pipeline_run_id}_enhanced", generation_results, args)
            logger.info(f"Evaluation of ENHANCED responses completed: {evaluation_enhanced_results}")
        else:
            # Use regular config for evaluate mode
            evaluation_results = await evaluate_pipeline(config, pipeline_run_id, generation_results, args)
            logger.info(f"Evaluation Phase Completed: {evaluation_results}")
    
    end_time = time.time()
    duration = end_time - start_time
    pipeline_span.set_attribute("pipeline.total_duration_seconds", duration)
    logger.info(f"Full pipeline finished in {duration:.2f} seconds. Run ID: {pipeline_run_id}")
    pipeline_span.set_status(trace.StatusCode.OK, "Pipeline completed successfully")
    
    return {
        "generation_results": generation_results,
        "evaluation_results": evaluation_results,
        "evaluation_enhanced_results": evaluation_enhanced_results,
        "dataset_download_result": dataset_download_result,
        "total_duration_seconds": duration
    }

if __name__ == "__main__":
    # Parse command line arguments for convenient launch
    parser = argparse.ArgumentParser(description="Weby Evaluation Pipeline")
    parser.add_argument("--mode", choices=["generate", "evaluate", "full"], 
                      default="full", help="Pipeline mode")
    parser.add_argument("--dataset-id", "--dataset_id", dest="dataset_id", 
                      help="Phoenix dataset ID for evaluation (e.g., RGF0YXNldDo0MQ==)")
    parser.add_argument("--dataset-name", "--dataset_name", dest="dataset_name",
                      help="Phoenix dataset name for evaluation (if ID is not provided)")
    parser.add_argument("--input-column", "--input_column", dest="input_column",
                      help="Column name to use for question input (e.g., 'question' or 'enhanced_q')")
    parser.add_argument("--output-column", "--output_column", dest="output_column",
                      help="Column name to use for response output (e.g., 'response' or 'enhanced_r')")
    parser.add_argument("--experiment-name", "--experiment_name", dest="experiment_name", 
                      default="weby_eval_run", help="Phoenix experiment name")
    parser.add_argument("--list-datasets", "--list_datasets", dest="list_datasets", action="store_true",
                      help="List all available datasets in Phoenix and exit")
    parser.add_argument("--limit", type=int, default=5, help="Dataset sample limit")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for dataset sampling")
    parser.add_argument("--concurrent", type=int, default=1, help="Max concurrent tasks")
    
    # New optional parameters for weby_client payload
    parser.add_argument("--files", nargs="*", default=[], help="Files to include in the payload")
    parser.add_argument("--temperature", type=float, default=0.6, help="Temperature parameter for generation")
    parser.add_argument("--top-p", "--top_p", dest="top_p", type=float, default=0.95, help="Top-p parameter for generation")
    parser.add_argument("--framework", default="Nextjs", help="Framework for code generation")
    parser.add_argument("--model", default=None, help="Model to use for generation")
    
    args = parser.parse_args()
    
    # Configure based on command line arguments
    pipeline_run_config = DEFAULT_CONFIG.copy()
    pipeline_run_config.update({
        "pipeline_mode": args.mode,
        "dataset_limit": args.limit,
        "dataset_seed": args.seed,
        "max_concurrent_tasks": args.concurrent,
        "phoenix_experiment_name": args.experiment_name,
        # Add new optional parameters
        "files": args.files,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "framework": args.framework,
        "model": args.model
    })
    
    # If dataset_id and evaluate mode are specified, add to configuration
    if args.dataset_id and args.mode == "evaluate":
        pipeline_run_config["evaluation_dataset_id"] = args.dataset_id
    
    # IMPORTANT: save dataset_name separately under explicitly different key
    if args.dataset_name:
        pipeline_run_config["evaluation_dataset_name"] = args.dataset_name
        logger.info(f"Added dataset_name to config: {args.dataset_name}")
    
    # Add specified column names if provided
    if args.input_column:
        pipeline_run_config["input_column"] = args.input_column
    
    if args.output_column:
        pipeline_run_config["output_column"] = args.output_column

    # Обработка аргумента list_datasets
    if args.list_datasets:
        try:
            # Initialize Phoenix client
            logger.info("Initializing Phoenix client...")
            phoenix_client = px.Client()
            
            logger.info("Unfortunately, listing datasets is not supported in this version of Phoenix API.")
            logger.info("Please use dataset ID or dataset name directly.")
            logger.info("If you have the ID, use: --dataset-id YOUR_ID")
            logger.info("If you have the name, use: --dataset-name YOUR_DATASET_NAME")
            exit(0)
        except Exception as e:
            logger.error(f"Error initializing Phoenix client: {str(e)}")
            exit(1)

    pipeline_run_id = str(uuid.uuid4())
    
    # Run pipeline
    logger.info(f"Starting pipeline with resolved config: {json.dumps(pipeline_run_config, indent=2)}")
    results = asyncio.run(main_pipeline(pipeline_run_config, pipeline_run_id, args))

    logger.info(f"Script finished with results: {json.dumps(results, indent=2)}")
    logger.info(f"Traces should be exported if OTLP endpoint and API key are correctly configured and reachable.")
    
    # Show where to find results in Phoenix UI
    experiment_name = pipeline_run_config.get("phoenix_experiment_name")
    logger.info(f"Check Phoenix UI for experiment: '{experiment_name}'")
    
    # Safely output dataset links
    generation_results = results.get("generation_results")
    if generation_results and isinstance(generation_results, dict) and generation_results.get("dataset_name"):
        logger.info(f"Generated code dataset: '{generation_results['dataset_name']}'")
    
    # Output dataset download information
    dataset_download_result = results.get("dataset_download_result")
    if dataset_download_result and isinstance(dataset_download_result, dict):
        logger.info(f"Dataset CSV downloaded: {dataset_download_result['filepath']}")
        logger.info(f"File size: {dataset_download_result['size_chars']} characters")
    
    # Handle evaluation results, considering possibility of multiple datasets
    evaluation_results = results.get("evaluation_results")
    if isinstance(evaluation_results, list):
        # Output for multiple datasets
        logger.info(f"Evaluation results for {len(evaluation_results)} datasets:")
        for i, result in enumerate(evaluation_results):
            if result and isinstance(result, dict):
                tag = result.get("experiment_tag") or "unknown"
                logger.info(f"  {i+1}. Experiment: '{tag}'")
    elif isinstance(evaluation_results, dict):
        # Output for single dataset
        tag = evaluation_results.get("experiment_tag")
        if tag:
            logger.info(f"Evaluation results: experiment '{tag}'")
            
    # Add detailed instructions for user
    logger.info("\n--- USAGE INSTRUCTIONS ---")
    logger.info("1. To evaluate a dataset using a regular dataset ID:")
    logger.info("   python main.py --mode evaluate --dataset-id YOUR_DATASET_ID --input-column question --output-column response --experiment-name original_eval")
    logger.info("\n2. To evaluate a dataset using its name:")
    logger.info("   python main.py --mode evaluate --dataset-name YOUR_DATASET_NAME --input-column question --output-column response --experiment-name original_eval")
    logger.info("\n3. To evaluate a specific version of a dataset (when you have version ID):")
    logger.info("   python main.py --mode evaluate --dataset-id RGF0YXNldFZlcnNpb246NDE= --dataset-name weby_nextjs_eval_run_v6_generated_d0b98120 --input-column question --output-column response --experiment-name original_eval")
    logger.info("\n4. To compare original vs. enhanced questions/responses, run two separate evaluations with different column names:")
    logger.info("   # For original questions/responses:")
    logger.info("   python main.py --mode evaluate --dataset-id YOUR_DATASET_ID --input-column question --output-column response --experiment-name original_eval")
    logger.info("   # For enhanced questions/responses:")
    logger.info("   python main.py --mode evaluate --dataset-id YOUR_DATASET_ID --input-column enhanced_q --output-column enhanced_r --experiment-name enhanced_eval")
    logger.info("\n5. Compare results in Phoenix UI for experiments 'original_eval' and 'enhanced_eval'")
    logger.info("\n6. Generated datasets are automatically downloaded as CSV files to the cache directory for offline analysis.")