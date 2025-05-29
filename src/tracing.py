import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHttpSpanExporter # Explicitly HTTP
from opentelemetry.sdk.resources import Resource
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()

_TRACER_PROVIDER_INITIALIZED = False
_ACTUAL_TRACER_PROVIDER = None # Store the successfully configured provider

OTEL_SPAN_TYPE_LLM = "LLM" 
OTEL_SPAN_TYPE_CHAIN = "CHAIN" 
OTEL_SPAN_TYPE_RETRIEVER = "RETRIEVER"
OTEL_SPAN_TYPE_TOOL = "TOOL"

# OpenInference span attributes
OPENINFERENCE_SPAN_KIND = "openinference.span.kind" 

LLM_MODEL_NAME = "llm.model_name"
LLM_INVOCATION_PARAMETERS = "llm.invocation_parameters"
LLM_INPUT_MESSAGE_PREFIX = "llm.input_messages"
LLM_INPUT_VALUE = "input.value" 
LLM_OUTPUT_VALUE = "output.value"

def create_llm_span(tracer, span_name, model_name=None):
    """
    Creates an OpenTelemetry span of LLM type with proper attributes.
    
    Args:
        tracer: OpenTelemetry tracer
        span_name: Span name
        model_name: LLM model name (optional)
    
    Returns:
        OpenTelemetry span object
    """
    span = tracer.start_span(span_name)
    span.set_attribute(OPENINFERENCE_SPAN_KIND, OTEL_SPAN_TYPE_LLM)
    
    if model_name:
        span.set_attribute(LLM_MODEL_NAME, model_name)
    
    return span

def set_llm_input_output(span, input_text=None, output_text=None, model_name=None, 
                        temperature=None, top_p=None, input_tokens=None, 
                        output_tokens=None, total_tokens=None):
    """
    Sets LLM call attributes on the span according to OpenInference semantic conventions.
    
    Args:
        span: OpenTelemetry span
        input_text: Input text for LLM (string or list of messages)
        output_text: Output text from LLM
        model_name: LLM model name
        temperature: Generation temperature
        top_p: Top_p parameter for generation
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        total_tokens: Total number of tokens
    """
    # Set span type according to OpenInference
    span.set_attribute(OPENINFERENCE_SPAN_KIND, OTEL_SPAN_TYPE_LLM)
    
    # Set input data
    if input_text:
        # If input data is a list of messages (e.g., for chat models)
        if isinstance(input_text, list):
            for i, message in enumerate(input_text):
                if isinstance(message, dict) and 'role' in message and 'content' in message:
                    span.set_attribute(f"{LLM_INPUT_MESSAGE_PREFIX}.{i}.message.role", message['role'])
                    span.set_attribute(f"{LLM_INPUT_MESSAGE_PREFIX}.{i}.message.content", message['content'])
        else:
            # Simple input as string
            span.set_attribute(LLM_INPUT_VALUE, input_text)
    
    # Set output data
    if output_text:
        span.set_attribute(LLM_OUTPUT_VALUE, output_text)
    
    # Set model metadata
    if model_name:
        span.set_attribute(LLM_MODEL_NAME, model_name)
    
    # Collect invocation parameters into JSON string if present
    if temperature is not None or top_p is not None:
        invocation_params = {}
        if temperature is not None:
            invocation_params["temperature"] = temperature
        if top_p is not None:
            invocation_params["top_p"] = top_p
        
        span.set_attribute(LLM_INVOCATION_PARAMETERS, json.dumps(invocation_params))
    
    # Set token information if available
    if input_tokens is not None:
        span.set_attribute("llm.token_count.input", input_tokens)
    if output_tokens is not None:
        span.set_attribute("llm.token_count.output", output_tokens)
    if total_tokens is not None:
        span.set_attribute("llm.token_count.total", total_tokens)

