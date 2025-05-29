import json
import os
import uuid
import phoenix as px
import pandas as pd # Added for DataFrame
import aiohttp # For async HTTP calls
from opentelemetry import trace # For trace.get_current_span() and trace.Status
from src.prompts import get_evaluation_prompts
from src.tracing import (
    get_opentelemetry_tracer, 
    set_llm_input_output, 
    OTEL_SPAN_TYPE_LLM,
    OPENINFERENCE_SPAN_KIND,
    LLM_MODEL_NAME,
    LLM_INPUT_VALUE,
    LLM_OUTPUT_VALUE
)
import time
import re
import math
from phoenix.experiments.evaluators import create_evaluator
import phoenix.experiments # For Score class
import logging

# Import necessary functions from other modules
from src.data_loader import download_and_process_dataset
from src.weby_client import call_weby_v1_generate

logger = logging.getLogger(__name__)

# Get tracer for this module
tracer = get_opentelemetry_tracer(__name__)

# Environment variables for the LLM Judge via OpenRouter
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("WARNING: OPENROUTER_API_KEY not set in .env. LLM evaluation will fail.")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "anthropic/claude-3-opus:beta") # Default to a fast model if not set

DEFAULT_EVAL_TIMEOUT = 300  # Значение по умолчанию (5 минут)
try:
    EVAL_TIMEOUT = int(os.getenv("WEBY_CLIENT_TIMEOUT", DEFAULT_EVAL_TIMEOUT))
    if EVAL_TIMEOUT > 600:
        logger.warning(f"WEBY_CLIENT_TIMEOUT value {EVAL_TIMEOUT} too high for evaluation, limiting to 600 seconds")
        EVAL_TIMEOUT = 600
except ValueError:
    logger.warning(f"Invalid WEBY_CLIENT_TIMEOUT value, using default: {DEFAULT_EVAL_TIMEOUT} seconds")
    EVAL_TIMEOUT = DEFAULT_EVAL_TIMEOUT

logger.info(f"Evaluation using timeout: {EVAL_TIMEOUT} seconds")

@tracer.start_as_current_span("create_phoenix_experiment_event") # Renamed to avoid confusion
def create_phoenix_experiment_event(experiment_name: str, parameters: dict = None):
    """
    Logs an experiment event to Phoenix OpenTelemetry.
    This is a simplified representation; Phoenix might have more specific ways to define/track experiments.
    """
    span = trace.get_current_span()
    experiment_id = str(uuid.uuid4())
    span.set_attribute("phoenix.experiment.name", experiment_name)
    span.set_attribute("phoenix.experiment.id", experiment_id)
    if parameters:
        for key, value in parameters.items():
            span.set_attribute(f"phoenix.experiment.param.{key}", str(value))

    try:
        # Log experiment creation details as an event on the current span
        event_payload = {
            "experiment_name": experiment_name,
            "experiment_id": experiment_id,
            "status": "started",
            "timestamp": time.time(),
            **(parameters if parameters else {})
        }
        span.add_event("experiment_created", attributes=event_payload)
        
        print(f"Phoenix experiment '{experiment_name}' (ID: {experiment_id}) logged as span event.")
        span.set_attribute("phoenix.log_successful", True) # Indicates we attempted to log
        return experiment_id
    except Exception as e:
        print(f"Error logging experiment '{experiment_name}' to Phoenix: {e}")
        span.record_exception(e)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        span.set_attribute("phoenix.log_successful", False)
        raise

