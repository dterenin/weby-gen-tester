import os
import pickle
from datasets import load_dataset
import pandas as pd
from opentelemetry import trace # For trace.get_current_span() and trace.Status
from src.tracing import get_opentelemetry_tracer
from huggingface_hub import login

tracer = get_opentelemetry_tracer(__name__)

cache_dir = "cache"
os.makedirs(cache_dir, exist_ok=True)

# Initialize Hugging Face authentication
def init_huggingface_auth():
    """Initialize Hugging Face authentication using token from environment"""
    hf_token = os.getenv('HF_TOKEN')
    if hf_token:
        try:
            login(token=hf_token)
            print("Successfully authenticated with Hugging Face")
        except Exception as e:
            print(f"Failed to authenticate with Hugging Face: {e}")
    else:
        print("Warning: HF_TOKEN not found in environment variables")

def get_cached_dataset(dataset_name, seed, limit):
    """Retrieve cached dataset if available"""
    cache_key = f"dataset_{dataset_name.replace('/', '_')}_{seed}_{limit}"
    cache_file = os.path.join(cache_dir, f"{cache_key}.pkl")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                print(f"Using cached dataset: {dataset_name} (seed={seed}, limit={limit})")
                return pickle.load(f)
        except Exception as e:
            print(f"Failed to load cached dataset {dataset_name}: {e}")
    return None

def save_dataset_to_cache(dataset_name, seed, limit, dataframe):
    """Save dataset to cache"""
    cache_key = f"dataset_{dataset_name.replace('/', '_')}_{seed}_{limit}"
    cache_file = os.path.join(cache_dir, f"{cache_key}.pkl")
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(dataframe, f)
        print(f"Saved dataset to cache: {dataset_name} (seed={seed}, limit={limit})")
    except Exception as e:
        print(f"Failed to cache dataset {dataset_name}: {e}")

@tracer.start_as_current_span("download_and_process_dataset")
def download_and_process_dataset(dataset_name: str, seed=None, limit=None):
    """
    Downloads the dataset, extracts the 'question' column, 
    and applies optional seed and limit.
    Traced with OpenTelemetry.
    """
    # Initialize HF authentication before loading dataset
    init_huggingface_auth()
    
    cached_dataset = get_cached_dataset(dataset_name, seed, limit)
    if cached_dataset is not None:
        current_span = trace.get_current_span()
        current_span.set_attribute("dataset_loaded_from_cache", True)
        current_span.set_attribute("num_questions_processed", len(cached_dataset))
        return cached_dataset
    
    span = tracer.start_span("load_dataset_from_huggingface")
    try:
        # Load the dataset (will download if not cached)
        # The dataset viewer on Hugging Face shows a 'train' split.
        dataset = load_dataset(dataset_name, split='train', use_auth_token=True) # Use the argument here
        span.set_attribute("dataset_name", dataset_name) # And here for tracing
        span.set_attribute("num_rows_original", len(dataset))
        print(f"Successfully loaded dataset: {dataset_name} with {len(dataset)} rows.")
    except Exception as e:
        print(f"Error loading dataset: {e}")
        span.record_exception(e)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        raise
    finally:
        span.end()

    # Convert to pandas DataFrame for easier manipulation if needed, though not strictly necessary for this step
    # df = dataset.to_pandas()

    # Shuffle if seed is provided
    if seed is not None:
        span_shuffle = tracer.start_span("shuffle_dataset")
        dataset = dataset.shuffle(seed=seed)
        span_shuffle.set_attribute("seed", seed)
        span_shuffle.end()
        print(f"Shuffled dataset with seed: {seed}")

    # Limit the number of rows if limit is provided
    questions = dataset['question']
    if limit is not None:
        span_limit = tracer.start_span("limit_dataset")
        questions = questions[:limit]
        span_limit.set_attribute("limit", limit)
        span_limit.set_attribute("num_rows_after_limit", len(questions))
        span_limit.end()
        print(f"Limited dataset to {len(questions)} questions.")
    else:
        print(f"Using all {len(questions)} questions from the dataset.")

    current_span = trace.get_current_span()
    current_span.set_attribute("num_questions_processed", len(questions))
    
    questions_df = pd.DataFrame({'question': questions})
    
    save_dataset_to_cache(dataset_name, seed, limit, questions_df)
    
    return questions_df

if __name__ == '__main__':
    # Example Usage:
    from src.tracing import init_tracer # Ensure tracer is initialized
    init_tracer("data_loader_test_service") # Use a distinct service name for testing

    print("Fetching all questions...")
    # Provide a default dataset name for example usage if DATASET_NAME was removed
    example_dataset_name = "smirki/UIGEN-T1.1-TAILWIND"
    all_questions_df = download_and_process_dataset(dataset_name=example_dataset_name)
    print(f"Retrieved {len(all_questions_df)} questions.")
    if not all_questions_df.empty:
        print("First question:", all_questions_df['question'].iloc[0])

    print("\nFetching 5 questions with seed 42...")
    limited_questions_df = download_and_process_dataset(dataset_name=example_dataset_name, seed=42, limit=5)
    print(f"Retrieved {len(limited_questions_df)} questions.")
    for i, q in enumerate(limited_questions_df['question']):
        print(f"{i+1}. {q}")