def init_tracer_provider(service_name="weby-eval-pipeline"):
    global _TRACER_PROVIDER_INITIALIZED, _ACTUAL_TRACER_PROVIDER
    
    if _TRACER_PROVIDER_INITIALIZED:
        return _ACTUAL_TRACER_PROVIDER

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    
    otlp_endpoint = os.getenv("PHOENIX_ENDPOINT")
    phoenix_api_key = os.getenv("PHOENIX_API_KEY")

    if not otlp_endpoint:
        print("ERROR: PHOENIX_ENDPOINT environment variable not set. OpenTelemetry SaaS export will NOT be configured.")
        print("Traces will likely NOT be sent to Phoenix. Please set PHOENIX_ENDPOINT (e.g., https://your-phoenix-instance/v1/traces).")
        # In this case, we set up a provider but without an exporter to Phoenix.
        # Spans might be lost or go to a console exporter if one is added later for debugging.
    else:
        headers = {}
        if phoenix_api_key:

            headers["Authorization"] = f"{phoenix_api_key}" # Simplest form, some systems want "Bearer <key>"
            headers["Authorization"] = f"Bearer {phoenix_api_key}"
            print(f"OTLP Exporter: Using 'Authorization: Bearer <PHOENIX_API_KEY>' header for endpoint: {otlp_endpoint}")
        else:
            print(f"Warning: PHOENIX_API_KEY not set. OTLP export to {otlp_endpoint} may be unauthorized.")

        try:
            print(f"Configuring OTLPHttpSpanExporter for endpoint: {otlp_endpoint}")
            span_exporter = OTLPHttpSpanExporter(
                endpoint=otlp_endpoint, # Full URL: e.g. "https://collector.example.com/v1/traces"
                headers=headers if headers else None
            )
            provider.add_span_processor(BatchSpanProcessor(span_exporter))
            print("OTLP HTTP Span Exporter configured and added to the TracerProvider.")
        except Exception as e:
            print(f"ERROR: Failed to initialize or configure OTLPHttpSpanExporter: {e}")
            print("Traces will likely NOT be sent to Phoenix.")
            # If exporter setup fails, we proceed without it for now.

    try:
        trace.set_tracer_provider(provider)
        _ACTUAL_TRACER_PROVIDER = provider
        _TRACER_PROVIDER_INITIALIZED = True
        print(f"OpenTelemetry TracerProvider initialized (globally set) for service: {service_name}.")
        if not otlp_endpoint:
             print("Reminder: PHOENIX_ENDPOINT was not set, so no OTLP SaaS exporter is active.")

    except Exception as e:
        print(f"Error setting global TracerProvider: {e}. This should not happen if called early.")
        _ACTUAL_TRACER_PROVIDER = trace.get_tracer_provider() # Fallback to whatever is global
        _TRACER_PROVIDER_INITIALIZED = True # Mark as initialized to prevent re-attempts
        print("Continuing with existing global or unconfigured provider.")
        
    return _ACTUAL_TRACER_PROVIDER

def get_opentelemetry_tracer(tracer_name: str, version: str = "0.1.0"):
    if not _TRACER_PROVIDER_INITIALIZED:
        # This implies init_tracer_provider was not called or failed critically before setting the flag.
        print("Critical Error: TracerProvider not initialized. Call init_tracer_provider() at application start.")
        # Attempt a last-ditch initialization, though this is not ideal.
        init_tracer_provider() 
        if not _TRACER_PROVIDER_INITIALIZED: # If it still failed
             raise RuntimeError("TracerProvider could not be initialized. Tracing will fail.")

    # Get tracer from the globally set provider by init_tracer_provider
    # or the fallback provider if global setting failed.
    provider_to_use = trace.get_tracer_provider()
    if not provider_to_use or not hasattr(provider_to_use, 'get_tracer'):
        # This might happen if provider is NoOpTracerProvider
        print("Warning: Current global tracer provider is a NoOpTracerProvider or invalid. Spans may not be generated/exported.")
        # Fallback to the one we stored if it's valid and different
        if _ACTUAL_TRACER_PROVIDER and _ACTUAL_TRACER_PROVIDER is not provider_to_use:
            print("Attempting to use internally stored tracer provider.")
            return _ACTUAL_TRACER_PROVIDER.get_tracer(tracer_name, version)
        # else, we proceed and let OTel potentially use NoOp
            
    return trace.get_tracer(tracer_name, version)