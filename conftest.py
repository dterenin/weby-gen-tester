import pytest
import allure
import os
from datetime import datetime

def pytest_addoption(parser):
    """
    Registers custom command-line options for pytest.
    """
    parser.addoption(
        "--csv-output-field",
        action="store",
        default="output_tesslate_response",
        help="CSV field name for the LLM generated code (tesslate response)"
    )
    parser.addoption(
        "--csv-framework-field",
        action="store",
        default="metadata_framework",
        help="CSV field name for the framework metadata"
    )
    parser.addoption(
        "--csv-input-field",
        action="store",
        default="input_question",
        help="CSV field name for the input question"
    )

@pytest.fixture(scope="session", autouse=True)
def global_test_context(request):
    """
    A global pytest fixture that makes the pytest config accessible
    to functions that run during test collection (like load_test_data).
    """
    class GlobalConfig:
        def __init__(self, config):
            self.config = config
        
        def getoption(self, option_name):
            return self.config.getoption(option_name)

    # Attach the config to a pytest attribute for easy access
    pytest.global_test_context = GlobalConfig(request.config)
    
    # Create environment.properties with run timestamp
    run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    allure_results_dir = "allure-results"
    if not os.path.exists(allure_results_dir):
        os.makedirs(allure_results_dir)
    
    env_file = os.path.join(allure_results_dir, "environment.properties")
    with open(env_file, "w") as f:
        f.write(f"Test.Run.Timestamp={run_timestamp}\n")
        f.write("Test.Type=NextJS Site Generation\n")
        f.write("Framework=Playwright + pytest\n")
        f.write("Environment=Local Development\n")
    
    yield
    # Clean up the attribute after the test session completes
    delattr(pytest, 'global_test_context')