# test_nextjs_site.py
# Test file for NextJS site generation and validation
import pytest
import os
import time
import requests
from playwright.sync_api import Playwright
import subprocess
import glob
import csv
import allure
import json
from pytest_assume.plugin import assume
import socket
import contextlib
from datetime import datetime
import shutil

# Import functions from your business logic module
# Make sure gen_site_logic.py is the correct filename and path
from gen_site_logic import process_generated_site, create_golden_template

# --- CONFIGURATION ---
RECORD_VIDEO = False
# The repository URL is now centralized here for consistency
NEXTJS_REPO_URL = "https://github.com/dterenin/weby-nextjs-template"

# Fallback LLM response for when CSV loading fails
LLM_TEST_RESPONSE_FALLBACK = """
<Edit filename="src/app/page.tsx">
export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <main className="flex flex-1 flex-col items-center justify-center p-4 text-center">
        <h1 className="text-4xl font-bold">Fallback Page!</h1>
        <p className="mt-2 text-lg text-muted-foreground">
          This is a fallback page content because no CSV data was found or valid.
        </p>
      </main>
    </div>
  );
}
</Edit>
"""

def get_free_port() -> int:
    """Get a free port for the next test."""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def load_test_data(csv_filepath=None):
    """Loads test data from a CSV file or uses fallback data."""
    test_cases = []
    # Use the globally stored config from conftest.py
    config = getattr(pytest, 'global_test_context', None)
    
    output_response_field = "output_response"
    framework_field = "metadata_framework"
    input_question_field = "input_question"

    if config and hasattr(config, "getoption"):
        output_response_field = config.getoption("csv_output_field") or output_response_field
        framework_field = config.getoption("csv_framework_field") or framework_field
        input_question_field = config.getoption("csv_input_field") or input_question_field
    
    if csv_filepath is None:
        datasets_dir = "datasets"
        if os.path.exists(datasets_dir):
            csv_files = glob.glob(os.path.join(datasets_dir, "*.csv"))
            if csv_files:
                csv_filepath = max(csv_files, key=os.path.getmtime)
                print(f"INFO: Using most recent CSV file: {csv_filepath}")
            else:
                print(f"WARNING: No CSV files found in {datasets_dir} folder. Using fallback.")
                return [("fallback_site_0", LLM_TEST_RESPONSE_FALLBACK, "Fallback: No CSV files in datasets")]
        else:
            print(f"WARNING: {datasets_dir} folder not found. Using fallback.")
            return [("fallback_site_0", LLM_TEST_RESPONSE_FALLBACK, "Fallback: datasets folder not found")]
    
    if not os.path.exists(csv_filepath):
        print(f"WARNING: CSV file not found: {csv_filepath}. Using fallback for one test.")
        return [("fallback_site_0", LLM_TEST_RESPONSE_FALLBACK, "Fallback: CSV not found")]

    with open(csv_filepath, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        if not reader.fieldnames:
            print(f"WARNING: CSV {csv_filepath} is empty or headerless. Using fallback.")
            return [("fallback_site_1", LLM_TEST_RESPONSE_FALLBACK, "Fallback: CSV empty/headerless")]
        
        for i, row in enumerate(reader):
            tesslate_response = row.get(output_response_field, '')
            framework = row.get(framework_field, '')
            input_question = row.get(input_question_field, f"CSV row {i+1}: No input question")
            if framework == 'Nextjs' and '<Edit filename="' in tesslate_response:
                test_cases.append((f"site_{i}", tesslate_response, input_question))
    
    if not test_cases and os.path.exists(csv_filepath):
        pytest.skip(f"No valid Next.js test cases with <Edit> blocks found in {csv_filepath}. Skipping tests.")
    return test_cases

@pytest.fixture(scope="session")
def golden_template_dir(tmp_path_factory):
    """
    PERFORMANCE: Creates a "golden image" which is a full local git repository
    with node_modules pre-installed. This is done ONCE per test session.
    """
    golden_dir_base = tmp_path_factory.mktemp("golden_template_base")
    print(f"\n[{time.strftime('%H:%M:%S')}] Creating golden template in {golden_dir_base} for the session...")
    
    try:
        # Assuming gen_site_logic.py has a working create_golden_template function
        from gen_site_logic import create_golden_template
        template_path = create_golden_template(str(golden_dir_base), NEXTJS_REPO_URL)
        if not template_path:
             pytest.fail("Failed to create the golden template using gen_site_logic.create_golden_template.")
    except ImportError:
        pytest.fail("Error: 'create_golden_template' not found in 'gen_site_logic'. Please ensure it's defined and imported correctly.")
    except Exception as e:
        pytest.fail(f"An error occurred during golden template creation: {e}")

    print(f"[{time.strftime('%H:%M:%S')}] Golden template created successfully at {template_path}")
    yield template_path


@pytest.fixture(scope="function", params=load_test_data())
def site_data_and_tmp_dir(tmp_path_factory, request, golden_template_dir):
    """
    PERFORMANCE: Uses `git clone` from the local golden template.
    Also handles automatic cleanup of the test directory, preserving it on failure.
    """
    site_identifier, tesslate_response_content, input_question = request.param
    test_run_dir = tmp_path_factory.mktemp(f"test_run_{site_identifier.replace('/', '_')}")
    site_build_path = os.path.join(test_run_dir, f"site_{site_identifier.replace('/', '_')}")

    print(f"[{time.strftime('%H:%M:%S')}] Cloning local golden template to {site_build_path} for test {site_identifier}...")
    try:
        subprocess.run(['git', 'clone', golden_template_dir, site_build_path], check=True, capture_output=True)
        git_dir_path = os.path.join(site_build_path, ".git")
        if os.path.exists(git_dir_path):
            shutil.rmtree(git_dir_path)
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to clone local golden template. Stderr: {e.stderr.decode()}")
    except FileNotFoundError:
        pytest.fail("'git' command not found.")

    print(f"[{time.strftime('%H:%M:%S')}] Local clone complete for {site_identifier}.")
    
    active_subprocesses = [] 

    # Yield control to the test function
    yield str(site_build_path), tesslate_response_content, input_question, site_identifier, active_subprocesses
    
    # --- POST-TEST CLEANUP (Executed after the test function returns) ---
    print(f"\n[{time.strftime('%H:%M:%S')}] Initiating cleanup for test: '{site_identifier}'")

    for proc in active_subprocesses:
        if proc.poll() is None:
            print(f"[{time.strftime('%H:%M:%S')}] Terminating lingering process (PID: {proc.pid})...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"[{time.strftime('%H:%M:%S')}] Process {proc.pid} did not terminate gracefully, killing.")
                proc.kill()
                proc.wait(timeout=5)

    # CORRECTED and MORE ROBUST CLEANUP LOGIC
    # This logic uses the 'rep_call' attribute set by the hook in conftest.py
    # to determine if the test failed, and preserves the directory in that case.
    test_failed = not hasattr(request.node, 'rep_call') or request.node.rep_call.failed

    if not test_failed:
        print(f"[{time.strftime('%H:%M:%S')}] Test '{site_identifier}' PASSED. Cleaning up directory {test_run_dir}...")
        shutil.rmtree(test_run_dir, ignore_errors=True)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Test '{site_identifier}' FAILED. Directory PRESERVED for analysis at: {test_run_dir}")


def wait_for_nextjs_server(url, timeout=180, poll_interval=3):
    """Polls a URL until it returns a 200 status or times out."""
    print(f"Waiting for Next.js server at {url} (timeout: {timeout}s)...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=poll_interval)
            response.raise_for_status()
            if response.status_code == 200:
                print(f"Server at {url} is ready.")
                return True
        except requests.exceptions.RequestException:
            time.sleep(poll_interval)
    raise TimeoutError(f"Next.js server at {url} did not become ready within {timeout} seconds.")

def convert_webm_to_gif(webm_path, gif_path):
    """
    Converts a .webm video to a .gif using ffmpeg. This function is compute-intensive.
    """
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"Warning: FFmpeg not found or not working ({e}). Skipping GIF conversion.")
        return False
        
    palette_path = os.path.join(os.path.dirname(gif_path), "palette.png")
    try:
        palette_gen_cmd = [
            'ffmpeg', '-loglevel', 'error', '-i', webm_path, 
            '-vf', 'fps=10,scale=640:-1:flags=lanczos,palettegen', '-y', palette_path
        ]
        subprocess.run(palette_gen_cmd, check=True, capture_output=True, text=True)
        
        gif_convert_cmd = [
            'ffmpeg', '-loglevel', 'error', '-i', webm_path, '-i', palette_path, 
            '-lavfi', 'fps=10,scale=640:-1:flags=lanczos[x];[x][1:v]paletteuse', 
            '-loop', '0', '-y', gif_path
        ]
        subprocess.run(gif_convert_cmd, check=True, capture_output=True, text=True)
        print(f"GIF conversion successful: {gif_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg conversion failed. CMD: {' '.join(e.cmd)}\nStderr: {e.stderr}\nStdout: {e.stdout}")
    except Exception as e_conv:
        print(f"Unexpected error during GIF conversion: {e_conv}")
    finally:
        if os.path.exists(palette_path):
            os.remove(palette_path)
    return False

def get_error_summary_from_stderr(stderr_text: str, max_lines: int = 10) -> str:
    """Extracts a concise summary of errors from a stderr string."""
    if not stderr_text or not stderr_text.strip():
        return "No STDERR content."
    lines = stderr_text.strip().splitlines()
    error_keywords = ["error", "failed", "typeerror", "cannot find", "is not assignable"]
    relevant_lines = [line for line in lines if any(keyword in line.lower() for keyword in error_keywords)]
    if relevant_lines:
        return "\nRelevant STDERR lines:\n" + "\n".join(relevant_lines[:max_lines]) + ("..." if len(relevant_lines) > max_lines else "")
    else:
        return "\nLast STDERR lines:\n" + "\n".join(lines[-max_lines:]) + ("..." if len(lines) > max_lines else "")

def test_generated_nextjs_site(site_data_and_tmp_dir, playwright: Playwright):
    """
    Main test function that orchestrates the entire validation process for a single generated site.
    """
    actual_site_directory, tesslate_response_content, input_question, site_identifier, active_subprocesses = site_data_and_tmp_dir
    
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    allure.dynamic.suite(f"NextJS_Testing_{run_timestamp}")
    allure.dynamic.sub_suite(f"Site_{site_identifier}")
    allure.dynamic.title(f"Test Next.js Site Build & UI: {site_identifier}")
    allure.dynamic.description(f"Run: {run_timestamp}\nInput Question: {input_question}\nSite Dir: {actual_site_directory}")
    allure.dynamic.parameter("Run Timestamp", run_timestamp)
    allure.dynamic.parameter("Site Directory", actual_site_directory or "Not created")
    
    with allure.step("Save Original Prompt and Generated Site Content"):
        allure.attach(input_question, name="Prompt", attachment_type=allure.attachment_type.TEXT)
        allure.attach(tesslate_response_content, name="LLM Response", attachment_type=allure.attachment_type.TEXT)
        allure.attach(f"Site Identifier: {site_identifier}\nDirectory: {actual_site_directory}", name="Site Generation Metadata", attachment_type=allure.attachment_type.TEXT)

    # --- THIS IS THE PRIMARY FIX FOR THE TypeError ---
    # The 'site_identifier' argument was missing. It is now passed.
    results = process_generated_site(tesslate_response_content, actual_site_directory, site_identifier)
    
    allure.attach(json.dumps(results, indent=2, default=lambda o: '<not serializable>'), 
                  name="Overall Process Summary JSON", attachment_type=allure.attachment_type.JSON)
    
    if results.get("error_messages"):
        allure.attach("\n".join(results["error_messages"]), 
                      name="Global Processing Error Messages", attachment_type=allure.attachment_type.TEXT)
    
    stage_to_success_key_map = {
        "Apply LLM Code": "llm_files_write_success",
        "Auto Fix (Project-wide)": "auto_fix_success",
        "pnpm Install": "pnpm_install_success",
        "ESLint Fix": "eslint_fix_success_optional", 
        "Prettier Format": "prettier_success_optional", 
        "pnpm Build": "build_success"
    }
    
    soft_assert_failures = []

    with allure.step("Project Build and Fix Process"):
        for stage_name in results.get("project_setup_stages", []):
            stage_output_data = results.get("command_outputs_map", {}).get(stage_name)
            success_key = stage_to_success_key_map.get(stage_name, None)
            stage_assert_success = results.get(success_key, True) if success_key else True
            
            step_title = stage_name
            if success_key and not stage_assert_success:
                rc_info = f" (RC: {stage_output_data.get('returncode', 'N/A') if stage_output_data else 'N/A'})"
                step_title = f"{stage_name} - FAILED{rc_info}"
            elif stage_name in ["ESLint Fix", "Prettier Format"] and success_key and stage_assert_success and stage_output_data and stage_output_data.get('returncode', 0) != 0:
                step_title = f"{stage_name} - COMPLETED WITH ISSUES (RC: {stage_output_data.get('returncode')})"

            with allure.step(step_title):
                if stage_output_data:
                    duration_info = f"Duration: {stage_output_data.get('duration', 0):.2f}s"
                    return_code_info = f"Return Code: {stage_output_data.get('returncode', 'N/A')}"
                    combined_log_output = f"Execution Info:\n  {duration_info}\n  {return_code_info}\n\n"
                    if stage_output_data.get("stdout"): combined_log_output += f"--- STDOUT ---\n{stage_output_data['stdout']}\n\n"
                    if stage_output_data.get("stderr"): combined_log_output += f"--- STDERR ---\n{stage_output_data['stderr']}\n"
                    if combined_log_output.strip(): allure.attach(combined_log_output.strip(), name=f"Output Log", attachment_type=allure.attachment_type.TEXT)
                
                if success_key:
                    base_assertion_message = f"Stage '{stage_name}' failed. Success flag '{success_key}' was False."
                    detailed_assertion_message = base_assertion_message
                    if not stage_assert_success and stage_output_data and stage_output_data.get('stderr'):
                        detailed_assertion_message += f"\n{get_error_summary_from_stderr(stage_output_data['stderr'])}"
                    
                    is_soft_assert_stage = "optional" in success_key
                    if is_soft_assert_stage:
                        with assume: assert stage_assert_success, detailed_assertion_message
                        if not stage_assert_success:
                            soft_assert_failures.append(detailed_assertion_message)
                    else:
                        assert stage_assert_success, detailed_assertion_message
        
    if soft_assert_failures:
        allure.attach("\n".join(soft_assert_failures), name="Soft Assertion Failures (Warnings)", attachment_type=allure.attachment_type.TEXT)
        print(f"WARNING: Soft assertions failed for {site_identifier}: {soft_assert_failures}")

    if not results.get("build_success"):
        build_fail_stderr = results.get("command_outputs_map", {}).get("pnpm Build", {}).get("stderr", "")
        error_summary = get_error_summary_from_stderr(build_fail_stderr) if build_fail_stderr else "No specific STDERR from build."
        pytest.fail(f"Overall build_success is False for {site_identifier}. Skipping UI tests. {error_summary}")

    if not actual_site_directory:
         pytest.fail(f"Site directory for {site_identifier} was not created. Skipping UI tests.")

    with allure.step(f"Verify UI for {site_identifier}"):
        dev_server_process = None
        output_media_dir = os.path.join(actual_site_directory, "test_output_media")
        os.makedirs(output_media_dir, exist_ok=True)
        port = get_free_port()
        server_url = f"http://localhost:{port}"
        page = None; browser = None; context = None
        context_closed_for_media = False

        try:
            with allure.step("Start Dev Server & Navigate"):
                dev_server_process = subprocess.Popen(
                   ["pnpm", "dev", "-p", str(port)], cwd=actual_site_directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                    env={**os.environ, "PORT": str(port)},
                    text=True, bufsize=1, creationflags=0 if os.name != 'nt' else subprocess.CREATE_NEW_PROCESS_GROUP
                )
                active_subprocesses.append(dev_server_process)
                
                wait_for_nextjs_server(server_url, timeout=180)
            
                browser = playwright.chromium.launch(headless=True)
                
                context_args = {'viewport': {'width': 1280, 'height': 720}}
                if RECORD_VIDEO:
                    context_args.update({
                        'record_video_dir': output_media_dir,
                        'record_video_size': {'width': 1280, 'height': 720}
                    })
                context = browser.new_context(**context_args)
                
                page = context.new_page()
                
                def _on_console(msg):
                    try:
                        msg_type = msg.type
                        msg_text = msg.text()
                        allure.attach(f"({msg_type}): {msg_text}", name="Browser Console Log", attachment_type=allure.attachment_type.TEXT)
                    except Exception as e:
                        print(f"Error in console listener: {e}")

                def _on_page_error(exc):
                    try:
                        allure.attach(str(exc), name="Browser Page Error", attachment_type=allure.attachment_type.TEXT)
                    except Exception as e:
                        print(f"Error in pageerror listener: {e}")
                
                page.on("console", _on_console)
                page.on("pageerror", _on_page_error)

                page.goto(server_url, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(5000) 

            with allure.step("Visual Verification & Page Content Check"):
                page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
                page.wait_for_timeout(2000)
                page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
                page.wait_for_timeout(2000)

                page_content_lower = page.content().lower()
                critical_error_substrings = [
                    "cannot resolve", "module not found", "typeerror:", "referenceerror:", "syntaxerror:",
                    "unhandled runtime error", "application error: a client-side exception has occurred",
                    "server error", "compilation failed", "failed to compile",
                ]
                found_errors = [s for s in critical_error_substrings if s in page_content_lower]
                assert not found_errors, f"Found critical error indicators in page content: {', '.join(found_errors)}"
                
                screenshot_filename = os.path.join(output_media_dir, f"{site_identifier}_ui_page.png")
                page.screenshot(path=screenshot_filename, full_page=True)
                allure.attach.file(screenshot_filename, name=f"Final UI Screenshot", attachment_type=allure.attachment_type.PNG)
        
        except Exception as e_ui:
            allure.attach(f"{type(e_ui).__name__}: {str(e_ui)}", name="UI Verification Error Details", attachment_type=allure.attachment_type.TEXT)
            if page and not page.is_closed():
                error_screenshot_path = os.path.join(output_media_dir, f"{site_identifier}_ui_error_page.png")
                try:
                    page.screenshot(path=error_screenshot_path, full_page=True)
                    allure.attach.file(error_screenshot_path, name=f"UI Error Screenshot", attachment_type=allure.attachment_type.PNG)
                except Exception:
                    pass
            raise 
        finally:
            if context:
                try: context.close()
                except Exception as e_ctx_media_close: print(f"Error closing playwright context: {e_ctx_media_close}")
            if browser:
                try: browser.close()
                except Exception as e_brw_close: print(f"Error closing playwright browser: {e_brw_close}")

            if RECORD_VIDEO and actual_site_directory and os.path.isdir(output_media_dir):
                with allure.step("Process Recorded Media"):
                    recorded_videos_list = glob.glob(os.path.join(output_media_dir, "*.webm"))
                    if recorded_videos_list:
                        recorded_video_path = recorded_videos_list[0]
                        allure.attach.file(recorded_video_path, name=f"Recorded Video (raw)", attachment_type=allure.attachment_type.WEBM)
                        gif_output_path = os.path.join(output_media_dir, f"{site_identifier}_animation.gif")
                        if convert_webm_to_gif(recorded_video_path, gif_output_path):
                            allure.attach.file(gif_output_path, name=f"Animation GIF", attachment_type=allure.attachment_type.GIF)
                    else:
                        allure.attach("No video file found for processing.", name="Media Processing Note", attachment_type=allure.attachment_type.TEXT)