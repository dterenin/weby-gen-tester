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
def session_cleanup(request):
    """
    Ensures a clean slate for every test session by deleting and recreating
    the --basetemp directory before any tests run.
    This fixture is now the foundational step for the session.
    """
    # This check ensures the cleanup code runs only on the master node, not on workers
    if not hasattr(request.config, "workerinput"):
        basetemp = request.config.getoption("basetemp", None)
        
        if basetemp:
            print(f"\nINFO: Pre-run cleanup: Deleting and recreating basetemp directory: {basetemp}")
            # Use ignore_errors=True to prevent crash if dir is in use or doesn't exist
            shutil.rmtree(basetemp, ignore_errors=True)
            try:
                os.makedirs(basetemp)
            except OSError as e:
                # This can happen in a race condition if another process is faster, but it's okay.
                print(f"Warning: Could not recreate basetemp dir, it might already exist: {e}")
    
    # Yield control to the test session
    yield

@pytest.fixture(scope="session", autouse=True)
def global_test_context(request, session_cleanup):
    """
    This fixture now explicitly depends on 'session_cleanup', guaranteeing
    it runs AFTER the temporary directory has been cleaned.
    """
    class GlobalConfig:
        def __init__(self, config):
            self.config = config
        
        def getoption(self, option_name):
            return self.config.getoption(option_name)

    pytest.global_test_context = GlobalConfig(request.config)
    
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
    
    if hasattr(pytest, 'global_test_context'):
        delattr(pytest, 'global_test_context')

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to access the test outcome in fixtures.
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)

@pytest.fixture(scope="session", autouse=True)
def worker_id_setup(request, session_cleanup):
    """
    This fixture also depends on 'session_cleanup' to ensure it runs
    after the environment is clean.
    """
    if hasattr(request.config, "workerinput"):
        pytest.worker_id = request.config.workerinput["workerid"]
    else:
        pytest.worker_id = "master"