@tracer.start_as_current_span("evaluate_response_with_llm_judge")
async def evaluate_response_with_llm_judge(question: str, response_content: str, experiment_id: str = None):
    """
    Evaluates a response using LLM as a judge.
    Returns a dictionary with metrics, error (if any).
    """
    span = trace.get_current_span()
    span.set_attribute(OPENINFERENCE_SPAN_KIND, OTEL_SPAN_TYPE_LLM)
    
    if not OPENROUTER_API_KEY:
        error_msg = "OPENROUTER_API_KEY not set in .env. Cannot call LLM judge."
        span.set_attribute("evaluation.error", error_msg)
        span.set_status(trace.StatusCode.ERROR, error_msg)
        return {"metrics": {}, "error": error_msg}

    if not question or not isinstance(question, str) or not question.strip():
        error_msg = "Question is empty or invalid."
        span.set_attribute("evaluation.error", error_msg)
        span.set_status(trace.StatusCode.ERROR, error_msg)
        return {"metrics": {}, "error": error_msg}

    # Handle case where response_content is None - convert to empty string
    if response_content is None:
        response_content = ""
        span.set_attribute("evaluation.empty_response", True)
        logger.warning("Response content is None, using empty string for evaluation")
    
    # Ensure response_content is a string
    if not isinstance(response_content, str):
        try:
            response_content = str(response_content)
            logger.warning(f"Converted non-string response to string: {type(response_content)}")
        except Exception as e:
            error_msg = f"Could not convert response_content to string: {str(e)}"
            span.set_attribute("evaluation.error", error_msg)
            span.set_status(trace.StatusCode.ERROR, error_msg)
            return {"metrics": {}, "error": error_msg}

    # Tag the evaluation with experiment_id (now item_id)
    if experiment_id:
        span.set_attribute("evaluation.experiment_id", experiment_id)

    # Get the evaluation prompts
    try:
        print("\n--- Calling LLM Judge (google/gemini-2.5-pro-preview) via OpenRouter ---")
        system_prompt, user_prompt_template = get_evaluation_prompts()
    except Exception as e:
        error_msg = f"Failed to get evaluation prompts: {str(e)}"
        span.set_attribute("evaluation.error", error_msg)
        span.record_exception(e)
        span.set_status(trace.StatusCode.ERROR, error_msg)
        return {"metrics": {}, "error": error_msg}
    
    try:
        formatted_user_prompt = user_prompt_template.format(
            question=question,
            response_content=response_content
        )
    except KeyError as e:
        error_msg = f"Error formatting user prompt template. Missing key: {e}. Template: {user_prompt_template}"
        print(error_msg)
        span.record_exception(KeyError(error_msg))
        span.set_status(trace.StatusCode.ERROR, error_msg)
        raise ValueError(error_msg)

    # Установка LLM-атрибутов для входных данных
    set_llm_input_output(
        span,
        input_text=formatted_user_prompt,
        model_name=JUDGE_MODEL
    )

    # Структурированные сообщения для LLM
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": formatted_user_prompt}
    ]

    payload = {
        "model": JUDGE_MODEL,
        "messages": messages,
        "response_format": { "type": "json_object" } # Request JSON output from the model
    }
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # Define a timeout for the API call
    client_timeout = aiohttp.ClientTimeout(total=EVAL_TIMEOUT)
    logger.debug(f"Using timeout for LLM judge: total={EVAL_TIMEOUT}s")

    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.post(
                f"{OPENROUTER_API_BASE}/chat/completions", 
                json=payload,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    error_msg = f"LLM Judge API returned non-200 status: {response.status}. Response: {error_text}"
                    span.set_attribute("evaluation.error", error_msg)
                    span.set_status(trace.StatusCode.ERROR, error_msg)
                    return {"metrics": {}, "error": error_msg}
                
                response_data = await response.json()
                
                if "choices" in response_data and response_data["choices"]:
                    llm_message_response = response_data["choices"][0]["message"]
                    llm_response_str = llm_message_response.get("content", "")
                    
                    # Установка выходных данных LLM
                    set_llm_input_output(
                        span,
                        output_text=llm_response_str
                    )
                    
                    # Добавление информации о токенах, если доступно
                    usage = response_data.get("usage")
                    if usage:
                        set_llm_input_output(
                            span,
                            input_tokens=usage.get("prompt_tokens", 0),
                            output_tokens=usage.get("completion_tokens", 0),
                            total_tokens=usage.get("total_tokens", 0)
                        )
                    
                    span.add_event("Received and parsed LLM Judge API response")
                else:
                    error_msg = "LLM Judge response malformed: No choices found."
                    print(error_msg)
                    print(f"Full LLM response: {response_data}")
                    span.set_status(trace.StatusCode.ERROR, error_msg)
                    span.set_attribute("llm_judge_raw_response", str(response_data)[:1000]) # Log part of raw response
                    llm_response_str = json.dumps({"error": error_msg, "details": "Response structure unexpected"})
                
                # Try to parse the evaluation metrics from the LLM response
                try:
                    # Handle common issues: Sometimes the model outputs a code block with JSON instead of pure JSON
                    if "```json" in llm_response_str:
                        # Extract JSON from code block
                        match = re.search(r"```json\s*([\s\S]*?)\s*```", llm_response_str)
                        if match:
                            llm_response_str = match.group(1).strip()
                    elif "```" in llm_response_str:
                        # Try to extract from any code block
                        match = re.search(r"```\s*([\s\S]*?)\s*```", llm_response_str)
                        if match:
                            llm_response_str = match.group(1).strip()
                    
                    llm_response_str = ''.join(c for c in llm_response_str if c.isprintable() or c in ['\n', '\t', ' '])
                
                    # Parse the JSON response
                    try:
                        eval_metrics = json.loads(llm_response_str)
                    except json.JSONDecodeError as json_err:
                        logger.warning(f"Failed to parse JSON directly: {json_err}. Trying to extract JSON subset.")
                        json_match = re.search(r'(\{.*\})', llm_response_str, re.DOTALL)
                        if json_match:
                            try:
                                eval_metrics = json.loads(json_match.group(1))
                                logger.info("Successfully extracted JSON subset from response")
                            except json.JSONDecodeError:
                                logger.error("JSON extraction failed. Creating default metrics.")
                                eval_metrics = create_default_evaluation_metrics()
                        else:
                            logger.error("No JSON-like structure found in the response. Creating default metrics.")
                            eval_metrics = create_default_evaluation_metrics()
                    
                    processed_metrics = handle_json_float_values(eval_metrics)
                    
                    required_fields = [
                        "score_overall", "score_functionality", "score_completeness", 
                        "score_code_quality", "score_responsiveness", "score_ux_ui", 
                        "summary_overall"
                    ]
                    
                    for field in required_fields:
                        if field not in processed_metrics or processed_metrics[field] is None:
                            if field == "summary_overall":
                                processed_metrics[field] = "No summary provided by evaluation model"
                            else:
                                processed_metrics[field] = 0.0
                    
                    # Двойная проверка - убедимся, что сериализация работает
                    try:
                        json.dumps(processed_metrics)
                    except Exception as e:
                        logger.error(f"Final JSON serialization check failed: {e}")
                        processed_metrics = create_default_evaluation_metrics()
                    
                    span.set_attribute("evaluation.metrics", json.dumps(processed_metrics))
                    print("Successfully parsed LLM judge response.")
                    span.set_status(trace.StatusCode.OK)
                    return {"metrics": processed_metrics}
                except Exception as e:
                    error_msg = f"Failed to parse LLM judge response: {str(e)}"
                    print(error_msg)
                    print(f"Raw response: {llm_response_str[:1000]}")
                    span.set_attribute("evaluation.error", error_msg)
                    span.record_exception(e)
                    span.set_status(trace.StatusCode.ERROR, error_msg)
                    default_metrics = create_default_evaluation_metrics()
                    return {"metrics": default_metrics, "error": error_msg}
                
    except aiohttp.ClientError as e:
        error_msg = f"Network error calling LLM judge API: {str(e)}"
        print(error_msg)
        span.set_attribute("evaluation.error", error_msg)
        span.record_exception(e)
        span.set_status(trace.StatusCode.ERROR, error_msg)
        default_metrics = create_default_evaluation_metrics()
        return {"metrics": default_metrics, "error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error calling LLM judge: {str(e)}"
        print(error_msg)
        span.set_attribute("evaluation.error", error_msg)
        span.record_exception(e)
        span.set_status(trace.StatusCode.ERROR, error_msg)
        default_metrics = create_default_evaluation_metrics()
        return {"metrics": default_metrics, "error": error_msg}

def create_default_evaluation_metrics():
    """Создаёт стандартный набор метрик для случаев, когда не удалось получить оценку"""
    return {
        "score_overall": 0.0,
        "score_functionality": 0.0,
        "score_completeness": 0.0,
        "score_code_quality": 0.0,
        "score_responsiveness": 0.0,
        "score_ux_ui": 0.0,
        "summary_overall": "Evaluation failed to generate valid metrics"
    }

# --- Phoenix Experiment Task Definition ---
async def weby_generation_task(example: dict):
    """
    Task function for Phoenix experiment.
    Takes a dataset example, calls weby_v1_generate, and returns its output.
    """
    current_task_span = trace.get_current_span() 
    question = example["input"]["question"] 
    current_task_span.set_attribute("task.input.question", question)

    generation_result = await call_weby_v1_generate(question)
    
    current_task_span.set_attribute("task.output.status_code", generation_result.get("status_code"))
    if "error" in generation_result:
        current_task_span.set_attribute("task.output.error", generation_result["error"])
        return {
            "response_content": None, 
            "error": generation_result["error"],
            "status_code": generation_result.get("status_code"),
            "raw_weby_response": generation_result.get("raw_response")
        }
    
    response_content = generation_result.get("code", "")
    current_task_span.set_attribute("task.output.response_content_length", len(response_content if response_content else ""))

    return {
        "response_content": response_content,
        "error": None, 
        "status_code": generation_result.get("status_code"),
        "raw_weby_response": generation_result.get("raw_response")
    }

# --- Phoenix Experiment Evaluator Definitions ---
async def _base_llm_judge_evaluator(output: dict, input: dict, criterion: str):
    """Helper function to call LLM judge and extract a specific criterion."""
    eval_span = trace.get_current_span()
    question = input["question"]
    
    if output.get("error") or output.get("response_content") is None:
        eval_span.set_attribute(f"evaluator.llm_judge_{criterion}.skipped", "Task produced error or no content")
        return px.experiments.Score(value=0.0, explanation="Task failed or no content")

    response_content = output["response_content"]
    eval_span.set_attribute(f"evaluator.llm_judge_{criterion}.input.question_length", len(question))
    eval_span.set_attribute(f"evaluator.llm_judge_{criterion}.input.response_length", len(response_content))

    # Assuming experiment_id is not strictly needed by evaluate_response_with_llm_judge for Phoenix runs
    evaluation_results = await evaluate_response_with_llm_judge(question, response_content)
    
    criterion_data = evaluation_results.get(criterion, {})
    score = criterion_data.get("score", 0.0)
    justification = criterion_data.get("justification", "")
    if criterion == "overall":
        justification = f"Summary: {criterion_data.get('summary', '')} | Justification: {justification}"

    eval_span.set_attribute(f"evaluator.llm_judge_{criterion}.score", score)
    eval_span.set_attribute(f"evaluator.llm_judge_{criterion}.justification", justification)
    
    return px.experiments.Score(value=float(score), explanation=justification)

async def llm_judge_overall_score_evaluator(output: dict, input: dict):
    return await _base_llm_judge_evaluator(output, input, "overall")

async def llm_judge_functionality_score_evaluator(output: dict, input: dict):
    return await _base_llm_judge_evaluator(output, input, "functionality")

async def llm_judge_completeness_score_evaluator(output: dict, input: dict):
    return await _base_llm_judge_evaluator(output, input, "completeness")

async def llm_judge_code_quality_score_evaluator(output: dict, input: dict):
    return await _base_llm_judge_evaluator(output, input, "code_quality")

async def llm_judge_responsiveness_score_evaluator(output: dict, input: dict):
    return await _base_llm_judge_evaluator(output, input, "responsiveness")

async def llm_judge_ux_ui_score_evaluator(output: dict, input: dict):
    return await _base_llm_judge_evaluator(output, input, "ux_ui")

def handle_json_float_values(data):
    """
    Обрабатывает специальные значения float (NaN, Infinity, -Infinity),
    заменяя их на значения, которые можно сериализовать в JSON.
    Также обрабатывает очень большие или маленькие float значения, которые могут вызвать проблемы.
    """
    if isinstance(data, dict):
        return {k: handle_json_float_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [handle_json_float_values(item) for item in data]
    elif isinstance(data, float):
        try:
            if math.isnan(data):
                return 0.0  # Replace NaN with 0.0
            elif math.isinf(data) and data > 0:
                return 1.0e308  # Replace +Infinity with largest valid float
            elif math.isinf(data) and data < 0:
                return -1.0e308  # Replace -Infinity with smallest valid float
                
            json.dumps(data)
            return data
        except (OverflowError, ValueError):
            if data > 0:
                return 1.0e308 
            else:
                return -1.0e308 
    elif data is None:
        return None
    return data

if __name__ == '__main__':
    import asyncio
    import nest_asyncio
    from phoenix.experiments import run_experiment # Import run_experiment

    nest_asyncio.apply()
    
    async def main_eval():
        from src.tracing import init_tracer
        # Initialize OpenTelemetry tracer provider
        # This should ideally be done once at the application entry point.
        init_tracer("evaluation_pipeline_service")

        # 1. Launch Phoenix app (if not already running elsewhere)
        # px.launch_app() # Typically called once.
        # For scripted runs, ensure the Phoenix server/collector is accessible.
        # If running locally with `phoenix server`, this might not be needed here.
        # If it's a separate Phoenix instance, ensure PHOENIX_ENDPOINT is set.
        print("Ensure Phoenix server/collector is running and accessible.")


        # 2. Load data using your data_loader
        print("Downloading and processing dataset...")
        # Using a small limit for testing purposes
        questions_df = download_and_process_dataset(seed=42, limit=3) 
        if questions_df.empty:
            print("No questions loaded, exiting.")
            return
        print(f"Loaded {len(questions_df)} questions for the experiment.")

        # 3. Initialize Phoenix client and upload dataset
        try:
            px_client = px.Client() # Assumes Phoenix server is running/configured
            print("Phoenix client initialized.")
            dataset = px_client.upload_dataset(
                dataframe=questions_df,
                dataset_name="uigens-tailwind-questions-eval", # Descriptive name
                input_keys=["question"], 
                # output_keys=[], # No reference outputs in this dataset
                # metadata_keys=[]
            )
            print(f"Dataset '{dataset.name}' uploaded/retrieved with {len(dataset.examples)} examples.")
        except Exception as e:
            print(f"Error initializing Phoenix client or uploading dataset: {e}")
            print("Please ensure Phoenix server is running and accessible, and PHOENIX_ENDPOINT is correctly set in .env if needed.")
            return

        # 4. Define evaluators list
        evaluators_list = [
            llm_judge_overall_score_evaluator,
            llm_judge_functionality_score_evaluator,
            llm_judge_completeness_score_evaluator,
            llm_judge_code_quality_score_evaluator,
            llm_judge_responsiveness_score_evaluator,
            llm_judge_ux_ui_score_evaluator,
        ]

        # 5. Define experiment metadata (optional, but good practice)
        experiment_params = {
            "weby_model_version": "v1_generate_default", # Example parameter
            "judge_llm_model": JUDGE_MODEL,
            "dataset_slice_config": "seed_42_limit_3"
        }
        
        # The old `create_phoenix_experiment_event` was for OTel events, not Phoenix experiments.
        # Example:
        # exp_event_id = create_phoenix_experiment_event("TestNavExperiment_OTelEvent", 
        #                                            {"llm_version": "gpt-4-turbo", "dataset_slice": "first_10"})
        # print(f"Logged OpenTelemetry experiment event: {exp_event_id}")


        print("Running Phoenix experiment...")
        try:
            # Run the experiment
            experiment = await run_experiment( # Use await as task and evaluators are async
                dataset=dataset,
                task=weby_generation_task,
                evaluators=evaluators_list,
                experiment_name="weby-tailwind-llm-judge-eval-run", # Descriptive name
                experiment_metadata=experiment_params,
                # concurrency=2 # Optional: control concurrency
            )
            print(f"Phoenix experiment '{experiment.name}' run completed.")
            if hasattr(experiment, 'url') and experiment.url:
                 print(f"View experiment details at: {experiment.url}")
            else:
                print("Experiment details can be viewed in the Phoenix UI if connected.")
            
        except Exception as e:
            print(f"Error during Phoenix experiment run: {e}")
            import traceback
            traceback.print_exc()


    asyncio.run(main_eval()) 