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

from gen_site_logic import process_generated_site

# Fallback LLM response
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
    config = getattr(pytest, 'global_test_context', {}).get('config', None)
    
    output_response_field = "output_response"
    framework_field = "metadata_framework"
    input_question_field = "input_question"

    if config and hasattr(config, "option"):
        output_response_field = getattr(config.option, "csv_output_field", output_response_field)
        framework_field = getattr(config.option, "csv_framework_field", framework_field)
        input_question_field = getattr(config.option, "csv_input_field", input_question_field)
    
    # If no specific CSV file is provided, find the most recent one in datasets folder
    if csv_filepath is None:
        datasets_dir = "datasets"
        if os.path.exists(datasets_dir):
            csv_files = glob.glob(os.path.join(datasets_dir, "*.csv"))
            if csv_files:
                # Sort by modification time, newest first
                csv_filepath = max(csv_files, key=os.path.getmtime)
                print(f"INFO: Using most recent CSV file: {csv_filepath}")
            else:
                print(f"WARNING: No CSV files found in {datasets_dir} folder. Using fallback.")
                return [("fallback_site_0", LLM_TEST_RESPONSE_FALLBACK, "Fallback: No CSV files in datasets")]
        else:
            print(f"WARNING: {datasets_dir} folder not found. Using fallback.")
            return [("fallback_site_0", LLM_TEST_RESPONSE_FALLBACK, "Fallback: datasets folder not found")]
    
    # Fallback to default filename if still None
    if csv_filepath is None:
        csv_filepath = "weby_eval_run_generated_b592c74d.csv"
    
    if not os.path.exists(csv_filepath):
        print(f"WARNING: CSV file not found: {csv_filepath}. Using fallback for one test.")
        return [("fallback_site_0", LLM_TEST_RESPONSE_FALLBACK, "Fallback: CSV not found")]

    with open(csv_filepath, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        if not reader.fieldnames:
            print(f"WARNING: CSV {csv_filepath} is empty or headerless. Using fallback.")
            return [("fallback_site_1", LLM_TEST_RESPONSE_FALLBACK, "Fallback: CSV empty/headerless")]
        
        required_fields_map = {
            "tesslate_response": output_response_field, "framework": framework_field, "input_question": input_question_field
        }
        actual_field_names = {}
        missing_fields = []
        for key, default_name in required_fields_map.items():
            if default_name in reader.fieldnames: actual_field_names[key] = default_name
            else:
                generic_names = {"output_response": "output_tesslate_response", "metadata_framework": "framework", "input_question": "input_question"}
                if key in generic_names and generic_names[key] in reader.fieldnames:
                    actual_field_names[key] = generic_names[key]
                else: missing_fields.append(default_name)
        if missing_fields:
            raise ValueError(f"Missing required CSV fields: {', '.join(missing_fields)}. Available: {', '.join(reader.fieldnames or [])}")

        for i, row in enumerate(reader):
            tesslate_response = row.get(actual_field_names["tesslate_response"], '')
            framework = row.get(actual_field_names["framework"], '')
            input_question = row.get(actual_field_names["input_question"], f"CSV row {i+1}: No input question")
            if framework == 'Nextjs' and '<Edit filename="' in tesslate_response:
                test_cases.append((f"site_{i}", tesslate_response, input_question))
    
    if not test_cases and os.path.exists(csv_filepath):
        pytest.skip(f"No valid Next.js test cases with <Edit> blocks found in {csv_filepath}. Skipping tests.")
    return test_cases

@pytest.fixture(scope="function", params=load_test_data())
def site_data_and_tmp_dir(tmp_path_factory, request):
    site_identifier, tesslate_response_content, input_question = request.param
    timestamp = str(int(time.time() * 1000))
    base_tmp_dir_name = f"cna_base_{site_identifier.replace('/', '_')}_{timestamp}"
    base_tmp_dir = tmp_path_factory.mktemp(base_tmp_dir_name)
    yield str(base_tmp_dir), tesslate_response_content, input_question, site_identifier

def wait_for_nextjs_server(url, timeout=180, poll_interval=3):
    print(f"Waiting for Next.js server at {url} (timeout: {timeout}s)...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=poll_interval)
            response.raise_for_status()
            if response.status_code == 200: print(f"Server at {url} is ready."); return True
        except requests.exceptions.RequestException: time.sleep(poll_interval)
    raise TimeoutError(f"Next.js server at {url} did not become ready within {timeout} seconds.")

def convert_webm_to_gif(webm_path, gif_path):
    try: subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"Warning: FFmpeg not found or not working ({e}). Skipping GIF conversion."); return False
    palette_path = os.path.join(os.path.dirname(gif_path), "palette.png")
    try:
        palette_gen_cmd = ['ffmpeg', '-loglevel', 'error', '-i', webm_path, '-vf', 'fps=10,scale=640:-1:flags=lanczos,palettegen', '-y', palette_path]
        subprocess.run(palette_gen_cmd, check=True, capture_output=True, text=True)
        gif_convert_cmd = ['ffmpeg', '-loglevel', 'error', '-i', webm_path, '-i', palette_path, '-lavfi', 'fps=10,scale=640:-1:flags=lanczos[x];[x][1:v]paletteuse', '-loop', '0', '-y', gif_path]
        subprocess.run(gif_convert_cmd, check=True, capture_output=True, text=True)
        print(f"GIF conversion successful: {gif_path}"); return True
    except subprocess.CalledProcessError as e: print(f"FFmpeg conversion failed. CMD: {' '.join(e.cmd)}\nStderr: {e.stderr}\nStdout: {e.stdout}")
    except Exception as e_conv: print(f"Unexpected error during GIF conversion: {e_conv}")
    finally:
        if os.path.exists(palette_path): os.remove(palette_path)
    return False

def get_error_summary_from_stderr(stderr_text: str, max_lines: int = 10) -> str:
    """Extracts a summary of errors from stderr text."""
    if not stderr_text or not stderr_text.strip():
        return "No STDERR content."
    lines = stderr_text.strip().splitlines()
    error_keywords = ["error", "failed", "typeerror", "cannot find", "is not assignable", "不允许"]
    relevant_lines = [line for line in lines if any(keyword in line.lower() for keyword in error_keywords)]
    if relevant_lines:
        return "\nRelevant STDERR lines:\n" + "\n".join(relevant_lines[:max_lines]) + ("..." if len(relevant_lines) > max_lines else "")
    else:
        return "\nLast STDERR lines:\n" + "\n".join(lines[-max_lines:]) + ("..." if len(lines) > max_lines else "")


def test_generated_nextjs_site(site_data_and_tmp_dir, playwright: Playwright):
    base_tmp_dir, tesslate_response_content, input_question, site_identifier = site_data_and_tmp_dir
    
    # Add timestamp for unique test run identification
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Configure suite with timestamp for multiple runs tracking
    allure.dynamic.suite(f"NextJS_Testing_{run_timestamp}")
    allure.dynamic.sub_suite(f"Site_{site_identifier}")
    
    allure.dynamic.title(f"Test Next.js Site Build & UI: {site_identifier}")
    allure.dynamic.description(f"Run: {run_timestamp}\nInput Question: {input_question}\nBase Temp Dir: {base_tmp_dir}")
    
    # Add run timestamp as parameter for filtering
    allure.dynamic.parameter("Run Timestamp", run_timestamp)
    # Remove this line - actual_site_directory is not defined yet
    # allure.dynamic.parameter("Site Directory", actual_site_directory or "Not created")
    
    # Add initial step to save original prompt and generated site content
    with allure.step("Save Original Prompt and Generated Site Content"):
        # Attach the original input question/prompt
        allure.attach(
            input_question,
            name="Prompt",
            attachment_type=allure.attachment_type.TEXT
        )
        
        # Attach the generated site content (LLM response)
        allure.attach(
            tesslate_response_content,
            name="LLM Response",
            attachment_type=allure.attachment_type.TEXT
        )
        
        # Attach site identifier for reference
        allure.attach(
            f"Site Identifier: {site_identifier}\nBase Directory: {base_tmp_dir}",
            name="Site Generation Metadata",
            attachment_type=allure.attachment_type.TEXT
        )

    results = process_generated_site(tesslate_response_content, base_tmp_dir, site_identifier)
    
    actual_site_directory = results.get("site_path")
    allure.dynamic.parameter("Site Directory", actual_site_directory or "Not created")

    allure.attach(json.dumps(results, indent=2, default=lambda o: '<not serializable>'), 
                  name="Overall Process Summary JSON", attachment_type=allure.attachment_type.JSON)
    
    if results.get("error_messages"):
        allure.attach("\n".join(results["error_messages"]), 
                      name="Global Processing Error Messages", attachment_type=allure.attachment_type.TEXT)

    stage_to_success_key_map = {
        "Create Next App (CNA)": "cna_success",
        "Configure Next.js (ESLint)": "next_config_success",
        "Update package.json": "pkg_json_success",
        "pnpm Install": "pnpm_install_success_optional",
        #"Shadcn Init": "shadcn_init_success_optional",
        #"Shadcn Add Components": "shadcn_add_success_optional",
        "Apply LLM Code": "llm_files_write_success",
        #"Auto Import Fix": "auto_fix_success",
        "pnpm Install (extra)": "pnpm_install_extra_success_optional",
        "ESLint Fix": "eslint_fix_success_optional", 
        "Prettier Format": "prettier_success_optional", 
        "pnpm Build": "build_success"
    }
    
    soft_assert_failures = []

    with allure.step("Project Setup and Build Process"):
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
                # Add original prompt and generated site content for pnpm Build stage
                if stage_name == "pnpm Build":
                    # Attach the original input question/prompt
                    allure.attach(
                        input_question,
                        name="Original Input Prompt",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    
                    # Attach the generated site content (LLM response)
                    allure.attach(
                        tesslate_response_content,
                        name="Generated Site Content (LLM Response)",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    
                    # Attach site identifier for reference
                    allure.attach(
                        f"Site Identifier: {site_identifier}\nBase Directory: {base_tmp_dir}",
                        name="Site Generation Metadata",
                        attachment_type=allure.attachment_type.TEXT
                    )
                
                combined_log_output = ""
                stderr_content_for_assert = ""
                if stage_output_data:
                    duration_info = f"Duration: {stage_output_data.get('duration', 0):.2f}s"
                    return_code_info = f"Return Code: {stage_output_data.get('returncode', 'N/A')}"
                    command_success_info = f"Command Success (raw exit code 0): {stage_output_data.get('success', 'N/A')}"
                    combined_log_output += f"Execution Info:\n  {duration_info}\n  {return_code_info}\n  {command_success_info}\n\n"
                    if stage_output_data.get("stdout"): combined_log_output += f"--- STDOUT ---\n{stage_output_data['stdout']}\n\n"
                    if stage_output_data.get("stderr"):
                        stderr_content_for_assert = stage_output_data['stderr']
                        combined_log_output += f"--- STDERR ---\n{stderr_content_for_assert}\n"
                    if combined_log_output.strip():
                        allure.attach(combined_log_output.strip(), name=f"Output Log", attachment_type=allure.attachment_type.TEXT)
                
                if success_key:
                    base_assertion_message = f"Stage '{stage_name}' failed. Success flag '{success_key}' was False. (RC: {stage_output_data.get('returncode', 'N/A') if stage_output_data else 'N/A'})"
                    detailed_assertion_message = base_assertion_message
                    if not stage_assert_success and stderr_content_for_assert:
                        error_summary = get_error_summary_from_stderr(stderr_content_for_assert)
                        detailed_assertion_message += f"\n{error_summary}"
                    is_soft_assert_stage = stage_name in ["ESLint Fix", "Prettier Format"]
                    is_critical_stage = stage_name not in ["ESLint Fix", "Prettier Format"]
                    if is_soft_assert_stage:
                        with assume: assert stage_assert_success, detailed_assertion_message
                        if not stage_assert_success:
                            soft_assert_failures.append(detailed_assertion_message)
                            allure.dynamic.status("broken"); allure.dynamic.status_details(message=f"Non-fatal issues in {stage_name}. RC: {stage_output_data.get('returncode', 'N/A') if stage_output_data else 'N/A'}")
                    elif is_critical_stage: assert stage_assert_success, detailed_assertion_message
        
    if soft_assert_failures:
        allure.attach("\n".join(soft_assert_failures), name="Soft Assertion Failures (Warnings)", attachment_type=allure.attachment_type.TEXT)
        print(f"WARNING: Soft assertions failed for {site_identifier}: {soft_assert_failures}")

    if not results.get("build_success"):
        build_fail_stderr = results.get("command_outputs_map", {}).get("pnpm Build", {}).get("stderr", "")
        error_summary = get_error_summary_from_stderr(build_fail_stderr) if build_fail_stderr else "No specific STDERR from build."
        pytest.fail(f"Overall build_success is False for {site_identifier}. Skipping UI tests. {error_summary}")

    if not actual_site_directory:
         pytest.fail(f"Site directory for {site_identifier} was not created. Skipping UI tests.")

    # --- UI Verification ---
    with allure.step(f"Verify UI for {site_identifier}"):
        dev_server_process = None
        output_media_dir = os.path.join(actual_site_directory, "test_output_media")
        os.makedirs(output_media_dir, exist_ok=True)
        port = get_free_port()
        server_url = f"http://localhost:{port}"
        page = None; browser = None; context = None # Initialize to None
        context_closed_for_media = False # Flag to track if context was closed for media

        try:
            with allure.step("Start Dev Server & Navigate"):
                dev_server_process = subprocess.Popen(
                   ["pnpm", "dev", "-p", str(port)], cwd=actual_site_directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                    env={**os.environ, "PORT": str(port)},
                    text=True, bufsize=1, creationflags=0
                )
                wait_for_nextjs_server(server_url, timeout=180)
            
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    record_video_dir=output_media_dir,
                    record_video_size={'width': 1280, 'height': 720}
                )
                page = context.new_page()
                
                def _on_console(msg):
                    try:
                        msg_type = getattr(msg, 'type', 'unknown_type')
                        msg_text = msg.text() if hasattr(msg, 'text') and callable(msg.text) else str(msg)
                        allure.attach(f"({msg_type}): {msg_text}", name="Browser Console Log", attachment_type=allure.attachment_type.TEXT)
                    except Exception: pass 
                
                def _on_page_error(exc):
                    try: allure.attach(str(exc), name="Browser Page Error", attachment_type=allure.attachment_type.TEXT)
                    except Exception: pass

                page.on("console", _on_console)
                page.on("pageerror", _on_page_error)

                page.goto(server_url, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(5000) 

            with allure.step("Visual Verification & Page Content Check"):
                with allure.step("Simulate Page Scroll"):
                    page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
                    page.wait_for_timeout(3000) 
                    page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
                    page.wait_for_timeout(3000) 

                with allure.step("Verify Page Content"):
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
            if page and context: # Ensure page and context exist before trying to screenshot
                # Check if context is not None and then if page is not closed (implicitly, page exists if context exists and page was created)
                # Playwright page.is_closed() is the correct method
                if not page.is_closed():
                    error_screenshot_path = os.path.join(output_media_dir, f"{site_identifier}_ui_error_page.png")
                    try:
                        page.screenshot(path=error_screenshot_path, full_page=True)
                        allure.attach.file(error_screenshot_path, name=f"UI Error Screenshot", attachment_type=allure.attachment_type.PNG)
                    except Exception: pass # Best effort for error screenshot
            raise 
        finally:
            if actual_site_directory and os.path.isdir(output_media_dir):
                with allure.step("Process Recorded Media (Video & GIF)"):
                    if context: # Context must be closed to finalize video
                        try:
                            context.close()
                            context_closed_for_media = True # Set flag
                            print(f"[{time.strftime('%H:%M:%S')}] Browser context closed for media finalization.")
                        except Exception as e_ctx_media_close:
                            print(f"[{time.strftime('%H:%M:%S')}] Error closing context for media: {e_ctx_media_close}")
                            allure.attach(f"Error closing context for media: {e_ctx_media_close}", name="Context Close Error (Media)", attachment_type=allure.attachment_type.TEXT)
                    
                    recorded_videos_list = glob.glob(os.path.join(output_media_dir, "*.webm"))
                    if recorded_videos_list:
                        recorded_video_path = recorded_videos_list[0]
                        allure.attach.file(recorded_video_path, name=f"Recorded Video (raw)", attachment_type=allure.attachment_type.WEBM)
                        gif_output_path = os.path.join(output_media_dir, f"{site_identifier}_animation.gif")
                        if convert_webm_to_gif(recorded_video_path, gif_output_path):
                            allure.attach.file(gif_output_path, name=f"Animation GIF", attachment_type=allure.attachment_type.GIF)
                        else:
                            allure.attach("GIF conversion failed or skipped.", name="Media Processing Note", attachment_type=allure.attachment_type.TEXT)
                    else:
                        allure.attach("No video file found for processing.", name="Media Processing Note", attachment_type=allure.attachment_type.TEXT)
            
            with allure.step("Cleanup Browser & Dev Server"):
                if context and not context_closed_for_media: # If context exists and wasn't closed for media
                    try:
                        context.close()
                        print(f"[{time.strftime('%H:%M:%S')}] Browser context closed (cleanup).")
                    except Exception as e_ctx_final_close:
                         print(f"[{time.strftime('%H:%M:%S')}] Error during final context close: {e_ctx_final_close}")
                
                if browser:
                    try:
                        browser.close()
                        print(f"[{time.strftime('%H:%M:%S')}] Browser closed.")
                    except Exception as e_brw_close:
                        print(f"[{time.strftime('%H:%M:%S')}] Error closing browser: {e_brw_close}")
                
                if dev_server_process and dev_server_process.poll() is None:
                    print(f"[{time.strftime('%H:%M:%S')}] Terminating dev server for {site_identifier} (PID: {dev_server_process.pid})...")
                    dev_server_process.terminate()
                    try:
                        stdout, stderr = dev_server_process.communicate(timeout=10)
                        log_content = []
                        if stdout and stdout.strip(): log_content.append(f"STDOUT:\n{stdout.strip()}")
                        if stderr and stderr.strip(): log_content.append(f"STDERR:\n{stderr.strip()}")
                        if log_content:
                            allure.attach("\n\n".join(log_content), name="Dev Server Output (on cleanup)", attachment_type=allure.attachment_type.TEXT)
                    except subprocess.TimeoutExpired:
                        print(f"[{time.strftime('%H:%M:%S')}] Dev server did not terminate gracefully, killing...")
                        dev_server_process.kill()
                    except Exception as e_comm:
                         print(f"[{time.strftime('%H:%M:%S')}] Error communicating with dev server process on terminate: {e_comm}")
                    print(f"[{time.strftime('%H:%M:%S')}] Dev server for {site_identifier} terminated.")