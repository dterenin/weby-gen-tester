# conftest.py
import pytest
import os
from datetime import datetime
import shutil

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
    to functions that run during test collection (like load_test_data)
    and handles session-level setup and teardown.
    """
    class GlobalConfig:
        def __init__(self, config):
            self.config = config
        
        def getoption(self, option_name):
            return self.config.getoption(option_name)

    # Attach the config to a pytest attribute for easy access
    pytest.global_test_context = GlobalConfig(request.config)
    
    # Create environment.properties for Allure report
    allure_results_dir = request.config.getoption("--alluredir") or "allure-results"
    if not os.path.exists(allure_results_dir):
        os.makedirs(allure_results_dir)
    
    env_file = os.path.join(allure_results_dir, "environment.properties")
    run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(env_file, "w") as f:
        f.write(f"Test.Run.Timestamp={run_timestamp}\n")
        f.write("Test.Type=NextJS Site Generation\n")
        f.write("Framework=Playwright + pytest\n")
        f.write("Environment=Local Development\n")
    
    yield
    
    # Clean up the attribute after the test session completes
    if hasattr(pytest, 'global_test_context'):
        delattr(pytest, 'global_test_context')

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to access the test outcome in fixtures.
    This is executed for each test phase (setup, call, teardown) and is
    essential for the automatic cleanup logic.
    """
    # Execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # Store the report outcome in the test item node for each phase.
    # This creates attributes on the test item like `rep_setup`, `rep_call`, `rep_teardown`.
    setattr(item, "rep_" + rep.when, rep)

@pytest.fixture(scope="session", autouse=True)
def worker_id_setup(request):
    """
    Makes the xdist worker ID available to other fixtures.
    This is necessary for creating per-worker golden templates.
    """
    # The 'workerinput' attribute is only present when running under pytest-xdist.
    if hasattr(request.config, "workerinput"):
        # e.g., "gw0", "gw1", etc.
        pytest.worker_id = request.config.workerinput["workerid"]
    else:
        # For non-parallel runs
        pytest.worker_id = "master"